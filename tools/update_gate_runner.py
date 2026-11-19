"""Isolated 29-to-candidate VM update experiment; never publishes release evidence."""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'out/update-gate/work/baselines/29-de-sdboot'
BASELINES = {'A': BASE, 'B': BASE.parent / '29-en-grub-uefi', 'C': BASE.parent / '29-en-grub-bios', 'D': BASE.parent / '29-en-refind-uefi', 'E': BASE.parent / '29-en-limine-uefi', 'F': BASE.parent / '29-en-limine-bios'}
VMROOT = ROOT / 'vm'
WORK = ROOT / 'out/update-gate/work'


def cmd(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, text=True, **kwargs)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def hook_order(log, configuration='A'):
    pre = log.find('Checking WinDoesNot boot filesystem before update')
    kernel = log.find('Updating linux initcpios')
    post = log.find('Validating WinDoesNot boot entries')
    if configuration in ('B', 'C', 'D', 'E', 'F'):
        # The 29 bootstrap installs no temporary guard on non-systemd boot layouts.
        # The newly installed packaged guard is checked by the subsequent probe.
        bootstrap = log.find('Kein systemd-boot-Layout; keine Änderung erforderlich.')
        return bootstrap >= 0 and kernel > bootstrap and post > kernel and (pre < 0 or bootstrap < pre < kernel)
    return pre >= 0 and kernel > pre and post > kernel


def verify_baseline(base=BASE):
    manifest = json.loads((base / 'manifest.json').read_text())
    if manifest.get('offline_install') is not True or not manifest.get('files'):
        raise RuntimeError('Baseline manifest does not prove offline installation')
    for name, expected in manifest['files'].items():
        path = ROOT / name
        if not path.is_file() or digest(path) != expected:
            raise RuntimeError('Baseline hash mismatch: ' + str(path))
    return manifest


