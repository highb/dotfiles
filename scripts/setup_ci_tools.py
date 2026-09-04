#!/usr/bin/env python3
"""Install the two pinned native check tools into GitHub's runner temp directory."""

import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import tarfile
import tempfile
import urllib.request


TOOLS = (
    ("twpayne/chezmoi", "chezmoi", "2.72.1"),
    ("trufflesecurity/trufflehog", "trufflehog", "3.97.4"),
)


def main():
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(machine)
    if system not in ("darwin", "linux") or arch is None:
        raise SystemExit(f"Unsupported CI platform: {system}/{machine}")

    runner_temp = Path(os.environ["RUNNER_TEMP"])
    github_path = Path(os.environ["GITHUB_PATH"])
    bin_dir = Path(tempfile.mkdtemp(prefix="dotfiles-ci-bin-", dir=runner_temp))
    with tempfile.TemporaryDirectory(prefix="dotfiles-ci-downloads-", dir=runner_temp) as downloads:
        for repo, binary, version in TOOLS:
            base_url = f"https://github.com/{repo}/releases/download/v{version}"
            archive_name = f"{binary}_{version}_{system}_{arch}.tar.gz"
            checksums_url = f"{base_url}/{binary}_{version}_checksums.txt"
            with urllib.request.urlopen(checksums_url, timeout=60) as response:
                checksums = response.read().decode("ascii")
            matches = re.findall(
                rf"^([0-9a-f]{{64}})  {re.escape(archive_name)}$",
                checksums,
                flags=re.MULTILINE,
            )
            if len(matches) != 1:
                raise SystemExit(f"Expected one published SHA256 for {archive_name}")

            archive_path = Path(downloads) / archive_name
            with urllib.request.urlopen(f"{base_url}/{archive_name}", timeout=60) as response:
                with archive_path.open("xb") as destination:
                    shutil.copyfileobj(response, destination)
            with archive_path.open("rb") as archive_file:
                actual = hashlib.file_digest(archive_file, "sha256").hexdigest()
            if actual != matches[0]:
                raise SystemExit(f"SHA256 mismatch for {archive_name}")

            # Never extract archive paths, links, permissions, or ancillary files.
            with tarfile.open(archive_path, "r:gz") as archive:
                members = [member for member in archive if member.name == binary]
                if len(members) != 1 or not members[0].isreg():
                    raise SystemExit(f"Expected one regular {binary} binary in {archive_name}")
                with archive.extractfile(members[0]) as source:
                    with (bin_dir / binary).open("xb") as destination:
                        shutil.copyfileobj(source, destination)
            (bin_dir / binary).chmod(0o755)
            print(f"Installed {binary} {version} for {system}/{arch} (SHA256 verified)")

    with github_path.open("a", encoding="utf-8") as output:
        output.write(f"{bin_dir}\n")


if __name__ == "__main__":
    main()
