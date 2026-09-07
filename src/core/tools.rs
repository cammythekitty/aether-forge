use crate::config::Config;
use anyhow::Result;
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
};

#[derive(Clone)]
pub struct Tool {
    pub name: String,
    pub path: PathBuf,
}

#[derive(Clone)]
pub struct ToolRegistry {
    tools: HashMap<String, Tool>,
    dir: PathBuf,
}

impl ToolRegistry {
    pub async fn load(cfg: &Config) -> Result<Self> {
        let dir = cfg.tools_dir.clone();
        let mut tools = HashMap::new();

        if dir.exists() {
            for entry in std::fs::read_dir(&dir)?.flatten() {
                let path = entry.path();
                if path.is_file() {
                    #[cfg(unix)]
                    {
                        use std::os::unix::fs::PermissionsExt;
                        let meta = std::fs::metadata(&path)?;
                        if meta.permissions().mode() & 0o111 == 0 {
                            continue;
                        }
                    }

                    if let Some(name) = path.file_stem().and_then(|s| s.to_str()) {
                        tools.insert(
                            name.to_string(),
                            Tool {
                                name: name.to_string(),
                                path: path.clone(),
                            },
                        );
                    }
                }
            }
        }

        Ok(Self { tools, dir })
    }

    pub fn len(&self) -> usize {
        self.tools.len()
    }

    pub fn get(&self, name: &str) -> Option<&Tool> {
        self.tools.get(name)
    }

    pub fn describe(&self) -> String {
        if self.tools.is_empty() {
            return "(none)".into();
        }
        self.tools
            .values()
            .map(|t| format!("  - {}", t.name))
            .collect::<Vec<_>>()
            .join("\n")
    }

    /// Save a new tool script, make it executable, git commit it, and register it live
    pub async fn save(&mut self, name: &str, script: &str, _cfg: &Config) -> Result<()> {
        let filename = sanitize_name(name);
        let path = self.dir.join(&filename);

        std::fs::write(&path, script)?;

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = std::fs::metadata(&path)?.permissions();
            perms.set_mode(0o755);
            std::fs::set_permissions(&path, perms)?;
        }

        git_commit(&self.dir, &path, &format!("forge: add tool '{}'", name))?;

        self.tools.insert(
            name.to_string(),
            Tool {
                name: name.to_string(),
                path,
            },
        );

        Ok(())
    }
}

fn sanitize_name(name: &str) -> String {
    let clean: String = name
        .chars()
        .map(|c| if c.is_alphanumeric() || c == '_' || c == '-' { c } else { '_' })
        .collect();
    clean.trim_matches('_').to_lowercase()
}

fn git_commit(repo_dir: &Path, file: &Path, message: &str) -> Result<()> {
    let repo = match git2::Repository::open(repo_dir) {
        Ok(r) => r,
        Err(_) => {
            // Init repo if it doesn't exist
            let r = git2::Repository::init(repo_dir)?;
            r
        }
    };

    let mut index = repo.index()?;
    let rel = file.strip_prefix(repo_dir)?;
    index.add_path(rel)?;
    index.write()?;

    let tree_id = index.write_tree()?;
    let tree = repo.find_tree(tree_id)?;

    let sig = git2::Signature::now("Æther Forge", "forge@vaelora.local")?;

    let parent = repo.head().ok().and_then(|h| h.peel_to_commit().ok());
    let parents: Vec<&git2::Commit> = parent.iter().collect();

    repo.commit(Some("HEAD"), &sig, &sig, message, &tree, &parents)?;
    Ok(())
}