"""Native vendor provisioning: render real helpers, execute only isolated fakes."""
import json
import os
import pty
import subprocess
import unittest

import test_package_groups as package_fixture
from test_package_groups import SOURCE


class VendorProvisioningTest(unittest.TestCase):
    setUpClass = classmethod(package_fixture.PackageGroupsTest.setUpClass.__func__)
    policy = package_fixture.PackageGroupsTest.policy
    run_chezmoi = package_fixture.PackageGroupsTest.run_chezmoi
    execute_template = package_fixture.PackageGroupsTest.execute_template
    render_text = package_fixture.PackageGroupsTest.render_text
    # Reuse the isolated fixture without inheriting the package policy test suite.
    def setUp(self):
        package_fixture.PackageGroupsTest.setUp(self)
        self.template = (SOURCE / 'run_onchange_after_16-1password-vendor.sh.tmpl').read_text()
        self.state = self.root / 'installed'
        self.env['VENDOR_STATE'] = str(self.state)
        self.env['TEST_FINGERPRINT'] = '3FEF9748469ADBE15DA7CA80AC2D62742012EA22'
        self.env['TEST_CERT'] = '14 1D D8 7B 2B 23 12 11 F1 44 08 49 79 80 07 DF 62 1D E6 EB 3D AB 98 5B C9 64 EE 97 04 C4 A1 C1'
        # Only ordinary file utilities reach the real system. No real installer,
        # package manager, network client or privilege escalation is on PATH.
        for name in ('uname', 'mktemp', 'rm', 'mkdir', 'awk', 'grep', 'tr', 'cmp', 'install'):
            (self.bin / name).symlink_to('/usr/bin/' + name)
        self.fake('uname', 'echo "${TEST_ARCH:-x86_64}"')
        self.fake('curl', 'echo curl >> "$PACKAGE_TEST_LOG"; while [ "$#" -gt 0 ]; do if [ "$1" = -o ]; then echo artifact > "$2"; exit; fi; shift; done')
        self.fake('gpg', 'echo pub:; printf "fpr:::::::::%s:\\n" "$TEST_FINGERPRINT"')
        self.fake('pkgutil', 'echo pkgutil >> "$PACKAGE_TEST_LOG"; echo "Developer ID Installer: ${TEST_IDENTITY:-AgileBits Inc. (2BUA8C4S2C)}"; echo "$TEST_CERT"; exit "${TEST_VERIFY_EXIT:-0}"')
        self.fake('spctl', 'echo spctl >> "$PACKAGE_TEST_LOG"; exit "${TEST_GATEKEEPER_EXIT:-0}"')
        self.fake('installer', ':')
        self.fake('rpm', 'case "$1" in -q) [ -f "$VENDOR_STATE" ];; *) echo "rpm $*" >> "$PACKAGE_TEST_LOG"; case "$*" in *--checksig*) echo "${TEST_RPM_SIGNATURE:-Header V4 RSA/SHA256 Signature, key ID 2012ea22: OK}"; exit "${TEST_RPM_VERIFY_EXIT:-0}";; esac;; esac')
        self.fake('dnf', ':')
        self.fake('sudo', 'echo "sudo $*" >> "$PACKAGE_TEST_LOG"; case "$1" in install) "$@";; installer|dnf|rpm-ostree) touch "$VENDOR_STATE";; esac')
        (self.bin / 'touch').symlink_to('/usr/bin/touch')
        self.platform('darwin')

    def fake(self, name, body):
        path = self.bin / name
        if path.is_symlink():
            path.unlink()
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o700)

    def platform(self, name, **machine):
        os_data = {'os': 'darwin' if name == 'darwin' else 'linux',
                   'osRelease': {'id': name, 'idLike': 'fedora'}}
        self.config.write_text(json.dumps({'data': {'machine': {'packageGroups': ['desktop'], **machine}, 'chezmoi': os_data}}))
        self.os_data = os_data

    def rendered(self, text=None):
        # `fromJson` creates the same scope used by the production helpers.
        encoded = json.dumps(json.dumps(self.os_data))
        return self.render_text('{{ $ctx := mergeOverwrite (dict) . (dict "chezmoi" (' + encoded + ' | fromJson)) }}{{ with $ctx }}' + (text or self.template) + '{{ end }}')

    def run_vendor(self, consent='1'):
        script = self.root / 'vendor.sh'
        rendered = self.rendered()
        for path in ('/etc/yum.repos.d', '/etc/pki/rpm-gpg', '/Applications', '/usr/local/bin/op'):
            rendered = rendered.replace(path, str(self.root / path.lstrip('/')))
        script.write_text(rendered)
        env = dict(self.env, DOTFILES_INSTALL_PACKAGES=consent)
        result = subprocess.run(['/bin/sh', str(script)], env=env, text=True, capture_output=True, timeout=10)
        return result, self.log.read_text() if self.log.exists() else ''

    def test_platforms_and_preview(self):
        for platform in ('darwin', 'fedora', 'rhel', 'bazzite', 'bluefin', 'aurora'):
            with self.subTest(platform=platform):
                self.platform(platform)
                result = json.loads(self.rendered('{{ includeTemplate "package-resolution" . }}'))
                self.assertEqual(len(result['assigned']['1password-vendor']), 2)
                self.assertNotIn('1password-vendor', result['enabled'])
                plan = self.rendered('{{ includeTemplate "package-plan" . }}')
                self.assertIn('vendor PKG' if platform == 'darwin' else 'via DNF', plan)
        self.platform('arch')
        result, log = self.run_vendor()
        self.assertIn('unsupported platform', result.stderr)
        self.assertNotIn('sudo', log)

    def test_mac_fail_closed(self):
        for key, value in (('TEST_CERT', 'BAD'), ('TEST_IDENTITY', 'Other Inc.'), ('TEST_VERIFY_EXIT', '1'), ('TEST_GATEKEEPER_EXIT', '1')):
            with self.subTest(check=key):
                self.log.write_text('')
                previous = self.env.get(key)
                self.env[key] = value
                result, log = self.run_vendor()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('sudo', log)
                if previous is None:
                    self.env.pop(key)
                else:
                    self.env[key] = previous

    def test_second_pkg_failure_prevents_both_installs(self):
        self.fake('pkgutil', 'case "$2" in *1password-cli.pkg) exit 1;; esac; echo "Developer ID Installer: AgileBits Inc. (2BUA8C4S2C)"; echo "$TEST_CERT"')
        result, log = self.run_vendor()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(log.count('curl'), 2)
        self.assertNotIn('sudo', log)

    def test_vendor_availability_is_required(self):
        (self.bin / 'pkgutil').unlink()
        result, log = self.run_vendor()
        self.assertIn('unavailable/disabled native vendor provider', result.stderr)
        self.assertNotIn('sudo', log)

    def test_rpm_key_failure(self):
        self.platform('fedora')
        self.env['TEST_FINGERPRINT'] = 'BAD'
        result, log = self.run_vendor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('fingerprint mismatch', result.stderr)
        self.assertNotIn('sudo', log)

    def test_consent_and_selection(self):
        result, log = self.run_vendor(consent='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log, '')
        for machine in ({'packageGroups': ['shell']}, {'packageExcludes': ['1password', '1password-cli']}, {'packageProviders': {'1password': 'mise', '1password-cli': 'brew'}}, {'manualProvisioning': True}):
            with self.subTest(machine=machine):
                self.platform('darwin', **machine)
                result, log = self.run_vendor()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('sudo', log)
                self.assertNotIn('curl', log)

    def test_interactive_consent(self):
        script = self.root / 'interactive.sh'
        script.write_text(self.rendered())
        for answer, installs in (('n\n', False), ('y\n', True)):
            self.log.write_text('')
            master, slave = pty.openpty()
            try:
                process = subprocess.Popen(['/bin/sh', str(script)], stdin=slave,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=dict(self.env, DOTFILES_INSTALL_PACKAGES=''))
                os.write(master, answer.encode())
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, stderr.decode())
                self.assertIn('vendor PKG', stdout.decode())
                self.assertEqual('sudo installer' in self.log.read_text(), installs)
            finally:
                os.close(master)
                os.close(slave)

    def test_mac_repeat_and_single_exclusion(self):
        self.platform('darwin', packageExcludes=['1password'])
        result, log = self.run_vendor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('1password-cli.pkg', log)
        self.assertNotIn('/1password.pkg', log)
        self.fake('op', ':')
        self.log.write_text('')
        result, log = self.run_vendor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log, '')

    def test_transaction_signature_failure_is_fatal(self):
        for ostree in (False, True):
            self.platform('bazzite' if ostree else 'fedora')
            if ostree:
                self.fake('rpm-ostree', ':')
            self.fake('sudo', 'echo "sudo $*" >> "$PACKAGE_TEST_LOG"; case "$1" in dnf|rpm-ostree) echo "invalid signature" >&2; exit 1;; esac')
            result, log = self.run_vendor()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid signature', result.stderr)
            self.assertNotIn('Reboot', result.stderr)
            self.assertFalse(self.state.exists())

    def test_rpm_repeat_and_signature_enforcement(self):
        self.platform('fedora')
        result, log = self.run_vendor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('1password.gpgcheck=1', log)
        self.assertIn('1password.repo_gpgcheck=1', log)
        self.log.write_text('')
        result, log = self.run_vendor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log, '')

    def test_ostree_selection_and_pending_repeat(self):
        self.fake('rpm-ostree', ':')
        self.platform('bazzite')
        plan = self.rendered('{{ includeTemplate "package-plan" . }}')
        self.assertIn('rpm-ostree layering (reboot required)', plan)
        for _ in range(2):
            self.state.unlink(missing_ok=True)  # Booted RPM database lacks pending packages.
            self.log.write_text('')
            result, log = self.run_vendor()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('rpm-ostree install --idempotent', log)
            self.assertNotIn('sudo dnf', log)
            self.assertIn('Reboot', result.stderr)

    def test_ostree_rpm_signatures_fail_closed(self):
        self.fake('rpm-ostree', ':')
        self.platform('bazzite')
        for output, status in (('Header V4 RSA/SHA256 Signature: NOKEY', '0'),
                               ('Payload SHA256 digest: OK', '0'),
                               ('Header V4 RSA/SHA256 Signature: OK', '1')):
            with self.subTest(output=output, status=status):
                self.log.write_text('')
                self.env['TEST_RPM_SIGNATURE'] = output
                self.env['TEST_RPM_VERIFY_EXIT'] = status
                result, log = self.run_vendor()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('sudo', log)
                self.assertFalse(self.state.exists())

    def test_existing_repository_and_key_are_not_rewritten(self):
        self.platform('fedora')
        result, log = self.run_vendor()
        self.assertEqual(result.returncode, 0, result.stderr)
        repo = self.root / 'etc/yum.repos.d/1password.repo'
        self.assertIn('gpgcheck=1', repo.read_text())
        self.assertIn('repo_gpgcheck=1', repo.read_text())
        self.state.unlink()
        self.log.write_text('')
        result, log = self.run_vendor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('install -m', log)
        self.assertEqual(len(list(repo.parent.glob('*.repo'))), 1)

    def test_duplicate_repository_is_reported(self):
        self.platform('fedora')
        directory = self.root / 'etc/yum.repos.d'
        directory.mkdir(parents=True)
        (directory / 'existing.repo').write_text('[1password]\nbaseurl=https://downloads.1password.com/linux/rpm/stable/$basearch\n')
        result, log = self.run_vendor()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('reconcile', result.stderr)
        self.assertNotIn('sudo', log)

    def test_architecture_rejection(self):
        for platform, arch in (('darwin', 'ppc64'), ('fedora', 'aarch64'), ('bazzite', 's390x')):
            self.platform(platform)
            self.env['TEST_ARCH'] = arch
            result, log = self.run_vendor()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Unsupported', result.stderr)
            self.assertNotIn('sudo', log)
