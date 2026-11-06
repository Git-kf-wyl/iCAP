import copy
import io
import json

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.skill_evolution.schemas import JobInput
from test_skill_evolution import workspace, payload, wait


def case(identifier='one', output=None, **kwargs):
    return {'id':identifier, 'input':[{'type':'list','data':[{'role':'user','content':'Question'}]}],
            'key_steps':[], 'output':output or [{'type':'word','data':{'whitelist':['wrong']}}], **kwargs}


def test_presets_and_large_case_limits():
    rewrite = JobInput(**payload(preset='rewrite'))
    assert rewrite.output_weights == {'word':1,'format':1}
    assert json.loads(rewrite.format_example)[0]['topic'] == '个人身份'
    spreadsheet = JobInput(**payload(preset='spreadsheet'))
    assert spreadsheet.execution_mode == 'hermes'
    assert spreadsheet.judgment_weights == {'process':.4,'conciseness':.2,'result':.4}
    assert len(JobInput(**payload(dataset=[case(str(i)) for i in range(750)])).dataset) == 750
    assert JobInput(**payload(cases_limit='')).cases_limit is None
    with pytest.raises(ValidationError):
        JobInput(**payload(cases_limit=10001))


def test_case_formats_overrides_and_errors(workspace):
    _, app, _ = workspace
    svc = app.state.skill_service
    source = case(output=[{'type':'word','data':{'whitelist':['wrong']}}, {'type':'format','data':''}],
                  output_weights={'word':2,'format':0,'text_output':0}, pre_condition=[])
    config = svc.prepare(JobInput(**payload(dataset=[source], output_weights={'word':1,'format':1})))
    assert config['dataset'][0]['output_weights']['word'] == 2
    assert config['dataset'][0]['output_weights']['text'] == 0
    assert config['dataset'][0]['pre_condition'] == []
    original = copy.deepcopy(source)
    source['output_weights']['format'] = 1
    with pytest.raises(HTTPException, match='') as error:
        svc.prepare(JobInput(**payload(dataset=[source])))
    assert 'OUTPUT_FORMAT_EXAMPLE' in error.value.detail and 'one' in error.value.detail
    config = svc.prepare(JobInput(**payload(preset='rewrite',dataset=[source])))
    assert isinstance(config['dataset'][0]['output'][1]['data'], list)
    source = original
    source['input'][0]['data'] = json.dumps(source['input'][0]['data'])
    with pytest.raises(HTTPException):
        svc.prepare(JobInput(**payload(dataset=[source])))
    source['input'][0]['type'] = 'json'
    svc.prepare(JobInput(**payload(dataset=[source])))
    source['pre_condition'] = ['rm -rf /']
    with pytest.raises(HTTPException):
        svc.prepare(JobInput(**payload(dataset=[source])))


@pytest.mark.parametrize('engine',['opt','enhanced'])
def test_workers_honor_case_weights_and_case_count(workspace, engine):
    client, _, _ = workspace
    data = [case('override',output=[{'type':'word','data':{'whitelist':['wrong']}}, {'type':'onlyllm','data':'rubric.md'}],
                 output_weights={'word':0,'onlyllm':1}), case('hard-rule')]
    response = client.post('/api/skill-evolution/jobs',json=payload(engine,dataset=data,output_weights={'word':1,'onlyllm':0}))
    assert response.status_code == 201, response.text
    row = wait(client,response.json()['id'])
    assert row['status'] == 'completed', row
    scores = {r['id']: r['score'] for r in row['result']['rounds'][0]['cases']}
    assert scores == {'override':0,'hard-rule':100}
    assert row['case_count'] == 2


def test_managed_rubric_snapshot_survives_deletion(workspace):
    client, app, _ = workspace
    response = client.post('/api/skill-evolution/files/upload',files={'file':('rule.txt',b'Candidate: {candidate_output}\nReturn score JSON','text/plain')})
    assert response.status_code == 201, response.text
    meta = response.json()['items'][0]
    app.state.skill_service.stop.set()
    app.state.skill_service.thread.join(timeout=3)
    created = client.post('/api/skill-evolution/jobs',json=payload(dataset=[case(output=[{'type':'onlyllm','data':meta['path']}])]))
    assert created.status_code == 201, created.text
    identifier = created.json()['id']
    saved = app.state.skill_service.get(identifier)
    assert 'source_path' not in json.dumps(saved['config']['managed_assets'])
    snapshot = app.state.skill_service.root / identifier / 'assets' / saved['config']['dataset'][0]['output'][0]['data']
    assert snapshot.read_text() == 'Candidate: {candidate_output}\nReturn score JSON'
    assert client.delete('/api/skill-evolution/files/'+meta['id']).status_code == 200
    assert snapshot.is_file()
    assert 'managed_assets' not in created.json()['config']


