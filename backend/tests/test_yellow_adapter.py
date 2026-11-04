"""Regression coverage for the private Yellow/Blue trust boundary."""
import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def platform(tmp_path,monkeypatch):
    monkeypatch.setenv('INNOVATION_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('DEMO_MODE','true')
    monkeypatch.setenv('INNOVATION_ADMIN_USER','admin')
    monkeypatch.setenv('INNOVATION_ADMIN_PASSWORD','private-test-password')
    monkeypatch.setenv('DEEPSEEK_API_KEY','')
    sys.modules.pop('adapter',None)
    adapter=importlib.import_module('adapter')
    with TestClient(adapter.app) as client:
        admin=client.post('/api/auth/login',json={'username':'admin','password':'private-test-password'}).json()
        users=[]
        for i in (1,2):
            response=client.post('/api/auth/register',json={'username':f'yellow{i}','phone':f'1381234500{i}',
                'password':'test-password-123','security_questions':[
                    {'question':q,'answer':a} for q,a in [('最喜欢的城市？','上海'),('第一只宠物？','小白'),('童年好友？','张三')]]})
            assert response.status_code==201,response.text
            users.append(response.json())
        yield client,adapter,users,admin
    adapter.runtime.shutdown()


def header(account):return {'Authorization':'Bearer '+account['access_token']}


def test_source_and_credentials_are_not_public(platform):
    client,adapter,users,admin=platform
    client.cookies.clear()
    for path in ['/api/platform/capabilities','/v1/get_model_info','/llm_bench/app.js']:
        assert client.get(path).status_code==401
    for path in ['/.env','/.git/config','/backend/adapter.py','/data/LLMInferencer.py']:
        assert client.get(path).status_code==404
    assert client.get('/api/school/jobs',headers=header(admin)).status_code==404
    assert client.get('/api/data-governance/jobs',headers=header(admin)).status_code==404
    h=header(users[0])
    response=client.post('/api/models',headers=h,json={'id':'test-private-model','name':'test','provider':'Local',
        'endpoints':[{'url':'https://example.test/v1','api_key':'backend-secret-test-only'}]})
    assert response.status_code==201
    catalog=client.get('/v1/get_model_info',headers=h)
    assert catalog.status_code==200
    assert 'backend-secret-test-only' not in catalog.text
    assert all(e['api_key']=='' for row in catalog.json() for e in row['config']['api_params'])
    for path in ['../../backend/config/provider_models.json','backend/config/provider_models.json','backend/yellow/server.py']:
        assert client.get('/v1/download/file',params={'filepath':path},headers=h).status_code==403


def test_resource_visibility_and_editing_follow_ownership(platform):
    client,adapter,users,_=platform
    owner,other=users;h=header(owner);h2=header(other)
    response=client.post('/api/datasets',headers=h,json={'name':'private resource','category':'训练集'})
    identifier=response.json()['id']
    assert identifier not in {row['id'] for row in client.get('/api/datasets',headers=h2).json()}
    assert client.put('/api/datasets/'+identifier,headers=h2,json={'name':'changed'}).status_code==403
    assert client.post('/api/datasets/'+identifier+'/files',headers=h,files={'file':('fixture.jsonl',b'{"text":"private fixture"}\n')}).status_code==201
    assert client.put('/api/datasets/'+identifier,headers=h,json={'name':'shared resource','visibility':'public'}).status_code==200
    assert identifier in {row['id'] for row in client.get('/api/datasets',headers=h2).json()}
    principal=adapter.app.state.auth.current(other['access_token'])
    root=adapter.runtime.initialize(principal)
    adapter.runtime.sync_resources(root,principal)
    assert identifier in json.loads((root/'backend/config/common_testcase_cfg.json').read_text('utf-8'))
    client.put('/api/datasets/'+identifier,headers=h,json={'name':'private again','visibility':'private'})
    assert identifier not in {row['id'] for row in client.get('/api/datasets',headers=h2).json()}
    adapter.runtime.sync_resources(root,principal)
    assert identifier not in json.loads((root/'backend/config/common_testcase_cfg.json').read_text('utf-8'))
    assert not (root/'testsuite/TestSuite'/identifier).exists()


def test_published_reports_revoke_shared_copies(platform):
    client,adapter,users,_=platform
    runtime=adapter.runtime
    owner=adapter.app.state.auth.current(users[0]['access_token'])
    other=adapter.app.state.auth.current(users[1]['access_token'])
    source=runtime.initialize(owner);target=runtime.initialize(other)
    report=source/'backend/report/output/example.pptx';report.write_bytes(b'private-report-fixture')
    path=source/'backend/config/publishedReportTasks.json'
    from app.yellow_runtime import write_json
    write_json(path,{'example':{'id':'example','status':'completed','published_filepath':report.relative_to(source).as_posix()}})
    runtime.sync_resources(target,other)
    records=json.loads((target/'backend/config/publishedReportTasks.json').read_text('utf-8'))
    assert len(records)==1
    shared=next(iter(records.values()))
    assert shared['can_edit'] is False
    copied=target/shared['published_filepath'];assert copied.read_bytes()==report.read_bytes()
    write_json(path,{})
    runtime.sync_resources(target,other)
    assert json.loads((target/'backend/config/publishedReportTasks.json').read_text('utf-8'))=={}
    assert not copied.exists()
