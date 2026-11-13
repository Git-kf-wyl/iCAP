"""Run adapter cases and harness regressions, keeping every result on disk."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]   # tools/harness_bench -> 仓库根
BENCH = ROOT if (ROOT / 'tools' / 'run_benchmark.py').is_file() else ROOT / 'harness-bench'
META = ROOT / 'metaAgent' if (ROOT / 'metaAgent').is_dir() else ROOT / 'docker/harnesses/metaagent/metaagent-src'
META_PYTHON = (META / '.venv/bin/python') if (META / '.venv/bin/python').exists() else Path(sys.executable)

# vendored 源码可直接 import（本地校验用）；镜像内由 pip 安装
_vendored_src = META / 'src'
if _vendored_src.is_dir() and str(_vendored_src) not in sys.path:
    sys.path.insert(0, str(_vendored_src))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Also check real services and run the two benchmark smoke tasks')
    parser.add_argument('--proxy', default='http://127.0.0.1:7890')
    parser.add_argument('--run-root', type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (args.run_root or META / '.artifacts' / f'harness-bench-{stamp}').resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    env = dict(os.environ)
    env['UV_CACHE_DIR'] = str(output / 'uv-cache')
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
        env[name] = args.proxy
    env['NO_PROXY'] = env['no_proxy'] = 'localhost,127.0.0.1,::1'
    env['HARNESSBENCH_DOCKER_BUILD_PROXY'] = args.proxy
    env['HARNESSBENCH_UPSTREAM_PROXY'] = args.proxy
    if sys.platform.startswith('linux'):
        env['HARNESSBENCH_DOCKER_BUILD_NETWORK'] = 'host'
    meta_python = str(META_PYTHON)

    def record(name, status, detail):
        results.append({'name': name, 'status': status, 'detail': detail})
        (output / 'results.json').write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f'{status.upper()}: {name}', flush=True)

    def run(name, command, timeout):
        log = output / f'{name}.log'
        try:
            with log.open('w') as handle:
                completed = subprocess.run(command, cwd=ROOT, env=env, stdout=handle,
                                           stderr=subprocess.STDOUT, timeout=timeout)
            text = log.read_text(errors='replace')
            status = 'passed' if completed.returncode == 0 else 'failed'
            if status == 'failed' and any(marker in text for marker in (
                'Operation not permitted', 'permission denied while trying to connect',
                'BLOCKED: missing', 'BLOCKED: cannot read', 'Could not connect to server')):
                status = 'blocked'
            record(name, status, {'exit_code': completed.returncode, 'log': str(log)})
            return status == 'passed'
        except (OSError, subprocess.TimeoutExpired) as exc:
            record(name, 'blocked' if isinstance(exc, OSError) else 'failed',
                   {'error': type(exc).__name__, 'log': str(log)})
            return False

    # These are diagnostics, not tests to skip or pretend have passed.
    for name, address in [('proxy', ('127.0.0.1', 7890))]:
        try:
            with socket.create_connection(address, timeout=3):
                pass
            record(name, 'passed', 'TCP connection available')
        except OSError as exc:
            record(name, 'blocked', {'error': type(exc).__name__, 'errno': exc.errno})
    run('docker', ['docker', 'info', '--format', '{{.ServerVersion}}'], 15)
    for case in ('answer', 'tools', 'search', 'model-error'):
        run(case, [meta_python, str(Path(__file__).with_name('check_adapter.py')),
                   '--case', case, '--output-dir', str(output / case)], 60)
    run('harness-tests', [sys.executable, '-m', 'pytest', '-q', str(BENCH / 'tests')], 120)
    if args.live:
        services = [run('service-' + target, [meta_python, str(BENCH / 'tools/smoke_volcano.py'),
                                target, '--proxy', args.proxy], 330)
                    for target in ('model', 'judge', 'search')]
        if all(services) and any(item['name'] == 'docker' and item['status'] == 'passed' for item in results):
            env.pop('HARNESSBENCH_WEB_SEARCH', None)
            completed = run('benchmark', [sys.executable, str(BENCH / 'tools/run_benchmark.py'),
                '--harness', 'metaagent', '--base-url', env['ARK_BASE_URL'], '--model', env['ARK_MODEL'],
                '--upstream-api-key-file', env['ARK_API_KEY_FILE'],
                '--tasks', '009-safe-archive-extraction,001-meeting-summary',
                '--workers', '1', '--max-agent-turns', '30', '--max-tokens', '8192',
                '--context-window', '32768', '--temperature', '0', '--thinking', 'off',
                '--timeout', '1200', '--run-root', str(output / 'benchmark')], 7200)
            if completed:
                expected = {'009-safe-archive-extraction', '001-meeting-summary'}
                task_results = [json.loads(path.read_text()) for path in (output / 'benchmark').rglob('result.json')]
                task_results = [item for item in task_results if item.get('task_id') in expected]
                native = [json.loads(path.read_text()) for path in (output / 'benchmark').rglob('session-summary.json')]
                native = [item for item in native if item.get('harness') == 'metaagent']
                valid = ({item['task_id'] for item in task_results} == expected
                         and all(item.get('harness') == 'metaagent'
                                 and item.get('status') == 'completed'
                                 and item.get('task_success') is True
                                 and item.get('provider_request_count', 0) > 0 for item in task_results)
                         and len(native) >= 2
                         and all(item.get('status') == 'completed' for item in native))
                judge = next((item.get('semantic_judge') for item in task_results
                              if item['task_id'] == '001-meeting-summary'), None)
                valid = valid and isinstance(judge, dict) and judge.get('status') == 'completed'
                record('benchmark-artifacts', 'passed' if valid else 'failed',
                       'Checked task success, native summaries, provider requests and semantic judge')
        else:
            record('benchmark', 'blocked', 'Required services or Docker are unavailable; not executed')
    print(f'Results: {output / "results.json"}')
    return 1 if any(item['status'] == 'failed' for item in results) else 2 if any(item['status'] == 'blocked' for item in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