def test_spreadsheet_prepares_managed_workbook_and_retains_steps(workspace):
    from openpyxl import Workbook
    client, app, _ = workspace
    stream=io.BytesIO(); wb=Workbook(); wb.active['J23']='old'; wb.save(stream)
    uploaded=client.post('/api/skill-evolution/files/upload',files={'file':('input.xlsx',stream.getvalue(),'application/octet-stream')}).json()['items'][0]
    data=case(output=[{'type':'device_state','data':'J23=January\nK23=<NONE>'}],input_path=uploaded['path'],
              output_weights={'device_state':1,'text_output':0})
    data['key_steps']=[{'description':'check workbook','weight':.4}]
    principal={'id':'admin','role':'admin'}
    cfg=app.state.skill_service.prepare(JobInput(**payload(preset='spreadsheet',dataset=[data])),principal)
    assert cfg['dataset'][0]['input_path'].startswith('managed/')
    assert cfg['dataset'][0]['key_steps'][0]['step_id']=='1'
    assert cfg['dataset'][0]['output_weights']['device_state']==1
    assert cfg['managed_assets'][0]['source_path']==uploaded['path']
    rejected=client.post('/api/skill-evolution/jobs',json={'name':'binary-reference','operation':'bootstrap','requirement':'Draft','managed_file_ids':[uploaded['id']]})
    assert rejected.status_code==422 and '二进制' in rejected.text

@pytest.mark.parametrize('engine',['opt','enhanced'])
def test_plain_rubric_receives_current_output(workspace, engine):
    client, _, requests = workspace
    created=client.post('/api/skill-evolution/jobs',json=payload(engine,rubric='仅依据这份专属规则评价当前候选回答。返回score和reason。')).json()
    row=wait(client,created['id'])
    assert row['status']=='completed',row
    assert any('这份专属规则' in m['content'] and '候选回答：wrong answer' in m['content'] for r in requests for m in r['messages'])


def test_enhanced_hermes_uses_case_rubric_without_legacy_helper(tmp_path):
    import subprocess, sys
    from pathlib import Path
    rubric=tmp_path/'rubric.txt'; rubric.write_text('Use the current answer and return score.',encoding='utf-8')
    code='''
import sys,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path('vendor/skill_evolution/enhanced').resolve()))
from app.skill_evolution.worker import patch_opt_judge,install_case_policy
patch_opt_judge()
cfg={'engine':'enhanced','execution_mode':'hermes','dataset':[{'id':'one','input':[{'type':'json','data':'[{"role":"user","content":"input"}]'}],'output_weights':{'onlyllm':1}}]}
install_case_policy(cfg)
from src.self_evolve.evaluators.components.session_analyzer import SessionAnalyzer
class Model:
 def generate(self,messages):
  assert 'current answer' in messages[0]['content'] and 'candidate-value' in messages[0]['content']
  return '{"score":25,"reason":"matched"}'
result=SessionAnalyzer(Model()).analyze(case_id='one',input_text='input',trajectory=[SimpleNamespace(role='assistant',content='candidate-value')],expected_outputs={'onlyllm':sys.argv[1]},judgment_weights={'process':0,'conciseness':0,'result':1},execution_mode='hermes')
assert result.output_scores['onlyllm']==25,result
analyzer=SessionAnalyzer(Model())
assert analyzer._analyze_format(final_output='[]',expected_format={'x':1})[0]==0
assert analyzer._analyze_format(final_output='{}',expected_format=[{'x':1}])[0]==0
assert analyzer._analyze_format(final_output='[]',expected_format=[{'x':1}])[0]==100
assert analyzer._analyze_format(final_output='{"x":2}',expected_format={'x':1})[0]==100
'''
    result=subprocess.run([sys.executable,'-c',code,str(rubric)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr

@pytest.mark.parametrize('engine',['opt','enhanced'])
def test_bootstrap_includes_script_references(workspace, engine):
    client, _, requests=workspace
    response=client.post('/api/skill-evolution/jobs',json={'name':'draft','engine':engine,'operation':'bootstrap','requirement':'Produce a draft','resources':[{'name':'reference.py','content':'# reference-only-marker\nprint(42)'}]})
    assert response.status_code==201,response.text
    job=wait(client,response.json()['id'])
    assert job['status']=='completed',job
    assert any('reference-only-marker' in m['content'] for r in requests for m in r['messages'])


def test_malformed_references_return_validation_error(workspace):
    _,app,_=workspace
    for item in (case(input_path={'bad':'path'}),case(output=[{'type':{},'data':'invalid'}]),case(output=[{'type':'onlyllm','data':{'bad':'path'}}])):
        with pytest.raises(HTTPException) as error:
            app.state.skill_service.prepare(JobInput(**payload(dataset=[item],execution_mode='hermes')))
        assert error.value.status_code==422
