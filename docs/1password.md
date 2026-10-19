# 1Password

The desktop role requests the native `1password` app and `1password-cli` (`op`)
from 1Password's own APT repository on Debian/Ubuntu-based hosts. Neither tool
uses mise, Snap, Flatpak or a community package. Other platforms remain unresolved
until a vendor installation method is added; there is no automatic fallback.

Before metapac installs packages, `15-1password-apt.sh` follows the
[official app instructions](https://support.1password.com/install-linux/#debian-or-ubuntu)
and [CLI instructions](https://developer.1password.com/docs/cli/get-started/):

- Download the vendor signing key over HTTPS and check its primary fingerprint
  against `3FEF9748469ADBE15DA7CA80AC2D62742012EA22` from the official guide.
- Configure the APT repository with its own `signed-by` keyring.
- Install the vendor debsig policy and keyring.
- Refresh APT metadata; APT verifies repository signatures and package hashes.
  Invalid signatures stop provisioning. No unauthenticated-install option is used.

The debsig policy makes the vendor's package-signature policy available to
`debsig-verify`; installing a policy alone does not invoke that tool. Automated
installation here uses APT's signed metadata and package-hash verification,
as in the documented APT installation method.

This setup requires curl, GnuPG, dpkg and sudo. Installation uses the same
interactive confirmation or scoped automation consent as other packages.
`manualProvisioning` skips repository setup as well as package installation.
The setup hook only runs when a selected, non-excluded 1Password tool resolves
to APT. It does not change this machine until you apply the dotfiles.

`home/private_dot_config/private_1Password/private_ssh/private_agent.toml`
captures the current SSH agent configuration, deployed with mode 0600 for the
desktop role. It selects the `1 SSH Keys` vault in `highsteiner.1password.com`.
This contains vault/account identifiers, not private keys or credentials.
Enable the SSH agent and CLI integration in the 1Password app's Developer
settings. Lock and unlock the app after first deploying the config.
