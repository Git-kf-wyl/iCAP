"""Authenticated feature bundles; login resources stay publicly loadable."""
import json
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import JSONResponse

def protect_assets(app):
    dist=Path(__file__).resolve().parents[2]/'frontend/dist'
    manifest=dist/'.vite/manifest.json'
    public=set()
    if manifest.is_file():
        data=json.loads(manifest.read_text('utf-8'))
        seen=set()
        def visit(key):
            if key in seen or key not in data:return
            seen.add(key);entry=data[key]
            for value in [entry.get('file'),*entry.get('css',[]),*entry.get('assets',[])]:
                if value:public.add('/'+value)
            for dependency in entry.get('imports',[]):visit(dependency)
        for key,entry in data.items():
            if entry.get('isEntry') or key.endswith(('/blue/views/Login.vue','/blue/views/Register.vue','/blue/views/PasswordSecurity.vue','/blue/views/SecurityQuestionsSetup.vue')):visit(key)
    @app.middleware('http')
    async def assets(request,call_next):
        path=request.url.path
        protected=(path.startswith('/assets/') and path not in public) or path.startswith('/llm_bench/')
        if protected:
            token=request.cookies.get('icap_assets','')
            header=request.headers.get('authorization','')
            if header.startswith('Bearer '):token=header[7:]
            try:app.state.auth.current(token)
            except HTTPException:
                return JSONResponse({'detail':'请先登录'},status_code=401,headers={'Cache-Control':'no-store'})
        response=await call_next(request)
        if protected:response.headers['Cache-Control']='private, no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        return response
