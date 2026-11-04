"""Offline migration, verification and reversible export for business storage."""
import argparse
import json
from pathlib import Path
import os
from app.store import Store
from state_storage import database,migrate_state_tree,close_state_root


def export_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.export.tmp')
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.flush();os.fsync(stream.fileno())
    temp.chmod(0o600);temp.replace(path)


def manage(base,action,refresh_legacy=False):
    base=Path(base).resolve()
    store=Store(base)
    if refresh_legacy and (base/'platform.json').is_file():store._save(json.loads((base/'platform.json').read_text('utf-8-sig')))
    imported=migrate_state_tree(base/'yellow',refresh_legacy=refresh_legacy)
    paths=[base/'platform.sqlite3',*(base/'yellow').rglob('.state.sqlite3')]
    total=0
    for path in paths:
        db=database(path)
        assert db.anchor.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Database integrity check failed'
        total+=db.anchor.execute('SELECT count(*) FROM records').fetchone()[0]
        if action=='export' and path.name=='.state.sqlite3':
            for name in db.names():export_json(path.parent/name,db.read(name))
    if action=='export':export_json(base/'platform.json',store.snapshot())
    result={'action':action,'databases':len(paths),'records':total,'imported_documents':imported,'integrity':'ok'}
    close_state_root(base)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['migrate','verify','export'])
    parser.add_argument('--data-dir',required=True)
    parser.add_argument('--refresh-legacy',action='store_true',help='Only use while the previous JSON-based release is stopped')
    args=parser.parse_args()
    print(json.dumps(manage(args.data_dir,args.action,args.refresh_legacy)))
