"""Private Docker-gateway OTLP ingress; bind only to the Docker bridge address.

Agent containers cannot reach Langfuse's loopback-published port directly.
This relay exposes only the authenticated OTLP ingestion path.
"""
import os

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)


@app.post('/api/public/otel/v1/traces')
async def ingest(request:Request):
    if not request.headers.get('authorization','').startswith('Basic '):
        raise HTTPException(401,'OTLP authentication required')
    payload=bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload)>32*1024*1024:raise HTTPException(413,'OTLP request too large')
    headers={key:request.headers[key] for key in
             ('authorization','content-type','content-encoding','x-langfuse-ingestion-version')
             if key in request.headers}
    try:
        async with httpx.AsyncClient(trust_env=False,timeout=30) as client:
            response=await client.post(os.getenv('LANGFUSE_HOST','http://127.0.0.1:3100').rstrip('/')+
                                       '/api/public/otel/v1/traces',headers=headers,content=bytes(payload))
    except httpx.HTTPError as exc:
        raise HTTPException(503,'OTLP backend unavailable') from exc
    return Response(response.content,status_code=response.status_code,
                    media_type=response.headers.get('content-type','application/x-protobuf'))
