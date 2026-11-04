"""Serve precompressed build files while preserving JavaScript MIME types."""
import mimetypes
import re
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

def versioned_asset(path):
    return bool(re.search(r'-[A-Za-z0-9_-]{8}-boot2\.[A-Za-z0-9]+$',path))

class WebAssets(StaticFiles):
    async def get_response(self,path,scope):
        headers=dict(scope.get('headers',[]))
        encodings=headers.get(b'accept-encoding',b'').decode('latin1')
        accepted=False
        for item in encodings.split(','):
            parts=[part.strip() for part in item.split(';')]
            if parts[0]!='gzip':continue
            try:quality=next((float(part[2:]) for part in parts[1:] if part.startswith('q=')),1)
            except ValueError:quality=0
            accepted=quality>0
        if accepted and path.endswith(('.js','.css')):
            source=Path(self.directory)/path
            compressed=source.with_name(source.name+'.gz')
            if compressed.resolve().is_relative_to(Path(self.directory).resolve()) and compressed.is_file():
                response=FileResponse(compressed,media_type=mimetypes.guess_type(source)[0],headers={'Content-Encoding':'gzip','Vary':'Accept-Encoding'})
                if versioned_asset(path):response.headers['Cache-Control']='public, max-age=31536000, immutable'
                return response
        response=await super().get_response(path,scope)
        if path.endswith(('.js','.css')):response.headers['Vary']='Accept-Encoding'
        if response.status_code in (200,304) and versioned_asset(path):response.headers['Cache-Control']='public, max-age=31536000, immutable'
        return response
