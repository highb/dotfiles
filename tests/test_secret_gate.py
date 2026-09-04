"""Exercise the installed commit gate in disposable repositories, without verification."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class SecretGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = {}
        for name in ("git", "bash", "dirname", "pre-commit", "trufflehog"):
            executable = shutil.which(name)
            if executable is None:
                raise RuntimeError(
                    f"Secret gate tests require {name} on PATH; "
                    "install pre-commit >= 4.4 and TruffleHog before running this suite."
                )
            cls.tools[name] = str(Path(executable).absolute())
        cls.tools["python3"] = sys.executable

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="secret-gate-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("home", "bin", "repo", "config", "cache", "data", "state", "tmp"):
            (self.root / name).mkdir()
        self.repo = self.root / "repo"
        self.bin = self.root / "bin"
        for name, executable in self.tools.items():
            (self.bin / name).symlink_to(executable)
        self.env = {
            "HOME": str(self.root / "home"),
            "PATH": str(self.bin),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "PRE_COMMIT_HOME": str(self.root / "cache" / "pre-commit"),
            "TMPDIR": str(self.root / "tmp"),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
        }
        # Hosted Python distributions may need their explicit shared-library path.
        if "LD_LIBRARY_PATH" in os.environ:
            self.env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        # Assemble only in the disposable fixture; never include a complete token
        # in this repository or in assertion messages.
        self.marker = (
            "".join(("gh", "p", "_")) + "Q7m2V9k4R6x8T3n5B1c0D2f4H6j8L0s9W3z5"
        ).encode("ascii")
        self.secret = b"GITHUB_TOKEN=" + self.marker + b"\n"
        self.clean = b"ordinary fixture content\n"
        self.require_success(self.git("init", "--quiet", "--template="), "git init")
        for key, value in (
            ("user.name", "Secret Gate Test"),
            ("user.email", "secret-gate@example.invalid"),
            ("commit.gpgsign", "false"),
            ("tag.gpgsign", "false"),
            ("core.autocrlf", "false"),
        ):
            self.require_success(self.git("config", "--local", key, value), "git config")
        (self.repo / "scripts").mkdir()
        for relative in (".pre-commit-config.yaml", "scripts/check_secrets.py"):
            shutil.copyfile(SOURCE / relative, self.repo / relative)
        self.stage(".pre-commit-config.yaml", "scripts/check_secrets.py")
        self.require_success(self.run_command("pre-commit", "install"), "pre-commit install")

    def run_command(self, *arguments):
        try:
            result = subprocess.run(
                arguments,
                cwd=self.repo,
                env=self.env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=90,
            )
        except subprocess.TimeoutExpired:
            # TimeoutExpired includes captured streams; do not expose them through
            # a chained exception or unittest's assertion representations.
            raise AssertionError("Secret gate command exceeded 90 seconds") from None
        self.assertFalse(
            self.marker in result.stdout or self.marker in result.stderr,
            "Secret gate leaked the synthetic credential into command output",
        )
        return result

    def git(self, *arguments):
        return self.run_command("git", "--literal-pathspecs", *arguments)

    def require_success(self, result, operation):
        self.assertEqual(result.returncode, 0, f"{operation} failed; output suppressed")

    def stage(self, *filenames):
        self.require_success(self.git("add", "--", *filenames), "git add")

    def write_staged(self, filename, contents):
        (self.repo / filename).write_bytes(contents)
        self.stage(filename)

    def head(self):
        result = self.git("rev-parse", "--verify", "HEAD")
        return result.stdout.strip() if result.returncode == 0 else None

    def commit(self, *, allowed, message=None):
        previous = self.head()
        result = self.git("commit", "--quiet", "-m", "Disposable gate fixture")
        current = self.head()
        if allowed:
            self.require_success(result, "git commit")
            self.assertIsNotNone(current, "Successful commit did not create HEAD")
            self.assertNotEqual(current, previous, "Successful commit did not advance HEAD")
        else:
            self.assertNotEqual(result.returncode, 0, "Secret gate unexpectedly allowed commit")
            self.assertEqual(current, previous, "Blocked commit changed HEAD")
            self.assertTrue(
                b"Commit blocked:" in result.stdout + result.stderr,
                "Commit failed without the secret gate's sanitized diagnostic",
            )
        if message is not None:
            self.assertTrue(
                message in result.stdout + result.stderr,
                "Expected sanitized gate diagnostic was absent",
            )
        return result

    def baseline(self):
        self.commit(allowed=True)

    def assert_file_content(self, filename, expected):
        self.assertTrue(
            (self.repo / filename).read_bytes() == expected,
            "Commit hook changed the worktree content",
        )

    def test_initial_clean_commit_is_allowed(self):
        self.assertIsNone(self.head())
        self.write_staged("ordinary.txt", self.clean)
        # Keep TruffleHog's normal false-positive filtering: this public project
        # slug resembles a legacy GitLab token, but is not a credential.
        self.write_staged(
            "public-link.md",
            b"[nautilus-new-folder-from-template]"
            b"(https://gitlab.com/edgimar/nautilus-new-folder-from-template).\n",
        )
        self.commit(allowed=True)
        self.assert_file_content("ordinary.txt", self.clean)

    def test_initial_staged_secret_blocks_commit_without_output_leak(self):
        self.assertIsNone(self.head())
        self.write_staged("credential.txt", self.secret)
        self.commit(allowed=False, message=b"found a possible secret")
        self.assertIsNone(self.head())
        self.assert_file_content("credential.txt", self.secret)

    def test_staged_secret_with_unstaged_clean_content_still_blocks(self):
        self.baseline()
        self.write_staged("credential.txt", self.secret)
        (self.repo / "credential.txt").write_bytes(self.clean)
        self.commit(allowed=False, message=b"found a possible secret")
        self.assert_file_content("credential.txt", self.clean)
        # Restoring the staged version proves the rejected snapshot remains
        # staged, without printing its contents through git show.
        self.require_success(self.git("checkout", "--", "credential.txt"), "git checkout")
        self.assert_file_content("credential.txt", self.secret)

    def test_staged_clean_with_unstaged_secret_commits_and_restores_worktree(self):
        self.baseline()
        self.write_staged("credential.txt", self.clean)
        (self.repo / "credential.txt").write_bytes(self.secret)
        self.commit(allowed=True)
        self.assert_file_content("credential.txt", self.secret)
        committed = self.git("show", "HEAD:credential.txt")
        self.require_success(committed, "git show clean committed content")
        self.assertTrue(committed.stdout == self.clean, "Commit did not preserve staged content")
        self.require_success(self.git("diff", "--cached", "--quiet"), "empty committed index")

    def test_unusual_paths_are_committed_clean_and_blocked_when_secret(self):
        filenames = ("with space.txt", "with\nnewline.txt", "-leading.txt", ":(glob)*.txt")
        for filename in filenames:
            self.write_staged(filename, self.clean)
        self.commit(allowed=True)
        for filename in filenames:
            with self.subTest(filename=filename):
                self.write_staged(filename, self.secret)
                self.commit(allowed=False, message=b"found a possible secret")
                self.assert_file_content(filename, self.secret)
                self.write_staged(filename, self.clean)

    def fake_scanner(self, body):
        scanner = self.bin / "trufflehog"
        scanner.unlink()
        scanner.write_text("#!/usr/bin/env python3\n" + body)
        scanner.chmod(0o700)

    def test_staged_symlink_is_not_exported_or_followed(self):
        external = self.root / "external-credential.txt"
        external.write_bytes(self.secret)
        (self.repo / "external-link").symlink_to(external)
        self.stage("external-link")
        self.write_staged("ordinary.txt", self.clean)
        report = self.root / "probe-result"
        self.env["SECRET_GATE_PROBE_REPORT"] = str(report)
        self.fake_scanner(
            "import os\n"
            "from pathlib import Path\n"
            "import sys\n"
            "root = Path(sys.argv[-1])\n"
            "marker = (''.join(('gh', 'p', '_')) + "
            "'Q7m2V9k4R6x8T3n5B1c0D2f4H6j8L0s9W3z5').encode('ascii')\n"
            "for path in root.rglob('*'):\n"
            "    if path.is_symlink() or path.name == 'external-link':\n"
            "        sys.exit(2)\n"
            "    if path.is_file() and marker in path.read_bytes():\n"
            "        sys.exit(2)\n"
            "Path(os.environ['SECRET_GATE_PROBE_REPORT']).write_text('safe')\n"
        )
        # pre-commit filters symlinks itself; explicitly exercise the wrapper's
        # own index-mode boundary as well, with a regular file forcing a scan.
        result = self.run_command(
            "python3", "scripts/check_secrets.py", "ordinary.txt", "external-link"
        )
        self.require_success(result, "direct staged-symlink probe")
        self.assertTrue(report.exists(), "Symlink probe did not invoke scanner")
        self.assertEqual(report.read_text(), "safe")
        report.unlink()
        self.commit(allowed=True)
        self.assertTrue(report.exists(), "Commit did not invoke symlink probe scanner")
        self.assertEqual(report.read_text(), "safe")
        self.assertTrue((self.repo / "external-link").is_symlink())
        self.assertTrue(external.read_bytes() == self.secret, "External fixture was modified")

    def test_scanner_error_blocks_commit_without_leaking_either_stream(self):
        self.write_staged("ordinary.txt", self.clean)
        self.fake_scanner(
            "import sys\n"
            "marker = ''.join(('gh', 'p', '_')) + "
            "'Q7m2V9k4R6x8T3n5B1c0D2f4H6j8L0s9W3z5'\n"
            "print(marker)\n"
            "print(marker, file=sys.stderr)\n"
            "sys.exit(2)\n"
        )
        self.commit(allowed=False, message=b"could not complete the staged scan (exit 2)")

    def test_unexecutable_scanner_blocks_commit(self):
        self.write_staged("ordinary.txt", self.clean)
        scanner = self.bin / "trufflehog"
        scanner.unlink()
        scanner.write_bytes(b"invalid executable format\n")
        scanner.chmod(0o700)
        self.commit(allowed=False, message=b"unable to scan the staged snapshot safely")

    def test_missing_scanner_blocks_commit(self):
        self.write_staged("ordinary.txt", self.clean)
        (self.bin / "trufflehog").unlink()
        self.commit(allowed=False, message=b"install the managed trufflehog package first")


if __name__ == "__main__":
    unittest.main()
