"""Transactional SQLite business records and a bounded legacy file adapter.

Only registered account metadata is managed here. Uploaded datasets, generated
documents, provider execution configs and ordinary files retain their formats.
"""
from __future__ import annotations

import builtins
from contextlib import closing, contextmanager
import io
import json
import os
from pathlib import Path
import threading
import time

import apsw


class DocumentDatabase:
    def __init__(self, path):
        self.path=Path(path).resolve()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.anchor=self.connect()
        self.path.chmod(0o600)
        self.anchor.execute('PRAGMA journal_mode=WAL')
        self.anchor.execute('''CREATE TABLE IF NOT EXISTS documents(
            name TEXT PRIMARY KEY, kind TEXT NOT NULL, updated_ns INTEGER NOT NULL)''')
        self.anchor.execute('''CREATE TABLE IF NOT EXISTS records(
            document TEXT NOT NULL, record_key TEXT NOT NULL, ordinal INTEGER NOT NULL,
            payload TEXT NOT NULL CHECK(json_valid(payload)),
            PRIMARY KEY(document,record_key),
            FOREIGN KEY(document) REFERENCES documents(name) ON DELETE CASCADE)''')
        self.anchor.execute('CREATE INDEX IF NOT EXISTS record_order ON records(document,ordinal)')
        self.path.chmod(0o600)

    def connect(self):
        db=apsw.Connection(str(self.path))
        db.set_busy_timeout(10000)
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        return db

    @contextmanager
    def transaction(self):
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def exists(self,name):
        with closing(self.connect()) as db:
            return db.execute('SELECT 1 FROM documents WHERE name=?',(name,)).fetchone() is not None

    def read(self,name,db=None):
        if db is None:
            with closing(self.connect()) as conn, conn:return self.read(name,conn)
        row=db.execute('SELECT kind FROM documents WHERE name=?',(name,)).fetchone()
        if row is None:raise FileNotFoundError(name)
        rows=list(db.execute('SELECT record_key,payload FROM records WHERE document=? ORDER BY ordinal',(name,)))
        if row[0]=='object':return {key:json.loads(payload) for key,payload in rows}
        if row[0]=='list':return [json.loads(payload) for _,payload in rows]
        return json.loads(rows[0][1]) if rows else None

    def write(self,name,value,db=None):
        if db is None:
            with self.transaction() as conn:return self.write(name,value,conn)
        kind='object' if isinstance(value,dict) else 'list' if isinstance(value,list) else 'value'
        entries=value.items() if kind=='object' else enumerate(value) if kind=='list' else [('value',value)]
        if kind=='list' and value and all(isinstance(row,dict) and isinstance(row.get('id'),str) for row in value) and len({row['id'] for row in value})==len(value):
            entries=[('#'+row['id'],row) for row in value]
        encoded={str(key):(i,json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)) for i,(key,row) in enumerate(entries)}
        previous={key:(ordinal,payload) for key,ordinal,payload in db.execute('SELECT record_key,ordinal,payload FROM records WHERE document=?',(name,))}
        old=db.execute('SELECT kind FROM documents WHERE name=?',(name,)).fetchone()
        if old and old[0]==kind and previous==encoded:return
        db.execute('INSERT INTO documents(name,kind,updated_ns) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET kind=excluded.kind,updated_ns=excluded.updated_ns',(name,kind,time.time_ns()))
        removed=previous.keys()-encoded.keys()
        db.executemany('DELETE FROM records WHERE document=? AND record_key=?',[(name,key) for key in removed])
        changed=[(name,key,ordinal,payload) for key,(ordinal,payload) in encoded.items() if previous.get(key)!=(ordinal,payload)]
        db.executemany('INSERT INTO records(document,record_key,ordinal,payload) VALUES(?,?,?,?) ON CONFLICT(document,record_key) DO UPDATE SET ordinal=excluded.ordinal,payload=excluded.payload',changed)

    def import_file(self,name,path):
        if self.exists(name):return
        # Import only once, under the same transaction as the existence check.
        value=json.loads(Path(path).read_text('utf-8-sig'))
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM documents WHERE name=?',(name,)).fetchone():self.write(name,value,db)

    def names(self):
        with closing(self.connect()) as db:return [row[0] for row in db.execute('SELECT name FROM documents ORDER BY name')]

    def close(self):
        self.anchor.close()


