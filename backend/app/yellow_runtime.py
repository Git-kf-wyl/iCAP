"""Private per-account workspaces for the original Yellow business services.

The public adapter authenticates every request. Workers bind loopback only and
require a random process secret; accounts never share mutable config or output.
"""
from __future__ import annotations

import atexit
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import shutil

import httpx
from fastapi import HTTPException

CODE = Path(__file__).resolve().parents[1] / 'yellow'

def write_json(path: Path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+secrets.token_hex(5)+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
    temp.chmod(0o600)
    temp.replace(path)

def legacy_model(model: dict, registry, *, full=False) -> dict:
    params=[]
    for endpoint in model.get('endpoints',[]):
        values=[{'key':key,'value':endpoint.get(key,default),'min':low,'max':high,'step':step,'enable':True,'type':'number'}
                for key,default,low,high,step in [('temperature',1,0,2,.1),('top_p',1,0,1,.01),('top_k',40,0,1000,1),('max_tokens',4096,1,65536,1)]]
        params.append({'endpoint':endpoint['url'] if full else '/v1/stream_chat',
                       'api_key':registry.api_key(endpoint) if full else '',
                       'is_openai_format':True,'is_available':True,'params':values})
    first=model.get('endpoints',[{}])[0] if model.get('endpoints') else {}
    return {'model_id':model['id'],'status':1,'is_available':bool(params),
            'visibility':model.get('visibility','public'),'owner_user_id':model.get('owner_user_id'),
            'can_edit':model.get('can_edit',False),
            'info':{'model_name':model['name'],'display_name':model['name'],'model_desc':model.get('description') or f"{model.get('provider','')} · 已接入 API 服务",
                    'model_doc':'','series':model.get('provider',''),'vendor':model.get('provider',''),
                    'tags':['chat','reason','tools'],'category':['LLM'],'size':'','context_length':first.get('max_context_length',32768),
                    'isInternalDeployed':bool(first.get('self_deployed')),'creation_date':'','zone':'云端','logo_url':model.get('logo_url','')},
            'config':{'filter':{'head':'','tail':''},'extra_headers':[],'is_openai_format':True,'api_params_available':params,'api_params':params,'params':params[0]['params'] if params else []}}

class YellowRuntime:
    def __init__(self, base: Path, registry, store):
        self.base=base/'yellow'
        self.registry=registry
        self.store=store
        self.workers={}
        self.lock=threading.RLock()
        self.base.mkdir(parents=True,exist_ok=True)
        self.catalog=self.base/'resources.json'
        if not self.catalog.exists():write_json(self.catalog,{})
        atexit.register(self.shutdown)

    def workspace(self, actor):
        key=hashlib.sha256(str(actor['id']).encode()).hexdigest()[:24]
        return self.base/'users'/key

    def initialize(self,actor):
        # Parallel homepage reads may initialize the same new account together.
        with self.lock:
            return self._initialize(actor)

    def _initialize(self,actor):
        root=self.workspace(actor)
        first=not (root/'backend/config/tasks.json').exists()
        for folder in ['backend/config','backend/database','backend/report/output','uploads','outputs','logs','testsuite/TestSuite','testsuite/TestSuiteRulerII','testsuite/TestSuiteDev','paper_agent_results']:
            (root/folder).mkdir(parents=True,exist_ok=True)
        if first:
            for name in ['common_testcase_cfg.json','field_testcase_cfg.json','dev_testcase_cfg.json']:
                write_json(root/'backend/config'/name,json.loads((CODE/'seed'/name).read_text('utf-8')))
            for name in ['tasks','evaluationResult','reportTasks','publishedReportTasks','ruler1_cheat','ruler2_cheat','ruler1_cheat_multi','ruler2_cheat_multi','min_cheat','special_model_list','eval_model_list','eval_report_list','training_dataset']:
                write_json(root/'backend/config'/f'{name}.json',{})
            for name in ['model_to_deploy','feedBack_list']:
                write_json(root/'backend/config'/f'{name}.json',[])
            (root/'backend/config/progress_list.jsonl').touch()
            for name in ['aisf_member','aisf_user_member','admin_member','ruler2_member']:
                (root/'backend/database'/f'{name}.csv').write_text('user\n'+actor['username']+'\n',encoding='utf-8')
            for name in ['eval_model_list','eval_report_list']:
                write_json(root/'backend/report'/f'{name}.json',{})
            # The workbook belongs to the rewrite service, rather than backend root.
            workbook=CODE/'services/aisf_rewrite/上下文数据标注09121440.xlsx'
            if workbook.is_file():
                target=root/'testsuite/TestSuiteRulerII/aisf_rewrite'
                target.mkdir(exist_ok=True)
                shutil.copy2(workbook,target/workbook.name)
                path=root/'backend/config/field_testcase_cfg.json'
                cfg=json.loads(path.read_text('utf-8'))
                cfg['aisf_rewrite']={'dataset_name':'上下文改写','input_path':'testsuite/TestSuiteRulerII/aisf_rewrite','description':'原版上下文改写评测数据',
                    'few_shot_num':0,'few_shot_file_path':[],'subset_list':[],'default_subsets':[],'metric_list':['accuracy'],
                    'testcase_tags':['改写'],'file_list':[workbook.name],'few_file_list':[],'is_field':2,'status':1,
                    'is_open_source':False,'availability':'ready','is_published':True,'register':'admin'}
                write_json(path,cfg)
        workbook=CODE/'services/aisf_rewrite/上下文数据标注09121440.xlsx'
        target=root/'testsuite/TestSuiteRulerII/aisf_rewrite'
        if workbook.is_file() and not (target/workbook.name).is_file():
            target.mkdir(parents=True,exist_ok=True)
            shutil.copy2(workbook,target/workbook.name)
            path=root/'backend/config/field_testcase_cfg.json'
            cfg=json.loads(path.read_text('utf-8'))
            cfg.setdefault('aisf_rewrite',{'dataset_name':'上下文改写','input_path':'testsuite/TestSuiteRulerII/aisf_rewrite',
                'description':'原版上下文改写评测数据','few_shot_num':0,'few_shot_file_path':[],
                'subset_list':[],'default_subsets':[],'metric_list':['accuracy'],'testcase_tags':['改写'],
                'file_list':[workbook.name],'few_file_list':[],'is_field':2,'status':1,'is_open_source':False,
                'availability':'ready','is_published':True,'register':'admin'})
            write_json(path,cfg)
        return root

    def sync_models(self,root,actor,record):
        public=self.registry.list_models(actor)
        rows=[];providers=[]
        for model in public:
            raw=self.registry.get_model(model['id'],actor)
            provider=copy.deepcopy(raw)
            for endpoint in provider['endpoints']:endpoint['api_key']=self.registry.api_key(endpoint)
            providers.append(provider)
            row=legacy_model(raw,self.registry,full=True)
            # Evaluation requests must use the immutable API ID, never a display alias.
            row['info']['model_name']=raw['id']
            for endpoint in row['config']['api_params_available']:
                endpoint['endpoint']=f"http://127.0.0.1:{record['port']}/_model/v1"
                endpoint['api_key']=record['secret']
            rows.append(row)
        write_json(root/'backend/config/model_cfg.json',rows)
        write_json(root/'backend/config/provider_models.json',providers)
        return public

    def sync_resources(self,root,actor):
        """Mirror public resources read-only; keep all mutation at the owner workspace."""
        from .access import can_view
        catalog=self.resource_catalog()
        for field in ['common','field','dev']:
            filename=f'{field}_testcase_cfg.json'
            path=root/'backend/config'/filename
            config=json.loads(path.read_text('utf-8'))
            # Remove previously public resources when their owner makes them private.
            for identifier,row in list(config.items()):
                if row.get('_shared_owner'):
                    info=catalog.get(identifier)
                    source_path=Path(info['workspace'])/'backend/config'/filename if info else None
                    original=json.loads(source_path.read_text('utf-8')).get(identifier) if source_path and source_path.is_file() else None
                    if not info or not original or original.get('status')!=1 or (info['visibility']!='public' and actor['role']!='admin'):
                        config.pop(identifier)
                        target=root/(row.get('local_path') or row.get('input_path','__missing'))
                        if target.is_symlink():target.unlink()
                        elif target.is_dir() and target.resolve().is_relative_to((root/'testsuite').resolve()):shutil.rmtree(target)
            for identifier,info in catalog.items():
                if info['owner_user_id']==actor['id'] or (info['visibility']!='public' and actor['role']!='admin'):continue
                source_root=Path(info['workspace'])
                source_cfg=source_root/'backend/config'/filename
                if not source_cfg.is_file():continue
                source=json.loads(source_cfg.read_text('utf-8')).get(identifier)
                if not source or source.get('status')!=1:continue
                row=copy.deepcopy(source)
                relative=row.get('local_path') or row.get('input_path')
                if not relative:continue
                source_dir=(source_root/relative).resolve()
                if not source_dir.is_relative_to(source_root.resolve()):continue
                target=root/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                if source_dir.is_dir() and not target.exists():
                    # Symlinks are read-only from HTTP: adapter denies mutation of shared IDs/paths.
                    if os.name=='nt':shutil.copytree(source_dir,target,dirs_exist_ok=True)
                    else:target.symlink_to(source_dir,target_is_directory=True)
                row['_shared_owner']=info['owner_user_id']
                row['can_edit']=False
                config[identifier]=row
            # Preserve existing Blue uploads in the original Yellow dataset pages.
            if field=='common':
                allowed_ids={ds['id'] for ds in self.store.snapshot()['datasets'] if can_view(ds,actor) and ds.get('files') and ds.get('category')!='训练集'}
                for identifier,row in list(config.items()):
                    if row.get('_blue_dataset') and identifier not in allowed_ids:
                        config.pop(identifier)
                        target=root/'testsuite/TestSuite'/identifier
                        if target.is_dir() and target.resolve().is_relative_to((root/'testsuite/TestSuite').resolve()):shutil.rmtree(target)
                for ds in self.store.snapshot()['datasets']:
                    if not can_view(ds,actor) or not ds.get('files') or ds.get('category')=='训练集':continue
                    target=root/'testsuite/TestSuite'/ds['id']
                    target.mkdir(parents=True,exist_ok=True)
                    files=[]
                    for entry in ds['files']:
                        src=self.store.uploads/ds['id']/entry['id']
                        if not src.is_file():
                            src=self.store.uploads/entry.get('storage_name','__missing')
                        if src.is_file():
                            filename=Path(entry.get('name') or entry.get('filename') or src.name).name
                            shutil.copy2(src,target/filename);files.append(filename)
                    if files:
                        config[ds['id']]={'dataset_name':ds['name'],'local_path':str(target.relative_to(root)).replace('\\','/'),
                            'few_shot_num':0,'description':ds.get('description',''),'subset_list':['default'],'default_subsets':['default'],
                            'testcase_tags':['自定义'],'metric_list':['accuracy'],'file_list':files,'few_file_list':[],
                            'is_field':1,'status':1,'is_published':ds.get('visibility')=='public','register':'历史资源','availability':'ready',
                            'can_edit':False,'_blue_dataset':True}
            write_json(path,config)
        # Publishing a report explicitly shares its document with logged-in users.
        published_path=root/'backend/config/publishedReportTasks.json'
        published=json.loads(published_path.read_text('utf-8'))
        own={key:value for key,value in published.items() if not value.get('_shared_owner')}
        retained=set()
        for source_root in (self.base/'users').glob('*'):
            if source_root==root:continue
            path=source_root/'backend/config/publishedReportTasks.json'
            if not path.is_file():continue
            for key,value in json.loads(path.read_text('utf-8')).items():
                if value.get('_shared_owner') or value.get('status')!='completed':continue
                raw=value.get('published_filepath')
                if not raw:continue
                source=(source_root/raw).resolve()
                if not source.is_relative_to((source_root/'backend/report/output').resolve()) or not source.is_file() or source.suffix.lower() not in ('.ppt','.pptx','.pdf'):continue
                target=root/'backend/report/output/shared'/source_root.name/source.name
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.is_file() or target.stat().st_mtime<source.stat().st_mtime or target.stat().st_size!=source.stat().st_size:shutil.copy2(source,target)
                row=copy.deepcopy(value)
                row['_shared_owner']=source_root.name;row['can_edit']=False
                row['id']=source_root.name+'-'+str(value.get('id') or key)
                row['published_filepath']=target.relative_to(root).as_posix()
                own[row['id']]=row;retained.add(row['published_filepath'])
        for key,value in published.items():
            if value.get('_shared_owner') and value.get('published_filepath') not in retained:
                target=(root/value.get('published_filepath','')).resolve()
                if target.is_relative_to((root/'backend/report/output/shared').resolve()) and target.is_file():target.unlink()
        write_json(published_path,own)

    def get(self,actor):
        with self.lock:
            key=actor['id'];root=self.initialize(actor)
            self.sync_resources(root,actor)
            record=self.workers.get(key)
            if record and record['process'].poll() is None:
                self.sync_models(root,actor,record)
                return record
            if sum(r['process'].poll() is None for r in self.workers.values()) >= 16:
                raise HTTPException(503,'工作空间运行数量已达上限，请稍后再试')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            token=secrets.token_urlsafe(40)
            available=self.sync_models(root,actor,{'port':port,'secret':token})
            env=dict(os.environ)
            for name in list(env):
                if name.startswith(('INNOVATION_ADMIN_','SKILL_EVOLVE_')) or name in ('INNOVATION_SECRET_KEY',):env.pop(name,None)
            env['YELLOW_JUDGE_MODEL']=available[0]['id'] if available else ''
            env.update(YELLOW_WORKSPACE=str(root),YELLOW_WORKER_PORT=str(port),YELLOW_WORKER_SECRET=token,
                       HOME=str(root),USERPROFILE=str(root),PYTHONUNBUFFERED='1',PYTHONIOENCODING='utf-8',
                       NO_PROXY='127.0.0.1,localhost,::1',
                       PYTHONPATH=os.pathsep.join([str(CODE),str(CODE/'CCNRuler1EvalScope'),str(CODE/'CCNRuler2EvalScope')]))
            log=(root/'runtime.log').open('ab',buffering=0)
            options={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
            process=subprocess.Popen([sys.executable,str(CODE/'worker.py')],cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,**options)
            record={'process':process,'port':port,'secret':token,'root':root,'log':log}
            self.workers[key]=record
        deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            if process.poll() is not None:raise HTTPException(503,'Yellow 工作空间启动失败，请查看管理员运行日志')
            try:
                with httpx.Client(trust_env=False,timeout=2) as client:
                    response=client.get(f'http://127.0.0.1:{port}/_ready',headers={'X-iCAP-Worker':token})
                    if response.is_success:
                        record['capabilities']=response.json()
                        return record
            except httpx.HTTPError:pass
            time.sleep(.2)
        raise HTTPException(503,'Yellow 工作空间正在启动，请稍后重试')

    def shutdown(self):
        for record in list(self.workers.values()):
            process=record['process']
            if process.poll() is None:
                try:
                    if os.name!='nt':
                        import signal
                        os.killpg(process.pid,signal.SIGTERM)
                    else:process.terminate()
                except ProcessLookupError:pass
            record['log'].close()

    def resource_catalog(self):
        return json.loads(self.catalog.read_text('utf-8'))

    def register_dataset(self,actor,body):
        identifier=body.get('dataset_id','')
        # Original server concatenates this ID into paths; reject traversal here.
        if not isinstance(identifier,str) or not identifier or len(identifier)>160 or any(c in identifier for c in '/\\:') or identifier.startswith('.'):
            raise HTTPException(422,'数据集 ID 不能包含路径或以点开头')
        with self.lock:
            data=self.resource_catalog()
            old=data.get(identifier)
            if old and old['owner_user_id']!=actor['id'] and actor['role']!='admin':
                raise HTTPException(409,'数据集 ID 已存在')
            data[identifier]={'owner_user_id':actor['id'],'workspace':str(self.workspace(actor)),
                              'visibility':body.get('visibility') or ('public' if body.get('is_published') else 'private'),
                              'is_field':str(body.get('is_field',1))}
            write_json(self.catalog,data)

    def require_dataset_edit(self,actor,identifier):
        row=self.resource_catalog().get(identifier)
        if row is None:
            if actor['role']!='admin':raise HTTPException(403,'只有管理员可以修改平台预置数据集')
        elif row['owner_user_id']!=actor['id']:
            raise HTTPException(403,'只能在资源所属工作空间中修改数据集')
