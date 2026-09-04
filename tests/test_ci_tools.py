"""Verify CI tool downloads fail closed before publishing executable paths."""

import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "setup_ci_tools", Path(__file__).resolve().parents[1] / "scripts/setup_ci_tools.py"
)
SETUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETUP)


class CiToolsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ci-tools-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pathfile = self.root / "github-path"
        self.responses = {}

    def releases(self, *, wrong_checksum=False, symlink=False):
        for repo, binary, version in SETUP.TOOLS:
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w:gz") as archive:
                info = tarfile.TarInfo(binary)
                if symlink:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "/outside/not-a-binary"
                    archive.addfile(info)
                else:
                    payload = f"fixture {binary}".encode()
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
                # Ancillary traversal entries must never be extracted.
                outside = tarfile.TarInfo("../unexpected")
                outside.size = 1
                archive.addfile(outside, io.BytesIO(b"x"))
            content = data.getvalue()
            name = f"{binary}_{version}_linux_amd64.tar.gz"
            base = f"https://github.com/{repo}/releases/download/v{version}"
            digest = "0" * 64 if wrong_checksum else hashlib.sha256(content).hexdigest()
            self.responses[f"{base}/{name}"] = content
            self.responses[f"{base}/{binary}_{version}_checksums.txt"] = (
                f"{digest}  {name}\n".encode()
            )

    def run_setup(self):
        with (
            patch.dict(os.environ, {"RUNNER_TEMP": str(self.root), "GITHUB_PATH": str(self.pathfile)}, clear=True),
            patch.object(SETUP.platform, "system", return_value="Linux"),
            patch.object(SETUP.platform, "machine", return_value="x86_64"),
            patch.object(SETUP.urllib.request, "urlopen", side_effect=lambda url, **kwargs: io.BytesIO(self.responses[url])),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            SETUP.main()

    def test_verified_regular_binaries_only_are_published(self):
        self.releases()
        self.run_setup()
        destination = Path(self.pathfile.read_text().strip())
        self.assertEqual(destination.parent, self.root)
        for _, binary, _ in SETUP.TOOLS:
            self.assertEqual((destination / binary).read_text(), f"fixture {binary}")
            self.assertTrue(os.access(destination / binary, os.X_OK))
        self.assertEqual({path.name for path in destination.iterdir()}, {tool[1] for tool in SETUP.TOOLS})
        self.assertFalse((self.root / "unexpected").exists())

    def test_checksum_mismatch_never_publishes_a_path(self):
        self.releases(wrong_checksum=True)
        with self.assertRaisesRegex(SystemExit, "SHA256 mismatch"):
            self.run_setup()
        self.assertFalse(self.pathfile.exists())
        self.assertFalse(any(path.is_file() for path in self.root.rglob("*")))

    def test_symlink_binary_never_publishes_a_path(self):
        self.releases(symlink=True)
        with self.assertRaisesRegex(SystemExit, "Expected one regular"):
            self.run_setup()
        self.assertFalse(self.pathfile.exists())
        self.assertFalse(any(path.is_file() for path in self.root.rglob("*")))


if __name__ == "__main__":
    unittest.main()
