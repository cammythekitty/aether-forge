use crate::{
    config::Config,
    core::{executor::Executor, rsi::Rsi, tools::ToolRegistry},
};
use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    stream: bool,
    temperature: f32,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Message {
    pub role: String,
    pub content: String,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: Message,
}

pub struct Brain {
    cfg: Config,
    tools: ToolRegistry,
    rsi: Rsi,
    history: Vec<Message>,
    client: reqwest::Client,
}

impl Brain {
    pub fn new(cfg: &Config, tools: ToolRegistry) -> Self {
        let forge_dir = cfg.tools_dir.parent().unwrap().to_path_buf();
        Self {
            cfg: cfg.clone(),
            tools,
            rsi: Rsi::new(forge_dir),
            history: Vec::new(),
            client: reqwest::Client::new(),
        }
    }

    pub async fn think(&mut self, input: &str) -> Result<String> {
        self.history.push(Message {
            role: "user".into(),
            content: input.into(),
        });

        let system = self.build_system_prompt();
        let mut messages = vec![Message {
            role: "system".into(),
            content: system,
        }];
        messages.extend(self.history.clone());

        let req = ChatRequest {
            model: "local".into(),
            messages,
            stream: false,
            temperature: 0.7,
        };

        let url = format!("{}/v1/chat/completions", self.cfg.llama_base_url());
        let resp: ChatResponse = self
            .client
            .post(&url)
            .json(&req)
            .send()
            .await?
            .json()
            .await?;

        let reply = resp
            .choices
            .into_iter()
            .next()
            .map(|c| c.message.content)
            .unwrap_or_default();

        // Check if the reply contains a tool invocation or shell block
        let output = self.handle_reply(&reply).await?;

        self.history.push(Message {
            role: "assistant".into(),
            content: reply.clone(),
        });

        Ok(output)
    }

    async fn handle_reply(&mut self, reply: &str) -> Result<String> {
        // Check for upgrade mode trigger
        let trimmed = reply.trim();
        if trimmed == "upgrade yourself"
            || reply.lines().any(|l| l.trim() == "ENTER_UPGRADE_MODE")
        {
            return Ok(self.rsi.enter()?);
        }

        // RSI mode is fully sandboxed — nothing else runs
        if self.rsi.active {
            if reply.lines().any(|l| l.trim() == "ABORT_UPGRADE") {
                self.rsi.active = false;
                return Ok(self.rsi.abort()?);
            }
            return match self.rsi.handle(reply).await? {
                Some(output) => Ok(format!("{}\n\n{}", reply, output)),
                None => Ok(reply.to_string()),
            };
        }

        // Normal mode — scan for SAVE_MEMORY first (always runs)
        for line in reply.lines() {
            if let Some(rest) = line.trim().strip_prefix("SAVE_MEMORY:") {
                let mut parts = rest.splitn(2, ':');
                if let (Some(section), Some(fact)) = (parts.next(), parts.next()) {
                    save_memory(&self.cfg.memory_path(), section.trim(), fact.trim())?;
                }
            }
        }

        // SAVE_TOOL takes priority — don't also execute the embedded shell block
        if let Some((name, script)) = parse_save_tool(reply) {
            self.tools.save(&name, &script, &self.cfg).await?;
            return Ok(format!("{}\n\n[Tool '{}' saved]", reply, name));
        }

        // Tool call: TOOL:<name>(<args>)
        if let Some(tool_call) = parse_tool_call(reply) {
            if let Some(tool) = self.tools.get(&tool_call.name) {
                let result = Executor::run_tool(tool, &tool_call.args).await?;
                return Ok(format!("{}\n\n[Tool output]\n{}", reply, result));
            }
        }

        // Inline shell block
        if let Some(script) = parse_shell_block(reply) {
            let result = Executor::run_script(&script, &self.cfg.shell).await?;
            return Ok(format!("{}\n\n[Output]\n{}", reply, result));
        }

        Ok(reply.to_string())
    }

