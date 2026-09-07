use crate::config::Config;
use colored::Colorize;
use std::io::{self, BufRead, Write};

const BRAND: &str = "ÆTHER-FORGE";
const TAGLINE: &str = "A fully local AI environment that grows with you.";
const POWERED: &str = "Powered by Vaelora Systems";

pub struct Terminal;

impl Terminal {
    pub fn new() -> Self {
        Self
    }

    pub fn boot_animation(&self) {
        println!();
        println!("        {}", BRAND.bold().bright_white());
        println!("        {}", TAGLINE.dimmed());
        println!("        {}", POWERED.dimmed());
    }

    pub fn info(&self, msg: &str) {
        println!("  {}", msg.bright_white());
    }

    pub fn spinner(&self, msg: &str) {
        print!("  {}", msg.bright_white());
        io::stdout().flush().ok();
    }

    pub fn ready(&self, cfg: &Config) {
        // Overwrite spinner line
        println!(" {}", "ready.".bright_green());
        println!(
            "  {} {} | {} {} | {} {}",
            "OS:".dimmed(),
            cfg.os.to_string().bright_white(),
            "Shell:".dimmed(),
            cfg.shell.bright_white(),
            "Session:".dimmed(),
            detect_session().bright_white(),
        );
    }

    pub fn awake(&self) {
        println!("  {}", "Æther Forge is awake.".bold().bright_white());
        println!();
    }

    pub fn forging(&self) {
        println!("  {}", "Forging...".dimmed());
    }

    pub fn respond(&self, msg: &str) {
        println!("{}", msg.bright_white());
        println!();
    }

    pub fn error(&self, msg: &str) {
        eprintln!("  {} {}", "✗".bright_red(), msg.red());
    }

    /// Block and read a line of text input from stdin
    pub fn prompt(&self) -> String {
        print!("  {} ", "⟁".bright_cyan());
        io::stdout().flush().ok();

        let stdin = io::stdin();
        let mut line = String::new();
        stdin.lock().read_line(&mut line).ok();
        line
    }
}

fn detect_session() -> String {
    if std::env::var("WAYLAND_DISPLAY").is_ok() {
        "wayland".into()
    } else if std::env::var("DISPLAY").is_ok() {
        "x11".into()
    } else {
        "tty".into()
    }
}