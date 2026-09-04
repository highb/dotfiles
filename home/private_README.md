# Home Directory

A partial layout of my home directory, managed and synced across Linux
machines with [chezmoi](https://www.chezmoi.io). The source repository lives at
`~/.local/share/chezmoi`; run `chezmoi cd` to get there.

Directories with an organisational scheme of their own carry their own
`README.md`.

## Directories

- **Applications/** — flatpak and AppImage files. Managed outside chezmoi.
- **bin/** — single-binary tools and personal scripts. The scripts are synced
  by chezmoi; the binaries are downloaded directly and are not.
- **Desktop/** — generally empty. I do not work from the desktop.
- **Documents/** — sorted into [PARA](https://fortelabs.co/blog/para/)
  subdirectories.
- **Downloads/** — landing area for downloaded files. Assumed disposable.
- **Music/** — largely vestigial, given streaming.
- **Pictures/** — sorted by category. Images belonging to a PARA project live
  under `Documents/` instead.
- **Public/** — shared files.
- **src/** — source repositories, organised by the organisation that owns them.
- **Templates/** — GNOME (Nautilus) right-click file templates. An XDG
  standard, and more useful in principle than in practice.
- **Videos/** — video belonging to a PARA project lives under `Documents/`.

## Shell configuration

`~/.bashrc` and `~/.zshrc` are thin. Everything shared between shells lives in
`~/.config/shell/`, most of it generated from a single YAML file in the chezmoi
source repo. See `~/.config/shell/README.md` before editing anything there.

## Dotfiles

Only the subset of dotfiles I actually care about is managed. `chezmoi managed`
lists them.
