# Private iCAP Yellow business implementation. Do not publish.
"""
HuggingFace Download Adapter — 统一收口网关服务

部署在 7.216.57.45:21827，作为前端唯一对接的服务。
职责：
  1. 对外暴露与 huggingface_download_server.py 一致的 API
  2. 将下载任务按分发规则（大小文件分类 + 权重）转发给 5 个后端子服务器

后端节点：
  7.216.57.181:21827  weight=0.2
  7.216.57.251:21827  weight=0.2
  7.216.57.33:21827   weight=0.2  (混合下载时专门负责小文件)
  7.216.57.92:21827   weight=0.2
  7.216.59.100:21827  weight=0.2

分发规则：
  - 混合下载（大文件 + 小文件同时存在）：
      小文件 → 全部路由到 7.216.57.33
      大文件 → 按权重分配给其余 4 台 + 7.216.57.33 的大文件部分
  - 纯大文件 或 纯小文件：
      按权重分配给全部 5 台
"""
import os
import sys
import json
import random
import logging
import threading
import re
import requests
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from urllib.parse import urlparse, unquote
BACKEND_SERVERS = [{'host': '7.216.57.181', 'port': 21827, 'weight': 0.25}, {'host': '7.216.57.251', 'port': 21827, 'weight': 0.25}, {'host': '7.216.57.33', 'port': 21827, 'weight': 0.25}, {'host': '7.216.57.92', 'port': 21827, 'weight': 0.25}]
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024
app = Flask(__name__)
CORS(app)
task_routing = {}
task_routing_lock = threading.Lock()

def setup_logger(log_file='modelscope_download_adapter.log', level=logging.INFO):
    logger = logging.getLogger('HuggingFaceDownloadAdapter')
    logger.setLevel(level)
    if logger.handlers:
        return logger
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(lineno)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
logger = setup_logger()

def backend_url(server, path=''):
    """拼接后端服务器的完整 URL"""
    return f"http://{server['host']}:{server['port']}{path}"

def weighted_choose(servers, exclude=None):
    """
    根据权重从 servers 列表中随机选取一个。
    exclude: 需要排除的 server 列表（不参与本次选择）
    """
    candidates = [s for s in servers if not exclude or s not in exclude]
    if not candidates:
        return None
    return random.choice(candidates)

def classify_files(files_list, files_len_list):
    """
    将文件列表分为大文件和小文件。

    返回:
        large_files: [(file_name, file_size), ...]
        small_files: [(file_name, file_size), ...]
        has_large: bool
        has_small: bool
    """
    large_files = []
    small_files = []
    for i, file_name in enumerate(files_list):
        file_size = files_len_list[i] if i < len(files_len_list) else 0
        if file_size >= LARGE_FILE_THRESHOLD:
            large_files.append((file_name, file_size))
        else:
            small_files.append((file_name, file_size))
    return (large_files, small_files, len(large_files) > 0, len(small_files) > 0)

