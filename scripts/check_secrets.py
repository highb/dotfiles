#!/usr/bin/env python3
"""Scan raw staged file contents without exposing scanner output or credentials."""

import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile


def check_secrets(filenames):
    scanner = shutil.which("trufflehog")
    if scanner is None:
        print("Commit blocked: install the managed trufflehog package first.", file=sys.stderr)
        return 1
    if not filenames:
        return 0

    try:
        index = subprocess.run(
            ["git", "--literal-pathspecs", "ls-files", "--stage", "-z", "--", *filenames],
            capture_output=True, check=True,
        ).stdout
        with tempfile.TemporaryDirectory(prefix="dotfiles-staged-secrets-") as temporary:
            root = Path(temporary)
            exported = False
            for record in index.split(b"\0"):
                if not record:
                    continue
                metadata, filename = record.split(b"\t", 1)
                mode, object_id, stage = metadata.split()
                if stage != b"0":
                    raise ValueError("unmerged index")
                # Never follow a staged symlink or descend into a submodule.
                if mode not in (b"100644", b"100755"):
                    continue
                relative = PurePosixPath(os.fsdecode(filename))
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("invalid index path")
                target = root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as contents:
                    subprocess.run(
                        ["git", "cat-file", "blob", object_id.decode("ascii")],
                        stdout=contents, stderr=subprocess.PIPE, check=True,
                    )
                exported = True
            if not exported:
                return 0
            # Raw, SecretParts, scanner errors, and detector metadata can contain
            # credentials. Do not forward either output stream into commit/CI logs.
            result = subprocess.run(
                [
                    scanner, "filesystem", "--no-verification", "--no-update",
                    "--fail", "--fail-on-scan-errors",
                    "--results=verified,unknown,unverified",
                    str(root),
                ],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Commit blocked: unable to scan the staged snapshot safely.", file=sys.stderr)
        return 1

    if result.returncode == 183:
        print(
            "Commit blocked: TruffleHog found a possible secret in staged content. "
            "Review staged changes privately; credential output is suppressed.",
            file=sys.stderr,
        )
    elif result.returncode:
        print(
            "Commit blocked: TruffleHog could not complete the staged scan "
            f"(exit {result.returncode}). Scanner output is suppressed.",
            file=sys.stderr,
        )
    return int(result.returncode != 0)


if __name__ == "__main__":
    sys.exit(check_secrets(sys.argv[1:]))
