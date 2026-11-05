"""Regression coverage for the private Yellow/Blue trust boundary."""
import importlib
import json
import sys
from pathlib import Path

import pytest
from state_storage import read_document,write_document
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


def test_workspace_bootstrap_is_private_current_and_worker_free(platform):
    client,adapter,users,_=platform
    client.cookies.clear()
    assert client.get('/api/workspace/bootstrap').status_code==401
    owner,other=users
    response=client.post('/api/models',headers=header(owner),json={'id':'bootstrap-private',
        'name':'private model','provider':'Local','visibility':'private',
        'endpoints':[{'url':'https://example.test/v1','api_key':'only-for-server'}]})
    assert response.status_code==201,response.text
    actor=adapter.app.state.auth.current(owner['access_token'])
    root=adapter.runtime.initialize(actor)
    write_document(root/'backend/config/evaluationResult.json',{'fixture':{'model_id':'bootstrap-private','dataset':'private-result'}})
    response=client.get('/api/workspace/bootstrap',headers=header(owner))
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert 'only-for-server' not in response.text
    entries=response.json()['entries']
    assert response.headers['content-encoding']=='gzip'
    identity=client.get('/api/workspace/bootstrap',headers={**header(owner),'Accept-Encoding':'identity'})
    assert 'content-encoding' not in identity.headers and identity.json()==response.json()
    assert 'bootstrap-private' in {row['model_id'] for row in entries['/v1/get_model_info']}
    assert entries['/v1/get_evaluation_result']['fixture']['dataset']=='private-result'
    for path,data in entries.items():
        actual=client.get(path,headers=header(owner))
        assert actual.status_code==200 and actual.json()==data,path
    other_entries=client.get('/api/workspace/bootstrap',headers=header(other)).json()['entries']
    assert 'bootstrap-private' not in {row['model_id'] for row in other_entries['/v1/get_model_info']}
    assert 'fixture' not in other_entries['/v1/get_evaluation_result']
    assert not adapter.runtime.workers
    write_document(root/'backend/config/evaluationResult.json',{})
    assert client.get('/api/workspace/bootstrap',headers=header(owner)).json()['entries']['/v1/get_evaluation_result']=={}


def test_parallel_reads_wait_for_workspace_readiness(platform):
    from concurrent.futures import ThreadPoolExecutor
    client,adapter,users,_=platform
    actor=users[0]
    paths=['/v1/get_current_full_res','/v1/get_current_multi_full_res','/v1/get_all_published_tasks']
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses=list(pool.map(lambda path:client.get(path,headers=header(actor)),paths))
    assert [response.status_code for response in responses]==[200,200,200]
    assert len(responses[0].json()['ruler1'])==27
    assert len(responses[0].json()['ruler2'])==17
    assert len(responses[1].json()['ruler1'])==14
    assert len(responses[1].json()['ruler2'])==15
    arena=client.get('/v1/lmarena/leaderboard',headers=header(actor))
    assert arena.status_code==200 and arena.json()
    assert len(adapter.runtime.workers)==0, "Browsing must not start the Flask evaluation worker"
    assert client.get('/v1/dataset/counts',headers=header(actor)).json()=={}
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses=list(pool.map(lambda _:client.post('/v1/dataset/update/view',json={'dataset':'fixture','is_field':1},headers=header(actor)),range(20)))
    assert all(response.status_code==200 for response in responses)
    assert client.get('/v1/dataset/counts',headers=header(actor)).json()['1']['fixture']['view_count']==20


def test_html_bootstrap_verifies_session_without_exposing_credential(platform):
    import hashlib,re
    client,_,users,_=platform
    token=users[0]['access_token']
    client.cookies.set('icap_assets',token)
    response=client.get('/')
    payload=json.loads(re.search(r'<script id="icap-session" type="application/json">(.*?)</script>',response.text).group(1))
    assert payload['profile']['id']==users[0]['id']
    assert payload['fingerprint']==hashlib.sha256(token.encode()).hexdigest()
    assert token not in response.text
    assert response.headers['cache-control']=='no-store'
    client.post('/api/auth/logout',headers=header(users[0]))
    response=client.get('/')
    payload=json.loads(re.search(r'<script id="icap-session" type="application/json">(.*?)</script>',response.text).group(1))
    assert payload=={}


def test_source_and_credentials_are_not_public(platform):
    client,adapter,users,admin=platform
    client.cookies.clear()
    for path in ['/api/platform/capabilities','/v1/get_model_info','/llm_bench/app.js']:
        response=client.get(path)
        assert response.status_code==401
        assert response.headers['Server-Timing'].startswith('app;dur=')
    manifest=json.loads((Path(__file__).resolve().parents[2]/'frontend/dist/.vite/manifest.json').read_text('utf-8'))
    dependencies=set()
    def public_assets(key):
        if key in dependencies:return
        dependencies.add(key);row=manifest[key]
        for name in [row['file'],*row.get('css',[])]:
            assert client.get('/'+name).status_code==200,'Login dependency is blocked: '+name
        for name in row.get('imports',[]):public_assets(name)
    public_assets('index.html')
    public_assets('src/blue/views/Login.vue')
    entry=manifest['index.html']['file']
    assert client.get('/'+entry).headers['cache-control']=='public, max-age=31536000, immutable'
    feature=manifest['src/components/homePage.vue']['file']
    response=client.get('/'+feature)
    assert response.status_code==401 and response.headers['cache-control']=='no-store'
    response=client.get('/'+feature,headers=header(users[0]))
    assert response.status_code==200 and response.headers['cache-control']=='private, max-age=28800, immutable'
    response=client.get('/'+feature,headers={**header(users[0]),'Accept-Encoding':'identity'})
    assert response.status_code==200 and response.headers['cache-control'].startswith('private,')
    client.cookies.clear()
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
    for path in ['../../backend/config/provider_models.json','backend/config/provider_models.json','backend/yellow/server.py','./backend/config/provider_models.json','backend//config/provider_models.json']:
        assert client.get('/v1/download/file',params={'filepath':path},headers=h).status_code==403
        assert client.get('/v1/download/dataset_zip',params={'filepaths[]':path},headers=h).status_code==403


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
    assert identifier in read_document(root/'backend/config/common_testcase_cfg.json')
    client.put('/api/datasets/'+identifier,headers=h,json={'name':'private again','visibility':'private'})
    assert identifier not in {row['id'] for row in client.get('/api/datasets',headers=h2).json()}
    adapter.runtime.sync_resources(root,principal)
    assert identifier not in read_document(root/'backend/config/common_testcase_cfg.json')
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
    records=read_document(target/'backend/config/publishedReportTasks.json')
    assert len(records)==1
    shared=next(iter(records.values()))
    assert shared['can_edit'] is False
    copied=target/shared['published_filepath'];assert copied.read_bytes()==report.read_bytes()
    write_json(path,{})
    runtime.sync_resources(target,other)
    assert read_document(target/'backend/config/publishedReportTasks.json')=={}
    assert not copied.exists()
