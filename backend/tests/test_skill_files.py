import io
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.store import Store
from app.skill_evolution.files import ManagedFiles


@pytest.fixture
def managed(tmp_path):
    store = Store(tmp_path)
    files = ManagedFiles(store)
    yield files
    store.close()


OWNER = {'id':'uploader','role':'user'}
OTHER = {'id':'other','role':'user'}


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w') as bundle:
        for name,content in entries: bundle.writestr(name,content)
    stream.seek(0)
    return stream


def test_nested_zip_path_registration_privacy_and_delete(managed):
    result = managed.ingest(archive([('spreadsheet/55060/input.xlsx',b'example'),('rubric/rules.txt','judge rules')]),'samples.zip',OWNER)
    directory, workbook, rubric = result['items']
    assert directory['kind']=='directory'
    assert workbook['path'].endswith(str(Path('spreadsheet/55060/input.xlsx')))
    assert len(managed.selected(OWNER,[directory['id']]))==2
    assert managed.resolve(OWNER,workbook['path'])['id']==workbook['id']
    assert managed.resolve(OWNER,'rubric/rules.txt',[directory['id']])['id']==rubric['id']
    assert managed.list(OTHER)==[]
    with pytest.raises(HTTPException):managed.get(workbook['id'],OTHER)
    with pytest.raises(HTTPException):managed.resolve(OTHER,workbook['path'])
    with pytest.raises(HTTPException):managed.resolve(OWNER,str(managed.store.path))
    managed.delete(directory['id'],OWNER)
    assert managed.list(OWNER)==[] and not Path(workbook['path']).exists()


@pytest.mark.parametrize('name',['../escape.txt','/tmp/escape.txt','C:/escape.txt','x/../../escape.txt','.env','a/.hidden/b.txt','CON.txt'])
def test_archive_rejects_path_escape_and_hidden_files(managed,name):
    with pytest.raises(HTTPException) as error:
        managed.ingest(archive([(name,'bad')]),'evil.zip',OWNER)
    assert error.value.status_code==422
    assert not managed.list(OWNER)
    assert not list(managed.root.rglob('evil.zip'))


def test_duplicate_zip_and_symlink_rejected(managed):
    with pytest.raises(HTTPException):managed.ingest(archive([('test.txt','x'),('TEST.txt','y')]),'dup.zip',OWNER)
    stream=io.BytesIO()
    info=zipfile.ZipInfo('link.txt');info.create_system=3;info.external_attr=0o120777<<16
    with zipfile.ZipFile(stream,'w') as bundle:bundle.writestr(info,'/etc/passwd')
    stream.seek(0)
    with pytest.raises(HTTPException):managed.ingest(stream,'link.zip',OWNER)


def test_upload_api_roundtrip_and_binary_preview(managed):
    app=FastAPI(); app.include_router(managed.router(lambda:OWNER))
    with TestClient(app) as client:
        created=client.post('/api/skill-evolution/files/upload',files={'file':('rules.md',b'# Rubric','text/markdown')})
        assert created.status_code==201,created.text
        row=created.json()['items'][0]
        assert client.get('/api/skill-evolution/files').json()['items'][0]['id']==row['id']
        assert client.get(f"/api/skill-evolution/files/{row['id']}/content").json()['content']=='# Rubric'
        assert client.get(f"/api/skill-evolution/files/{row['id']}/download").content==b'# Rubric'
        binary=client.post('/api/skill-evolution/files/upload',files={'file':('input.xlsx',b'xlsx')}).json()['items'][0]
        assert client.get(f"/api/skill-evolution/files/{binary['id']}/content").status_code==422
        assert client.delete(f"/api/skill-evolution/files/{row['id']}").status_code==200
        assert client.get(f"/api/skill-evolution/files/{row['id']}/download").status_code==404
