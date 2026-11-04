from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import pytest

from app.store import Store
from state_storage import (DocumentDatabase,register_state_root,read_document,
                           write_document,open_state,state_exists,close_state_root)


def test_platform_import_is_one_time_and_updates_are_atomic(tmp_path):
    legacy={'models':[{'id':'private','name':'模型','visibility':'private','owner_user_id':'u'}],
            'datasets':[],'counter':0}
    (tmp_path/'platform.json').write_text(json.dumps(legacy,ensure_ascii=False),'utf-8')
    store=Store(tmp_path)
    assert store.get_record('models','private')==legacy['models'][0]
    assert store.database.anchor.execute('PRAGMA journal_mode').fetchone()[0]=='wal'
    def increment(_):store.update(lambda data:data.update(counter=data['counter']+1))
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(increment,range(40)))
    assert store.snapshot()['counter']==40
    def fail(data):
        data['counter']=999
        raise RuntimeError('abort transaction')
    with pytest.raises(RuntimeError):store.update(fail)
    assert store.snapshot()['counter']==40
    assert json.loads((tmp_path/'platform.json').read_text('utf-8'))==legacy
    store.close()
    reopened=Store(tmp_path)
    assert reopened.snapshot()['counter']==40
    reopened.close()


def test_legacy_metadata_uses_database_without_rewriting_json(tmp_path):
    register_state_root(tmp_path)
    path=tmp_path/'users'/'account'/'backend/config/tasks.json'
    path.parent.mkdir(parents=True)
    path.write_text('{"old":{"status":"queued"}}','utf-8')
    assert read_document(path)['old']['status']=='queued'
    with open_state(path,'w',encoding='utf-8') as stream:json.dump({'new':{'status':'completed'}},stream)
    assert read_document(path)=={'new':{'status':'completed'}}
    assert json.loads(path.read_text('utf-8'))=={'old':{'status':'queued'}}
    new_path=path.parent/'dataset_download_view_count.json'
    write_document(new_path,{})
    assert state_exists(new_path) and not new_path.exists()
    with open_state(new_path,'rb') as stream:assert json.load(stream)=={}
    data=tmp_path/'users/account/testsuite/cases.json'
    data.parent.mkdir();data.write_text('[{"input":"original data"}]','utf-8')
    with open_state(data,'r',encoding='utf-8') as stream:assert json.load(stream)==[{'input':'original data'}]
    close_state_root(tmp_path)
