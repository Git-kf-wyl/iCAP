"""Compress catalogue JSON only; leave auth, streams and file responses alone."""
from starlette.middleware.gzip import GZipMiddleware
from .yellow_reads import FAST_READS


READ_PATHS = {'/v1/' + path for path in FAST_READS} | {
    '/v1/get_model_info', '/api/workspace/bootstrap', '/api/models',
    '/api/datasets', '/api/evaluations', '/api/rulers',
    '/api/skill-evolution/capabilities',
}


class ReadCompression:
    def __init__(self, app):
        self.app = app
        self.compressed = GZipMiddleware(app, minimum_size=1024, compresslevel=5)

    async def __call__(self, scope, receive, send):
        accepted = False
        if scope['type'] == 'http' and scope['method'] == 'GET' and scope['path'] in READ_PATHS:
            encodings = dict(scope.get('headers', [])).get(b'accept-encoding', b'').decode('latin1')
            for item in encodings.lower().split(','):
                parts = [part.strip() for part in item.split(';')]
                if parts[0] != 'gzip':
                    continue
                try:
                    accepted = next((float(part[2:]) for part in parts[1:] if part.startswith('q=')), 1) > 0
                except ValueError:
                    accepted = False
        await (self.compressed if accepted else self.app)(scope, receive, send)
