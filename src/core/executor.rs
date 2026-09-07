use crate::core::tools::Tool;
use anyhow::Result;
use std::process::Stdio;
use tokio::process::Command;

pub struct Executor;

impl Executor {
    /// Run a saved tool with arguments
    pub async fn run_tool(tool: &Tool, args: &str) -> Result<String> {
        let output = Command::new(&tool.path)
            .arg(args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .await?;

        let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
        let stderr = String::from_utf8_lossy(&output.stderr).into_owned();

        if output.status.success() {
            Ok(stdout)
        } else {
            Ok(format!("exit {}\n{}{}", output.status.code().unwrap_or(-1), stdout, stderr))
        }
    }

    /// Run an inline shell script via the detected shell
    pub async fn run_script(script: &str, shell: &str) -> Result<String> {
        let output = Command::new(shell)
            .arg("-c")
            .arg(script)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .await?;

        let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
        let stderr = String::from_utf8_lossy(&output.stderr).into_owned();

        let combined = format!("{}{}", stdout, stderr).trim().to_string();
        Ok(if combined.is_empty() {
            format!("exit {}", output.status.code().unwrap_or(0))
        } else {
            combined
        })
    }
}