def distribute_files(files_list, files_len_list):
    """
    根据分发规则，将文件分配到各后端服务器。

    返回:
        assignments: [
            {
                "server": {"host": ..., "port": ..., "weight": ...},
                "files": [file_name, ...],
                "files_len": [file_size, ...]
            },
            ...
        ]
    """
    large_files, small_files, has_large, has_small = classify_files(files_list, files_len_list)
    assignments = {}
    for srv in BACKEND_SERVERS:
        assignments[srv['host']] = {'server': srv, 'files': [], 'files_len': []}
    if has_large and has_small:
        logger.info('混合下载模式：小文件 -> 7.216.57.33, 大文件 -> 按权重分配')
        small_server = next((s for s in BACKEND_SERVERS if s['host'] == '7.216.57.33'))
        for fname, fsize in small_files:
            assignments[small_server['host']]['files'].append(fname)
            assignments[small_server['host']]['files_len'].append(fsize)
        machineid = 0
        num = [len(large_files) // len(assignments) for _ in range(len(assignments))]
        for i in range(len(large_files) % len(assignments)):
            num[i] = num[i] + 1
        for fname, fsize in large_files:
            if 0 == num[machineid]:
                machineid = machineid + 1
            num[machineid] = num[machineid] - 1
            assignments[BACKEND_SERVERS[machineid]['host']]['files'].append(fname)
            assignments[BACKEND_SERVERS[machineid]['host']]['files_len'].append(fsize)
    else:
        file_type = '大文件' if has_large else '小文件'
        logger.info(f'纯{file_type}下载模式：按权重分配')
        all_file_pairs = large_files + small_files
        machineid = 0
        num = [len(large_files) // len(assignments) for _ in range(len(assignments))]
        for i in range(len(large_files) % len(assignments)):
            num[i] = num[i] + 1
        for fname, fsize in all_file_pairs:
            if 0 == num[machineid]:
                machineid = machineid + 1
            num[machineid] = num[machineid] - 1
            assignments[BACKEND_SERVERS[machineid]['host']]['files'].append(fname)
            assignments[BACKEND_SERVERS[machineid]['host']]['files_len'].append(fsize)
    result = [a for a in assignments.values() if a['files']]
    for r in result:
        logger.info(f"  -> {r['server']['host']}:{r['server']['port']} 分配 {len(r['files'])} 个文件")
    return result

def forward_request(method, server, path, json_body=None, params=None, timeout=300):
    """向指定的后端服务器转发请求"""
    url = backend_url(server, path)
    try:
        kwargs = {'timeout': timeout, 'verify': False}
        if params:
            kwargs['params'] = params
        if json_body is not None:
            kwargs['json'] = json_body
        resp = requests.request(method, url, **kwargs)
        return (resp.status_code, resp.json())
    except requests.exceptions.Timeout:
        logger.error(f'请求后端超时: {url}')
        return (504, {'status': 'error', 'message': f"后端 {server['host']} 超时"})
    except requests.exceptions.ConnectionError as e:
        logger.error(f'后端连接失败: {url}, {e}')
        return (502, {'status': 'error', 'message': f"后端 {server['host']} 连接失败"})
    except Exception as e:
        logger.error(f'转发请求失败: {url}, {e}')
        return (500, {'status': 'error', 'message': str(e)})

@app.route('/v1/ms_download/files_info', methods=['GET'])
def files_info():
    """
    获取 HuggingFace 仓库文件列表。
    转发到任意一个可用的后端即可（所有后端数据一致）。
    """
    url = request.args.get('url', '')
    max_files = request.args.get('max_files', 'full')
    if not url:
        return (jsonify({'status': 'error', 'message': 'url is required'}), 400)
    server = random.choice(BACKEND_SERVERS)
    logger.info(f"files_info 请求转发到 {server['host']}:{server['port']}")
    print(url)
    print(max_files)
    print(server)
    status_code, data = forward_request('GET', server, '/v1/ms_download/files_info', params={'url': url, 'max_files': max_files}, timeout=60)
    print(data)
    return (jsonify(data), status_code)

@app.route('/v1/ms_download/download_files', methods=['POST'])
def download_files():
    """
    发起下载任务。
    根据分发规则将文件列表拆分，分别转发给各后端，返回一组 task_id。
    前端轮询时，adapter 会聚合所有子任务的状态。
    """
    user_req = request.get_json()
    print(user_req)
    url = user_req.get('url', '')
    repo_type = user_req.get('repo_type', 'model')
    repo_name = user_req.get('repo_name', '')
    files_list = user_req.get('files_list', [])
    files_len_list = user_req.get('files_len_list', [])
    max_files_param = user_req.get('max_files', 'full')
    if not url:
        return (jsonify({'status': 'error', 'message': 'url is required'}), 400)
    if not files_list:
        return (jsonify({'status': 'error', 'message': 'files_list is required'}), 400)
    assignments = distribute_files(files_list, files_len_list)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_folder_name = f'bak_{timestamp}'
    sub_tasks = []
    for assign in assignments:
        server = assign['server']
        body = {'url': url, 'repo_type': repo_type, 'repo_name': repo_name, 'files_list': assign['files'], 'files_len_list': assign['files_len'], 'max_files': max_files_param, 'backup_folder_name': backup_folder_name}
        status_code, data = forward_request('POST', server, '/v1/ms_download/download_files', json_body=body, timeout=30)
        if status_code == 202 and data.get('status') == 'success':
            sub_tasks.append({'server': server, 'task_id': data['task_id'], 'files': assign['files'], 'files_len': assign['files_len'], 'total': len(assign['files'])})
            logger.info(f"  子任务 {data['task_id']} -> {server['host']}:{server['port']} ({len(assign['files'])} 个文件)")
        else:
            logger.error(f"  子任务提交失败 -> {server['host']}:{server['port']}, status={status_code}, data={data}")
    if not sub_tasks:
        return (jsonify({'status': 'error', 'message': '所有后端子任务提交失败'}), 502)
    adapter_task_id = os.urandom(8).hex()
    with task_routing_lock:
        task_routing[adapter_task_id] = {'status': 'running', 'sub_tasks': sub_tasks, 'total': len(files_list), 'url': url, 'repo_type': repo_type, 'repo_name': repo_name, 'backup_folder_name': backup_folder_name, 'created_at': datetime.datetime.now().isoformat()}
    total_files = sum((st['total'] for st in sub_tasks))
    return (jsonify({'status': 'success', 'task_id': adapter_task_id, 'total': total_files}), 202)

@app.route('/v1/ms_download/download_status', methods=['GET'])
def download_status():
    """
    查询下载任务的实时状态。
    聚合所有子任务的状态。
    """
    task_id = request.args.get('task_id', '')
    if not task_id:
        return (jsonify({'status': 'error', 'message': 'task_id is required'}), 400)
    with task_routing_lock:
        task_info = task_routing.get(task_id)
    if not task_info:
        return (jsonify({'status': 'error', 'message': f'task_id not found: {task_id}'}), 404)
    all_downloaded = []
    all_failed = []
    any_running = False
    any_failed_task = False
    total = task_info['total']
    download_paths = []
    backup_folder_paths = []
    for sub in task_info['sub_tasks']:
        server = sub['server']
        stid = sub['task_id']
        status_code, data = forward_request('GET', server, '/v1/ms_download/download_status', params={'task_id': stid}, timeout=30)
        if status_code != 200 or data.get('status') != 'success':
            any_running = True
            logger.warning(f'子任务 {stid} 状态查询失败，标记为 running 等待重试')
            continue
        task_status = data.get('task_status', 'running')
        if task_status == 'running':
            any_running = True
        elif task_status == 'failed':
            any_failed_task = True
        all_downloaded.extend(data.get('downloaded_files', []))
        all_failed.extend(data.get('failed_files', []))
        if data.get('download_path'):
            download_paths.append(data['download_path'])
        if data.get('backup_folder_path'):
            backup_folder_paths.append(data['backup_folder_path'])
    if not any_running and (not any_failed_task):
        agg_status = 'completed'
    elif any_running:
        agg_status = 'running'
    else:
        agg_status = 'failed'
    with task_routing_lock:
        if task_id in task_routing:
            task_routing[task_id]['status'] = agg_status
    return (jsonify({'status': 'success', 'task_status': agg_status, 'downloaded_files': all_downloaded, 'failed_files': all_failed, 'total': total, 'download_path': download_paths[0] if download_paths else '', 'backup_folder_path': backup_folder_paths[0] if backup_folder_paths else '', 'sub_task_count': len(task_info['sub_tasks'])}), 200)

@app.route('/v1/ms_download/upload_files', methods=['POST'])
def upload_files():
    """
    上传已下载的文件夹到 S3 存储。
    由于各后端的 backup_folder_path 不同，需要根据 repo_type/repo_name 找到
    各子任务对应的备份文件夹并发起上传。
    """
    user_req = request.get_json()
    repo_type = user_req.get('repo_type', 'model')
    repo_name = user_req.get('repo_name', '')
    backup_folder_path = user_req.get('backup_folder_path', '')
    if not repo_name:
        return (jsonify({'status': 'error', 'message': 'repo_name is required'}), 400)
    if not backup_folder_path:
        return (jsonify({'status': 'error', 'message': 'backup_folder_path is required'}), 400)
    upload_results = []
    any_success = False
    bucket_path = ''
    for server in BACKEND_SERVERS:
        body = {'repo_type': repo_type, 'repo_name': repo_name, 'backup_folder_path': backup_folder_path}
        status_code, data = forward_request('POST', server, '/v1/ms_download/upload_files', json_body=body, timeout=7200)
        if data and data.get('status') == 'success':
            if data.get('bucket_path') and (not bucket_path):
                bucket_path = data['bucket_path']
            upload_results.extend(data.get('upload_results', []))
            if any((r.get('status') == 'success' for r in data.get('upload_results', []))):
                any_success = True
        elif data and data.get('status') == 'error':
            if 'not found' in data.get('message', '').lower():
                continue
            upload_results.append({'folder': backup_folder_path, 'status': 'failed', 'server': server['host'], 'error': data.get('message', '')})
    normalized_path = backup_folder_path.rstrip('/\\').replace('\\', '/')
    m = re.search('_bak_\\d{8}_\\d{6}$', normalized_path)
    if m:
        backup_folder_name = m.group(0)[1:]
    else:
        backup_folder_name = os.path.basename(normalized_path)
        logger.warning(f'无法从 backup_folder_path 中提取 backup_folder_name，使用 basename: {backup_folder_name}')
    expected_total = None
    with task_routing_lock:
        for tid, info in list(task_routing.items()):
            if info.get('repo_type') == repo_type and info.get('repo_name') == repo_name and (info.get('backup_folder_name') == backup_folder_name):
                expected_total = info.get('total')
                logger.info(f'从 task_routing 命中上传统计：repo={repo_name}, folder={backup_folder_name}, total={expected_total}')
                break
    if expected_total is not None:
        logger.info(f'最终上传统计：repo={repo_name}, folder={backup_folder_name}, total={expected_total}, any_success={any_success}')
    else:
        logger.warning(f'缓存未命中上传统计：repo={repo_name}, folder={backup_folder_name}，回退到按后端返回条目统计')
    if expected_total is not None:
        total_files = expected_total
        success_files = expected_total if any_success else 0
        fail_files = 0 if any_success else expected_total
    else:
        total_files = len(upload_results)
        success_files = sum((1 for r in upload_results if r.get('status') == 'success'))
        fail_files = total_files - success_files
    return (jsonify({'status': 'success', 'upload_results': upload_results, 'backup_folder_deleted': any_success, 'total': total_files, 'success_count': success_files, 'fail_count': fail_files, 'bucket_path': bucket_path}), 200)

@app.route('/v1/ms_download/backends', methods=['GET'])
def list_backends():
    """返回所有后端服务器的状态"""
    results = []
    for server in BACKEND_SERVERS:
        try:
            status_code, data = forward_request('GET', server, '/health', timeout=5)
            results.append({'host': server['host'], 'port': server['port'], 'weight': server['weight'], 'status': 'ok' if status_code == 200 else 'error', 'detail': data if isinstance(data, dict) else {}})
        except Exception as e:
            results.append({'host': server['host'], 'port': server['port'], 'weight': server['weight'], 'status': 'unreachable', 'error': str(e)})
    return (jsonify({'status': 'success', 'backends': results}), 200)

def _cleanup_stale_cache():
    """定期清理 task_routing 中已完成的过期任务，防止内存泄漏。"""
    while True:
        threading.Event().wait(3600)
        now = datetime.datetime.now()
        with task_routing_lock:
            stale_tasks = []
            for tid, info in list(task_routing.items()):
                if info.get('status') in ('completed', 'failed'):
                    created = datetime.datetime.fromisoformat(info['created_at'])
                    if (now - created).total_seconds() > 6 * 3600:
                        stale_tasks.append(tid)
                elif info.get('status') == 'running':
                    created = datetime.datetime.fromisoformat(info['created_at'])
                    if (now - created).total_seconds() > 24 * 3600:
                        stale_tasks.append(tid)
            for tid in stale_tasks:
                del task_routing[tid]
        if stale_tasks:
            logger.info(f'清理了 {len(stale_tasks)} 条过期的 task_routing 记录')
