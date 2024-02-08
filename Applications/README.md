# Applications Directory

The `Applications/` directory is where flatpak and AppImage files are stored. These files are not directly managed by Chezmoi.

## Purpose
This directory serves as a centralized location for storing application files that are not installed via package managers or managed directly by Chezmoi.

## Management
Currently, the management of flatpak and AppImage files is manual.  

TODO There is a potential for improvement through the implementation of an idempotent tool for flatpak management and installation.

## Usage
When downloading flatpak or AppImage files, they can be placed in this directory for easy access and organization. I use [AppImageLauncher](https://github.com/TheAssassin/AppImageLauncher) to manage moving files here and creating the Desktop files to launch them.

## Contributing
If you have suggestions for improving the management or organization of applications within this directory, feel free to contribute by opening an issue or pull request.

