"""iCAP's single authenticated, same-origin HTTP entry point.

Blue accounts, model registry, Skill/Hermes and AgentCompass remain native APIs.
Yellow's original business routes run in private per-account workspaces; no
Nginx routing, corporate SSO, upstream model credentials or old scores are used.
"""
from __future__ import annotations
from state_storage import read_document,state_exists,state_isfile

import asyncio
import hashlib
import json
import re
import time
import logging
from collections import deque
from pathlib import Path, PurePosixPath

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.main import create_app, ChatInput, DatasetInput, now
from app.access import require_edit
from app.yellow_runtime import YellowRuntime, legacy_model, write_json

app=create_app()
from app.private_assets import protect_assets
protect_assets(app)

@app.middleware('http')
async def server_timing(request:Request,call_next):
    started=time.perf_counter()
    response=await call_next(request)
    elapsed=(time.perf_counter()-started)*1000
    response.headers['Server-Timing']=f'app;dur={elapsed:.1f}'
    if elapsed>1000 and request.url.path.startswith(('/api/','/v1/')):
        logging.getLogger('icap.web').warning('slow_request %s %s %.0fms',request.method,request.url.path,elapsed)
    return response
# Register all APIs before the native SPA fallback.
spa=[r for r in app.router.routes if getattr(r,'path',None)=='/{spa_path:path}']
app.router.routes[:]=[r for r in app.router.routes if r not in spa and not getattr(r,'path','').startswith(('/api/school','/api/data-governance'))]
runtime=YellowRuntime(app.state.store.base,app.state.registry,app.state.store)
app.state.yellow=runtime
from app.hub_downloads import HubDownloads
hubs=HubDownloads(runtime,app.state.store)
native_chat=next(r.endpoint for r in app.router.routes if getattr(r,'path','')=='/api/agents/chat/stream')
boot_reports={}

@app.post('/v1/dataset/update/view')
async def dataset_view(request:Request):
    actor=authorized(request)
    try:body=await request.json()
    except ValueError:raise HTTPException(422,'请求体必须为 JSON')
    identifier=body.get('dataset');group=body.get('is_field')
    if not isinstance(identifier,str) or not identifier or len(identifier)>160 or str(group) not in {'1','2','3'}:
        raise HTTPException(422,'数据集和分组无效')
    def update():
        from state_storage import increment_dataset_counter
        root=runtime.initialize(actor)
        increment_dataset_counter(root/'backend/config/dataset_download_view_count.json',group,identifier,'view_count')
    await asyncio.to_thread(update)
    return {'message':'成功'}

@app.post('/api/client-errors',status_code=204)
async def client_error(request:Request):
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>4096:raise HTTPException(413,'诊断内容过大')
    try:body=json.loads(content)
    except (ValueError,TypeError):raise HTTPException(400,'诊断格式无效')
    if not isinstance(body,dict) or body.get('kind') not in {'resource','runtime','navigation'}:raise HTTPException(400,'诊断类型无效')
    key=request.client.host if request.client else ''
    now_time=time.monotonic()
    if len(boot_reports)>1024:boot_reports.clear()
    reports=boot_reports.setdefault(key,deque())
    while reports and reports[0]<now_time-60:reports.popleft()
    if len(reports)<10:
        reports.append(now_time)
        message=re.sub(r'sk-[A-Za-z0-9_-]{16,}','[redacted]',str(body.get('message','')))[:180]
        path=str(body.get('path','')).split('?')[0][:240]
        logging.getLogger('icap.web').warning('frontend_boot %s',json.dumps({'kind':body['kind'],'path':path,'message':message},ensure_ascii=False))
    return Response(status_code=204)

def authorized(request: Request):
    header=request.headers.get('authorization','')
    if not header.startswith('Bearer ') and request.method=='GET' and request.url.path.startswith(('/v1/download/','/v1/preview/','/v1/templates/','/v1/paper_agent/results/','/v1/paper_agent/search_results/')):
        token=request.cookies.get('icap_assets','')
        if token:header='Bearer '+token
    if not header.startswith('Bearer '):raise HTTPException(401,'请先登录')
    return app.state.auth.current(header[7:])