class Runner:
    def __init__(self, packages, mutation=None, configuration='A'):
        if mutation not in (None, 'A', 'B', 'C'):
            raise ValueError('unknown mutation')
        self.mutation = mutation
        if configuration not in BASELINES:
            raise ValueError('unknown boot configuration')
        self.configuration = configuration
        self.base = BASELINES[configuration]
        self.packages = Path(packages).resolve(strict=True)
        self.name = 'update-gate-' + uuid.uuid4().hex[:12]
        self.vm = VMROOT / self.name
        self.run = WORK / ('run-' + self.name)
        self.run.mkdir(parents=True)
        self.vmproc = None
        self.server = None
        self.result = {'timestamp': datetime.now(timezone.utc).isoformat(), 'vm': self.name,
                       'scope': '29-to-candidate experimental run; not a release approval', 'checks': {}}

    @classmethod
    def attach(cls, name):
        if not re.fullmatch(r'update-gate-[0-9a-f]{12}', name):
            raise ValueError('invalid gate VM name')
        run = WORK / ('run-' + name)
        state = json.loads((run / 'state.json').read_text())
        obj = cls.__new__(cls)
        obj.name, obj.run, obj.vm = name, run, VMROOT / name
        obj.packages = Path(state['packages']).resolve(strict=True)
        obj.result, obj.phase = state['result'], state['phase']
        obj.vmproc = obj.server = None
        obj.mutation = state.get('mutation')
        obj.configuration = state.get('configuration', 'A')
        obj.base = BASELINES[obj.configuration]
        marker = obj.vm / '.update-gate-owner'
        if not marker.is_file() or marker.read_text().strip() != name:
            raise RuntimeError('missing VM ownership marker')
        pid = int((obj.vm / 'qemu.pid').read_text())
        if ('WinDoesNot-' + name).encode() not in Path('/proc', str(pid), 'cmdline').read_bytes():
            raise RuntimeError('VM PID no longer identifies this gate VM')
        return obj

    def checkpoint(self, phase):
        self.phase = phase
        state = {'packages': str(self.packages), 'phase': phase, 'result': self.result, 'mutation': self.mutation, 'configuration': self.configuration}
        temporary = self.run / 'state.json.tmp'
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        os.replace(temporary, self.run / 'state.json')

    def stop_server(self):
        if self.server:
            self.server.terminate()
            try: self.server.wait(timeout=10)
            except subprocess.TimeoutExpired: self.server.kill(); self.server.wait()
            self.server = None

    def vmctl(self, *args, timeout=40, check=True):
        return subprocess.run([sys.executable, 'tools/vmctl.py', '--vm-name', self.name, *args],
                              cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=check)

    def guest(self, *args, check=True):
        return self.vmctl('exec', *args, check=check).stdout

    def ready(self, previous=None, seconds=240):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.vmproc and self.vmproc.poll() is not None:
                raise RuntimeError('QEMU launcher exited before guest became ready')
            try:
                value = self.guest('/usr/bin/cat', '/proc/sys/kernel/random/boot_id').strip()
                if value and value != previous:
                    return value
            except (OSError, subprocess.SubprocessError):
                pass
            time.sleep(3)
        raise TimeoutError('guest-agent or new boot ID did not become ready')

    def install(self):
        self.result['configuration'] = self.configuration
        self.result['baseline_manifest'] = verify_baseline(self.base)
        self.vm.mkdir()
        (self.vm / '.update-gate-owner').write_text(self.name + '\n')
        cmd('qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(self.base / 'disk.qcow2'), str(self.vm / 'disk.qcow2'), stdout=subprocess.DEVNULL)
        if self.configuration not in ('C', 'F'):
            shutil.copy2(self.base / 'OVMF_VARS.fd', self.vm / 'OVMF_VARS.fd')
            (self.vm / 'OVMF_VARS.fd').chmod(0o600)
        log = (self.run / 'qemu-launch.log').open('w')
        self.vmproc = subprocess.Popen(['./build-and-run.sh', '--boot-installed', '--vm-name', self.name,
                                       '--headless', '--graphics', 'soft', '--memory', '4096', '--cpus', '2'],
                                      cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                      start_new_session=True, env={**os.environ, 'WINDOESNOT_VM_BIOS': '1' if self.configuration in ('C', 'F') else '0'})
        log.close()
        self.result['baseline_boot_id'] = self.ready()
        self.result['baseline_kernel'] = self.guest('/usr/bin/uname', '-r').strip()
        self.result['checks']['install_offline'] = True  # Reused hash-verified documented offline baseline.

    def update(self):
        repo = self.run / 'repo'
        cmd(sys.executable, 'tools/build-repository.py', '--packages', str(self.packages), '--output', str(repo), '--unsigned-test', stdout=subprocess.DEVNULL)
        metadata = json.loads((repo / 'REPOSITORY.json').read_text())['packages']
        expected = {'windoesnot-desktop', 'windoesnot-tools', 'windoesnot-plugins', 'windoesnot-components',
                    'windoesnot-device-manager', 'windoesnot-device-manager-core', 'windoesnot-bluetooth',
                    'windoesnot-network', 'windoesnot-audio', 'windoesnot-graphics', 'windoesnot-store'}
        if set(metadata) != expected:
            raise RuntimeError('Candidate repository lacks required packages')
        core = ('windoesnot-desktop', 'windoesnot-tools', 'windoesnot-plugins', 'windoesnot-components')
        versions = {metadata[x]['version'] for x in core}
        if len(versions) != 1 or not next(iter(versions)):
            raise RuntimeError('Candidate core versions do not match')
        self.result['target_core_version'] = next(iter(versions))
        # A tiny, otherwise uninstalled package exercises an ordinary -S/-Rns
        # transaction using the same offline candidate repository.
        probe = self.run / 'probe-build'
        probe.mkdir()
        (probe / 'usr/lib/modules/windoesnot-gate-probe').mkdir(parents=True)
        (probe / 'usr/lib/modules/windoesnot-gate-probe/vmlinuz').write_text('gate probe\n')
        (probe / '.PKGINFO').write_text('pkgname = windoesnot-gate-probe\npkgbase = windoesnot-gate-probe\npkgver = 1-1\npkgdesc = disposable update gate probe\nurl = https://windoesnot.me\nbuilddate = 1\npackager = WinDoesNot test\nsize = 11\narch = any\n')
        archive_probe = repo / 'windoesnot-gate-probe-1-1-any.pkg.tar.zst'
        cmd('bsdtar', '--zstd', '-cf', str(archive_probe), '-C', str(probe), '.PKGINFO', 'usr', stdout=subprocess.DEVNULL)
        cmd('repo-add', str(repo / 'windoesnot.db.tar.gz'), str(archive_probe), stdout=subprocess.DEVNULL)
        shutil.rmtree(probe)
        from update_gate_common import package_set
        self.result['package_set_sha256'] = package_set(self.packages)
        self.result['packages'] = metadata
        (repo / 'windoesnot-candidate.db').symlink_to('windoesnot.db.tar.gz')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        with (self.run / 'http.log').open('w') as http_log:
            self.server = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', str(repo)],
                                           stdout=http_log, stderr=subprocess.STDOUT, start_new_session=True)
        self.guest('/usr/bin/bash', '-c', 'mkdir -p /var/lib/windoesnot-update-gate; printf "e2e personal data 29\\n" > /home/maxt/e2e-preserve.txt; chown maxt:maxt /home/maxt/e2e-preserve.txt; printf "[Autologin]\\nUser=maxt\\nSession=windoesnot.desktop\\n" > /etc/sddm.conf.d/zz-gate-autologin.conf')
        setup = self.run / 'setup.py'
        setup.write_text("from pathlib import Path\np=Path('/etc/pacman.conf')\ns=p.read_text()\nt='Include = /etc/pacman.d/windoesnot.conf'\nassert s.count(t)==1\np.write_text(s.replace(t, '[windoesnot-candidate]\\nSigLevel = Never\\nServer = http://10.0.2.2:" + str(port) + "\\n\\n'+t))\n")
        self.vmctl('push', str(setup), '/var/lib/windoesnot-update-gate/setup.py')
        self.guest('/usr/bin/python3', '/var/lib/windoesnot-update-gate/setup.py')
        for local, remote in [('tools/update-bootstrap.py', 'bootstrap.py'), ('tools/vm-test/guest-update-run.py', 'runner.py'), ('tools/vm-test/guest-update-verify.py', 'verify.py')]:
            self.vmctl('push', local, '/var/lib/windoesnot-update-gate/' + remote)
        archive = repo / metadata['windoesnot-tools']['filename']
        for name in ('windoesnot-update', 'windoesnot-update-plan'):
            dest = self.run / name
            with dest.open('wb') as output:
                subprocess.run(['bsdtar', '-xOf', str(archive), 'usr/bin/' + name], check=True, stdout=output)
            self.vmctl('push', str(dest), '/usr/local/bin/' + name)
        self.guest('/usr/bin/chmod', '755', '/usr/local/bin/windoesnot-update', '/usr/local/bin/windoesnot-update-plan')
        if self.mutation == 'A':
            self.guest('/usr/bin/bash', '-c', 'test ! -e /usr/bin/windoesnot-update && printf gate-conflict > /usr/bin/windoesnot-update && ! pacman -Qo /usr/bin/windoesnot-update >/dev/null 2>&1')
        elif self.mutation == 'B':
            self.guest('/usr/bin/bash', '-c', "printf '#!/bin/sh\necho GATE_MUTATION_B_PLANNER_DISABLED >&2\nexit 73\n' > /usr/local/bin/windoesnot-update-plan; chmod 755 /usr/local/bin/windoesnot-update-plan")
        elif self.mutation == 'C':
            self.guest('/usr/bin/bash', '-c', 'mkdir -p /etc/pacman.d/hooks; ln -s /dev/null /etc/pacman.d/hooks/zzzz-windoesnot-boot-entries.hook; test "$(readlink /etc/pacman.d/hooks/zzzz-windoesnot-boot-entries.hook)" = /dev/null')
        if self.mutation:
            self.result['mutation'] = self.mutation
            self.result['mutation_active'] = True
        self.guest('/usr/bin/bash', '-c', 'nohup env LC_ALL=C /usr/bin/python3 /var/lib/windoesnot-update-gate/runner.py </dev/null >/var/lib/windoesnot-update-gate/launcher.log 2>&1 &')
        deadline = time.monotonic() + 2400
        while time.monotonic() < deadline:
            result = self.vmctl('exec', '/usr/bin/cat', '/var/lib/windoesnot-update-gate/result.json', check=False)
            if result.returncode == 0:
                job = json.loads(result.stdout)
                break
            time.sleep(10)
        else:
            raise TimeoutError('update job did not finish within 40 minutes')
        for filename in ('result.json', 'update.log'):
            self.vmctl('pull', '/var/lib/windoesnot-update-gate/' + filename, filename)
            shutil.copy2(self.vm / filename, self.run / filename)
        self.result['job'] = job
        self.result['checks']['test_repo'] = True
        self.result['checks']['regular_syu'] = job.get('success') is True
        log = (self.run / 'update.log').read_text(errors='replace')
        self.result['checks']['hook_order'] = hook_order(log, self.configuration)
        hook_result = self.vmctl('exec', '/usr/bin/cat', '/var/lib/windoesnot/boot-migration/result.json', check=False)
        try:
            if self.configuration in ('B', 'C', 'D', 'E', 'F'):
                post = log.find('Validating WinDoesNot boot entries')
                self.result['checks']['post_hook_status'] = post >= 0 and 'not a systemd-boot layout' in log[post:] and 'nothing to do' in log[post:]
            else:
                hook = json.loads(hook_result.stdout)
                started = datetime.fromisoformat(hook['started'])
                update_start = datetime.fromisoformat(job['step_times']['update']['started'])
                update_end = datetime.fromisoformat(job['step_times']['update']['finished'])
                self.result['checks']['post_hook_status'] = hook.get('state') in ('ok', 'nothing-to-do') and update_start <= started <= update_end
                self.result['post_hook_result'] = hook
        except (ValueError, KeyError, TypeError):
            self.result['checks']['post_hook_status'] = False
        if not job.get('success'):
            raise RuntimeError('bootstrap or update failed; see update.log')
        probe_result = self.vmctl('exec', '/usr/bin/bash', '-c',
                                  'pacman -S --noconfirm windoesnot-candidate/windoesnot-gate-probe && pacman -Rns --noconfirm windoesnot-gate-probe', check=False, timeout=180)
        (self.run / 'pacman-probe.log').write_text(probe_result.stdout + probe_result.stderr)
        self.result['checks']['pacman_install_remove'] = (probe_result.returncode == 0 and 'Checking WinDoesNot boot filesystem before update' in probe_result.stdout)
        # Preserve the failure in checks, but still observe both boots of this disposable VM.

    def verify(self):
        previous = self.result['baseline_boot_id']
        boots = []
        for _ in range(2):
            self.vmctl('exec', '/usr/bin/systemctl', 'reboot', check=False)
            bootid = self.ready(previous)
            # The login and plugins may start after the guest agent.
            end = time.monotonic() + 120
            while True:
                observation = json.loads(self.guest('/usr/bin/python3', '/var/lib/windoesnot-update-gate/verify.py', self.configuration, self.result['target_core_version']))
                if observation['checks']['desktop_plugins'] or time.monotonic() >= end:
                    break
                time.sleep(4)
            if observation['boot_id'] != bootid:
                raise RuntimeError('boot ID changed during verification')
            boots.append(observation)
            previous = bootid
        self.result['reboots'] = boots
        for key in boots[0]['checks']:
            self.result['checks'][key] = all(b['checks'].get(key) is True for b in boots)
        self.result['checks']['two_new_boots'] = len({self.result['baseline_boot_id'], *(b['boot_id'] for b in boots)}) == 3
        self.result['checks']['kernel_changed'] = all(b['kernel'] != self.result['baseline_kernel'] for b in boots)
        from update_gate_common import package_set
        self.result['checks']['package_set_unchanged'] = package_set(self.packages) == self.result['package_set_sha256']
        if not all(self.result['checks'].values()):
            raise RuntimeError('one or more update assertions failed')

    def cleanup(self):
        self.stop_server()
        for temporary in (self.run / 'repo', self.run / 'probe-build'):
            if temporary.is_dir():
                shutil.rmtree(temporary)
        if self.vm.exists():
            marker = self.vm / '.update-gate-owner'
            if not marker.is_file() or marker.read_text().strip() != self.name:
                raise RuntimeError('VM ownership marker missing; directory retained')
            pidfile = self.vm / 'qemu.pid'
            pid = int(pidfile.read_text()) if pidfile.exists() else None
            if not pid and self.vmproc and self.vmproc.poll() is None:
                os.killpg(self.vmproc.pid, 15)
                self.vmproc.wait(timeout=10)
            if pid:
                try:
                    process_args = Path('/proc', str(pid), 'cmdline').read_bytes()
                except FileNotFoundError:
                    process_args = b''
                if process_args and ('WinDoesNot-' + self.name).encode() not in process_args:
                    raise RuntimeError('VM PID belongs to a different process; directory retained')
                if process_args:
                    self.vmctl('stop', check=False)
                for _ in range(50):
                    try: os.kill(pid, 0)
                    except ProcessLookupError: break
                    time.sleep(.2)
                else: raise RuntimeError('owned QEMU still running; VM retained')
            shutil.rmtree(self.vm)
        if self.vmproc:
            try: self.vmproc.wait(timeout=10)
            except subprocess.TimeoutExpired: pass

    def execute(self):
        try:
            self.install(); self.update(); self.verify()
            self.result['passed'] = True
        except Exception as exc:
            self.result['passed'] = False
            self.result['error'] = str(exc)
            if isinstance(exc, subprocess.CalledProcessError):
                self.result['error_stdout'] = (exc.stdout or '')[-16000:]
                self.result['error_stderr'] = (exc.stderr or '')[-16000:]
        finally:
            try: self.cleanup()
            except Exception as exc:
                self.result['passed'] = False
                self.result['cleanup_error'] = str(exc)
            self.result['finished'] = datetime.now(timezone.utc).isoformat()
            temporary = self.run / 'result.json.tmp'
            temporary.write_text(json.dumps(self.result, indent=2) + '\n')
            os.replace(temporary, self.run / 'result.json')
        return self.result
