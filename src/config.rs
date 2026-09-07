use anyhow::{Context, Result};
use std::path::{Path, PathBuf};

const MODEL_SEARCH_DIRS: &[&str] = &[
    "~/.local/share/aether-forge/models",
    "~/Documents/Ai_Models",
    "~/models",
    "~/llm/models",
    "~/.cache/lm-studio/models",
    "/opt/models",
];

const GGUF_PRIORITY: &[&str] = &["qwen", "mistral", "llama", "phi"];

#[derive(Clone)]
pub struct Config {
    pub model_path: PathBuf,
    pub tools_dir: PathBuf,
    pub llama_host: String,
    pub llama_port: u16,
    pub shell: String,
    pub os: Os,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Os {
    Linux,
    Windows,
    MacOs,
    Other(String),
}

impl Config {
    pub fn load() -> Result<Self> {
        let model_path = find_model().context("No GGUF model found. Place one in ~/models or ~/.local/share/aether-forge/models")?;
        let tools_dir = expand("~/.aetherforge/tools");
        std::fs::create_dir_all(&tools_dir)?;

        // Init memory.md with empty sections if it doesn't exist
        let memory_path = tools_dir.parent().unwrap().join("memory.md");
        if !memory_path.exists() {
            std::fs::write(&memory_path, "## System\n\n## Tools\n\n## Paths\n\n## Specs\n")?;
        }

        Ok(Self {
            model_path,
            tools_dir,
            llama_host: "127.0.0.1".into(),
            llama_port: 8080,
            shell: detect_shell(),
            os: detect_os(),
        })
    }

    pub fn model_name(&self) -> String {
        self.model_path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned()
    }

    pub fn llama_base_url(&self) -> String {
        format!("http://{}:{}", self.llama_host, self.llama_port)
    }

    pub fn memory_path(&self) -> PathBuf {
        self.tools_dir.parent().unwrap().join("memory.md")
    }
}

fn find_model() -> Option<PathBuf> {
    // Check env override first
    if let Ok(p) = std::env::var("AETHER_MODEL") {
        let p = PathBuf::from(p);
        if p.exists() {
            return Some(p);
        }
    }

    let _candidates: Vec<PathBuf> = MODEL_SEARCH_DIRS
        .iter()
        .flat_map(|dir| {
            let dir = expand(dir);
            std::fs::read_dir(&dir)
                .ok()?
                .filter_map(|e| e.ok())
                .map(|e| e.path())
                .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("gguf"))
                .collect::<Vec<_>>()
                .into_iter()
                .next()
                .map(|_| dir)
        })
        .collect();

    // Also walk dirs for actual .gguf files
    let gguf_files: Vec<PathBuf> = MODEL_SEARCH_DIRS
        .iter()
        .flat_map(|dir| {
            let dir = expand(dir);
            std::fs::read_dir(&dir)
                .into_iter()
                .flatten()
                .filter_map(|e| e.ok())
                .map(|e| e.path())
                .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("gguf"))
                .collect::<Vec<_>>()
        })
        .collect();

    if gguf_files.is_empty() {
        return None;
    }

    // Prefer by priority keywords
    for keyword in GGUF_PRIORITY {
        if let Some(p) = gguf_files.iter().find(|p| {
            p.file_name()
                .and_then(|n| n.to_str())
                .map(|n| n.to_lowercase().contains(keyword))
                .unwrap_or(false)
        }) {
            return Some(p.clone());
        }
    }

    gguf_files.into_iter().next()
}

pub fn expand(path: &str) -> PathBuf {
    if let Some(rest) = path.strip_prefix("~/") {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(rest)
    } else {
        PathBuf::from(path)
    }
}

fn detect_shell() -> String {
    std::env::var("SHELL")
        .map(|s| {
            Path::new(&s)
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .into_owned()
        })
        .unwrap_or_else(|_| {
            if cfg!(windows) {
                "powershell".into()
            } else {
                "bash".into()
            }
        })
}

fn detect_os() -> Os {
    if cfg!(target_os = "linux") {
        Os::Linux
    } else if cfg!(target_os = "windows") {
        Os::Windows
    } else if cfg!(target_os = "macos") {
        Os::MacOs
    } else {
        Os::Other(std::env::consts::OS.into())
    }
}

impl std::fmt::Display for Os {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Os::Linux => write!(f, "Linux"),
            Os::Windows => write!(f, "Windows"),
            Os::MacOs => write!(f, "macOS"),
            Os::Other(s) => write!(f, "{}", s),
        }
    }
}