@app.put('/api/datasets/{identifier}')
def update_dataset(identifier:str,body:DatasetInput,actor=Depends(authorized)):
    def update(data):
        row=next((row for row in data['datasets'] if row['id']==identifier),None)
        if not row:raise HTTPException(404,'资源不存在')
        require_edit(row,actor)
        row.update(body.model_dump(),updated_at=now())
        return row
    return app.state.store.update(update)

@app.api_route('/v1/{provider}_download/{action}',methods=['GET','POST'])
async def hub_api(provider:str,action:str,request:Request,actor=Depends(authorized)):
    if provider not in ('hg','ms'):raise HTTPException(404,'下载站点不存在')
    if action=='files_info' and request.method=='GET':return await asyncio.to_thread(hubs.info,request.query_params.get('url',''),provider)
    if action=='download_status' and request.method=='GET':return hubs.status(actor,request.query_params.get('task_id',''))
    if action=='backends':return {'status':'success','backends':[{'host':'当前资源库','status':'ok'}]}
    if request.method=='POST':
        body=await request.json()
        if action=='download_files':return await asyncio.to_thread(hubs.start,actor,provider,body)
        if action=='upload_files':return await asyncio.to_thread(hubs.register,actor,body)
    raise HTTPException(404,'下载操作不存在')

@app.get('/v1/templates/evaluation-report.docx')
def evaluation_template(actor=Depends(authorized)):
    from fastapi.responses import FileResponse
    return FileResponse(Path(__file__).parent/'yellow/templates/EvaluationReport.docx',filename='EvaluationReport.docx')

@app.get('/v1/preview/report/pdf')
async def report_pdf(filepath:str,actor=Depends(authorized)):
    root=await asyncio.to_thread(runtime.initialize,actor)
    validate_paths(filepath,root,'filepath')
    from app.report_preview import preview_pdf
    return await preview_pdf(root,filepath)

