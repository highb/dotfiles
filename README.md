# dotfiles

Miscellaneous config files, etc that I manage using [chezmoi](https://www.chezmoi.io).

## Usage

### Preferred archy way

```
pamac install mise
# Will get overwritten when we pull down the new .config/mise.toml
mise use --global chezmoi@2.63.1
mise install
GITHUB_USERNAME=highb chezmoi init --apply $GITHUB_USERNAME
# Close and re-open active term/session
```

### curly way

```
gpg --keyserver hkps://keyserver.ubuntu.com --recv-keys 0x7413A06D
curl https://mise.jdx.dev/install.sh.sig | gpg --decrypt > install.sh
# ensure the above is signed with the mise release key
sh ./install.sh
# Will get overwritten when we pull down the new .config/mise.toml
mise use --global chezmoi@2.63.1
mise install
GITHUB_USERNAME=highb sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply $GITHUB_USERNAME
# Close and re-open active term/session
./bin/up
```

## TODO

- setup a boot.sh script to do the above steps correctly on different OS
- add something similar to my [.bhell](https://github.com/highb/.bhell)
scripts here that will manage installing any necessary packages using some cobbled
together scripts that use _waves hands around_ a package manager (Nix, brew, etc.)
- determine a good way to sync the .config/chezmoi/chezmoi.toml file, as well
- manage application color schemes in some sane way
- use some fancy templates and secrets manager stuff
- add other useful scripts powered by some useful shared libraries like https://gitlab.com/bertrand-benoit/scripts-common/-/blob/master/utilities.sh?ref_type=heads

# Home Directory Structure

This repository contains a partial layout of my home directory, which is managed and synced across Linux systems using [Chezmoi](https://github.com/twpayne/chezmoi). Each directory with an organizational scheme typically has a README.md file for reference.

## Directory Structure

- **Applications/**
  - Directory for storing flatpak and AppImage files. Managed outside of Chezmoi.
  - *TODO:* Consider implementing an idempotent tool for flatpak management and installation.

- **bin/**
  - Directory for storing single binary tools and personal scripts. Scripts are synced by Chezmoi, while binaries are often directly downloaded.
  - *TODO:* Consider implementing an idempotent tool for binary management (aside from asdf). Could be nix?

- **Desktop/**
  - Generally empty, as I do not frequently access my desktop.

- **Documents/**
  - Various document artifacts, sorted into [PARA](https://fortelabs.co/blog/para/) subdirectories for ease of organization.

- **Downloads/**
  - Temporary landing area for downloaded files.

- **Music/**
  - Storage for MP3s and other music files. Largely unnecessary due to streaming services like Spotify or Synology.

- **Pictures/**
  - Various pictures, sorted into relevant categories. Image data related to [PARA](https://fortelabs.com/blog/para/) projects should be stored under Documents.

- **Public/**
  - Directory for shared files.

- **src/**
  - Directory for storing various source code repositories, organized by the organization that "owns" the source.

- **Templates/**
  - GNOME (Nautilus) file templates, accessible via the file browser's right-click menu. Potentially useful, but may not be frequently utilized.
  - This is apparently an XDG standard.

- **Videos/**
  - Directory for storing video content. Video data related to [PARA](https://fortelabs.com/blog/para/) projects should be stored under Documents.

- **Dotfiles (hidden files)**
  - Collection of dotfiles, managed and synced by Chezmoi. Only a subset of dotfiles that I care about are actively managed.

## Usage
This directory structure and file management helps maintain organization and consistency across my Linux systems. Each directory serves a specific purpose, facilitating efficient file management and access.

## Contributing
If you have suggestions for improving this directory structure or tools for management, feel free to open an issue or pull request.

