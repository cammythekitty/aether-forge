use anyhow::Result;

/// Check if whisper-cli is available in PATH
pub fn available() -> bool {
    which("whisper-cli")
}

/// Record audio and transcribe via whisper-cli
/// Returns None if nothing was captured (silence / no input)
pub async fn listen() -> Result<Option<String>> {
    // TODO: implement push-to-talk audio capture + whisper transcription
    // This will use cpal for audio capture and whisper-cli for STT
    // For now returns None so the main loop falls back to text input
    Ok(None)
}

fn which(bin: &str) -> bool {
    std::env::var_os("PATH")
        .map(|paths| {
            std::env::split_paths(&paths).any(|dir| {
                let full = dir.join(bin);
                full.exists()
                    || {
                        #[cfg(windows)]
                        {
                            dir.join(format!("{}.exe", bin)).exists()
                        }
                        #[cfg(not(windows))]
                        false
                    }
            })
        })
        .unwrap_or(false)
}