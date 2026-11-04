"""Atomic service cutover with a private backup and automatic code rollback."""
from pathlib import Path
from datetime import datetime,timezone
import json
import os
import shutil
import subprocess
import tarfile
import time
import httpx

current=Path('/opt/icap/current')
candidate=Path(Path('/opt/icap/yellow-candidate').read_text().strip()).resolve()
assert candidate.is_relative_to(Path('/opt/icap/releases')) and (candidate/'backend/adapter.py').is_file()
previous=current.resolve()
assert current.is_symlink() and previous.is_relative_to(Path('/opt/icap/releases'))
backup=Path('/var/backups/icap')/('before-yellow-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True,mode=0o700);backup.chmod(0o700)
dropin=Path('/etc/systemd/system/icap.service.d/yellow.conf')
old_dropin=dropin.read_bytes() if dropin.exists() else None
shutil.copy2('/etc/systemd/system/icap.service',backup/'icap.service')
shutil.copytree('/etc/systemd/system/icap.service.d',backup/'service.d')
shutil.copy2('/etc/icap/production.env',backup/'production.env')
(backup/'previous-release.txt').write_text(str(previous))
for p in backup.rglob('*'):
    if p.is_file():p.chmod(0o600)

def switch(path):
    temp=Path('/opt/icap/.yellow-current-next')
    if temp.is_symlink():temp.unlink()
    elif temp.exists():raise RuntimeError('Unexpected temporary release link')
    temp.symlink_to(path,target_is_directory=True)
    temp.replace(current)

subprocess.run(['systemctl','stop','icap-yellow-check.service'],check=True)
subprocess.run(['systemctl','stop','icap.service'],check=True)
try:
    with tarfile.open(backup/'data.tar.gz','w:gz') as archive:archive.add('/var/lib/icap',arcname='icap')
    (backup/'data.tar.gz').chmod(0o600)
    dropin.parent.mkdir(exist_ok=True)
    dropin.write_text('''[Service]
ExecStart=
ExecStart=/opt/icap-yellow-venv/bin/python -m uvicorn adapter:app --host 127.0.0.1 --port 8081 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
Environment=YELLOW_CODE_SANDBOX_ENABLED=true
Environment=HF_ENDPOINT=https://hf-mirror.com
''')
    dropin.chmod(0o644)
    switch(candidate)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','start','icap.service'],check=True)
    for attempt in range(30):
        try:
            response=httpx.get('http://127.0.0.1:8081/health',trust_env=False,timeout=2)
            if response.status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(1)
    else:raise RuntimeError('New service did not become healthy')
    subprocess.run(['/opt/icap-yellow-venv/bin/python','/tmp/check_remote_release.py','production'],check=True)
except Exception:
    subprocess.run(['systemctl','stop','icap.service'])
    switch(previous)
    if old_dropin is None:dropin.unlink(missing_ok=True)
    else:dropin.write_bytes(old_dropin)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','start','icap.service'],check=True)
    print('Cutover failed; previous code and service configuration restored',flush=True)
    raise
print('Production switched:',candidate.name,flush=True)
print('Private backup:',backup,flush=True)
