"""Server-only staging: production state is copied, never edited by this check."""
from pathlib import Path
import os
import pwd
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import json

release=sys.argv[1]
if not release.startswith('yellow-') or '/' in release or '..' in release:raise ValueError('invalid release')
archive=Path('/tmp')/(release+'.tar.gz')
root=Path('/opt/icap/releases')/release
root.mkdir(mode=0o750)
with tarfile.open(archive) as bundle:bundle.extractall(root,filter='data')
account=pwd.getpwnam('icap')
for path in [root,*root.rglob('*')]:
    os.chown(path,0,account.pw_gid);path.chmod(0o750 if path.is_dir() else 0o640)
stage=Path('/var/lib/icap-yellow-check')
if stage.exists():raise RuntimeError('Staging directory already exists; inspect it before reusing')
shutil.copytree('/var/lib/icap',stage,ignore=shutil.ignore_patterns('agentcompass_results','agentcompass','skill-evolution','yellow'))
# SQLite backup captures a consistent auth database while the old service stays online.
with sqlite3.connect('/var/lib/icap/auth.sqlite3') as source,sqlite3.connect(stage/'auth.sqlite3') as target:source.backup(target)
state=stage/'platform.json'
data=json.loads(state.read_text())
for key in ('skill_jobs','evaluations','school_jobs','deployments','reports'):data[key]=[]
state.write_text(json.dumps(data,ensure_ascii=False))
for path in [stage,*stage.rglob('*')]:
    os.chown(path,account.pw_uid,account.pw_gid);path.chmod(0o700 if path.is_dir() else 0o600)
runner=Path('/opt/icap/yellow-check-runner.py')
runner.write_text('''import os,sys
os.environ['INNOVATION_DATA_DIR']='/var/lib/icap-yellow-check'
os.environ['AGENTCOMPASS_DATA_DIR']='/var/lib/icap-yellow-check/agentcompass'
os.environ['AGENTCOMPASS_RESULTS_DIR']='/var/lib/icap-yellow-check/agentcompass_results'
os.environ['HOME']='/var/lib/icap-yellow-check'
os.environ['SKILL_EVOLVE_HERMES_ENABLED']='true'
os.environ['ICAP_HERMES_RUNTIME']='/opt/icap-hermes'
os.environ['YELLOW_CODE_SANDBOX_ENABLED']='true'
sys.path.insert(0,os.getcwd())
import uvicorn
uvicorn.run('adapter:app',host='127.0.0.1',port=8083,workers=1)
''')
runner.chmod(0o644)
unit=Path('/etc/systemd/system/icap-yellow-check.service')
unit.write_text('''[Unit]
Description=iCAP private Yellow pre-deployment check
[Service]
User=icap
Group=icap
WorkingDirectory='''+str(root/'backend')+'''
EnvironmentFile=/etc/icap/production.env
ExecStart=/opt/icap-yellow-venv/bin/python /opt/icap/yellow-check-runner.py
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/icap-yellow-check
KillMode=control-group
TimeoutStopSec=30
''')
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','start','icap-yellow-check.service'],check=True)
Path('/opt/icap/yellow-candidate').write_text(str(root))
print('Private candidate staged:',release)
