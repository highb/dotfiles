"""Bootstrap consent tests using only isolated, logging fake backends."""

from pathlib import Path
import subprocess
import tempfile
import unittest


BOOTSTRAP = Path(__file__).resolve().parents[1] / "bootstrap.sh"


class BootstrapConsentTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="bootstrap-consent-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.source = self.root / "source"
        self.log = self.root / "commands.log"
        self.ready = self.root / "chezmoi-ready"
        self.script = self.root / "bootstrap.sh"
        self.script.write_text(BOOTSTRAP.read_text())
        for name in ("home", "bin", "source", "config", "cache", "data", "state", "tmp"):
            (self.root / name).mkdir()
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.bin),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "TMPDIR": str(self.root / "tmp"),
            "LANG": "C",
            "LC_ALL": "C",
            "BOOTSTRAP_TEST_LOG": str(self.log),
            "BOOTSTRAP_TEST_BIN": str(self.bin),
            "BOOTSTRAP_TEST_SOURCE": str(self.source),
            "BOOTSTRAP_TEST_READY": str(self.ready),
        }
        fake = '''#!/bin/sh
name=${0##*/}
{
    printf '%s\t%s' "$name" "${DOTFILES_INSTALL_PACKAGES:-}"
    for arg do printf '\t%s' "$arg"; done
    printf '\n'
} >> "$BOOTSTRAP_TEST_LOG"
case "$name:$1" in
    mise:--version) printf 'mise-test\n' ;;
    mise:which)
        [ -f "$BOOTSTRAP_TEST_READY" ] || exit 1
        printf '%s/chezmoi\n' "$BOOTSTRAP_TEST_BIN"
        ;;
    mise:use) : > "$BOOTSTRAP_TEST_READY" ;;
    chezmoi:source-path) printf '%s\n' "$BOOTSTRAP_TEST_SOURCE" ;;
    cat:*|head:*)
        while IFS= read -r line; do printf '%s\n' "$line"; done
        ;;
    curl:*) exit 90 ;; # No network, even if a future bootstrap path calls curl.
esac
'''
        for name in ("curl", "git", "mise", "chezmoi", "cargo", "cat", "head", "brew"):
            executable = self.bin / name
            executable.write_text(fake)
            executable.chmod(0o700)

    def run_bootstrap(self, consent=None, *, legacy=False):
        env = dict(self.env)
        if consent is not None:
            env["DOTFILES_INSTALL_PACKAGES"] = consent
        if legacy:
            env["METAPAC_AUTOSYNC"] = "1"
        return subprocess.run(
            ["/bin/sh", str(self.script)],
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            env=env,
            cwd=self.root,
            timeout=30,
        )

    def commands(self):
        if not self.log.exists():
            return []
        return [line.split("\t") for line in self.log.read_text().splitlines()]

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()
        }

    def test_default_invalid_and_retired_consent_do_not_run_commands_or_mutate(self):
        before = self.snapshot()
        for consent in (None, "", "0", "true", "yes", "01", "1 ", "1\n"):
            for legacy in (False, True):
                with self.subTest(consent=consent, legacy=legacy):
                    result = self.run_bootstrap(consent, legacy=legacy)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("DOTFILES_INSTALL_PACKAGES=1 sh bootstrap.sh", result.stderr)
                    self.assertEqual(self.commands(), [])
                    self.assertEqual(self.snapshot(), before)

    def test_explicit_consent_runs_fake_installers_and_preserves_provider_commands(self):
        result = self.run_bootstrap("1")
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.commands()
        self.assertIn(["mise", "1", "use", "--global", "chezmoi@latest"], commands)
        self.assertIn(["chezmoi", "1", "apply"], commands)
        self.assertIn(["cargo", "1", "install", "metapac", "--locked"], commands)
        self.assertTrue(all(command[1] == "1" for command in commands))
        self.assertFalse(any(command[0] in ("curl", "brew") for command in commands))
        self.assertIn("DOTFILES_INSTALL_PACKAGES=1 chezmoi apply", result.stdout)
        self.assertIn("machine.manualProvisioning", result.stdout)

    def test_opt_in_preserves_prerequisite_refusal_without_system_install(self):
        (self.bin / "git").unlink()
        result = self.run_bootstrap("1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("brew install git", result.stderr)
        self.assertEqual(self.commands(), [])
        self.assertFalse(self.ready.exists())


if __name__ == "__main__":
    unittest.main()
