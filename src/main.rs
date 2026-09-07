mod core {
    pub mod brain;
    pub mod executor;
    pub mod rsi;
    pub mod server;
    pub mod tools;
    pub mod voice;
}
mod ui {
    pub mod terminal;
}
mod config;

use anyhow::Result;
use clap::Parser;
use core::{brain::Brain, server::LlamaServer, tools::ToolRegistry};
use ui::terminal::Terminal;

#[derive(Parser)]
#[command(name = "aether-forge", about = "A fully local AI environment that grows with you.")]
struct Cli {
    /// Text-only mode (no voice)
    #[arg(long)]
    text: bool,

    /// Voice-only mode (no text prompt)
    #[arg(long)]
    voice: bool,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    let term = Terminal::new();
    term.boot_animation();

    let cfg = config::Config::load()?;

    // Check for a staged RSI update from previous session
    let staged_flag = cfg.tools_dir.parent().unwrap().join("staged");
    if staged_flag.exists() {
        let staged_bin = std::fs::read_to_string(&staged_flag).unwrap_or_default();
        let staged_bin = staged_bin.trim();
        if !staged_bin.is_empty() && std::path::Path::new(staged_bin).exists() {
            let current_exe = std::env::current_exe()?;
            std::fs::copy(staged_bin, &current_exe)?;
            std::fs::remove_file(&staged_flag)?;
            term.info("RSI update applied. Restarting...");
            std::process::Command::new(&current_exe).spawn()?;
            std::process::exit(0);
        }
        std::fs::remove_file(&staged_flag).ok();
    }

    term.info(&format!("Found model: {}", cfg.model_name()));

    term.spinner("Starting llama-server...");
    let mut server = LlamaServer::new(&cfg);
    server.start().await?;
    term.spinner("Waiting for model to load");
    server.wait_ready().await?;
    term.ready(&cfg);

    let tools = ToolRegistry::load(&cfg).await?;
    term.info(&format!("Tools: {} loaded", tools.len()));

    let voice_available = !cli.text && core::voice::available();
    term.info(&format!(
        "Voice: {}",
        if voice_available { "available" } else { "unavailable" }
    ));

    term.awake();

    let brain = Brain::new(&cfg, tools);
    run_loop(brain, &term, cli.voice, cli.text, voice_available).await?;

    server.stop().await?;
    Ok(())
}

async fn run_loop(
    mut brain: Brain,
    term: &Terminal,
    voice_only: bool,
    text_only: bool,
    voice_available: bool,
) -> Result<()> {
    loop {
        let input = if voice_available && !text_only {
            // voice input path (falls back to text if nothing captured)
            match core::voice::listen().await {
                Ok(Some(text)) => text,
                Ok(None) => continue,
                Err(_) => {
                    if voice_only {
                        continue;
                    }
                    term.prompt()
                }
            }
        } else {
            term.prompt()
        };

        let input = input.trim().to_string();
        if input.is_empty() {
            continue;
        }
        if input == "exit" || input == "quit" {
            break;
        }

        term.forging();
        match brain.think(&input).await {
            Ok(response) => term.respond(&response),
            Err(e) => term.error(&e.to_string()),
        }
    }
    Ok(())
}
