"""Exercise the Bash wizard with a terminal and isolated chezmoi config."""
import json
import os
from pathlib import Path
import pty
import select
import shutil
import tempfile
import time
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WizardTest(unittest.TestCase):
    def test_wizard_preserves_config_and_requires_confirmation(self):
        for suffix, initial in (
            ('toml', None),
            ('json', '{"data":{"machine":{"packageExcludes":["git"],"manualProvisioning":true}}}'),
            ('toml', '[data.machine]\npackageExcludes = ["git"]\nmanualProvisioning = true\n'),
            ('json', 'APPROVE'),
            ('yaml', 'data:\n  machine:\n    packageExcludes: [git]\n    manualProvisioning: true\n'),
        ):
            with self.subTest(format=suffix), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = root / f'chezmoi.{suffix}'
                approve = initial == "APPROVE"
                if approve:
                    initial = '{"data":{"machine":{"packageExcludes":["git"],"manualProvisioning":true}}}'
                if initial is not None:
                    config.write_text(initial)
                wrapper = root / 'chezmoi'
                executable = shutil.which('chezmoi')
                wrapper.write_text(f'#!/bin/sh\nif [ \"$1\" = apply ]; then printf \"%s\" \"$DOTFILES_INSTALL_PACKAGES\" > \"{root / "applied"}\"; exit; fi\nexec "{executable}" --config "{config}" --source "{ROOT / "home"}" --destination "{root / "home"}" --persistent-state "{root / "state"}" "$@"\n')
                wrapper.chmod(0o700)
                env = dict(os.environ, HOME=str(root), CHEZMOI=str(wrapper))
                env.pop('DOTFILES_INSTALL_PACKAGES', None)
                pid, master = pty.fork()
                if pid == 0:
                    os.execve('/bin/bash', ['bash', str(ROOT / 'scripts/configure.sh')], env)
                output = b''
                os.write(master, (b'n\n' * 6 + b'y\nn\ny\n') if approve else b'n\n' * 9)
                deadline = time.monotonic() + 20
                status = None
                try:
                    while time.monotonic() < deadline:
                        if select.select([master], [], [], .1)[0]:
                            try:
                                output += os.read(master, 65536)
                            except OSError:
                                break
                        child, status = os.waitpid(pid, os.WNOHANG)
                        if child:
                            break
                    else:
                        os.kill(pid, 9)
                        self.fail('Wizard timed out: ' + output.decode())
                    if status is None or child == 0:
                        _, status = os.waitpid(pid, 0)
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0, output.decode())
                finally:
                    os.close(master)
                if suffix == 'json':
                    data = json.loads(config.read_text())
                elif suffix == 'toml':
                    data = tomllib.loads(config.read_text())
                else:
                    # Use chezmoi's parser so the test needs no YAML library.
                    import subprocess
                    data = json.loads(subprocess.check_output([str(wrapper), '--no-tty', 'execute-template', '{{ .machine | toJson }}'], env=env, text=True))
                    data = {'data': {'machine': data}}
                machine = data['data']['machine']
                self.assertEqual(machine['packageGroups'], ['shell'] if approve else [])
                if initial is not None:
                    self.assertEqual(machine['packageExcludes'], ['git'])
                    self.assertTrue(machine['manualProvisioning'])
                if approve:
                    self.assertEqual((root / 'applied').read_text(), '1')
                else:
                    self.assertIn(b'installation skipped', output)
                    self.assertFalse((root / 'applied').exists())
                self.assertFalse((root / 'home').exists())
