"""Delta archive installation in temporary homes; no real downloads or apps."""

import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "home/bin/executable_install-delta"
loader = importlib.machinery.SourceFileLoader("delta_install", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
delta = importlib.util.module_from_spec(spec)
loader.exec_module(delta)


class DeltaInstallTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / "Delta"
        (self.bundle / "bin").mkdir(parents=True)
        (self.bundle / "bin/delta").write_text("fixture executable")
        (self.bundle / "bin/delta").chmod(0o755)
        self.app = self.root / "home/.local/delta.app"
        self.link = self.root / "home/.local/bin/delta"

    def install(self):
        delta.install(self.bundle, self.app, Path("bin/delta"), self.link, {"version": "fixture"})

    def test_install_and_replace_preserve_link_and_receipt(self):
        self.install()
        self.assertEqual(self.link.resolve(), self.app / "bin/delta")
        self.assertEqual(json.loads((self.app / ".dotfiles-install.json").read_text()), {"version": "fixture"})
        (self.bundle / "bin/delta").write_text("updated fixture")
        self.install()
        self.assertEqual(self.link.read_text(), "updated fixture")

    def test_unrelated_cli_is_preserved(self):
        self.link.parent.mkdir(parents=True)
        self.link.write_text("unrelated command")
        with self.assertRaisesRegex(ValueError, "Unrelated command"):
            self.install()
        self.assertEqual(self.link.read_text(), "unrelated command")
        self.assertFalse(self.app.exists())

    def test_unrelated_symlink_is_preserved(self):
        self.link.parent.mkdir(parents=True)
        self.link.symlink_to(self.root / "other")
        with self.assertRaisesRegex(ValueError, "Unrelated command"):
            self.install()
        self.assertEqual(self.link.readlink(), self.root / "other")

    def test_invalid_bundle_does_not_replace_working_app(self):
        self.install()
        (self.bundle / "bin/delta").unlink()
        with self.assertRaisesRegex(ValueError, "missing Delta"):
            self.install()
        self.assertEqual(self.link.read_text(), "fixture executable")

    def test_reuse_repairs_cli_and_linux_desktop_integration(self):
        self.install()
        self.link.unlink()
        with patch.object(Path, "home", return_value=self.root / "home"):
            delta.integrate(self.app, Path("bin/delta"), self.link, "linux")
        self.assertEqual(self.link.resolve(), self.app / "bin/delta")
        desktop = self.root / "home/.local/share/applications/dev.zed.Delta.desktop"
        self.assertIn('" open %U', desktop.read_text())
        self.assertIn("StartupWMClass=dev.zed.Delta", desktop.read_text())

    def test_failed_swap_restores_old_app(self):
        self.install()
        original_rename = Path.rename

        def fail_new(path, destination):
            if path.name == "new":
                raise OSError("fixture swap failure")
            return original_rename(path, destination)

        with patch.object(Path, "rename", fail_new):
            with self.assertRaisesRegex(OSError, "swap failure"):
                self.install()
        self.assertEqual(self.link.read_text(), "fixture executable")

    def test_release_metadata_must_match_official_versioned_url(self):
        def fake_fetch(url, destination):
            destination.write_text(json.dumps({"version": "0.20.1", "url": "https://example.com/other.tar.gz"}))

        with patch.object(delta, "fetch", fake_fetch):
            with self.assertRaisesRegex(ValueError, "Unexpected Delta release URL"):
                delta.release("linux", "x86_64", None, self.root)
        with patch.object(delta, "fetch") as fetch:
            _, url = delta.release("linux", "aarch64", "0.20.1", self.root)
            self.assertTrue(url.endswith("/0.20.1/delta-linux-aarch64.tar.gz"))
            fetch.assert_not_called()

    def test_tar_path_traversal_is_rejected(self):
        archive = self.root / "bad.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            member = tarfile.TarInfo("../../escape")
            member.size = 1
            output.addfile(member, io.BytesIO(b"x"))
        with self.assertRaises(tarfile.FilterError):
            delta.extract(archive, self.root, "linux")
        self.assertFalse((self.root.parent / "escape").exists())

    def test_dry_run_and_checksum_failure_do_not_install(self):
        for options in (["--dry-run"], ["--sha256", "0" * 64]):
            with self.subTest(options=options):
                with patch.object(delta, "target", return_value=("linux", "x86_64")), \
                     patch.object(Path, "home", return_value=self.root / "home"), \
                     patch.object(delta, "fetch", side_effect=lambda url, dest: dest.write_bytes(b"fixture")), \
                     patch("sys.argv", ["install-delta", "--version", "0.20.1", *options]), \
                     patch("sys.stdout", new_callable=io.StringIO):
                    if "--sha256" in options:
                        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                            delta.main()
                    else:
                        delta.main()
                    self.assertFalse(self.app.exists())


if __name__ == "__main__":
    unittest.main()
