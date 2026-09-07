use anyhow::{Context, Result};
use std::path::{Path, PathBuf};
use tokio::process::Command;

const STAGED_FLAG: &str = "staged";
const SRC_DIR: &str = "src";
const BAK_DIR: &str = "src.bak";

pub struct Rsi {
    pub active: bool,
    forge_dir: PathBuf,   // ~/.aetherforge/
    src_dir: PathBuf,     // ~/.aetherforge/src/
    bak_dir: PathBuf,     // ~/.aetherforge/src.bak/
}

impl Rsi {
    pub fn new(forge_dir: PathBuf) -> Self {
        let src_dir = forge_dir.join(SRC_DIR);
        let bak_dir = forge_dir.join(BAK_DIR);
        Self {
            active: false,
            forge_dir,
            src_dir,
            bak_dir,
        }
    }

    /// Enter upgrade mode. Copies source into ~/.aetherforge/src/ if not present,
    /// takes a backup, returns a status message.
    pub fn enter(&mut self) -> Result<String> {
        // Find the original source tree
        let origin = find_source_origin()?;

        // Copy source to working dir if not already there
        if !self.src_dir.exists() {
            copy_dir(&origin, &self.src_dir)
                .context("Failed to copy source to ~/.aetherforge/src/")?;
        }

        // Always snapshot a fresh backup before editing
        if self.bak_dir.exists() {
            std::fs::remove_dir_all(&self.bak_dir)?;
        }
        copy_dir(&self.src_dir, &self.bak_dir)
            .context("Failed to snapshot backup")?;

        self.active = true;
        Ok(format!(
            "[RSI] Upgrade mode active.\nWorking copy: {}\nBackup: {}\nDirectives: READ_SOURCE:<file> | PATCH_SOURCE:<file>\\n<content> | COMPILE_CHECK | STAGE_UPDATE | ABORT_UPGRADE",
            self.src_dir.display(),
            self.bak_dir.display()
        ))
    }

    /// Handle an RSI directive from the LLM. Returns output to show the model.
    pub async fn handle(&self, reply: &str) -> Result<Option<String>> {
        if !self.active {
            return Ok(None);
        }

        // READ_SOURCE:<file>
        for line in reply.lines() {
            if let Some(file) = line.trim().strip_prefix("READ_SOURCE:") {
                return Ok(Some(self.read_source(file.trim())?));
            }
        }

        // PATCH_SOURCE:<file>\n<content until END_PATCH>
        if let Some(result) = self.try_patch(reply)? {
            return Ok(Some(result));
        }

        // COMPILE_CHECK
        if reply.lines().any(|l| l.trim() == "COMPILE_CHECK") {
            return Ok(Some(self.compile_check().await?));
        }

        // STAGE_UPDATE
        if reply.lines().any(|l| l.trim() == "STAGE_UPDATE") {
            return Ok(Some(self.stage_update()?));
        }

        // ABORT_UPGRADE
        if reply.lines().any(|l| l.trim() == "ABORT_UPGRADE") {
            return Ok(Some(self.abort()?));
        }

        Ok(None)
    }

    pub fn abort(&self) -> Result<String> {
        if self.bak_dir.exists() {
            if self.src_dir.exists() {
                std::fs::remove_dir_all(&self.src_dir)?;
            }
            copy_dir(&self.bak_dir, &self.src_dir)?;
        }
        Ok("[RSI] Aborted. Working copy restored from backup.".into())
    }

    fn read_source(&self, file: &str) -> Result<String> {
        let path = self.resolve(file)?;
        let content = std::fs::read_to_string(&path)
            .with_context(|| format!("Cannot read {}", path.display()))?;
        Ok(format!("[READ_SOURCE: {}]\n```rust\n{}\n```", file, content))
    }

    fn try_patch(&self, reply: &str) -> Result<Option<String>> {
        // Format:
        // PATCH_SOURCE:<file>
        // ```rust  (or any lang)
        // <content>
        // ```
        for line in reply.lines() {
            if let Some(file) = line.trim().strip_prefix("PATCH_SOURCE:") {
                let file = file.trim();
                // Extract fenced code block after the directive
                let after = &reply[reply.find(line).unwrap() + line.len()..];
                let content = extract_code_block(after)
                    .context("PATCH_SOURCE requires a fenced code block")?;
                let path = self.resolve(file)?;
                if let Some(parent) = path.parent() {
                    std::fs::create_dir_all(parent)?;
                }
                std::fs::write(&path, &content)?;
                return Ok(Some(format!(
                    "[RSI] Patched {}. Run COMPILE_CHECK to verify.",
                    file
                )));
            }
        }
        Ok(None)
    }

