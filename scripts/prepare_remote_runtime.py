"""Prepare an isolated runtime; leaves the currently running release untouched."""
from pathlib import Path
import subprocess
import sys

root=Path('/opt/icap-yellow-venv')
if not root.exists():subprocess.run(['/opt/icap-venv/bin/python','-m','venv',str(root)],check=True)
site=root/'lib/python3.12/site-packages'
(site/'blue-runtime.pth').write_text('/opt/icap-venv/lib/python3.12/site-packages\n')
subprocess.run([str(root/'bin/python'),'-m','pip','install','-r','/tmp/icap-yellow-requirements.txt','--index-url','https://mirrors.aliyun.com/pypi/simple','--disable-pip-version-check'],check=True)
print('Isolated Yellow runtime ready')
