# Repository instructions for all agents

Read README.md and KNOWN_ISSUES.md before changing provisioning or platform behavior.
These instructions apply to this entire repository, including delegated agents.

## Supported platforms

- Primary: Ubuntu/Debian Linux, including Pop!_OS, and macOS.
- CI: Ubuntu 24.04 and macOS 15; keep changes portable to both.
- Partial: Arch Linux and Fedora. Bootstrap recognizes them, but many inventory
  entries lack providers. Report unresolved packages rather than implying full support.
- Unsupported deployment targets: Windows, WSL, Android/Termux, and other OSes.
  Do not infer platform support from an upstream application's error message.
  Adding a target requires explicit documentation, provisioning, and validation.
- Linux desktops may use Wayland or X11; headless and SSH sessions may have neither.
  Select clipboard providers at runtime: wl-copy/wl-paste on Wayland, xclip on
  X11, built-in pbcopy/pbpaste on macOS. Do not force a desktop backend globally.

## Implementation and validation

- `.chezmoiroot` points at `home/`. Edit source files here, not generated targets.
- Package definitions belong in `home/.chezmoidata/packages.yaml`; selection and
  resolution live in `home/.chezmoitemplates/`. Use `platforms` OS restrictions
  for tools that must not be selected on other targets.
- Preserve task selection, exclusions, provider overrides, manualProvisioning,
  and scoped install consent. Avoid broad package syncs for a narrow repair.
- Keep Bash compatible with macOS's bundled Bash 3.2. Do not assume GNU utilities
  on macOS. Linux desktop helpers must remain gated by platform and task.
- Run relevant isolated tests with `python3 -B -m unittest discover -s tests -v`.
  Tests must not read workstation credentials or provision real host packages.
- Do not commit secrets or bypass the repository's commit protection.
