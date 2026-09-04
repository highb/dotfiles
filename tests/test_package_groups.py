"""Package policy integration tests; requires Python 3.11+ and chezmoi on PATH.

Run with: python3 -m unittest discover -s tests -v
Production package data, partials, and hooks are copied. Every subprocess has a
temporary HOME, config, cache, state, and a PATH of logging fake package managers.
"""

import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import tomllib
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "home"
TEMPLATES = {
    "group": "private_dot_config/metapac/groups/dotfiles.toml.tmpl",
    "config": "private_dot_config/metapac/config.toml.tmpl",
    "binaries": "private_dot_config/metapac/binaries.json.tmpl",
    "direct": "run_onchange_after_10-mise-direct.sh.tmpl",
    "sync": "run_onchange_after_20-metapac-sync.sh.tmpl",
}
PARTIALS = (
    "package-selection",
    "package-resolution",
    "metapac-platform",
    "metapac-backends",
    "toml-value",
)
BACKENDS = ("mise", "brew", "cargo")


class PackageGroupsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executable = shutil.which("chezmoi")
        if executable is None:
            raise RuntimeError("Package group integration tests require chezmoi on PATH")
        cls.chezmoi = str(Path(executable).resolve())
        cls.templates = {
            name: (SOURCE / path).read_text() for name, path in TEMPLATES.items()
        }

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="package-groups-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.log = self.root / "commands.log"
        self.config = self.root / "chezmoi.json"
        for path in (
            self.source / ".chezmoidata",
            self.source / ".chezmoitemplates",
            self.home,
            self.bin,
            self.root / "cache",
            self.root / "config",
            self.root / "data",
            self.root / "state",
            self.root / "tmp",
        ):
            path.mkdir(parents=True, exist_ok=True)
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
            "PACKAGE_TEST_LOG": str(self.log),
        }
        for name in PARTIALS:
            shutil.copyfile(
                SOURCE / ".chezmoitemplates" / name,
                self.source / ".chezmoitemplates" / name,
            )
        inventory = self.source / ".chezmoidata" / "packages.yaml"
        shutil.copyfile(SOURCE / ".chezmoidata" / "packages.yaml", inventory)
        self.policy()
        # Let chezmoi parse the real YAML; no third-party Python YAML dependency.
        self.packages = json.loads(self.render_text("{{ .packages | toJson }}"))
        inventory.unlink()
        # Preserve the production inventory and groups, but remove host-dependent
        # package-manager availability and probes from the test fixture.
        self.packages["provider_priority"] = {
            platform: list(BACKENDS)
            for platform in self.packages["provider_priority"]
        }
        self.packages["backend_probe"] = {}
        (self.source / ".chezmoidata" / "packages.json").write_text(
            json.dumps({"packages": self.packages})
        )
        for name in (*BACKENDS, "metapac"):
            executable = self.bin / name
            executable.write_text(
                '#!/bin/sh\n'
                '{\n'
                '  printf "%s" "${0##*/}"\n'
                '  for arg do printf "\\t%s" "$arg"; done\n'
                '  printf "\\n"\n'
                '} >> "$PACKAGE_TEST_LOG"\n'
            )
            executable.chmod(0o700)
        (self.bin / "sh").symlink_to("/bin/sh")

    def policy(self, **machine):
        self.config.write_text(json.dumps({"data": {"machine": machine}}))

    def run_chezmoi(self, *args, input=None):
        return subprocess.run(
            [
                self.chezmoi,
                "--config", str(self.config),
                "--config-format", "json",
                "--source", str(self.source),
                "--destination", str(self.home),
                "--cache", str(self.root / "cache"),
                "--persistent-state", str(self.root / "state" / "chezmoi.boltdb"),
                "--no-tty",
                *args,
            ],
            input=input,
            text=True,
            capture_output=True,
            env=self.env,
            cwd=self.root,
            timeout=30,
        )

    def execute_template(self, template):
        return self.run_chezmoi("execute-template", input=template)

    def render_text(self, template):
        result = self.execute_template(template)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def render(self, name):
        return self.render_text(self.templates[name])

    def manifests(self):
        return (
            tomllib.loads(self.render("group")),
            json.loads(self.render("binaries")),
            tomllib.loads(self.render("config")),
        )

    def run_hook(self, name, *, consent=None, legacy=False, tty=False):
        self.log.write_text("")
        script = self.root / f"{name}.sh"
        script.write_text(self.render(name))
        env = dict(self.env)
        env.pop("DOTFILES_INSTALL_PACKAGES", None)
        if consent is not None:
            env["DOTFILES_INSTALL_PACKAGES"] = consent
        if legacy:
            env["METAPAC_AUTOSYNC"] = "1"
        if tty:
            master, terminal = pty.openpty()
            self.addCleanup(os.close, master)
            self.addCleanup(os.close, terminal)
        result = subprocess.run(
            ["/bin/sh", str(script)],
            stdin=terminal if tty else subprocess.DEVNULL,
            stdout=terminal if tty else subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=self.root,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.commands()
        return commands, result

    def commands(self):
        if not self.log.exists():
            return []
        return [line.split("\t") for line in self.log.read_text().splitlines()]

    @staticmethod
    def requests(group):
        return [
            (backend, package["name"])
            for backend, manifest in group.items()
            for package in manifest["packages"]
        ]

    def direct_commands(self, tools):
        return [
            ["mise", "use", "--global", "--quiet", f'{tool["providers"]["mise"]["name"]}@latest']
            for _, tool in sorted(tools.items())
            if tool["status"] == "mise-direct"
        ]

    def test_omitted_equals_all_and_groups_cover_installable_inventory(self):
        inventory = self.packages["tools"]
        installable = {
            name for name, tool in inventory.items()
            if tool["status"] in ("active", "mise-direct")
        }
        members = set().union(*map(set, self.packages["groups"].values()))
        self.assertEqual(members, installable)
        omitted = self.manifests()
        direct, _ = self.run_hook("direct", consent="1")
        self.assertEqual(direct, self.direct_commands(inventory))
        expected_resolvable = {
            name for name, tool in inventory.items()
            if tool["status"] == "active"
            and set(tool["providers"]).intersection(BACKENDS)
        }
        self.assertEqual(set(omitted[1]), expected_resolvable)
        self.assertEqual(len(self.requests(omitted[0])), len(expected_resolvable))
        self.policy(packageGroups=list(self.packages["groups"]))
        self.assertEqual(self.manifests(), omitted)
        self.assertEqual(self.run_hook("direct", consent="1")[0], direct)

    def test_empty_selection_requests_and_installs_nothing(self):
        self.policy(packageGroups=[])
        group, binaries, _ = self.manifests()
        self.assertEqual(group, {})
        self.assertEqual(binaries, {})
        for name in ("direct", "sync"):
            for consent in (None, "1"):
                with self.subTest(hook=name, consent=consent):
                    self.assertEqual(self.run_hook(name, consent=consent)[0], [])

    def test_writing_selects_only_writing_packages_and_direct_commands(self):
        self.policy(packageGroups=["writing"])
        group, binaries, _ = self.manifests()
        self.assertCountEqual(
            self.requests(group), [("mise", "hugo"), ("mise", "node"), ("mise", "zola")]
        )
        self.assertEqual(binaries, {"hugo": "hugo", "node": "node", "zola": "zola"})
        self.assertEqual(self.run_hook("direct", consent="1")[0], [
            ["mise", "use", "--global", "--quiet", "npm:markdownlint-cli@latest"],
            ["mise", "use", "--global", "--quiet", "npm:prettier@latest"],
        ])

    def test_overlapping_and_repeated_groups_are_a_union(self):
        individual = []
        for group in ("writing", "development"):
            self.policy(packageGroups=[group])
            individual.append(self.manifests())
        self.policy(packageGroups=["writing", "development", "writing"])
        group, binaries, _ = self.manifests()
        expected = set(self.requests(individual[0][0])) | set(self.requests(individual[1][0]))
        self.assertCountEqual(self.requests(group), expected)
        self.assertEqual(binaries, individual[0][1] | individual[1][1])
        self.assertEqual(self.requests(group).count(("mise", "node")), 1)
        self.assertEqual(len(self.run_hook("direct", consent="1")[0]), 2)
        self.policy(packageGroups=["development", "writing"])
        self.assertEqual(self.manifests()[:2], (group, binaries))

    def test_excludes_and_authoritative_providers_apply_to_both_manifests(self):
        self.policy(packageGroups=["core", "shell"])
        default_group, default_binaries, _ = self.manifests()
        self.assertIn(("mise", "ripgrep"), self.requests(default_group))
        self.assertEqual(default_binaries["ripgrep"], "rg")
        self.policy(
            packageGroups=["core", "shell", "writing"],
            packageExcludes=["age", "direnv", "prettier"],
            packageProviders={"ripgrep": "brew", "fzf": "brew", "age": "mise", "kubectl": "brew"},
        )
        group, binaries, _ = self.manifests()
        requests = self.requests(group)
        for name in ("ripgrep", "fzf"):
            self.assertIn(("brew", name), requests)
            self.assertNotIn(("mise", name), requests)
            self.assertEqual(binaries[name], name)
        for name in ("age", "direnv", "kubectl"):
            self.assertNotIn(name, binaries)
            self.assertNotIn(name, [name for _, name in requests])
        self.assertEqual(self.run_hook("direct", consent="1")[0], [
            ["mise", "use", "--global", "--quiet", "npm:markdownlint-cli@latest"]
        ])

    def test_invalid_group_values_reject_every_consumer(self):
        for value in (["not-a-group"], None, "writing", {"writing": True}, ["writing", 1]):
            self.policy(packageGroups=value)
            for consumer, template in self.templates.items():
                with self.subTest(selection=value, consumer=consumer):
                    result = self.execute_template(template)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("machine.packageGroups", result.stderr)
        self.assertFalse(self.log.exists(), "Rendering must not execute package managers")

    def test_unavailable_override_never_falls_back_and_inactive_tools_stay_absent(self):
        inactive = {
            name: tool for name, tool in self.packages["tools"].items()
            if tool["status"] not in ("active", "mise-direct")
        }
        # Membership must not reactivate a retired or superseded tool.
        self.packages["groups"]["core"].extend(inactive)
        (self.source / ".chezmoidata" / "packages.json").write_text(
            json.dumps({"packages": self.packages})
        )
        self.policy(packageProviders={"ripgrep": "apt", "zola": "cargo"})
        group, binaries, _ = self.manifests()
        requests = self.requests(group)
        for name in ("ripgrep", "zola"):
            self.assertNotIn(name, binaries)
            self.assertNotIn(name, [name for _, name in requests])
        direct, _ = self.run_hook("direct", consent="1")
        self.assertTrue(inactive, "Fixture must retain inactive production inventory")
        self.assertTrue(set(inactive).isdisjoint(binaries))
        for tool in inactive.values():
            for backend, spec in tool["providers"].items():
                self.assertNotIn((backend, spec["name"]), requests)
                self.assertNotIn(
                    ["mise", "use", "--global", "--quiet", f'{spec["name"]}@latest'], direct
                )
        resolution = json.loads(self.render_text('{{ includeTemplate "package-resolution" . }}'))
        self.assertTrue({"ripgrep", "zola"}.issubset(resolution["unresolved"]))
        self.assertTrue(set(inactive).isdisjoint(resolution["unresolved"]))

    def test_provider_options_survive_toml_serialization(self):
        self.policy(packageGroups=["writing", "development", "core"])
        group, _, config = self.manifests()
        packages = {
            (backend, entry["name"]): entry
            for backend, manifest in group.items()
            for entry in manifest["packages"]
        }
        self.assertEqual(packages["mise", "hugo"]["options"], {"version": "0.155.1"})
        self.assertEqual(packages["cargo", "kickstart"]["options"], {"features": ["cli"], "locked": True})
        self.assertEqual(packages["cargo", "metapac"]["options"], {"locked": True})
        self.assertIs(config["cargo"]["locked"], True)

    def test_sync_tracks_selection_and_requires_explicit_consent(self):
        self.policy(packageGroups=["writing"])
        writing = self.render("sync")
        self.policy(packageGroups=[])
        self.assertNotEqual(self.render("sync"), writing)
        self.policy(packageGroups=["writing"], packageExcludes=["zola"])
        self.assertNotEqual(self.render("sync"), writing)
        self.policy(packageGroups=["writing"], packageProviders={"zola": "brew"})
        self.assertNotEqual(self.render("sync"), writing)
        commands, result = self.run_hook("sync")
        self.assertEqual(commands, [])
        self.assertIn("DOTFILES_INSTALL_PACKAGES=1 chezmoi apply", result.stderr)
        commands, _ = self.run_hook("sync", consent="1")
        self.assertEqual(commands, [[
            "metapac", "--config-dir", str(self.root / "config" / "metapac"), "sync", "--no-confirm"
        ]])

    def test_no_backend_is_an_empty_list_not_an_empty_backend_name(self):
        for backend in BACKENDS:
            (self.bin / backend).unlink()
        group, binaries, config = self.manifests()
        self.assertEqual(config["enabled_backends"], [])
        self.assertEqual(group, {})
        self.assertEqual(binaries, {})
        resolution = json.loads(self.render_text('{{ includeTemplate "package-resolution" . }}'))
        self.assertEqual(resolution["enabled"], [])
        self.assertTrue(resolution["unresolved"])

    def test_hooks_require_exact_runtime_consent_even_with_tty(self):
        self.policy(packageGroups=["writing"])
        # A previously authorized rendering must still refuse without runtime
        # consent. Neither arbitrary values nor the retired variable authorize.
        self.env["DOTFILES_INSTALL_PACKAGES"] = "1"
        for name in ("direct", "sync"):
            for consent in (None, "", "0", "true", "yes", "01", "1 ", "1\n"):
                for tty in (False, True):
                    with self.subTest(hook=name, consent=consent, tty=tty):
                        commands, result = self.run_hook(
                            name, consent=consent, legacy=True, tty=tty
                        )
                        self.assertEqual(commands, [])
                        self.assertIn(
                            "DOTFILES_INSTALL_PACKAGES=1 chezmoi apply", result.stderr
                        )
            for tty in (False, True):
                with self.subTest(hook=name, consent="1", tty=tty):
                    commands, _ = self.run_hook(name, consent="1", tty=tty)
                    self.assertTrue(commands)
                    if name == "sync":
                        self.assertEqual(commands[0][-1], "--no-confirm")

    def test_excluding_every_selected_package_invokes_no_installers(self):
        self.policy(
            packageGroups=["writing"],
            packageExcludes=self.packages["groups"]["writing"],
        )
        for name in ("direct", "sync"):
            with self.subTest(hook=name):
                self.assertEqual(self.run_hook(name, consent="1")[0], [])

    def test_apply_skip_then_opt_in_runs_actual_onchange_hooks(self):
        self.policy(packageGroups=["writing"])
        for name in ("direct", "sync"):
            shutil.copyfile(SOURCE / TEMPLATES[name], self.source / TEMPLATES[name])
        expected = [
            ["mise", "use", "--global", "--quiet", "npm:markdownlint-cli@latest"],
            ["mise", "use", "--global", "--quiet", "npm:prettier@latest"],
            ["metapac", "--config-dir", str(self.root / "config" / "metapac"),
             "sync", "--no-confirm"],
        ]
        # Real persistent script state, unchanged source, and only the consent
        # environment transition may cause the skipped hooks to execute again.
        for consent, installations in (
            (None, 0), ("1", 1), ("1", 1), (None, 1), ("1", 2),
        ):
            with self.subTest(consent=consent, installations=installations):
                if consent is None:
                    self.env.pop("DOTFILES_INSTALL_PACKAGES", None)
                else:
                    self.env["DOTFILES_INSTALL_PACKAGES"] = consent
                result = self.run_chezmoi("apply")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.commands(), expected * installations)


if __name__ == "__main__":
    unittest.main()
