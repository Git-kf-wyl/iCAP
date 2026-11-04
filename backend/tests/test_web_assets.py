import gzip
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.web_assets import WebAssets

def test_precompressed_javascript_keeps_mime_and_encoding(tmp_path):
    source=b'window.assetReady=true;'
    (tmp_path/'app.js').write_bytes(source)
    compressed=gzip.compress(source,mtime=0)
    (tmp_path/'app.js.gz').write_bytes(compressed)
    app=FastAPI();app.mount('/assets',WebAssets(directory=tmp_path))
    with TestClient(app) as client:
        response=client.get('/assets/app.js',headers={'Accept-Encoding':'gzip'})
        assert response.content==source
        assert response.headers['Content-Encoding']=='gzip'
        assert response.headers['Content-Type'].startswith(('text/javascript','application/javascript'))
        assert int(response.headers['Content-Length'])==len(compressed)
        response=client.get('/assets/app.js',headers={'Accept-Encoding':'gzip;q=0'})
        assert 'Content-Encoding' not in response.headers and response.content==source
        assert response.headers['Vary']=='Accept-Encoding'
        assert client.get('/assets/../../private.env').status_code==404
