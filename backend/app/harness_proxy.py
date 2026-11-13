"""Expose only the reduced Langfuse application behind the existing iCAP login."""
import os
import re
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response


def router(auth_service):
    api=APIRouter()
    upstream=os.getenv('HARNESS_LAB_URL','http://127.0.0.1:3101').rstrip('/')

    @api.api_route('/harness-lab/{path:path}',methods=['GET','POST'],include_in_schema=False)
    async def proxy(path: str, request: Request):
        token=request.cookies.get('icap_assets','')
        if not token: raise HTTPException(401,'请先登录 iCAP')
        auth_service.current(token)
        allowed=(path=='harness' or path.startswith('_next/') or path.startswith('api/harness/')
                 or path in {'favicon.ico','icon.svg','api/trpc/public.markdownRenderConfig','api/workers/elk-worker'})
        if not allowed: raise HTTPException(404,'页面不存在')
        if any(part in {'.','..'} for part in path.split('/')):
            raise HTTPException(405,'不允许的操作')
        if request.method!='GET':
            origin=request.headers.get('origin','')
            if not origin or urlsplit(origin).netloc!=request.headers.get('host',''):
                raise HTTPException(403,'请求来源无效')
            if not path.startswith('api/harness/'):
                raise HTTPException(405,'不支持此操作')
            if not request.headers.get('content-type','').startswith('application/json'):
                raise HTTPException(415,'仅接受 JSON')
        query=('?'+request.url.query) if request.url.query else ''
        target=upstream+'/harness-lab/'+path+query
        headers={'cookie':'icap_assets='+token,'content-type':request.headers.get('content-type','application/json'),
                 'x-forwarded-host':request.headers.get('host',''),
                 'x-forwarded-proto':request.headers.get('x-forwarded-proto',request.url.scheme)}
        if request.headers.get('origin'):headers['origin']=request.headers['origin']
        if path.startswith('api/harness/'):
            resource=path[len('api/harness/'):]
            read=re.fullmatch(r'(catalog|model-capabilities|runs|runs/[A-Za-z0-9_-]+(?:/(?:context|metrics|traces)(?:/[0-9a-f]{32})?)?)',resource)
            write=re.fullmatch(r'runs(?:/[A-Za-z0-9_-]+/stop)?',resource)
            if not ((request.method=='GET' and read) or (request.method=='POST' and write)):
                raise HTTPException(405,'不允许的操作')
            # The source-built web container needs no access to iCAP's loopback listener.
            target=os.getenv('ICAP_LOOPBACK_URL','http://127.0.0.1:8081')+'/api/harness-eval/'+resource+query
            headers={'authorization':'Bearer '+token,'content-type':headers['content-type']}
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>256*1024:raise HTTPException(413,'请求体过大')
        try:
            async with httpx.AsyncClient(trust_env=False,timeout=90) as client:
                response=await client.request(request.method,target,headers=headers,content=bytes(body))
        except httpx.HTTPError as exc:
            raise HTTPException(503,'评测观测界面尚未启动') from exc
        return Response(response.content,status_code=response.status_code,
                        headers={'content-type':response.headers.get('content-type','application/octet-stream'),
                                 'cache-control':'no-store','x-content-type-options':'nosniff',
                                 'content-security-policy':"frame-ancestors 'self'"})

    return api
