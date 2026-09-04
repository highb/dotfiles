"""Exercise task/platform deployment with real chezmoi and isolated homes."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "home"


class DeploymentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executable = shutil.which("chezmoi")
        if executable is None:
            raise RuntimeError("Deployment tests require chezmoi on PATH")
        cls.chezmoi = str(Path(executable).resolve())

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dotfiles-deployment-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.home = self.root / "home"
        self.config = self.root / "chezmoi.json"
        self.source.mkdir()
        self.home.mkdir()
        (self.root / "bin").mkdir()
        for entry in (
            ".chezmoiignore", ".chezmoidata", ".chezmoitemplates",
            "dot_bashrc", "dot_zshrc", "dot_profile", "dot_zshenv",
            "dot_gitconfig.tmpl", "private_dot_config", "private_dot_local", "bin",
            "run_onchange_after_10-mise-direct.sh.tmpl",
            "run_onchange_after_20-metapac-sync.sh.tmpl",
        ):
            original = SOURCE / entry
            target = self.source / entry
            if original.is_dir():
                shutil.copytree(original, target)
            else:
                shutil.copyfile(original, target)
        self.config.write_text("{}\n")
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.root / "bin"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "LANG": "C",
            "LC_ALL": "C",
        }
        self.policy = {"chezmoi": {"os": "darwin"}, "machine": {}}

    def command(self, *args):
        result = subprocess.run(
            [
                self.chezmoi,
                "--source", str(self.source),
                "--destination", str(self.home),
                "--config", str(self.config),
                "--config-format", "json",
                "--cache", str(self.root / "cache"),
                "--persistent-state", str(self.root / "state.boltdb"),
                "--override-data", json.dumps(self.policy),
                "--no-tty", *args,
            ],
            env=self.env, cwd=self.root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def targets(self, groups=None, *, platform="darwin", **machine):
        if groups is not None:
            machine["packageGroups"] = groups
        self.policy = {"chezmoi": {"os": platform}, "machine": machine}
        return set(self.command("managed", "--include=files").splitlines())

    def test_minimal_host_gets_complete_shell_without_development_or_desktop(self):
        targets = self.targets(["core", "shell"], platform="linux")
        self.assertTrue({
            ".bashrc", ".zshrc", ".profile", ".zshenv", ".gitconfig",
            ".config/shell/env.sh", ".config/shell/tools.sh",
            ".config/shell/bash.sh", ".config/shell/zsh.sh", ".config/starship.toml",
        }.issubset(targets))
        self.assertFalse(any(path.startswith((".config/nvim/", ".config/ghostty/")) for path in targets))
        self.assertTrue({"bin/scaffold", "bin/audio_fix.sh", "bin/gnome_toggle_dark_mode.sh"}.isdisjoint(targets))

    def test_development_and_writing_keep_their_dependency_bundles(self):
        development = self.targets(["development"])
        self.assertTrue({
            ".gitconfig", ".config/git/allowed_signers", ".config/nvim/init.lua",
            ".config/nvim/lazy-lock.json", "bin/all_pull.sh", "bin/gh_clone_all.sh",
            "bin/scaffold", ".local/share/scaffold/templates/hugo/template.toml",
        }.issubset(development))
        writing = self.targets(["writing"])
        self.assertIn("bin/scaffold", writing)
        templates = {path for path in development if path.startswith(".local/share/scaffold/")}
        self.assertTrue(templates.issubset(writing))
        self.assertNotIn(".config/nvim/init.lua", writing)
        self.assertNotIn(".gitconfig", writing)

    def test_desktop_helpers_require_both_linux_and_desktop_task(self):
        linux = self.targets(["desktop"], platform="linux")
        macos = self.targets(["desktop"], platform="darwin")
        helpers = {"bin/audio_fix.sh", "bin/gnome_toggle_dark_mode.sh"}
        self.assertTrue(helpers.issubset(linux))
        self.assertTrue(helpers.isdisjoint(macos))
        self.assertIn(".config/ghostty/config", linux)
        self.assertIn(".config/ghostty/config", macos)
        self.assertTrue(helpers.isdisjoint(self.targets(["shell"], platform="linux")))

    def test_empty_tasks_keep_package_control_but_no_task_configs(self):
        targets = self.targets([])
        self.assertTrue({
            ".config/metapac/config.toml", ".config/metapac/groups/dotfiles.toml",
            ".config/metapac/binaries.json", "bin/pkg-doctor",
        }.issubset(targets))
        self.assertTrue({".bashrc", ".zshrc", ".profile", ".zshenv", ".gitconfig", "bin/scaffold"}.isdisjoint(targets))
        self.assertFalse(any(path.startswith((".config/nvim/", ".config/shell/", ".config/ghostty/")) for path in targets))

    def test_package_exclusions_do_not_disable_config_for_external_tools(self):
        normal = self.targets(["core", "shell", "development", "desktop"])
        external = self.targets(
            ["core", "shell", "development", "desktop"],
            packageExcludes=["git", "starship", "ghostty", "vim"],
        )
        self.assertEqual(external, normal)
        self.assertIn(".gitconfig", external)
        self.assertIn(".config/starship.toml", external)
        self.assertIn(".config/ghostty/config", external)

    def test_default_selection_retains_all_applicable_bundles(self):
        targets = self.targets()
        self.assertTrue({
            ".zshrc", ".gitconfig", ".config/nvim/init.lua",
            ".config/ghostty/config", "bin/scaffold",
        }.issubset(targets))
        self.assertNotIn("bin/audio_fix.sh", targets)

    def test_apply_preserves_deselected_files_and_local_overrides(self):
        existing = self.home / ".config/nvim/init.lua"
        existing.parent.mkdir(parents=True)
        existing.write_text("-- preserve existing editor configuration\n")
        override = self.home / ".zshrc.local"
        override.write_text("# preserve local override\n")
        self.targets(["core", "shell"], manualProvisioning=True)
        self.command("apply", "--include=files,dirs")
        self.assertEqual(existing.read_text(), "-- preserve existing editor configuration\n")
        self.assertEqual(override.read_text(), "# preserve local override\n")
        self.assertTrue((self.home / ".zshrc").is_file())
        self.assertTrue((self.home / ".config/shell/env.sh").is_file())
        self.assertFalse((self.home / ".config/ghostty").exists())
        self.assertFalse((self.home / "bin/scaffold").exists())

    def test_manual_provisioning_excludes_hooks_even_with_install_opt_in(self):
        self.env["DOTFILES_INSTALL_PACKAGES"] = "1"
        self.targets(["writing"], manualProvisioning=True)
        self.assertEqual(self.command("managed", "--include=scripts").strip(), "")
        self.targets(["writing"], manualProvisioning=False)
        scripts = set(self.command("managed", "--include=scripts").splitlines())
        self.assertEqual(scripts, {"10-mise-direct.sh", "20-metapac-sync.sh"})


if __name__ == "__main__":
    unittest.main()
