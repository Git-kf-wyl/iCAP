"""Private, quota-limited uploads with an explicit registry of usable server paths."""
from __future__ import annotations

import hashlib
import mimetypes
import shutil
import stat
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from ..access import require_view, require_edit

UPLOAD_LIMIT = 90 * 1024 * 1024
EXPANDED_LIMIT = 1024 * 1024 * 1024
USER_QUOTA = 2 * 1024 * 1024 * 1024
FILE_COUNT_LIMIT = 10000
TEXT_LIMIT = 50 * 1024 * 1024
ALLOWED = {'.md', '.txt', '.json', '.jsonl', '.csv', '.tsv', '.xlsx', '.xls', '.pdf', '.docx', '.py', '.js', '.sh', '.yaml', '.yml'}


def checked_name(value: str) -> PurePosixPath:
    value = value.replace('\\', '/')
    p = PurePosixPath(value)
    if (not value or len(value) > 500 or p.is_absolute() or ':' in value or any(ord(c)<32 or c in '<>"|?*' for c in value)
            or any(part in {'', '.', '..'} or part.startswith('.') or part.rstrip(' .') != part
                   for part in value.rstrip('/').split('/'))
            or any(part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for part in p.parts)):
        raise HTTPException(422, '文件名必须是普通相对路径，不能包含隐藏目录、盘符或 ..')
    return p


