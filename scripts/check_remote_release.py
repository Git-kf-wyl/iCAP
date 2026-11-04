"""Authenticated server-side smoke checks; prints no credentials or response bodies."""
from pathlib import Path
import hashlib
import json
import os
import pwd
import sys
import time
import httpx
from dotenv import dotenv_values

mode=sys.argv[1] if len(sys.argv)>1 else 'stage'
base='http://127.0.0.1:'+('8083' if mode=='stage' else '8081')
values=dotenv_values('/etc/icap/production.env')
data=Path('/var/lib/icap-yellow-check' if mode=='stage' else '/var/lib/icap')
account=pwd.getpwnam('icap')
with httpx.Client(base_url=base,trust_env=False,timeout=180) as client:
    for attempt in range(30):
        try:
            if client.get('/health').status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(1)
    response=client.post('/api/auth/login',json={'username':values['INNOVATION_ADMIN_USER'],'password':values['INNOVATION_ADMIN_PASSWORD']})
    assert response.status_code==200,'production account login failed'
    auth=response.json();headers={'Authorization':'Bearer '+auth['access_token']}
    for endpoint in ['/api/platform/capabilities','/api/models','/api/datasets','/api/agent-benchmarks','/api/skill-evolution/capabilities','/api/monitor','/v1/get_model_info','/v1/get_testcase_info?is_field=2','/v1/get_all_report_tasks']:
        response=client.get(endpoint,headers=headers)
        assert response.status_code==200,endpoint+' failed: '+str(response.status_code)
        print('PASS',endpoint.split('?')[0],flush=True)
        if endpoint=='/api/models':models=response.json()
        if endpoint=='/api/skill-evolution/capabilities':assert 'hermes' in response.json()['execution_modes'],'Hermes unavailable'
        if endpoint=='/api/monitor':assert response.json()['simulated'] is False
        if endpoint=='/v1/get_model_info':
            assert all(not e['api_key'] for row in response.json() for e in row['config']['api_params'])
    for path in ['/.env','/.git/config','/backend/adapter.py','/data/LLMInferencer.py','/api/school/jobs','/api/data-governance/jobs']:
        assert client.get(path).status_code==404,path+' accessible'
    anonymous=httpx.get(base+'/v1/get_model_info',trust_env=False)
    assert anonymous.status_code==401
    response=client.post('/api/agents/chat/stream',headers=headers,json={'model_id':models[0]['id'],'message':'请只回复 OK','max_tokens':32,'thinking':False})
    assert response.status_code==200 and 'event: chunk' in response.text and 'event: error' not in response.text,'real model chat failed'
    print('PASS real model response and source access guards',flush=True)
    if mode=='stage':
        actor=client.get('/api/auth/me',headers=headers).json()
        root=data/'yellow/users'/hashlib.sha256(str(actor['id']).encode()).hexdigest()[:24]
        path=root/'backend/config/common_testcase_cfg.json'
        cfg=json.loads(path.read_text());row=cfg['aime25']
        folder=root/row['local_path'];folder.mkdir(parents=True,exist_ok=True)
        fixture=folder/'AIME2025-I.jsonl';fixture.write_text('{"question":"Compute 1+1.","answer":"2"}\n')
        row.update(file_list=['AIME2025-I.jsonl'],availability='ready',status=1)
        path.write_text(json.dumps(cfg,ensure_ascii=False))
        for p in [folder,fixture,path]:os.chown(p,account.pw_uid,account.pw_gid)
        payload=json.loads(Path('/tmp/stage-ruler-request.json').read_text())
        payload['model_id']=next((m['id'] for m in models if m['id']=='deepseek-flash'),models[0]['id'])
        response=client.post('/v1/run_testcase_ruler1',headers=headers,json=payload)
        assert response.status_code==200,'original Ruler1 submit failed'
        identifier=response.json()['task_id']
        for _ in range(90):
            time.sleep(2)
            response=client.get('/v1/check_run_test_progress/'+identifier,headers=headers)
            task=response.json()
            if task.get('status') in ('completed','failed'):break
        assert task.get('status')=='completed','original Ruler1 evaluation failed'
        print('PASS original Ruler1 real API evaluation',flush=True)
        # Free local report conversion, from a deliberately separate staging fixture.
        from pptx import Presentation
        ppt=root/'backend/report/output/deployment-check.pptx'
        deck=Presentation();deck.slides.add_slide(deck.slide_layouts[0]).shapes.title.text='iCAP deployment check';deck.save(ppt)
        os.chown(ppt,account.pw_uid,account.pw_gid)
        response=client.get('/v1/preview/report/pdf',headers=headers,params={'filepath':ppt.relative_to(root).as_posix()})
        assert response.status_code==200 and response.content.startswith(b'%PDF-'),'report PDF conversion failed'
        print('PASS report PDF preview',flush=True)
print('Release smoke checks complete',flush=True)
