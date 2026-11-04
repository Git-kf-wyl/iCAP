"""Private, per-account Yellow runtime. Only adapter.py can reach its routes."""
import hmac
import importlib
import json
import os
from pathlib import Path
import sys
import traceback

CODE=Path(__file__).resolve().parent
sys.path.insert(0,str(CODE))

def main():
    from flask import Flask, request, jsonify, Response
    from werkzeug.serving import run_simple
    root=Path(os.environ['YELLOW_WORKSPACE']).resolve()
    os.chdir(root)
    # Original libraries occasionally print complete request/config dictionaries.
    # Filter provider credentials before any line reaches a persistent worker log.
    import re
    class RedactedStream:
        def __init__(self, stream): self.stream=stream
        def write(self, text):
            try:
                rows=json.loads((root/'backend/config/model_cfg.json').read_text('utf-8'))
                for row in rows:
                    for endpoint in row.get('config',{}).get('api_params_available',[]):
                        key=endpoint.get('api_key','')
                        if len(key)>8:text=text.replace(key,'[redacted]')
            except (OSError,ValueError): pass
            text=re.sub(r'sk-[A-Za-z0-9_-]{16,}','[redacted]',text)
            return self.stream.write(text)
        def flush(self): return self.stream.flush()
        def __getattr__(self,name):return getattr(self.stream,name)
    sys.stdout=RedactedStream(sys.stdout)
    sys.stderr=RedactedStream(sys.stderr)
    import utils.consts as consts
    # All mutable original relative paths resolve inside this account's workspace.
    # Keep script entry points in the private release; no source directory is served.
    for key,value in list(vars(consts).items()):
        if isinstance(value,str) and value.startswith('backend/services/'):
            setattr(consts,key,str(CODE/value.removeprefix('backend/')))
        elif key in ('RULER_1_EXEC','RULER_2_EXEC','UPDATE_SCORE'):
            setattr(consts,key,str(CODE/value.removeprefix('backend/')))
    consts.PROXY_URL=''
    consts.ELD_DATASET_PATH_BASE=str(root/'testsuite/TestSuiteRulerII')
    consts.CUSTOM_RULER2_PROC_DISPATCH={tag:str(CODE/value.removeprefix('backend/')) for tag,value in consts.CUSTOM_RULER2_PROC_DISPATCH.items()}
    # Institutional identity/network services are intentionally not loaded.
    app=Flask('icap_yellow_private')
    app.config.update(MAX_CONTENT_LENGTH=128*1024*1024)
    secret=os.environ['YELLOW_WORKER_SECRET']

    @app.before_request
    def authorize():
        if request.path in ('/_model/v1','/_model/v1/chat/completions') and hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+secret):
            return None
        if not hmac.compare_digest(request.headers.get('X-iCAP-Worker',''),secret):
            return jsonify(error='Forbidden'),403

    import threading
    import httpx
    route_lock=threading.Lock()
    route_counts={}

    @app.post('/_model/v1/chat/completions')
    @app.post('/_model/v1')
    def model_gateway():
        payload=request.get_json()
        models=json.loads((root/'backend/config/provider_models.json').read_text('utf-8'))
        model=next((m for m in models if m['id']==payload.get('model')),None)
        if not model:return {'error':{'message':'模型不可用'}},404
        with route_lock:
            count=route_counts.get(model['id'],0);route_counts[model['id']]=count+1
        endpoint=model['endpoints'][count%len(model['endpoints'])]
        if model.get('provider','').lower()=='deepseek' and not endpoint.get('self_deployed'):
            thinking=payload.get('enable_thinking')
            if thinking is None:thinking=(payload.get('chat_template_kwargs') or {}).get('enable_thinking',False)
            payload={k:v for k,v in payload.items() if k in {'model','messages','stream','max_tokens','temperature','top_p','stop','frequency_penalty','presence_penalty','thinking','response_format','tools','tool_choice','logprobs','top_logprobs'}}
            if 'thinking' not in payload:payload.update((endpoint.get('thinking_schema') or {}).get('enabled' if thinking else 'disabled',{}))
        url=endpoint['url'].rstrip('/')
        if not url.endswith('/chat/completions'):url+='/chat/completions'
        headers={'Authorization':'Bearer '+endpoint['api_key'],'Content-Type':'application/json'}
        client=httpx.Client(timeout=180)
        response=client.send(client.build_request('POST',url,json=payload,headers=headers),stream=bool(payload.get('stream')))
        if response.status_code>=400:
            response.close();client.close()
            return {'error':{'message':'模型服务请求失败'}},502
        if payload.get('stream'):
            def body():
                try:yield from response.iter_bytes()
                finally:response.close();client.close()
            return Response(body(),mimetype='text/event-stream')
        content=response.read();response.close();client.close()
        return Response(content,mimetype='application/json')

    @app.get('/_ready')
    def ready():
        return {'status':'ok','loaded':list(loaded),'errors':list(failures)}

    loaded={}
    failures={}
    for module_name in ['server','run_test_server','paper_agent_server']:
        try:
            module=importlib.import_module(module_name)
            loaded[module_name]=module
            module.UPLOAD_FOLDERS=str(root/'uploads')
            if module_name=='run_test_server' and not (root/'backend/report/template_all.pptx').is_file():
                from report_fallback import generate
                module._generate_report_thread=lambda *args,_module=module:generate(_module,*args)
            for rule in module.app.url_map.iter_rules():
                if rule.endpoint=='static' or any(str(r)==str(rule) for r in app.url_map.iter_rules()):
                    continue
                app.add_url_rule(str(rule),endpoint=module_name+'.'+rule.endpoint,
                                 view_func=module.app.view_functions[rule.endpoint],methods=rule.methods)
        except Exception as exc:
            failures[module_name]=type(exc).__name__
            traceback.print_exc()

    @app.errorhandler(Exception)
    def error(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc,HTTPException):
            return {'error':exc.description},exc.code
        # Never return upstream URLs, credentials or tracebacks to the browser.
        traceback.print_exc()
        return {'error':'该操作执行失败，请检查输入和已安装的运行依赖'},500

    from waitress import serve
    serve(app,host='127.0.0.1',port=int(os.environ['YELLOW_WORKER_PORT']),threads=20,channel_timeout=180)

if __name__=='__main__':
    main()
