# Repository instructions for all agents

Read README.md and KNOWN_ISSUES.md before changing provisioning or platform behavior.
These instructions apply to this entire repository, including delegated agents.

## Purpose and core loop

These dotfiles augment Brandon's shell and OS environment to expand his own
capabilities through as much deterministic code as possible. They also provide
access to LLMs to help drive further augmentation of that environment.

- Turn recurring needs and lessons from LLM-assisted work into reusable local
  tools: scripts, commands, configuration, and repeatable workflows.
- Prefer deterministic code for behavior that can be expressed and verified
  reliably. Use LLMs to help discover, build, explain, and improve those tools.
- Always seek to leave Brandon with tools he can run locally without LLM
  assistance. Where a capability inherently requires an LLM, make that dependency
  explicit and keep the surrounding workflow usable and inspectable locally.
- Treat comprehensive documentation as part of the deliverable. Explain the
  purpose, prerequisites, setup, commands, expected results, verification, and
  troubleshooting in enough detail for Brandon to follow independently.
- Keep durable instructions and examples in the repository alongside the tools;
  a chat response alone is not sufficient documentation for a new workflow.
- Close the loop by making each augmentation reproducible through chezmoi and
  the repository's provisioning model, with an independent local entry point
  and documentation for using and maintaining it.

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