class ManagedFiles:
    def __init__(self, store):
        self.store = store
        self.root = (store.base / 'skill-files').resolve()
        self.root.mkdir(exist_ok=True, mode=0o700)
        self.lock = threading.RLock()

    def records(self):
        return self.store.snapshot(['skill_files']).get('skill_files') or []

    def list(self, principal):
        # Management never enumerates another account's files, including for admins.
        return [row for row in self.records() if row['owner_user_id'] == principal['id']]

    def get(self, identifier, principal):
        row = next((r for r in self.records() if r['id'] == identifier), None)
        if row is None:
            raise HTTPException(404, '文件不存在')
        require_view(row, principal)
        self.safe_path(row)
        return row

    def safe_path(self, row):
        path = Path(row['path'])
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root) or path.is_symlink() or not resolved.exists():
            raise HTTPException(404, '文件不存在或已移除')
        current = path
        while current != self.root:
            if current.is_symlink():
                raise HTTPException(422, '不允许通过链接访问文件')
            current = current.parent
        return resolved

    def selected(self, principal, ids):
        result = {}
        records = self.records()
        for identifier in ids:
            row = self.get(identifier, principal)
            children = [r for r in records if r.get('upload_id') == row['upload_id'] and r['kind'] == 'file'] if row['kind'] == 'directory' else [row]
            for child in children:
                require_view(child, principal)
                self.safe_path(child)
                result[child['id']] = child
        return list(result.values())

    def resolve(self, principal, path, selected_ids=None):
        rows = self.selected(principal, selected_ids) if selected_ids is not None else self.list(principal)
        reference = str(path).replace('\\', '/')
        exact = [r for r in rows if r['kind'] == 'file' and (r['id'] == reference or r['path'].replace('\\','/') == reference)]
        if not exact and selected_ids is not None:
            exact = [r for r in rows if r['kind'] == 'file' and r['relative_path'] == reference]
        if len(exact) != 1:
            raise HTTPException(422, f'文件路径未注册、无权使用或存在重名，请从文件管理复制路径：{reference[:180]}')
        self.safe_path(exact[0])
        return exact[0]

    def ingest(self, source, filename, principal):
        filename = str(checked_name(filename or 'upload'))
        if '/' in filename:
            raise HTTPException(422, '上传文件名不能包含目录')
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED | {'.zip'}:
            raise HTTPException(422, '支持 ZIP、表格、JSON、文本、文档和参考脚本文件')
        upload_id = 'upload-' + uuid.uuid4().hex
        owner = hashlib.sha256(principal['id'].encode()).hexdigest()[:24]
        directory = self.root / owner / upload_id
        directory.mkdir(parents=True, mode=0o700)
        archive_path = directory / filename
        try:
            size = 0
            with archive_path.open('xb') as target:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > UPLOAD_LIMIT:
                        raise HTTPException(413, '单次上传不能超过 90 MB；更大的资源请拆分上传')
                    target.write(chunk)
            archive_path.chmod(0o600)
            paths = []
            folder = None
            if extension == '.zip':
                folder = directory / 'contents'
                folder.mkdir(mode=0o700)
                with zipfile.ZipFile(archive_path) as archive:
                    entries = archive.infolist()
                    if len(entries) > FILE_COUNT_LIMIT or sum(i.file_size for i in entries) > EXPANDED_LIMIT:
                        raise HTTPException(413, '压缩包最多 10000 个条目，解压后不能超过 1 GB')
                    names = set()
                    total = 0
                    for info in entries:
                        name = checked_name(info.filename)
                        if str(name).casefold() in names:
                            raise HTTPException(422, '压缩包内有重复或大小写冲突的路径')
                        names.add(str(name).casefold())
                        mode = info.external_attr >> 16
                        if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)) or info.flag_bits & 1:
                            raise HTTPException(422, '压缩包不支持链接、特殊文件或加密条目')
                        destination = folder.joinpath(*name.parts)
                        if not destination.resolve().is_relative_to(folder.resolve()):
                            raise HTTPException(422, '压缩包路径越界')
                        if info.is_dir():
                            destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                            continue
                        if name.suffix.lower() not in ALLOWED:
                            raise HTTPException(422, f'压缩包中含不支持的文件：{name}')
                        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        with archive.open(info) as src, destination.open('xb') as target:
                            while chunk := src.read(1024 * 1024):
                                total += len(chunk)
                                if total > EXPANDED_LIMIT:
                                    raise HTTPException(413, '解压大小超过 1 GB')
                                target.write(chunk)
                        destination.chmod(0o600)
                        paths.append((destination, str(name)))
                archive_path.unlink()
                if not paths:
                    raise HTTPException(422, '压缩包中没有可用文件')
            else:
                paths = [(archive_path, filename)]
            created = datetime.now(timezone.utc).isoformat(timespec='seconds')
            folder_id = 'file-' + uuid.uuid4().hex if folder else None
            rows = []
            for path, relative in paths:
                rows.append(dict(id='file-'+uuid.uuid4().hex, upload_id=upload_id, name=path.name,
                    kind='file', path=str(path.resolve()), relative_path=relative, size=path.stat().st_size,
                    created_at=created, parent_id=folder_id, owner_user_id=principal['id'], visibility='private',
                    mime_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'))
            total_size = sum(r['size'] for r in rows)
            if folder:
                rows.insert(0, dict(id=folder_id, upload_id=upload_id, name=filename, kind='directory',
                    path=str(folder.resolve()), relative_path='', size=total_size, created_at=created,
                    parent_id=None, owner_user_id=principal['id'], visibility='private'))
            with self.lock:
                def save(data):
                    current = data.get('skill_files') or []
                    used = sum(r['size'] for r in current if r['owner_user_id']==principal['id'] and r['kind']=='file')
                    if used + total_size > USER_QUOTA:
                        raise HTTPException(413, '个人文件空间超过 2 GB，请清理不再使用的文件')
                    data['skill_files'] = rows + current
                self.store.update(save, collections=['skill_files'])
            return {'items': rows, 'root_path': str((folder or directory).resolve())}
        except Exception as exc:
            shutil.rmtree(directory, ignore_errors=True)
            if isinstance(exc, (zipfile.BadZipFile, RuntimeError, UnicodeError, NotADirectoryError, IsADirectoryError, FileExistsError)):
                raise HTTPException(422, '压缩包损坏或格式不受支持') from None
            if isinstance(exc, OSError):
                raise HTTPException(503, '文件存储失败，请检查服务器剩余空间和目录权限') from None
            raise

    def delete(self, identifier, principal):
        with self.lock:
            row = self.get(identifier, principal)
            require_edit(row, principal)
            path = self.safe_path(row)
            if row['kind'] == 'directory':
                shutil.rmtree(path)
            else:
                path.unlink()
            def remove(data):
                data['skill_files'] = [r for r in data['skill_files'] if not (r['id']==identifier or
                    (row['kind']=='directory' and r['upload_id']==row['upload_id']))]
            self.store.update(remove, collections=['skill_files'])
        return {'deleted': True}

    def router(self, authorized):
        router = APIRouter(prefix='/api/skill-evolution/files', tags=['skill files'])

        @router.get('')
        def listing(principal=Depends(authorized)):
            return {'items': self.list(principal), 'limits': {'upload_bytes':UPLOAD_LIMIT,'expanded_bytes':EXPANDED_LIMIT,'quota_bytes':USER_QUOTA}}

        @router.post('/upload', status_code=201)
        async def upload(file: UploadFile = File(...), principal=Depends(authorized)):
            try:
                return await run_in_threadpool(self.ingest, file.file, file.filename, principal)
            finally:
                await file.close()

        @router.get('/{identifier}/content')
        def content(identifier: str, principal=Depends(authorized)):
            row = self.get(identifier, principal)
            if row['kind'] != 'file' or Path(row['name']).suffix.lower() not in {'.md','.txt','.json','.jsonl','.csv','.tsv','.py','.js','.sh','.yaml','.yml'}:
                raise HTTPException(422, '该文件不能作为文本预览，请下载查看')
            if row['size'] > TEXT_LIMIT:
                raise HTTPException(413, '文本文件超过 50 MB，请下载查看')
            try:
                text = self.safe_path(row).read_text('utf-8-sig')
            except UnicodeError:
                raise HTTPException(422, '文本需使用 UTF-8 编码') from None
            return {'content':text,'path':row['path'],'name':row['name']}

        @router.get('/{identifier}/download')
        def download(identifier: str, principal=Depends(authorized)):
            row = self.get(identifier, principal)
            if row['kind'] != 'file':
                raise HTTPException(422, '请展开目录选择具体文件')
            return FileResponse(self.safe_path(row),filename=row['name'],media_type='application/octet-stream',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

        @router.delete('/{identifier}')
        def delete(identifier: str, principal=Depends(authorized)):
            return self.delete(identifier,principal)

        return router
