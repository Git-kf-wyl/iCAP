"""Credential-free TLS comparison for model API routes; never sends model prompts."""
import argparse
import http.client
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit


def safe_proxy(value):
    parsed = urlsplit(value)
    if parsed.scheme != 'http' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only an HTTP proxy without embedded credentials is supported')
    return parsed


def native_probe(target, proxy_url='', tls12=False):
    route = 'proxy' if proxy_url else 'direct'
    result = {'client': 'python', 'route': route, 'tls_mode': 'TLS1.2' if tls12 else 'default',
              'stage': 'connect', 'ok': False}
    connection = None
    try:
        context = ssl.create_default_context()
        if tls12:
            context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        if proxy_url:
            proxy = safe_proxy(proxy_url)
            connection = http.client.HTTPSConnection(proxy.hostname, proxy.port or 80,
                                                      timeout=8, context=context)
            connection.set_tunnel(target.hostname, target.port or 443)
        else:
            connection = http.client.HTTPSConnection(target.hostname, target.port,
                                                      timeout=8, context=context)
        connection.connect()
        result.update(ok=True, stage='tls_complete', tls=connection.sock.version(),
                      peer=connection.sock.getpeername()[0])
        # TLS completion is sufficient. No API key, HTTP request or prompt is sent.
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc)[:300])
    finally:
        if connection is not None:
            connection.close()
    return result


def curl_probe(target, proxy_url=''):
    route = 'proxy' if proxy_url else 'direct'
    result = {'client': 'curl', 'route': route, 'ok': False}
    if shutil.which('curl') is None:
        return {**result, 'error': 'curl unavailable'}
    # An unauthenticated HEAD can return 401/404/405; any HTTP status proves
    # that TCP, TLS and HTTP completed. No -v, headers, response body or key.
    url = urlunsplit((target.scheme, target.netloc, target.path or '/', '', ''))
    command = ['curl', '--silent', '--show-error', '--head', '--output', os.devnull,
               '--connect-timeout', '5', '--max-time', '10', '--write-out', '%{http_code}',
               '--proxy', proxy_url, '--noproxy', '' if proxy_url else '*', url]
    env = dict(os.environ)
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
        env.pop(name, None)
    try:
        completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=12)
        code = completed.stdout.strip()
        result.update(ok=completed.returncode == 0 and code.isdigit() and code != '000',
                      exit_code=completed.returncode, http_status=code,
                      error=completed.stderr.strip()[:300])
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.update(error_type=type(exc).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=os.environ.get('HB_LLM_BASE_URL') or os.environ.get('ARK_BASE_URL'))
    parser.add_argument('--proxy', default=os.environ.get('HB_PROXY_URL') or 'http://127.0.0.1:7890')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    target = urlsplit(args.base_url or '')
    if target.scheme != 'https' or not target.hostname or target.username or target.password or target.query or target.fragment:
        parser.error('Provide an HTTPS base URL without embedded credentials, query or fragment')
    if args.proxy:
        try:
            safe_proxy(args.proxy)
        except ValueError as exc:
            parser.error(str(exc))
    result = {'endpoint': urlunsplit((target.scheme, target.netloc, target.path, '', '')),
              'python': sys.version.split()[0], 'openssl': ssl.OPENSSL_VERSION,
              'selected_service_route': 'direct' if os.environ.get('HB_SERVICE_PROXY_URL') == '' else 'see preflight log',
              'note': 'No credentials or model requests; routes here are explicitly forced for comparison', 'probes': []}
    print(json.dumps({k: v for k, v in result.items() if k != 'probes'}, ensure_ascii=False), flush=True)
    for proxy in (['', args.proxy] if args.proxy else ['']):
        for tls12 in (False, True):
            probe = native_probe(target, proxy, tls12)
            result['probes'].append(probe)
            print(json.dumps(probe, ensure_ascii=False), flush=True)
        probe = curl_probe(target, proxy)
        result['probes'].append(probe)
        print(json.dumps(probe, ensure_ascii=False), flush=True)
    native = {(probe['route'], probe.get('tls_mode')): probe['ok']
              for probe in result['probes'] if probe['client'] == 'python'}
    curl = {probe['route']: probe['ok'] for probe in result['probes'] if probe['client'] == 'curl'}
    observations = []
    for route in ('direct', 'proxy'):
        if native.get((route, 'TLS1.2')) and not native.get((route, 'default')):
            observations.append(f'{route}: TLS1.2 works but default TLS fails; investigate TLS-version or middlebox compatibility')
        if curl.get(route) and not native.get((route, 'default')):
            observations.append(f'{route}: curl reaches HTTP but Python default TLS fails; investigate Python/OpenSSL path')
    if native.get(('direct', 'default')) and not native.get(('proxy', 'default')) and args.proxy:
        observations.append('Direct works, proxy fails: select HB_SERVICE_PROXY_URL empty')
    if native.get(('proxy', 'default')) and not native.get(('direct', 'default')):
        observations.append('Proxy works, direct fails: select HB_SERVICE_PROXY_URL with the tested proxy')
    if not any(probe['ok'] for probe in result['probes']):
        observations.append('All routes failed before model invocation; check endpoint, network and proxy service')
    result['observations'] = observations
    print(json.dumps({'observations': observations}, ensure_ascii=False), flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if any(probe['ok'] for probe in result['probes']) else 2


if __name__ == '__main__':
    raise SystemExit(main())
