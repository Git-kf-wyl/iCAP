"""Build a private release, excluding credentials, state and development tools."""
from pathlib import Path
import json
import subprocess
import tarfile
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
release='yellow-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+commit[:8]
destination=root/'.releases';destination.mkdir(exist_ok=True)
path=destination/(release+'.tar.gz')
files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
with tarfile.open(path,'w:gz',compresslevel=6) as archive:
    for name in files:
        source=root/name
        if not name or not source.is_file():continue
        if name.startswith(('scripts/import_yellow','scripts/prepare_frontend')):continue
        archive.add(source,arcname=name,recursive=False)
    dist=root/'frontend/dist'
    assert (dist/'.vite/manifest.json').is_file()
    for source in dist.rglob('*'):
        if source.is_file():archive.add(source,arcname=source.relative_to(root).as_posix(),recursive=False)
(destination/'latest.json').write_text(json.dumps({'release':release,'commit':commit,'archive':str(path)}),'utf-8')
print(release,path.stat().st_size)
