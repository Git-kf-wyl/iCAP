"""Check Volcano model, judge or search credentials from the trusted host."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen

from proxy_env import configure_no_proxy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=['model', 'judge', 'search'])
    parser.add_argument('--transport', choices=['urllib', 'controller'], default='urllib',
                        help='controller exercises the same TLS/proxy transport as benchmark model requests')
    parser.add_argument('--proxy', default=os.environ.get('HARNESSBENCH_PROXY'),
                        help='HTTP proxy for upstream calls (does not alter benchmark isolation)')
    args = parser.parse_args()
    if args.proxy:
        for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
            os.environ[name] = args.proxy
    required = {'model': ('ARK_BASE_URL', 'ARK_MODEL', 'ARK_API_KEY_FILE'),
                'judge': ('HARNESSBENCH_JUDGE_BASE_URL', 'HARNESSBENCH_JUDGE_MODEL',
                          'HARNESSBENCH_JUDGE_API_KEY_FILE'),
                'search': ('VOLC_SEARCH_API_KEY',)}[args.target]
    missing = [name for name in required if not os.environ.get(name, '').strip()]
    if missing:
        raise SystemExit('BLOCKED: missing ' + ', '.join(missing))
    if args.target != 'search':
        configure_no_proxy([os.environ.get('ARK_BASE_URL'), os.environ.get('HARNESSBENCH_JUDGE_BASE_URL')])
    if args.target == 'search':
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'docker/harnesses/openjiuwen'))
        from volc_search import VolcanoSearch
        result = asyncio.run(VolcanoSearch().search('火山引擎', 1))
        if result.get('error') or not result.get('results'):
            raise SystemExit('FAIL search: no results; check search API key and service activation')
        print('PASS search: Volcano returned results')
        return
    if args.target == 'model':
        base = os.environ['ARK_BASE_URL']
        model = os.environ['ARK_MODEL']
        key_file = os.environ['ARK_API_KEY_FILE']
    else:
        base = os.environ['HARNESSBENCH_JUDGE_BASE_URL']
        model = os.environ['HARNESSBENCH_JUDGE_MODEL']
        key_file = os.environ['HARNESSBENCH_JUDGE_API_KEY_FILE']
    try:
        key = Path(key_file).read_text().strip()
    except OSError:
        raise SystemExit('BLOCKED: cannot read API key file') from None
    if not key or '\n' in key or '\r' in key:
        raise SystemExit('FAIL: API key must contain exactly one nonempty line')
    payload = {'model': model, 'messages': [{'role': 'user', 'content': 'Return JSON: {"ok": true}'}],
               'max_tokens': 1024, 'stream': False}
    if args.target == 'judge':
        payload.update(temperature=0, response_format={'type': 'json_object'})
    request = Request(base.rstrip('/') + '/chat/completions',
                      data=json.dumps(payload).encode(),
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    if args.transport == 'controller':
        from urllib.parse import urlsplit
        from model_budget_proxy import ModelBudgetProxy
        # An empty explicit proxy is a direct controller connection. Unlike
        # urllib, http.client never implicitly reads HTTP(S)_PROXY.
        if args.proxy is not None:
            os.environ['HARNESSBENCH_UPSTREAM_PROXY'] = args.proxy
        parsed = urlsplit(base)
        proxy = ModelBudgetProxy(base, max_agent_turns=1, temperature=0,
                                 max_output_tokens=1024, timeout_sec=120)
        path = parsed.path.rstrip('/') + '/chat/completions'
        import ssl as _ssl
        try:
            connection, target = proxy._upstream_connection(path)
        except AttributeError:
            # 新分支 ModelBudgetProxy 不再暴露 _upstream_connection；
            # 用标准库构造同样的 direct/proxy 连接（语义等价）。
            import http.client
            proxy_url = getattr(proxy, 'upstream_proxy', None) or args.proxy or ''
            if proxy_url:
                from urllib.parse import urlsplit as _us
                pu = proxy_url if '://' in proxy_url else 'http://' + proxy_url
                pp = _us(pu)
                if parsed.scheme == 'https':
                    connection = http.client.HTTPSConnection(
                        pp.hostname, pp.port or 80, timeout=120,
                        context=_ssl.create_default_context())
                    connection.set_tunnel(parsed.hostname, parsed.port or 443)
                    target = path
                else:
                    connection = http.client.HTTPConnection(
                        pp.hostname, pp.port or 80, timeout=120)
                    target = f'{parsed.scheme}://{parsed.netloc}{path}'
            elif parsed.scheme == 'https':
                connection = http.client.HTTPSConnection(
                    parsed.hostname, parsed.port or 443, timeout=120,
                    context=_ssl.create_default_context())
                target = path
            else:
                connection = http.client.HTTPConnection(
                    parsed.hostname, parsed.port or 80, timeout=120)
                target = path
        import ssl
        route = 'direct'
        if getattr(proxy, 'upstream_proxy', None) is not None:
            route = f'http-proxy {proxy.upstream_proxy.hostname}:{proxy.upstream_proxy.port or 80}'
        print(f'Model transport: endpoint={parsed.scheme}://{parsed.hostname}:{parsed.port or 443}{path}; route={route}; Python={sys.version.split()[0]}; {ssl.OPENSSL_VERSION}', flush=True)
        try:
            connection.request('POST', target, body=json.dumps(payload).encode(),
                               headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            if response.status != 200:
                raise SystemExit(f'FAIL {args.target}: HTTP {response.status}; check endpoint, model and credentials')
            result = json.load(response)
        finally:
            connection.close()
    else:
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
    content = result['choices'][0]['message']['content']
    if not content:
        raise SystemExit('FAIL: empty content; increase tokens or use a non-thinking endpoint')
    if args.target == 'judge':
        assert json.loads(content)['ok'] is True, 'judge did not return expected JSON'
    print('PASS ' + args.target + ': chat/completions' + (' + JSON mode' if args.target == 'judge' else ''))


if __name__ == '__main__':
    main()
