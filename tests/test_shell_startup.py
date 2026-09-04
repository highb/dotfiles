"""Exercise production startup chains with temporary homes and fake integrations.

Requires chezmoi, /bin/bash (Apple Bash 3.2 on macOS), and zsh. System rc
files are disabled; loaders are sourced explicitly, not discovered implicitly.
Zsh's compiled-in global zshenv cannot be disabled, so it receives only the
fixture HOME/ZDOTDIR, which are restored before any production loader runs.
"""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "home"
STARTUP_FILES = (".bashrc", ".profile", ".zshenv", ".zshrc")
FRAGMENTS = (
    "env.sh.tmpl", "aliases.sh.tmpl", "tools.sh.tmpl",
    "bash.sh", "zsh.sh", "functions.sh", "interactive.sh",
)
TOOLS = ("mise", "direnv", "zoxide", "fzf", "atuin", "starship")


class ShellStartupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shells = {"bash": "/bin/bash"}
        for name in ("chezmoi", "zsh"):
            executable = shutil.which(name)
            if executable is None:
                raise RuntimeError(f"Shell startup tests require {name} on PATH")
            if name == "chezmoi":
                cls.chezmoi = str(Path(executable).resolve())
            else:
                cls.shells[name] = str(Path(executable).resolve())
        if not os.access(cls.shells["bash"], os.X_OK):
            raise RuntimeError("Shell startup tests require executable /bin/bash")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="shell-startup-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home with spaces"
        self.bin = self.root / "fake bin"
        self.shell_dir = self.home / ".config" / "shell"
        self.source = self.root / "source"
        self.log = self.root / "integrations.log"
        self.order_log = self.root / "startup-order.log"
        self.activated = self.root / "activated bin"
        self.fpath = self.root / "fake functions"
        self.managed = [
            self.home / "bin",
            self.home / ".local/bin",
            self.home / ".cargo/bin",
            self.home / ".local/share/JetBrains/Toolbox/scripts",
        ]
        for path in (
            self.shell_dir, self.bin, self.activated, self.fpath,
            self.source / ".chezmoidata", self.root / "cache",
            self.root / "state", self.root / "tmp",
            self.home / ".cache", self.home / ".local/state",
            *self.managed,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.env = {
            "HOME": str(self.home),
            "ZDOTDIR": str(self.home),
            "PATH": str(self.bin),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "TMPDIR": str(self.root / "tmp"),
            "HISTFILE": str(self.home / "initial.history"),
            "TERM": "dumb",
            "LANG": "C",
            "LC_ALL": "C",
            "USER": "shell-test",
            "LOGNAME": "shell-test",
            "DOTFILES_SKIP_LOCAL_INTEGRATIONS": "1",
            "SHELL_TEST_LOG": str(self.log),
            "SHELL_TEST_ORDER": str(self.order_log),
            "SHELL_TEST_ACTIVATED": str(self.activated),
        }
        shutil.copyfile(
            SOURCE / ".chezmoidata/shell.yaml",
            self.source / ".chezmoidata/shell.yaml",
        )
        config = self.root / "chezmoi.json"
        config.write_text(json.dumps({}))
        for name in STARTUP_FILES:
            shutil.copyfile(SOURCE / f"dot_{name[1:]}", self.home / name)
        for name in FRAGMENTS:
            source = SOURCE / "private_dot_config/shell" / name
            destination = self.shell_dir / name.removesuffix(".tmpl")
            if not name.endswith(".tmpl"):
                shutil.copyfile(source, destination)
                continue
            result = subprocess.run(
                [
                    self.chezmoi,
                    "--config", str(config), "--config-format", "json",
                    "--source", str(self.source),
                    "--destination", str(self.home),
                    "--cache", str(self.root / "cache"),
                    "--persistent-state", str(self.root / "state/chezmoi.boltdb"),
                    "--no-tty", "execute-template",
                ],
                input=source.read_text(), text=True, capture_output=True,
                env=self.env, cwd=self.root, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            destination.write_text(result.stdout)
        for shell in self.shells:
            # The loaders' final conditional otherwise returns 1 when absent.
            (self.home / f".{shell}rc.local").write_text(":\n")
        # Even a broken skip guard must not autoload real zsh integrations.
        for name in ("compinit", "promptinit", "prompt"):
            (self.fpath / name).write_text(
                f"printf '%s\\n' '{name}' >> \"$SHELL_TEST_LOG\"\n"
            )

    def run_shell(self, shell, body, *, interactive=True, login=False, env=None):
        child_env = dict(self.env)
        if env:
            child_env.update(env)
        child_env["SHELL"] = self.shells[shell]
        # Restore the complete allowlist after zsh's unavoidable global zshenv.
        # No host PATH, HOME, startup override, or exported function is inherited.
        prelude = "\n".join(
            f"export {name}={shlex.quote(value)}"
            for name, value in child_env.items()
        )
        if shell == "bash":
            args = [self.shells[shell], "--noprofile", "--norc"]
            if login:
                args.append("--login")
            loader = '. "$HOME/.profile"' if login else '. "$HOME/.bashrc"'
        else:
            args = [self.shells[shell], "-d", "-f"]
            if login:
                args.append("-l")
            prelude += (
                "\nunsetopt GLOBAL_RCS\n"
                f"fpath=({shlex.quote(str(self.fpath))})\n"
            )
            loader = '. "$HOME/.zshenv"\n'
            if interactive:
                loader += '. "$HOME/.zshrc"'
        if interactive:
            args.append("-i")
        result = subprocess.run(
            [*args, "-c", f"{prelude}\n{loader}\n{body}"],
            stdin=subprocess.DEVNULL, text=True, capture_output=True,
            env=child_env, cwd=self.root, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        diagnostics = result.stderr.splitlines()
        if shell == "bash" and interactive:
            diagnostics = [
                line for line in diagnostics
                if not (
                    "cannot set terminal process group" in line
                    or "no job control in this shell" in line
                )
            ]
        self.assertEqual(diagnostics, [], result.stderr)
        return result.stdout

    def state(self, shell, body, **kwargs):
        output = self.run_shell(shell, body, **kwargs)
        return dict(line.split("=", 1) for line in output.splitlines())

    def commands(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def fake_tool(self, name, *, mode="success", directory=None):
        executable = (directory or self.bin) / name
        script = (
            "#!/bin/sh\n"
            '{ printf "%s" "${0##*/}"\n'
            '  for arg do printf "\\t%s" "$arg"; done\n'
            '  printf "\\t%s\\n" "${HOOK_TRACE-}"\n'
            '} >> "$SHELL_TEST_LOG"\n'
        )
        if mode == "failure":
            script += (
                "printf '%s\\n' 'fixture hook failure' >&2\n"
                "printf '%s\\n' 'HOOK_FAILURE_EVALUATED=1'\nexit 42\n"
            )
        elif mode == "success":
            script += (
                f"printf '%s\\n' 'HOOK_TRACE=\"${{HOOK_TRACE:+${{HOOK_TRACE}}:}}{name}\"'\n"
                "printf '%s\\n' 'export HOOK_TRACE'\n"
            )
            if name == "mise":
                script += (
                    "printf '%s\\n' 'PATH=\"$SHELL_TEST_ACTIVATED:$PATH\"; export PATH'\n"
                )
            if name == "starship":
                script += "printf '%s\\n' 'PS1=fixture-prompt'\n"
        elif mode != "empty":
            raise ValueError(mode)
        executable.write_text(script)
        executable.chmod(0o700)

    def test_interactive_and_login_startup_matrix(self):
        probe = r'''
case $- in *i*) interactive=yes ;; *) interactive=no ;; esac
if alias ll >/dev/null 2>&1; then has_aliases=yes; else has_aliases=no; fi
if command -v mkcd >/dev/null 2>&1; then has_functions=yes; else has_functions=no; fi
if [ -n "${BASH_VERSION-}" ]; then
    if shopt -q login_shell; then login=yes; else login=no; fi
else
    if [[ -o login ]]; then login=yes; else login=no; fi
fi
printf 'interactive=%s\nlogin=%s\n' "$interactive" "$login"
printf 'editor=%s\naliases=%s\nfunctions=%s\n' "${EDITOR-}" "$has_aliases" "$has_functions"
printf 'home=%s\nzdotdir=%s\npath=%s\n' "$HOME" "$ZDOTDIR" "$PATH"
'''
        for shell in self.shells:
            for interactive in (False, True):
                for login in (False, True):
                    with self.subTest(shell=shell, interactive=interactive, login=login):
                        state = self.state(shell, probe, interactive=interactive, login=login)
                        has_env = shell == "zsh" or interactive or login
                        self.assertEqual(state["interactive"], "yes" if interactive else "no")
                        self.assertEqual(state["login"], "yes" if login else "no")
                        self.assertEqual(state["editor"], "nvim" if has_env else "")
                        self.assertEqual(state["aliases"], "yes" if interactive else "no")
                        self.assertEqual(state["functions"], "yes" if interactive else "no")
                        self.assertEqual(state["home"], str(self.home))
                        self.assertEqual(state["zdotdir"], str(self.home))
                        expected_path = [*self.managed, self.bin] if has_env else [self.bin]
                        self.assertEqual(state["path"].split(":"), list(map(str, expected_path)))

    def test_noninteractive_rc_guards_do_not_load_local_overrides(self):
        for shell in self.shells:
            with self.subTest(shell=shell):
                (self.home / f".{shell}rc.local").write_text("RC_LOCAL_RAN=yes\n")
                state = self.state(
                    shell,
                    f'. "$HOME/.{shell}rc"\nprintf "local=%s\\n" "${{RC_LOCAL_RAN-no}}"',
                    interactive=False,
                )
                self.assertEqual(state["local"], "no")

    def test_environment_is_exported_to_children(self):
        (self.shell_dir / "env.local.sh").write_text("export EDITOR=fixture-editor\n")
        for shell in self.shells:
            with self.subTest(shell=shell):
                state = self.state(
                    shell,
                    "/bin/sh -c 'printf \"editor=%s\\npager=%s\\nconfig=%s\\n\" "
                    '"$EDITOR" "$PAGER" "$XDG_CONFIG_HOME"\'',
                    interactive=False, login=True,
                )
                self.assertEqual(state, {
                    "editor": "fixture-editor", "pager": "less",
                    "config": str(self.home / ".config"),
                })

    def test_path_priority_is_restored_and_idempotent(self):
        first = self.root / "foreign first"
        second = self.root / "foreign second"
        system = self.root / "system bin"
        seeded = [first, self.managed[2], second, self.managed[0], self.managed[0], first]
        for shell in self.shells:
            with self.subTest(shell=shell):
                state = self.state(
                    shell,
                    'printf "first=%s\\n" "$PATH"\n'
                    f'PATH={shlex.quote(str(system))}:"$PATH"\n'
                    '. "$HOME/.config/shell/env.sh"\n'
                    'printf "second=%s\\n" "$PATH"\n'
                    '. "$HOME/.config/shell/env.sh"\n'
                    'printf "third=%s\\n" "$PATH"\n',
                    interactive=False, login=True,
                    env={"PATH": ":".join(map(str, seeded))},
                )
                self.assertEqual(state["first"].split(":"), list(map(str, [
                    *self.managed, first, second, first,
                ])))
                self.assertEqual(state["second"].split(":"), list(map(str, [
                    *self.managed, system, first, second, first,
                ])))
                self.assertEqual(state["third"], state["second"])

    def test_missing_path_directories_are_not_added(self):
        missing = self.managed[1]
        missing.rmdir()
        for shell in self.shells:
            with self.subTest(shell=shell):
                state = self.state(
                    shell, 'printf "path=%s\\n" "$PATH"',
                    interactive=False, login=True,
                )
                self.assertEqual(state["path"].split(":"), list(map(str, [
                    *(path for path in self.managed if path != missing), self.bin,
                ])))

    def test_local_environment_precedes_settings_and_rc_override_is_last(self):
        (self.shell_dir / "env.local.sh").write_text(
            'printf "env\\n" >> "$SHELL_TEST_ORDER"\n'
            'export EDITOR=early-editor\nHISTFILE="$HOME/early.history"\n'
        )
        for shell in self.shells:
            (self.home / f".{shell}rc.local").write_text(
                'printf "local\\n" >> "$SHELL_TEST_ORDER"\n'
                'printf "before_editor=%s\\nbefore_history=%s\\n" "$EDITOR" "$HISTFILE"\n'
                'alias ll >/dev/null && command -v mkcd >/dev/null || return 9\n'
                'export EDITOR=late-editor\nHISTFILE="$HOME/late.history"\n'
                "alias ll='fixture-final-alias'\n"
            )
            for login in (False, True):
                with self.subTest(shell=shell, login=login):
                    self.order_log.write_text("")
                    state = self.state(
                        shell,
                        'printf "editor=%s\\nhistory=%s\\n" "$EDITOR" "$HISTFILE"\n'
                        'printf "alias=%s\\n" "$(alias ll)"\n', login=login,
                    )
                    default_history = ".bash_history" if shell == "bash" else ".zsh_histfile"
                    self.assertEqual(state["before_editor"], "early-editor")
                    self.assertEqual(state["before_history"], str(self.home / default_history))
                    self.assertEqual(state["editor"], "late-editor")
                    self.assertEqual(state["history"], str(self.home / "late.history"))
                    self.assertIn("fixture-final-alias", state["alias"])
                    count = 2 if shell == "zsh" or login else 1
                    self.assertEqual(self.order_log.read_text().splitlines(), ["env"] * count + ["local"])

    def test_bash_vi_history_and_version_compatible_options(self):
        state = self.state("bash", r'''
[[ -o vi ]] || exit 10
shopt -q histappend && shopt -q checkwinsize && shopt -q cdspell || exit 11
if [ "${BASH_VERSINFO[0]}" -ge 4 ]; then
    shopt -q globstar || exit 12
fi
printf 'version=%s.%s\nhistory=%s\nsize=%s\ncontrol=%s\n' \
    "${BASH_VERSINFO[0]}" "${BASH_VERSINFO[1]}" "$HISTFILE" "$HISTSIZE" "$HISTCONTROL"
''')
        self.assertEqual(state["history"], str(self.home / ".bash_history"))
        self.assertEqual(state["size"], "1000000")
        self.assertEqual(state["control"], "ignoreboth:erasedups")
        if sys.platform == "darwin":
            self.assertEqual(state["version"], "3.2", "macOS must exercise native Bash 3.2")

    def test_zsh_vi_history_and_search_bindings(self):
        state = self.state("zsh", r'''
[[ -o append_history && -o share_history && -o hist_ignore_all_dups ]] || exit 10
[[ -o autocd && -o extendedglob && -o nomatch ]] || exit 11
[[ ! -o beep && ! -o notify ]] || exit 12
printf 'main=%s\nescape=%s\nup=%s\ndown=%s\n' \
    "$(bindkey -lL main)" "$(bindkey -M viins '^[')" \
    "$(bindkey '^[[A')" "$(bindkey '^[[B')"
printf 'history=%s\nsize=%s\nsave=%s\n' "$HISTFILE" "$HISTSIZE" "$SAVEHIST"
''')
        self.assertIn("viins main", state["main"])
        self.assertIn("vi-cmd-mode", state["escape"])
        self.assertIn("up-line-or-beginning-search", state["up"])
        self.assertIn("down-line-or-beginning-search", state["down"])
        self.assertEqual(state["history"], str(self.home / ".zsh_histfile"))
        self.assertEqual(state["size"], "1000000")
        self.assertEqual(state["save"], "1000000")

    def test_early_skip_policy_prevents_all_optional_integration_hooks(self):
        for name in (*TOOLS, "dircolors", "tty", "lesspipe"):
            self.fake_tool(name)
        (self.home / ".dircolors").write_text("# fixture only\n")
        (self.shell_dir / "env.local.sh").write_text(
            "export DOTFILES_SKIP_LOCAL_INTEGRATIONS=1\n"
        )
        for shell in self.shells:
            with self.subTest(shell=shell):
                self.log.write_text("")
                state = self.state(
                    shell,
                    'alias ll >/dev/null && command -v mkcd >/dev/null || exit 10\n'
                    'printf "skip=%s\\nhooks=%s\\n" "$DOTFILES_SKIP_LOCAL_INTEGRATIONS" "${HOOK_TRACE-}"',
                    env={"DOTFILES_SKIP_LOCAL_INTEGRATIONS": "0"},
                )
                self.assertEqual(state, {"skip": "1", "hooks": ""})
                self.assertEqual(self.commands(), [])

    def test_enabled_tool_hooks_evaluate_in_order_and_extend_path(self):
        for name in TOOLS:
            self.fake_tool(name, directory=self.activated if name == "direnv" else None)
        for shell in self.shells:
            with self.subTest(shell=shell):
                self.log.write_text("")
                # Enable only the rendered tool loader after isolated startup:
                # Bash distro completions must not source absolute host paths.
                state = self.state(shell, r'''
DOTFILES_SKIP_LOCAL_INTEGRATIONS=0
. "$HOME/.config/shell/tools.sh"
printf 'hooks=%s\nprompt=%s\n' "$HOOK_TRACE" "$PS1"
''')
                self.assertEqual(state, {"hooks": ":".join(TOOLS), "prompt": "fixture-prompt"})
                expected = []
                for index, name in enumerate(TOOLS):
                    args = {
                        "mise": ["activate", shell], "direnv": ["hook", shell],
                        "zoxide": ["init", shell], "fzf": [f"--{shell}"],
                        "atuin": ["init", shell], "starship": ["init", shell],
                    }[name]
                    expected.append("\t".join([name, *args, ":".join(TOOLS[:index])]))
                self.assertEqual(self.commands(), expected)

    def test_missing_failing_and_empty_tool_hooks_allow_later_hooks(self):
        self.fake_tool("mise", mode="failure")
        # direnv is deliberately absent; zoxide succeeds without emitting code.
        self.fake_tool("zoxide", mode="empty")
        self.fake_tool("fzf")
        self.fake_tool("atuin", mode="failure")
        self.fake_tool("starship")
        for shell in self.shells:
            with self.subTest(shell=shell):
                self.log.write_text("")
                state = self.state(shell, r'''
DOTFILES_SKIP_LOCAL_INTEGRATIONS=0
. "$HOME/.config/shell/tools.sh"
printf 'hooks=%s\nfailed_output=%s\nprompt=%s\n' \
    "$HOOK_TRACE" "${HOOK_FAILURE_EVALUATED-no}" "$PS1"
''')
                self.assertEqual(state, {
                    "hooks": "fzf:starship", "failed_output": "no", "prompt": "fixture-prompt",
                })
                self.assertEqual(
                    [line.split("\t")[0] for line in self.commands()],
                    ["mise", "zoxide", "fzf", "atuin", "starship"],
                )

    def test_all_missing_tool_hooks_leave_fallback_prompt_intact(self):
        for shell in self.shells:
            with self.subTest(shell=shell):
                state = self.state(shell, r'''
before=$PS1
DOTFILES_SKIP_LOCAL_INTEGRATIONS=0
. "$HOME/.config/shell/tools.sh"
[ "$PS1" = "$before" ] || exit 10
printf 'alive=yes\nhooks=%s\n' "${HOOK_TRACE-}"
''')
                self.assertEqual(state, {"alive": "yes", "hooks": ""})
                self.assertEqual(self.commands(), [])


if __name__ == "__main__":
    unittest.main()