    fn build_system_prompt(&self) -> String {
        let tool_list = self.tools.describe();
        let os = &self.cfg.os;
        let shell = &self.cfg.shell;
        let memory = std::fs::read_to_string(self.cfg.memory_path()).unwrap_or_default();
        let memory_section = if memory.trim().is_empty() {
            "(none yet)".to_string()
        } else {
            memory
        };

        let rsi_section = if self.rsi.active {
            r#"
## UPGRADE MODE ACTIVE
You are now operating in a sandboxed workspace with access to your own source code.
All normal tools, shell execution, and memory writes are disabled.
Only the following directives are available:

- READ_SOURCE:<file>       — read a source file (e.g. READ_SOURCE:core/brain.rs)
- PATCH_SOURCE:<file>      — write changes to a file, followed by a fenced code block with the full new content
- COMPILE_CHECK            — compile the working copy and see errors
- STAGE_UPDATE             — mark the compiled binary for deployment on next restart
- ABORT_UPGRADE            — restore working copy from backup and exit upgrade mode

Always READ_SOURCE before patching. Always COMPILE_CHECK before STAGE_UPDATE.
Work incrementally — patch one file at a time."#
        } else {
            ""
        };

        format!(
            r#"You are Æther Forge, a fully local AI assistant running on {os} with shell {shell}.
You control the user's computer by executing shell commands or calling saved tools.
{rsi_section}
## Memory (persists across sessions)
{memory_section}

## Saved tools
{tool_list}

## Rules
- To call a saved tool: TOOL:<name>(<argument>)
- To save a new tool (always include #!/bin/bash, never use placeholders):
  SAVE_TOOL:<snake_case_name>
  ```bash
  #!/bin/bash
  <actual working script>
  ```
- To save a fact to memory: SAVE_MEMORY:<section>:<fact>
  Sections: system, tools, paths, specs
  Example: SAVE_MEMORY:paths:downloads=/home/Camilla/Downloads
  Example: SAVE_MEMORY:tools:get_ip=fetches public IP via curl
- Never put tool names in bash blocks — use TOOL: format
- Prefer existing tools over writing new ones
- Never ask for confirmation — act immediately
- Keep responses concise"#
        )
    }
}

// --- Parsers ---

struct ToolCall {
    name: String,
    args: String,
}

fn parse_tool_call(text: &str) -> Option<ToolCall> {
    for line in text.lines() {
        if let Some(rest) = line.trim().strip_prefix("TOOL:") {
            if let Some(paren) = rest.find('(') {
                let name = rest[..paren].trim().to_string();
                let args = rest[paren + 1..].trim_end_matches(')').trim().to_string();
                return Some(ToolCall { name, args });
            }
        }
    }
    None
}

fn parse_shell_block(text: &str) -> Option<String> {
    let langs = ["bash", "sh", "shell", "powershell", "zsh", "fish"];
    for lang in langs {
        let open = format!("```{}", lang);
        if let Some(start) = text.find(&open) {
            let after = &text[start + open.len()..];
            if let Some(end) = after.find("```") {
                return Some(after[..end].trim().to_string());
            }
        }
    }
    None
}

fn parse_save_tool(text: &str) -> Option<(String, String)> {
    for line in text.lines() {
        if let Some(name) = line.trim().strip_prefix("SAVE_TOOL:") {
            let name = name.trim().to_string();
            if let Some(script) = parse_shell_block(text) {
                return Some((name, script));
            }
        }
    }
    None
}

fn save_memory(path: &std::path::Path, section: &str, fact: &str) -> Result<()> {
    let content = std::fs::read_to_string(path).unwrap_or_default();
    let header = format!("## {}", capitalize(section));

    let new_content = if let Some(pos) = content.find(&header) {
        let after_header = pos + header.len();
        let next_section = content[after_header..]
            .find("\n##")
            .map(|i| after_header + i)
            .unwrap_or(content.len());
        let mut s = content.clone();
        s.insert_str(next_section, &format!("\n- {}", fact));
        s
    } else {
        format!("{}\n{}\n- {}\n", content.trim_end(), header, fact)
    };

    std::fs::write(path, new_content)?;
    Ok(())
}

fn capitalize(s: &str) -> String {
    let mut c = s.chars();
    match c.next() {
        None => String::new(),
        Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
    }
}