@app.get('/v1/model_shelf.xlsx')
def shelf(actor=Depends(authorized)):
    from io import BytesIO
    from openpyxl import Workbook
    book=Workbook();sheet=book.active;sheet.title='已接入模型'
    sheet.append(['模型名称','模型厂商','模型类型','模型介绍','部署方式'])
    for row in app.state.registry.list_models(actor):sheet.append([row['name'],row['provider'],'LLM',row['id'],'API 服务'])
    body=BytesIO();book.save(body)
    return Response(body.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.get('/api/platform/capabilities')
def capabilities(actor=Depends(authorized)):
    return {'interface':'yellow','upstream':'17862a2c6c58b96e611a99c9e71642906b1ba050',
            'features':['models','chat','datasets','evaluations','reports','papers','skill-evolution','agentcompass'],
            'external_services':{'phone_lab':False,'vla_devices':False,'dify':False,'coze':False,'owl':False},
            'disabled':['ai-school','data-pipeline']}

def models(actor):
    registry=app.state.registry
    return [legacy_model(row,registry) for row in registry.list_models(actor)]

@app.get('/v1/get_model_info')
def model_info(actor=Depends(authorized)):
    return models(actor)

@app.post('/v1/get_one_model_info')
async def one_model(request:Request,actor=Depends(authorized)):
    body=await request.json()
    row=next((r for r in models(actor) if r['model_id']==body.get('model_id')),None)
    if not row:raise HTTPException(404,'模型不存在')
    return row

@app.post('/v1/delete_model')
async def delete_model(request:Request,actor=Depends(authorized)):
    body=await request.json()
    for identifier in (body if isinstance(body,list) else [body.get('model_id')]):
        app.state.registry.delete(identifier,actor)
    return {'status':'success'}

@app.post('/v1/register_model')
@app.post('/v1/modify_model')
async def write_model(actor=Depends(authorized)):
    raise HTTPException(422,'请使用模型连接管理注册或编辑模型，支持多个端点和思考配置')

@app.post('/v1/stream_chat')
@app.post('/v1/chat')
async def stream_chat(request:Request,actor=Depends(authorized)):
    data=await request.json()
    if data.get('file_path'):
        raise HTTPException(422,'当前接入的是文本模型，请移除音频、图片或其他附件')
    identifier=data.get('model') or data.get('model_id')
    query=data.get('query','')
    config=data.get('config') or {}
    if isinstance(config,list):config={p['key']:p.get('value') for p in config if isinstance(p,dict) and 'key' in p}
    if not isinstance(config,dict):raise HTTPException(422,'模型参数必须为对象')
    root=await asyncio.to_thread(runtime.initialize,actor)
    key=hashlib.sha256((str(data.get('chat_id','default'))+'|'+str(identifier)).encode()).hexdigest()
    path=root/'chats'/f'{key}.json'
    history=read_document(path) if state_isfile(path) else []
    body=ChatInput(model_id=identifier,message=query,history=history[-20:],thinking=bool(data.get('isThink')),
                   **{k:config[k] for k in ['top_p','temperature','top_k','max_tokens'] if config.get(k) is not None})
    response=await native_chat(body,actor)
    async def stream():
        result='';reasoning=False;pending='';failed=False
        async for chunk in response.body_iterator:
            pending+=chunk.decode() if isinstance(chunk,bytes) else chunk
            while '\n\n' in pending:
                event,pending=pending.split('\n\n',1)
                name=next((line[7:] for line in event.splitlines() if line.startswith('event: ')),'')
                raw=next((line[6:] for line in event.splitlines() if line.startswith('data: ')),'{}')
                payload=json.loads(raw)
                text=''
                if name=='reasoning':
                    if not reasoning:text='<think>\n';reasoning=True
                    text+=payload.get('text','')
                elif name=='chunk':
                    if reasoning:text='\n</think>\n';reasoning=False
                    value=payload.get('text','');result+=value;text+=value
                elif name=='error':failed=True;text='\n请求失败：'+payload.get('message','模型服务错误')
                if text:
                    yield 'data: '+text.replace('\n','\ndata: ')+'\n\n'
        if result and not failed:
            await asyncio.to_thread(write_json,path,(history+[{'role':'user','content':query},{'role':'assistant','content':result}])[-20:])
        yield 'data: [DONE]\n\n'
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

def validate_paths(value,root:Path,key='',allow_shared=True):
    """Validate every client-provided path before an original handler sees it."""
    if isinstance(value,dict):
        for k,v in value.items():validate_paths(v,root,k,allow_shared)
    elif isinstance(value,list):
        for v in value:validate_paths(v,root,key,allow_shared)
    elif isinstance(value,str):
        if '\x00' in value:raise HTTPException(422,'参数包含无效字符')
        path_key=key.lower().endswith(('_path','_paths','_dir')) or key.lower() in {'filepath','filepaths','files','folder','file_path','folder_path','directory','local_path','input_path','path','uuid_val','use_cache','file_list','few_file_list','prompt_file','test_file','filename','file_name','dataset_id','business_name','task_id','model_id','model_name','model_names','dataset','datasets','dataset_name','subset','zip_name','report_name','id'}
        if path_key:
            clean=value.replace('\\','/')
            if '..' in clean.split('/') or clean.startswith(('/','~')) or re.match(r'^[a-zA-Z]:',clean):
                raise HTTPException(403,'仅允许访问当前工作空间中的资源')
            clean=str(PurePosixPath(clean))
            lowered=clean.lower()
            if (lowered=='backend' or lowered.startswith(('backend/','services/','utils/','.git/','.env'))) and not lowered.startswith('backend/report/output/'):
                raise HTTPException(403,'不允许访问服务代码或配置')
            if key.lower() in ('filepath','filepaths','files','local_path','input_path','file_path','folder_path','directory','path','use_cache') and clean:
                resolved=(root/clean).resolve()
                if not resolved.is_relative_to(root.resolve()):
                    # Public dataset links point only to registered dataset directories.
                    allowed=False
                    for record in runtime.resource_catalog().values():
                        if not allow_shared or record.get('visibility')!='public':continue
                        owner=Path(record['workspace']).resolve()
                        if resolved.is_relative_to(owner/'testsuite'):allowed=True;break
                    if not allowed:raise HTTPException(403,'资源路径超出工作空间')
        if key.lower()=='url':
            from urllib.parse import urlsplit
            parsed=urlsplit(value)
            allowed=('arxiv.org','huggingface.co','modelscope.cn','modelscope.com','hf-mirror.com')
            if parsed.scheme!='https' or not any(parsed.hostname==host or (parsed.hostname or '').endswith('.'+host) for host in allowed):
                raise HTTPException(422,'下载地址必须是受支持的公开论文或模型站点 HTTPS 地址')

DENIED={'login','logout','get_pubkey','cont_online_users','user_statistics/apply_api_key','user_statistics/get_api_key','user_statistics/refresh_dept_cache'}
EXTERNAL_PREFIXES=('api/','ai_school','ai-school','school/','deployment/','deep_research','call_agent','call_hjfy','dsh-proxy')
EDIT_DATASETS={'edit_testcase_ruler','delete_testcase_ruler','update_testcase_in_use'}
RUNS={'run_testcase_ruler1','run_testcase_ruler2','run_testcase_dev','run_vlm_ruler1','run_aisf_release','run_simultaneous_interpretation','run_testcase_mcp_atlas'}

def clean_response(value,secrets_to_hide=()):
    if isinstance(value,dict):
        return {k:('' if k.lower() in ('api_key','authorization','password','private_key','token','key_env') else clean_response(v,secrets_to_hide)) for k,v in value.items()}
    if isinstance(value,list):return [clean_response(v,secrets_to_hide) for v in value]
    if isinstance(value,str):
        for secret in secrets_to_hide:
            if len(secret)>8:value=value.replace(secret,'[redacted]')
        value=re.sub(r'sk-[A-Za-z0-9_-]{16,}','[redacted]',value)
    return value

@app.api_route('/v1/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE'])
async def yellow_api(path:str,request:Request,actor=Depends(authorized)):
    if path in DENIED or path.startswith(EXTERNAL_PREFIXES):
        raise HTTPException(503,'此功能依赖的外部服务尚未部署；当前账户与模型访问由 iCAP 管理')
    if path=='run_simultaneous_interpretation':raise HTTPException(422,'当前 DeepSeek 接口不支持语音识别或语音合成')
    root=await asyncio.to_thread(runtime.initialize,actor)
    query=list(request.query_params.multi_items())
    for key,value in query:validate_paths(value,root,key.removesuffix('[]'))
    from app.yellow_reads import FAST_READS,read_business
    if request.method=='GET' and path in FAST_READS:
        result=await asyncio.to_thread(read_business,runtime,actor,path,dict(query))
        if result is not None:return clean_response(result)
    data=None;content=await request.body()
    headers={'Content-Type':request.headers.get('content-type','application/json')}
    if 'application/json' in headers['Content-Type'] and content:
        try:data=json.loads(content)
        except ValueError:raise HTTPException(422,'请求体必须为 JSON')
        validate_paths(data,root,allow_shared=path in RUNS or path.startswith(('get_','retrieve/')))
        if isinstance(data,dict):
            # Identity always comes from the authenticated account, never a form.
            for field in ['username','userName','user_id','register','publisher']:
                if field in data:data[field]=actor['username']
            if path in EDIT_DATASETS:runtime.require_dataset_edit(actor,data.get('dataset_id',''))
            if path in {'delete_published_task','update_published_report'}:
                published=read_document(root/'backend/config/publishedReportTasks.json')
                row=published.get(data.get('id',''),{})
                if row.get('_shared_owner'):raise HTTPException(403,'只有报告发布者可以修改报告')
            if path in RUNS:
                data['eval_type']='service'
                data.setdefault('evaluationType','language')
                data['assessmentType']='通用评估(Ruler1)' if path=='run_testcase_ruler1' else '领域评估(Ruler2)'
                if data.get('limit') not in (None,''):
                    try:limit=float(data['limit'])
                    except (ValueError,TypeError):raise HTTPException(422,'采样数量无效')
                    if limit<=0 or limit>10000:raise HTTPException(422,'单次评测最多 10000 条')
                data['username']=actor['username']
                data.pop('use_cache',None) # cannot select another task/source directory
                if any('live_code_bench' in str(name) for name in data.get('datasets',[])):
                    import os
                    if os.getenv('YELLOW_CODE_SANDBOX_ENABLED')!='true':raise HTTPException(503,'代码执行评测的隔离运行器尚未启用')
                for arg in data.get('dataset_args',[]):
                    if int(arg.get('eval_batch_size') or 1)>16:raise HTTPException(422,'模型请求并发数最多为 16')
                model_id=data.get('model_id')
                await asyncio.to_thread(app.state.registry.get_model,model_id,actor)
                # Fail before scheduling rather than create a fabricated successful job.
                cfg_name={'run_testcase_ruler1':'common','run_testcase_ruler2':'field'}.get(path,'dev')
                cfg_path=root/'backend/config'/f'{cfg_name}_testcase_cfg.json'
                cfg=read_document(cfg_path)
                for name in data.get('datasets',[]):
                    row=cfg.get(name)
                    if not row:raise HTTPException(422,f'数据集 {name} 尚未注册')
                    resource=root/(row.get('local_path') or row.get('input_path',''))
                    if not resource.is_dir() or not any(resource.iterdir()):raise HTTPException(503,f'数据集 {name} 的语料未包含在原仓库中，请先上传数据集文件')
            if path=='register_testcase_ruler':
                identifier=data.get('dataset_id','')
                if identifier in runtime.resource_catalog():raise HTTPException(409,'数据集 ID 已存在')
            content=json.dumps(data,ensure_ascii=False).encode()
    elif 'multipart/form-data' in headers['Content-Type']:
        # Parser validates filenames/form paths but passes the original multipart body.
        form=await request.form()
        for key,value in form.multi_items():
            if hasattr(value,'filename'):
                filename=value.filename or ''
                if '/' in filename or '\\' in filename or filename.startswith('.'):raise HTTPException(422,'文件名不能包含路径')
            else:validate_paths(str(value),root,key)
    record=await asyncio.to_thread(runtime.get,actor)
    headers['X-iCAP-Worker']=record['secret']
    target=f"http://127.0.0.1:{record['port']}/v1/{path}"
    async with httpx.AsyncClient(timeout=180,trust_env=False) as client:
        try:response=await client.request(request.method,target,params=query,content=content,headers=headers)
        except httpx.HTTPError:raise HTTPException(503,'业务服务连接中断，请稍后重试')
    media=response.headers.get('content-type','application/json')
    if 'json' in media:
        result=response.json()
        if response.is_success and isinstance(data,dict) and path in {'register_testcase_ruler','edit_testcase_ruler'}:
            runtime.register_dataset(actor,data)
        return JSONResponse(clean_response(result),status_code=response.status_code)
    safe_headers={k:v for k,v in response.headers.items() if k.lower() in ('content-disposition','cache-control')}
    return Response(response.content,status_code=response.status_code,media_type=media,headers=safe_headers)

@app.api_route('/v2/{path:path}',methods=['GET','POST'])
def external_devices(path:str,actor=Depends(authorized)):
    raise HTTPException(503,'原设备实验室未随源码提供，请在管理员配置设备服务后使用')

app.router.routes.extend(spa)