_roots=set()
_databases={}
_lock=threading.RLock()
if os.getenv('YELLOW_WORKSPACE'):_roots.add(Path(os.environ['YELLOW_WORKSPACE']).resolve())

def register_state_root(path):
    with _lock:_roots.add(Path(path).resolve())

def database(path):
    path=Path(path).resolve()
    with _lock:
        if path not in _databases:_databases[path]=DocumentDatabase(path)
        return _databases[path]

def close_state_root(path):
    path=Path(path).resolve()
    with _lock:
        for key in list(_databases):
            if key==path or key.is_relative_to(path):
                _databases.pop(key).close()
        _roots.discard(path)

def state_location(path):
    if isinstance(path,int):return None
    try:path=Path(path).resolve()
    except (ValueError,TypeError):return None
    if path.suffix!='.json':return None
    for base in sorted(_roots,key=lambda p:len(p.parts),reverse=True):
        if not path.is_relative_to(base):continue
        root=base;parts=path.relative_to(base).parts
        if len(parts)>2 and parts[0]=='users':root=base/parts[0]/parts[1];parts=parts[2:]
        name='/'.join(parts)
        managed=(name=='resources.json' or name=='downloads/tasks.json' or name.startswith('chats/') or
                 (name.startswith('backend/config/') and path.name not in {'model_cfg.json','provider_models.json'}) or
                 name in {'backend/report/eval_model_list.json','backend/report/eval_report_list.json'})
        if managed:return root/'.state.sqlite3',name
    return None

def read_document(path):
    location=state_location(path)
    if location:
        db=database(location[0]);name=location[1]
        if not db.exists(name) and Path(path).is_file():db.import_file(name,path)
        return db.read(name)
    return json.loads(Path(path).read_text('utf-8-sig'))

def write_document(path,value):
    location=state_location(path)
    if not location:raise ValueError('Not a managed business document')
    database(location[0]).write(location[1],value)

def update_document(path,transform):
    location=state_location(path)
    if not location:raise ValueError('Not a managed business document')
    db=database(location[0])
    with db.transaction() as conn:
        value=db.read(location[1],conn)
        result=transform(value)
        db.write(location[1],value,conn)
        return result

def increment_dataset_counter(path,group,dataset,counter):
    def change(data):
        row=data.setdefault(str(group),{}).setdefault(str(dataset),{'view_count':0,'download_count':0})
        row[counter]=int(row.get(counter,0))+1
    return update_document(path,change)

def state_exists(path):
    location=state_location(path)
    if location and database(location[0]).exists(location[1]):return True
    return os.path.exists(path)

def state_isfile(path):
    location=state_location(path)
    if location and database(location[0]).exists(location[1]):return True
    return os.path.isfile(path)

class _StateStream:
    def __exit__(self,kind,value,traceback):
        if kind:self._save=False
        self.close()
        return False

    def close(self):
        if not self.closed and self._save:
            self._save=False
            value=self.getvalue()
            if isinstance(value,bytes):value=value.decode('utf-8-sig')
            write_document(self.name,json.loads(value))
        super().close()

class _TextState(_StateStream,io.StringIO):pass
class _BinaryState(_StateStream,io.BytesIO):pass

def open_state(file,mode='r',*args,**kwargs):
    if not state_location(file):return builtins.open(file,mode,*args,**kwargs)
    writable=any(c in mode for c in 'wax+')
    if 'x' in mode and state_exists(file):raise FileExistsError(str(file))
    content='' if any(c in mode for c in 'wx') else json.dumps(read_document(file),ensure_ascii=False)
    stream=_BinaryState(content.encode('utf-8')) if 'b' in mode else _TextState(content)
    stream.name=str(file);stream._save=writable
    if 'a' in mode:stream.seek(0,2)
    return stream

def migrate_state_tree(base,refresh_legacy=False):
    register_state_root(base)
    imported=0
    paths=[Path(base)/'resources.json']
    for root in (Path(base)/'users').glob('*'):
        paths.extend((root/'backend/config').glob('*.json'))
        paths.extend((root/'backend/report').glob('eval_*_list.json'))
        paths.extend((root/'chats').glob('*.json'))
        paths.append(root/'downloads/tasks.json')
    for path in paths:
        if not path.is_file():continue
        location=state_location(path)
        if location:
            db=database(location[0])
            if refresh_legacy:
                db.write(location[1],json.loads(path.read_text('utf-8-sig')));imported+=1
            elif not db.exists(location[1]):db.import_file(location[1],path);imported+=1
    return imported
