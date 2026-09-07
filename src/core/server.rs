use crate::config::Config;
use anyhow::{Context, Result};
use std::process::Stdio;
use tokio::process::{Child, Command};
use tokio::time::{sleep, Duration};

pub struct LlamaServer {
    cfg: Config,
    child: Option<Child>,
}

impl LlamaServer {
    pub fn new(cfg: &Config) -> Self {
        Self {
            cfg: cfg.clone(),
            child: None,
        }
    }

    pub async fn start(&mut self) -> Result<()> {
        let child = Command::new("llama-server")
            .args([
                "--model",
                self.cfg.model_path.to_str().context("Invalid model path")?,
                "--host",
                &self.cfg.llama_host,
                "--port",
                &self.cfg.llama_port.to_string(),
                "--ctx-size",
                "8192",
                "--threads",
                &num_cpus().to_string(),
            ])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .kill_on_drop(true)
            .spawn()
            .context("Failed to spawn llama-server — is it in PATH?")?;

        self.child = Some(child);
        Ok(())
    }

    pub async fn wait_ready(&self) -> Result<()> {
        let url = format!("{}/health", self.cfg.llama_base_url());
        let client = reqwest::Client::new();

        for _ in 0..60 {
            sleep(Duration::from_secs(1)).await;
            if let Ok(resp) = client.get(&url).send().await {
                if resp.status().is_success() {
                    return Ok(());
                }
            }
        }
        anyhow::bail!("llama-server did not become ready within 60 seconds")
    }

    pub async fn stop(&mut self) -> Result<()> {
        if let Some(mut child) = self.child.take() {
            child.kill().await.ok();
        }
        Ok(())
    }
}

fn num_cpus() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4)
}
