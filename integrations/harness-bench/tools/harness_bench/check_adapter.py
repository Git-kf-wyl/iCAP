"""Exercise actual MetaAgent with deterministic HTTP replies; no paid services."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]   # tools/harness_bench -> 仓库根
BENCH = ROOT if (ROOT / 'tools' / 'run_benchmark.py').is_file() else ROOT / 'harness-bench'
META = ROOT / 'metaAgent' if (ROOT / 'metaAgent').is_dir() else ROOT / 'docker/harnesses/metaagent/metaagent-src'
META_PYTHON = (META / '.venv/bin/python') if (META / '.venv/bin/python').exists() else Path(sys.executable)

# vendored 源码可直接 import（本地校验用）；镜像内由 pip 安装
_vendored_src = META / 'src'
if _vendored_src.is_dir() and str(_vendored_src) not in sys.path:
    sys.path.insert(0, str(_vendored_src))
sys.path.insert(0, str(BENCH / 'docker/harnesses/openjiuwen'))
sys.path.insert(0, str(BENCH / 'tools'))
from harness_runtime import SPECS, render_harness_config

calls = []
search_calls = []
case = 'answer'


async def fake_send(client, request, **kwargs):
    import httpx
    payload = json.loads(request.content)
    assert request.url.path == '/v1/chat/completions', request.url
    assert payload['model'] == 'adapter-smoke'
    calls.append(payload)
    if case == 'model-error':
        return httpx.Response(401, request=request, json={'error': {'message': 'scripted auth failure', 'type': 'authentication_error'}})
    workspace = Path(os.environ['HARNESSBENCH_WORKSPACE'])
    steps = []
    if case == 'tools':
        command = shlex.join([sys.executable, '-c', "from pathlib import Path; p=Path('answer.txt'); assert p.read_text() == '42'; Path('shell.txt').write_text('shell-ok')"])
        steps = [('write_file', {'file_path': str(workspace / 'answer.txt'), 'content': '42'}),
                 ('read_file', {'file_path': str(workspace / 'answer.txt')}),
                 ('bash', {'command': command, 'workdir': str(workspace), 'timeout': 10})]
    elif case == 'search':
        steps = [('web_search', {'query': '火山引擎', 'count': 1})]
    index = len(calls) - 1
    message = {'role': 'assistant', 'content': 'METAAGENT_ADAPTER_OK'}
    reason = 'stop'
    if index < len(steps):
        name, arguments = steps[index]
        assert name in [item['function']['name'] for item in payload['tools']]
        message = {'role': 'assistant', 'content': None, 'tool_calls': [{
            'id': f'call-{index}', 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(arguments)}}]}
        reason = 'tool_calls'
    response = {'id': f'smoke-{index}', 'object': 'chat.completion', 'created': 0,
                'model': 'adapter-smoke', 'choices': [{'index': 0, 'message': message, 'finish_reason': reason}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
    if payload.get('stream'):
        response['object'] = 'chat.completion.chunk'
        response['choices'][0]['delta'] = response['choices'][0].pop('message')
        return httpx.Response(200, request=request, headers={'content-type': 'text/event-stream'},
                              content=('data: ' + json.dumps(response) + '\n\ndata: [DONE]\n\n').encode())
    return httpx.Response(200, request=request, json=response)


class SearchResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def text(self):
        return json.dumps({'Result': {'ResultCount': 1, 'WebResults': [
            {'Title': 'Volcano', 'Url': 'https://www.volcengine.com/', 'Summary': 'search-ok'}]}})


class SearchSession(SearchResponse):
    def __init__(self, *args, **kwargs):
        pass

    def post(self, url, **kwargs):
        assert url == 'https://open.feedcoopapi.com/search_api/web_search'
        assert kwargs['headers']['Authorization'] == 'Bearer smoke-search-key'
        assert kwargs['json']['Query'] == '火山引擎'
        search_calls.append(kwargs['json'])
        return SearchResponse()


class ConfigChecked(Exception):
    pass


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
    return module


def main():
    global case
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-only', action='store_true')
    parser.add_argument('--case', choices=['answer', 'tools', 'search', 'model-error'], default='answer')
    parser.add_argument('--output-dir', type=Path, help='Keep workspace and traces for inspection')
    args = parser.parse_args()
    case = args.case
    calls.clear()
    search_calls.clear()
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ):
        root = (args.output_dir or Path(directory)).resolve()
        root.mkdir(parents=True, exist_ok=True)
        for name in ('workspace', 'state', 'trace'):
            (root / name).mkdir(exist_ok=False)
            os.environ['HARNESSBENCH_' + name.upper()] = str(root / name)
        # Verify task-owned names survive product scaffold cleanup.
        (root / 'workspace/AGENT.md').write_text('task-owned-document')
        (root / 'prompt').write_text('Execute the requested tools and reply METAAGENT_ADAPTER_OK.')
        os.environ['HARNESSBENCH_PROMPT'] = str(root / 'prompt')
        os.environ['HARNESSBENCH_CONFIG'] = str(root / 'config.json')
        os.environ.pop('HARNESSBENCH_WEB_SEARCH', None)
        if case == 'search':
            os.environ['HARNESSBENCH_WEB_SEARCH'] = 'volc'
            os.environ['VOLC_SEARCH_API_KEY'] = 'smoke-search-key'
        (root / 'config.json').write_text(render_harness_config(
            SPECS['metaagent'], base_url='http://adapter.invalid/v1', model='adapter-smoke',
            max_tokens=1024, temperature=0, max_agent_turns=8))
        load_module('openjiuwen_run', BENCH / 'docker/harnesses/openjiuwen/run_agent.py')
        module = load_module('adapter', BENCH / 'docker/harnesses/metaagent/run_agent.py')
        with patch('httpx.AsyncClient.send', fake_send), patch('aiohttp.ClientSession', SearchSession):
            if args.config_only:
                from meta_agent import MetaBootLoader

                async def validate(loader):
                    loaded = loader.load()
                    assert loaded.spec.deep_agent.enable_sys_operation
                    assert loaded.spec.deep_agent.max_iterations == 8
                    raise ConfigChecked()

                with patch.object(MetaBootLoader, 'boot', validate):
                    try:
                        module.main()
                    except ConfigChecked:
                        print('PASS: production MetaAgent package validates, including native system tools')
                        return
                    raise AssertionError('Package validation was not reached')
            error = None
            try:
                module.main()
            except Exception as exc:
                error = exc
            summary = json.loads((root / 'trace/session-summary.json').read_text())
            assert (root / 'workspace/AGENT.md').read_text() == 'task-owned-document'
            if case == 'model-error':
                assert error is not None, 'Model failure must propagate'
                assert summary['status'] == 'error', summary
            else:
                if error is not None:
                    raise error
                assert summary['status'] == 'completed', summary
                assert 'METAAGENT_ADAPTER_OK' in (root / 'trace/final-answer.txt').read_text()
                assert calls
                if case == 'tools':
                    assert (root / 'workspace/answer.txt').read_text() == '42'
                    assert (root / 'workspace/shell.txt').read_text() == 'shell-ok'
                    tool_results = [m for call in calls for m in call['messages'] if m['role'] == 'tool']
                    assert len(tool_results) >= 3
                if case == 'search':
                    assert len(search_calls) == 1
                    assert any('search-ok' in str(call['messages']) for call in calls)
            print(f'PASS: {case}; real MetaAgent lifecycle, trace and cleanup')


if __name__ == '__main__':
    main()
