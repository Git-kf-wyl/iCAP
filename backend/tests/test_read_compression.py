import gzip
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient
from app.read_compression import ReadCompression


def test_read_compression_negotiation_and_stream_exclusion():
    app=FastAPI()
    payload=b'{"catalog":"'+b'repeated catalogue metadata '*1000+b'"}'
    @app.get('/api/workspace/bootstrap')
    def read():return Response(payload,media_type='application/json')
    @app.get('/api/agents/chat/stream')
    def stream():return Response(b'data: '+b'x'*3000+b'\n\n',media_type='text/event-stream')
    @app.get('/assets/already.js')
    def static():return Response(gzip.compress(payload),headers={'Content-Encoding':'gzip'})
    app.add_middleware(ReadCompression)
    with TestClient(app) as client:
        response=client.get('/api/workspace/bootstrap',headers={'Accept-Encoding':'gzip'})
        assert response.content==payload and response.headers['content-encoding']=='gzip'
        assert int(response.headers['content-length'])<len(payload)/10
        assert 'Accept-Encoding' in response.headers['vary']
        for encoding in ('identity','gzip;q=0','gzip;q=invalid'):
            response=client.get('/api/workspace/bootstrap',headers={'Accept-Encoding':encoding})
            assert response.content==payload and 'content-encoding' not in response.headers
        response=client.get('/api/agents/chat/stream',headers={'Accept-Encoding':'gzip'})
        assert 'content-encoding' not in response.headers and response.content.startswith(b'data: ')
        assert client.get('/assets/already.js').content==payload