    async fn compile_check(&self) -> Result<String> {
        // Build the working copy's Cargo project
        let cargo_toml = self.src_dir.parent().unwrap().join("Cargo.toml");
        if !cargo_toml.exists() {
            // Try one level up — src/ is inside the project root
            return Ok("[RSI] No Cargo.toml found adjacent to src/. Cannot compile.".into());
        }

        let output = Command::new("cargo")
            .args(["build", "--manifest-path", cargo_toml.to_str().unwrap()])
            .output()
            .await?;

        let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
        let stdout = String::from_utf8_lossy(&output.stdout).into_owned();

        if output.status.success() {
            Ok("[RSI] Compile OK. Run STAGE_UPDATE to mark for deployment.".into())
        } else {
            Ok(format!("[RSI] Compile FAILED:\n{}{}", stdout, stderr))
        }
    }

    fn stage_update(&self) -> Result<String> {
        let flag = self.forge_dir.join(STAGED_FLAG);
        // Write the path to the compiled binary so main knows what to swap
        let binary = self.src_dir
            .parent()
            .unwrap()
            .join("target/debug/aether-forge");
        std::fs::write(&flag, binary.to_str().unwrap_or(""))?;
        Ok(format!(
            "[RSI] Update staged. Restart Æther Forge to apply.\nBinary: {}",
            binary.display()
        ))
    }

    fn resolve(&self, file: &str) -> Result<PathBuf> {
        // Strip leading slashes or src/ prefix so model can use natural paths
        let file = file
            .trim_start_matches('/')
            .trim_start_matches("src/");
        let path = self.src_dir.join(file);
        // Prevent path traversal outside src_dir
        let canonical_src = self.src_dir.canonicalize().unwrap_or(self.src_dir.clone());
        let canonical_path = path.canonicalize().unwrap_or(path.clone());
        if !canonical_path.starts_with(&canonical_src) {
            anyhow::bail!("Path traversal attempt blocked: {}", file);
        }
        Ok(path)
    }
}

// --- Helpers ---

fn find_source_origin() -> Result<PathBuf> {
    // 1. Env override
    if let Ok(p) = std::env::var("AETHER_SOURCE") {
        let p = PathBuf::from(p);
        if p.exists() {
            return Ok(p);
        }
    }

    // 2. Common dev locations relative to binary
    let exe = std::env::current_exe().unwrap_or_default();
    let candidates = [
        exe.parent().and_then(|p| p.parent()).map(|p| p.join("src")),
        Some(PathBuf::from("src")),
        dirs::home_dir().map(|h| h.join("aether-forge/src")),
        dirs::home_dir().map(|h| h.join("Documents/GitHub/aether-forge/src")),
        dirs::home_dir().map(|h| h.join("Projects/aether-forge/src")),
    ];

    for candidate in candidates.into_iter().flatten() {
        if candidate.exists() && candidate.join("main.rs").exists() {
            return Ok(candidate);
        }
    }

    anyhow::bail!(
        "Cannot find aether-forge source. Set AETHER_SOURCE=/path/to/aether-forge/src"
    )
}

fn copy_dir(src: &Path, dst: &Path) -> Result<()> {
    std::fs::create_dir_all(dst)?;
    for entry in std::fs::read_dir(src)?.flatten() {
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        if src_path.is_dir() {
            copy_dir(&src_path, &dst_path)?;
        } else {
            std::fs::copy(&src_path, &dst_path)?;
        }
    }
    Ok(())
}

fn extract_code_block(text: &str) -> Option<String> {
    let fence_start = text.find("```")?;
    let after_fence = &text[fence_start + 3..];
    // Skip language tag line
    let content_start = after_fence.find('\n')? + 1;
    let content = &after_fence[content_start..];
    let end = content.find("```")?;
    Some(content[..end].to_string())
}
