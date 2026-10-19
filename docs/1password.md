# 1Password

The desktop role selects the native `1password` app and `1password-cli` (`op`).
Both come directly from official vendor sources. Neither uses mise, Homebrew,
Snap, Flatpak, or community packages.

| Platform | Architectures | Installation and verification |
| --- | --- | --- |
| Debian/Ubuntu | Existing APT architecture policy | Existing vendor APT repository, pinned GPG key, signed metadata and package hashes |
| macOS | Intel x86_64, Apple arm64 | Official desktop PKG and universal CLI PKG; Apple certificate-chain validation, AgileBits developer identity, published SHA-256 certificate pins, and Gatekeeper assessment before installation |
| Fedora/RHEL | x86_64 for both tools; aarch64 for CLI alone | Official RPM repository with pinned GPG key, `gpgcheck=1` and `repo_gpgcheck=1`; DNF validates metadata and package signatures before installation |
| Bazzite/Universal Blue | x86_64 for both tools | Official RPM downloads; package signatures checked against an isolated database containing only the pinned vendor key, then `rpm-ostree` layering; reboot required |

Bazzite, Bluefin, Aurora, and `ublue` OS IDs are recognized, as are Fedora IDs
used by Universal Blue images. Availability of `rpm-ostree` selects layering
instead of DNF. Other platforms and unavailable or disabled vendor providers
are explicitly reported with no fallback. Unsupported architectures stop the
vendor hook. The desktop RPM path currently rejects ARM; a CLI-only selection
can use aarch64. The existing APT implementation and architecture policy are
unchanged.

The shared selection, availability, resolution, and planning helpers apply host
roles, `packageExcludes`, and authoritative `packageProviders` overrides. The
`1password-vendor` provider handles PKGs and RPMs outside metapac; `apt` remains
the Debian/Ubuntu provider. Selecting an undeclared provider leaves the tool
unresolved. Previews identify PKG verification, DNF, or rpm-ostree layering.
`manualProvisioning` disables installation hooks. Installation requires the
shared interactive confirmation or `DOTFILES_INSTALL_PACKAGES=1`; a noninteractive
run without consent performs no downloads or installation.

## Verification and official references

The preserved `15-1password-apt.sh` setup follows the
[Linux app instructions](https://support.1password.com/install-linux/)
and [CLI installation guide](https://developer.1password.com/docs/cli/get-started/).
It pins the primary GPG fingerprint
`3FEF9748469ADBE15DA7CA80AC2D62742012EA22`, configures a dedicated `signed-by`
keyring, installs the vendor debsig policy/keyring, and refreshes signed APT
metadata. APT verifies repository signatures and package hashes. Installing the
debsig policy does not itself invoke `debsig-verify`.

`16-1password-vendor.sh` uses the same pinned GPG fingerprint for RPMs, checking
it in an isolated GnuPG home before any privileged repository changes. On DNF
hosts, both repository and package signature checks remain enabled. DNF excludes these two package names from
other repositories while allowing dependencies from normal system repositories.
An existing differently named 1Password repository causes a reconciliation
error instead of adding a duplicate. The canonical repository and key are only
written when their contents differ.

On immutable systems the hook downloads the official latest RPMs and imports the pinned key into a temporary RPM database. `rpm --checksig --verbose`
must succeed and report an actual valid signature; digest-only unsigned RPMs
are rejected. All missing artifacts pass before invoking rpm-ostree. This avoids
selecting a same-named community package from another enabled repository:
rpm-ostree's host client does not support repository-scoping flags. No repository
or booted RPM database is modified by this path.

On macOS, the [official deployment PKG](https://support.1password.com/deploy-1password/)
installs the app in `/Applications`. The CLI uses the official universal
[2.41.0 release PKG](https://app-updates.agilebits.com/product_history/CLI2), pinned
in the hook. `pkgutil --check-signature` validates the Apple certificate chain;
the hook checks `Developer ID Installer: AgileBits Inc. (2BUA8C4S2C)` and the
published certificate fingerprints from the
[desktop verification guide](https://support.1password.com/verify-download/) and
[CLI verification guide](https://developer.1password.com/docs/cli/verify/).
`spctl --assess --type install` must also accept each PKG. All missing PKGs are
verified before either installer is invoked. Any failed verification terminates
the hook without installing the downloaded artifacts; there is no bypass.
Certificate rotation requires reviewing official documentation and updating pins.

Existing apps and `op` installations are preserved. RPM package queries also
recognize apps supplied by the base image. `rpm-ostree install --idempotent`
handles packages already requested in a pending deployment; the hook never
reboots automatically. See the [rpm-ostree administrator handbook](https://coreos.github.io/rpm-ostree/administrator-handbook/).
The current [Bazzite application recipe file](https://github.com/ublue-os/bazzite/blob/main/system_files/desktop/shared/usr/share/ublue-os/just/82-bazzite-apps.just) was inspected; no 1Password recipe
was found there. Provisioning uses the vendor RPM downloads directly rather than
assuming a `ujust` recipe exists or delegating trust to a changing recipe.

Prerequisites: curl and sudo; GnuPG and rpm plus DNF or rpm-ostree on RPM hosts;
Apple's pkgutil, spctl and installer on macOS. Missing prerequisites are reported.
These hooks install missing tools rather than upgrading existing installations.
Manage desktop PKG updates explicitly (the vendor deployment PKG does not enable
automatic app updates); review the CLI version pin when updating. DNF packages
use normal system updates. Locally layered RPMs retain their
installed versions across rpm-ostree updates; updating them requires explicitly
replacing the local packages with newly downloaded and verified vendor RPMs.
The hook provisions missing tools and does not automate that upgrade workflow.

Isolated tests render real policy templates and use fake downloaders, verifiers, and installers; they install no host packages.
Actual macOS and immutable-system installation still needs validation on those
operating systems. The vendor [stable release notes](https://releases.1password.com/linux/stable/)
record the rpm-ostree installation fix in 8.12.32; use the current stable
vendor downloads rather than old cached RPMs.

## SSH agent configuration

`home/private_dot_config/private_1Password/private_ssh/private_agent.toml`
preserves the current SSH agent configuration. For the desktop role it deploys
as `~/.config/1Password/ssh/agent.toml` on Linux and macOS, with mode 0600 and
private parent directories. It selects the `1 SSH Keys` vault in
`highsteiner.1password.com`. These are vault/account identifiers, not credentials
or private keys. Package exclusions and manual provisioning do not remove this
configuration, so externally installed apps can use it.

Enable the SSH agent and CLI integration in the app's Developer settings, then
lock and unlock the app after first deploying the config.
