# Aether Forge

Aether Forge is a Rust-based project. The current version builds and runs without errors, but the optional `voice` module is not present, so all voice-related features are disabled by default.

## Features
- Text-based input and output
- Modular core components (see `src/core/`)

## Getting Started

### Prerequisites
- Rust toolchain (https://rustup.rs/)

### Build and Run
```bash
cargo build
cargo run
```

### Testing
```bash
cargo test
```

## Project Structure
- `src/main.rs`: Main entry point
- `src/core/`: Core modules (executor, server, tools, brain, rsi)

## Notes
- Voice features are currently disabled due to missing module.
- Contributions are welcome!

## License
idc do whatever