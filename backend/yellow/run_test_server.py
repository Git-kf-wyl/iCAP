from state_storage import open_state, state_exists, state_isfile
# Private iCAP Yellow business implementation. Do not publish.
import json
import math
import os.path
import os
import sys
import uuid
import io
import zipfile
import urllib.parse
from datetime import datetime
import httpx
import chardet
import glob
import csv
import re
import requests
import time
import atexit
import psutil
import threading
import subprocess
import jsonlines as jsonl
import pandas as pd
import numpy as np
import traceback
from openai import OpenAI
from flask import Flask, request, send_file
from flask_cors import CORS
from services.updateTopChartServer import *
from utils.consts import RULER_2_TESTCASETAGS, MEMORY_TASK_SUBSET_MAP, GAIXIE_DATASET_PATH, MEMORY_DATASET_PATH, MCP_ATLAS_EXEC, CUSTOM_RULER2_PROC_DISPATCH
from call_api import call_judge_model, EVAL_JUDGE_MODEL_NAME, EVAL_JUDGE_MODEL_URL

def run_aisf_32b_dataset(*args, **kwargs):
    raise RuntimeError('原仓库未包含完整 AISF box 执行依赖，请使用已接入的数据集评测')
from services.custom_proc_common import extract_generation_config
from services.minitest.min_test import MinDatasetEvaluator
from services.multi.mutil_ruler1_entry import evaluate_model
from services.multi_ruler2.outfit.auto_run import run_custom_outfit_eval
from services.multi_ruler2.children_study.result_statistics import get_global_variables_from_df, add_all_acc_column, build_evaluation_statistics_sheet, build_product_acceptance_sheet, CAMERA_POSITION_COL, DYNAMIC_STATISTICS_COLS
from services.multi_ruler2.children_study.upload_result_builder import build_result_from_uploaded_excel
from services.multi_ruler2.children_study.upload_result_builder import build_memory_result_from_uploaded_excel, MEMORY_BUSINESS_MAP
from services.aisf_banxue.upload_result_builder import build_banxue_result_from_uploaded_excel, BANXUE_SUBTASKS
from services.aisf_coordinator.upload_result_builder import build_coordinator_result_from_uploaded_excel
from services.aisf_guiTican.upload_result_builder import build_gui_result_from_uploaded_excel
from services.aisf_skillTiCan.upload_result_builder import build_skill_result_from_uploaded_excel
from services.aisf_rewrite.upload_result_builder import build_rewrite_result_from_uploaded_excel
from services.multi_ruler2.aisf_yitu.upload_result_builder import build_yitu_result_from_uploaded_excel
from services.aisf_memory.runMemoryServer import *
from services.multi_ruler2.children_study.analyze_statistics import analyze_cost_time
from utils.utils import *
from utils.eval_utils import *
from services.simultaneous_interpretation import run_mt_eval, run_asr_eval, run_tts_eval
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'CCNRuler1EvalScope'))
sys.path.append(os.path.join(current_dir, 'CCNRuler2EvalScope'))
app = Flask(__name__)
CORS(app)
TEST_TASK_INDEX = 1
SUCCESS = 200
PARAM_ERR = 400
TESTCASE_ALREADY_EXIST = 408
MODEL_ALREADY_EXIST = 409
MODEL_NOT_EXIST = 410
SERVER_ERR = 500
tasks = {}
current_processes = []
proxy_url = ''
proxies = {}
transport = httpx.HTTPTransport(retries=3, verify=True)
http_client = httpx.Client(transport=transport, timeout=10)

@app.route('/v1/check_run_test_progress/<task_id>', methods=['GET'])
def check_run_test_progress(task_id):
    task = tasks.get(task_id)
    if task is None:
        return (jsonify({'error': '任务不存在'}), 404)
    if task['status'] == 'failed':
        return jsonify({'task_id': task_id, 'status': 'failed', 'res': task.get('error') or task.get('description','评测失败')})
    return (jsonify(task), 200)

def _pack_files_to_zip(file_paths, dataset_name, base_dir):
    """将多个文件打包为单个 zip，返回 zip 的相对路径（相对 cwd，供 download/file 下载）。

    zip 落在 base_dir 下（与源文件同目录），文件名用数据集标识，避免同名冲突追加序号；
    每次重新打包覆盖旧 zip，保证下载内容最新。
    """
    os.makedirs(base_dir, exist_ok=True)
    safe_name = re.sub('[\\\\/:*?"<>|]', '_', str(dataset_name)) or 'files'
    zip_path = os.path.join(base_dir, f'{safe_name}_files.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fp in file_paths:
            full = os.path.join(os.getcwd(), fp) if not os.path.isabs(fp) else fp
            if state_isfile(full):
                zf.write(full, os.path.basename(fp))
    return zip_path

@app.route('/v1/get_file_path', methods=['GET'])
def get_file_path():
    global tasks
    task_id = request.args.get('task_id')
    dataset = request.args.get('dataset')
    assessment_type = request.args.get('assessmentType', '')
    evaluation_type = request.args.get('evaluationType', '')
    if not task_id or not dataset or (not assessment_type) or (not evaluation_type):
        return (jsonify({'error': 'get_file_path need 4 params, params must be not null'}), 400)
    if task_id is None or task_id in tasks:
        if task_id in tasks:
            use_cache_config = tasks[task_id]['taskConfig']['use_cache']
            model_id = tasks[task_id]['model_id'].split('/')[-1].split(';')[-1]
        else:
            use_cache_config = './outputs/0820伴学'
            model_id = None
        cache_path = use_cache_config[-1] if isinstance(use_cache_config, list) else use_cache_config
        if 'Ruler1' in assessment_type and 'multiple' in evaluation_type:
            model_cache_path = os.path.join(cache_path, model_id) if model_id else cache_path
        else:
            model_cache_path = os.path.join(cache_path, 'reviews', model_id) if model_id else cache_path
    else:
        virtual_task = _build_virtual_task_from_local(task_id)
        if virtual_task is None:
            return (jsonify({'error': f'task_id {task_id} 对应的本地结果不存在'}), 404)
        model_id = virtual_task['model_id']
        reviews_repo = os.path.join('outputs', model_id, task_id, 'reviews', model_id)
        model_cache_path = reviews_repo if os.path.isdir(reviews_repo) else os.path.join('outputs', model_id, task_id)
    print('model_cache_path: ', model_cache_path)
    all_file = []
    if assessment_type in {'TTS', 'ASR+MT+TTS'}:
        excel_files = glob.glob(os.path.join(model_cache_path, '*.xlsx'))
        wav_files = glob.glob(os.path.join(model_cache_path, '*.wav'))
        pcm_files = glob.glob(os.path.join(model_cache_path, '*.pcm'))
        all_file = excel_files + wav_files + pcm_files
    else:
        csv_path = os.path.join(model_cache_path, '*.csv')
        csv_files = glob.glob(csv_path)
        if csv_files:
            all_file = csv_files
            excel_file = glob.glob(os.path.join(model_cache_path, '*.xlsx'))
            all_file += excel_file
        else:
            all_file = glob.glob(os.path.join(model_cache_path, '*.jsonl'))
            json_file = glob.glob(os.path.join(model_cache_path, '*.json'))
            excel_file = glob.glob(os.path.join(model_cache_path, '*.xlsx'))
            all_file += excel_file + json_file
    files = []
    dataset = os.path.basename(dataset).replace('.xlsx', '')
    try:
        if all_file:
            for file_path in all_file:
                file_name = os.path.basename(file_path)
                if dataset == 'all' or dataset in file_name:
                    files.append(file_path)
            if len(files) > 1:
                zip_path = _pack_files_to_zip(files, dataset, model_cache_path)
                files = [zip_path]
            return files
        else:
            return (jsonify({'error': '没有可下载的文件'}), 400)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/get_run_test_progress_list', methods=['GET'])
def get_run_test_progress_list():
    global tasks
    tasks = get_tasks()
    res = []
    update_eval_rate(tasks)
    with open_state(TASKS, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)
    for key, val in tasks.items():
        res.insert(0, val)
    return (jsonify(res), 200)

@app.route('/v1/get_one_test_task', methods=['POST'])
def get_one_test_task():
    user_req = request.get_json()
    task_id = user_req['task_id']
    task = get_one_task(task_id)
    if task == {}:
        return (jsonify({'message': 'not find the task'}), 500)
    return (jsonify(task), 200)

@app.route('/v1/delete_test_progress', methods=['POST'])
def delete_test_progress():
    user_req = request.get_json()
    task_id = user_req['task_id']
    if task_id not in tasks:
        return (jsonify({'error': '任务不存在'}), 404)
    del tasks[task_id]
    set_tasks(tasks)
    return (jsonify({'info': '删除成功'}), 200)

def run_eval(python_file, task_config, task_id):
    global tasks, current_processes
    python_interpreter = sys.executable
    config_str = json.dumps(task_config, ensure_ascii=False)
    if os.name == 'nt':
        import tempfile
        tmp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False)
        tmp_file.write(config_str)
        tmp_file.close()
        encoding = 'gbk' if os.name == 'nt' else 'utf-8'
        proc = subprocess.Popen([python_interpreter, '-u', python_file, '--config', tmp_file.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding=encoding, errors='replace', bufsize=1)
        tmp_path = tmp_file.name
    else:
        proc = subprocess.Popen([python_interpreter, '-u', python_file], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', bufsize=1)
    pid = proc.pid
    tasks[task_id]['process_id'] = pid
    set_tasks(tasks)
    current_processes.append(proc)
    try:
        if os.name == 'nt':
            stdout, stderr = proc.communicate()
        else:
            stdout, stderr = proc.communicate(input=config_str)
        ret_code = proc.returncode
        print(f'子进程退出码: {ret_code}')
        if stdout:
            print('STDOUT:', stdout[:500])
        if stderr:
            print('STDERR:', stderr[:500])
    except (BrokenPipeError, OSError) as e:
        print(f'子进程错误信息: {e}')

def spawn_eval_proc(script, config_dict, task_id):
    """以独立子进程方式启动一个评测，立即返回不等待（非阻塞）。

    用于尺子2特殊业务（儿童伴读/意图/记忆/改写）的进程隔离：
    子进程存活不依赖 flask 服务进程，服务启动/重启不会中断测评。

    每个特殊业务子进程会把自身的进度/状态写回 backend/config/tasks.json，
    由 /v1/get_test_tasks 轮询读取，因此前端无需改动。
    """
    global tasks, current_processes
    python_interpreter = sys.executable
    import tempfile
    config_str = json.dumps(config_dict, ensure_ascii=False, default=str)
    tmp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False)
    tmp_file.write(config_str)
    tmp_file.close()
    log_path = os.path.join('outputs', str(config_dict.get('model_id', '')), str(task_id), 'logs')
    os.makedirs(log_path, exist_ok=True)
    proc_log = open_state(os.path.join(log_path, 'eval_log.log'), 'a', encoding='utf-8', errors='replace')
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    creationflags = 0
    if os.name == 'nt':
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen([python_interpreter, '-u', script, '--config', tmp_file.name], stdout=proc_log, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=env, creationflags=creationflags)
    pid = proc.pid
    if task_id in tasks:
        tasks[task_id]['process_id'] = pid
        tasks[task_id]['proc_type'] = 'ruler2_custom'
        tasks[task_id]['proc_script'] = script
        set_tasks(tasks)
    current_processes.append(proc)
    print(f'spawn_eval_proc: {script} pid={pid} task_id={task_id}')
    return pid

def run_ruler1_eval(task_id, model_id, model_config, user_req, opensource_testcases):
    all_start_time = time.time()
    global tasks
    try:
        model_name = model_config['info']['model_name']
        tasks[task_id] = generate_run_task_info(user_req, model_id, model_name, model_config, task_id)
        set_tasks(tasks)
        public_conf = [{'api_url': param['endpoint'], 'api_key': param['api_key'] if param['api_key'] else 'EMPTY', 'model': model_name, 'non_openai_format': not param['is_openai_format']} for param in model_config['config']['api_params_available']]
        task_config = []
        for arg in user_req['dataset_args']:
            try:
                generation_config = json.loads(arg['generate_config'])
            except:
                generation_config = get_generate_config(model_config['config']['params'], model_name)
            if 'qwen3.' in model_name.lower() and generation_config.get('enable_thinking', '0') in ('0', 'false'):
                generation_config.update({'chat_template_kwargs': {'enable_thinking': False}})
            print('run_ruler1_eval generation_config', generation_config)
            try:
                metric_list = arg['metric_list']
            except:
                metric_list = get_metric(arg['dataset_name'])
            try:
                eval_batch_size = int(arg['eval_batch_size'])
            except:
                eval_batch_size = 1
            request_retry = user_req['request_retry'] if 'request_retry' in user_req else False
            retry_content_none = user_req['retry_content_none'] if 'retry_content_none' in user_req else False
            use_cache = user_req['use_cache'] if 'use_cache' in user_req else None
            dataset_args = get_dataset_args(model_config, opensource_testcases, metric_list, arg, user_req)
            iter_config = {'models': public_conf, 'model': model_id, 'stream': user_req['stream'], 'eval_type': user_req['eval_type'], 'datasets': [arg['dataset_name']], 'dataset_args': dataset_args, 'eval_batch_size': eval_batch_size, 'generation_config': generation_config, 'limit': get_limit(user_req['limit']), 'request_retry': request_retry, 'retry_content_none': retry_content_none, 'judge_worker_num': user_req['judge_worker_num'], 'task_id': task_id, 'use_cache': use_cache, 'seed': None, 'judge_strategy': 'auto', 'judge_model_args': [{'model_id': EVAL_JUDGE_MODEL_NAME, 'api_url': EVAL_JUDGE_MODEL_URL, 'api_key': '', 'generation_config': {'max_tokens': 4096, 'temperature': 0.01, 'request_nums': 1, 'enable_thinking': False, 'chat_template_kwargs': {'enable_thinking': False}}}]}
            task_config.append(iter_config)
        start_time = time.time()
        run_eval(RULER_1_EXEC, task_config, task_id)
        update_eval_res(tasks, task_id, model_name, model_id)
        end_time = time.time()
        duration = end_time - start_time
        print('test time: ', duration)
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
    all_end_time = time.time()
    tasks[task_id]['runningTime'] = all_end_time - all_start_time
    set_tasks(tasks)

def run_mcp_atlas_eval(task_id, model_id, model_config, user_req):
    """Run MCP-Atlas evaluation via subprocess (similar to run_ruler1_eval)."""
    all_start_time = time.time()
    global tasks
    try:
        model_name = model_config['info']['model_name']
        tasks[task_id] = generate_run_task_info(user_req, model_id, model_name, model_config, task_id)
        set_tasks(tasks)
        public_conf = [{'api_url': param['endpoint'], 'api_key': param['api_key'] if param['api_key'] else 'EMPTY', 'model': model_name, 'non_openai_format': not param['is_openai_format']} for param in model_config['config']['api_params_available']]
        task_config = []
        for arg in user_req['dataset_args']:
            try:
                generation_config = json.loads(arg['generate_config'])
            except Exception:
                generation_config = get_generate_config(model_config['config']['params'], model_name)
            if 'qwen3.' in model_name.lower() and generation_config.get('enable_thinking', '0') in ('0', 'false'):
                generation_config.update({'chat_template_kwargs': {'enable_thinking': False}})
            metric_list = arg.get('metric_list', ['coverage_score', 'pass_rate'])
            eval_batch_size = int(arg.get('eval_batch_size', 1))
            dataset_cfg = arg.get('dataset_args', {})
            mcp_server_url = dataset_cfg.get('mcp_server_url', 'http://127.0.0.1:1/unconfigured')
            filter_enabled_servers = dataset_cfg.get('filter_enabled_servers', True)
            max_tool_calls = int(dataset_cfg.get('max_tool_calls', 100))
            pass_threshold = float(dataset_cfg.get('pass_threshold', 0.75))
            iter_config = {'models': public_conf, 'model': model_id, 'stream': user_req['stream'], 'eval_type': user_req.get('eval_type', 'ruler2'), 'datasets': [arg['dataset_name']], 'dataset_args': {arg['dataset_name']: {'local_path': arg.get('local_path', './testsuite/TestSuite/mcp_atlas'), 'metric_list': metric_list, 'few_shot_num': arg.get('few_shot_num', 0), 'mcp_server_url': mcp_server_url, 'filter_enabled_servers': filter_enabled_servers, 'max_tool_calls': max_tool_calls, 'pass_threshold': pass_threshold}}, 'eval_batch_size': eval_batch_size, 'generation_config': generation_config, 'limit': get_limit(user_req.get('limit')), 'task_id': task_id, 'judge_strategy': 'llm', 'judge_model_args': [{'model_id': EVAL_JUDGE_MODEL_NAME, 'api_url': EVAL_JUDGE_MODEL_URL, 'api_key': '', 'generation_config': {'max_tokens': 4096, 'temperature': 0.01, 'enable_thinking': False, 'chat_template_kwargs': {'enable_thinking': False}}}], 'mcp_server_url': mcp_server_url, 'filter_enabled_servers': filter_enabled_servers, 'max_tool_calls': max_tool_calls, 'pass_threshold': pass_threshold}
            task_config.append(iter_config)
        start_time = time.time()
        run_eval(MCP_ATLAS_EXEC, task_config, task_id)
        update_eval_res(tasks, task_id, model_name, model_id)
        end_time = time.time()
        duration = end_time - start_time
        print('mcp_atlas test time: ', duration)
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
    all_end_time = time.time()
    tasks[task_id]['runningTime'] = all_end_time - all_start_time
    set_tasks(tasks)

def run_outfit(model_config, task_id, model_id, limit):
    model_name = model_config['info']['model_name']
    public_conf = [{'api_url': param['endpoint'], 'model': model_name} for param in model_config['config']['api_params_available']]
    api_url = public_conf[0]['api_url']
    try:
        print('run_outfit 1')
        unzip_if_needed(OUTFIT_DATASET_IMAGE_ZIP_PATH, OUTFIT_DATASET_PATH)
        output_path = f'outputs/{model_id}/{task_id}'
        print('run_outfit 2')
        run_custom_outfit_eval(model_name, api_url, OUTFIT_DATASET_PATH, output_path, model_id, limit)
        print('run_outfit over')
    except Exception as e:
        print(f'run_outfit error:{e}')
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)

def _parse_excel_sheet_into_tables(excel_file, sheet_name):
    """解析Excel中一个统计sheet，将其中的多个 (title, DataFrame) 分离为 [{title, columns, rows}, ...]

    Excel中的统计sheet格式（由 write_dataframes_to_sheet 写入）：
        行1: 标题（##开头）
        行2: 列名
        行3+: 数据行
        （空行）
        （空行）
        下一个标题...

    返回: [{title, columns, rows}, ...]
    """
    from openpyxl import load_workbook
    wb = load_workbook(excel_file, read_only=True, data_only=True)
    if sheet_name not in wb.sheetnames:
        wb.close()
        return []
    ws = wb[sheet_name]
    tables = []
    current_title = None
    current_headers = []
    current_rows = []
    state = 0
    consecutive_empty = 0
    for row in ws.iter_rows(values_only=True):
        values = list(row)
        first_val = values[0] if values else None
        is_empty_row = all((v is None for v in values))
        if is_empty_row:
            consecutive_empty += 1
            if current_title and state == 2 and (consecutive_empty >= 1):
                if current_headers and current_rows:
                    tables.append({'title': current_title, 'columns': current_headers, 'rows': current_rows})
                current_title = None
                current_headers = []
                current_rows = []
                state = 0
            continue
        consecutive_empty = 0
        if state == 0:
            if first_val and isinstance(first_val, str) and first_val.startswith('##'):
                current_title = first_val
                state = 1
            continue
        if state == 1:
            current_headers = [str(v) if v is not None else '' for v in values]
            state = 2
            continue
        if state == 2:
            row_dict = {}
            for i, v in enumerate(values):
                col_name = current_headers[i] if i < len(current_headers) else f'col{i}'
                if v is not None and (not isinstance(v, float) or (not pd.isna(v) and (not np.isinf(v)))):
                    row_dict[col_name] = v
                else:
                    row_dict[col_name] = None
            current_rows.append(row_dict)
            continue
    if current_title and current_headers and current_rows:
        tables.append({'title': current_title, 'columns': current_headers, 'rows': current_rows})
    wb.close()
    if not tables:
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            if df is not None and (not df.empty):
                rows = df.replace([np.nan, pd.NA, float('inf'), float('-inf')], None).astype(object).to_dict(orient='records')
                for row in rows:
                    for k, v in list(row.items()):
                        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                            row[k] = None
                tables.append({'title': sheet_name, 'columns': list(df.columns), 'rows': rows})
        except Exception:
            pass
    return tables

def _build_eld_statistics_json(output_path, model_name_safe, dataset_name, task_id, subset_list, limit):
    """在run_eld评测完成后，读取输出的Excel文件，生成结构化统计JSON

    从Excel中读取除第一个工作表（原始数据）外的所有统计工作表，
    将每个sheet解析为 [{title, columns, rows}, ...] 格式。

    返回: (json_file_path, all_stats_dict) 或 None
    """
    import glob as glob_mod
    review_dir = os.path.join(output_path, 'reviews', model_name_safe)
    if not state_exists(review_dir):
        print(f'[_build_eld_statistics_json] review_dir not found: {review_dir}')
        return None
    excel_pattern = os.path.join(review_dir, f'{dataset_name}报告_{task_id}.xlsx')
    excel_files = glob_mod.glob(excel_pattern)
    if not excel_files and '稳定性' in (subset_list or []):
        excel_pattern = os.path.join(review_dir, f'{dataset_name}报告_{task_id}_run1.xlsx')
        excel_files = glob_mod.glob(excel_pattern)
    if not excel_files:
        print(f'[_build_eld_statistics_json] Excel not found: {excel_pattern}')
        return None
    excel_file = excel_files[0]
    try:
        from openpyxl import load_workbook
        wb = load_workbook(excel_file, read_only=True)
        all_sheet_names = wb.sheetnames
        wb.close()
        stat_sheet_names = all_sheet_names[1:] if len(all_sheet_names) > 1 else []
        if not stat_sheet_names:
            print(f'[_build_eld_statistics_json] No statistic sheets found in Excel')
            return None
        all_stats_data = {}
        for sheet_name in stat_sheet_names:
            tables = _parse_excel_sheet_into_tables(excel_file, sheet_name)
            if tables:
                all_stats_data[sheet_name] = tables
        if not all_stats_data:
            print('[_build_eld_statistics_json] No data parsed from statistic sheets')
            return None
        json_file = os.path.join(review_dir, f'{dataset_name}_statistics_{task_id}.json')
        with open_state(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_stats_data, f, ensure_ascii=False, indent=2)
        print(f'[_build_eld_statistics_json] saved: {json_file} (sheets: {list(all_stats_data.keys())})')
        return (json_file, all_stats_data)
    except Exception as e:
        print(f'[_build_eld_statistics_json] error: {e}')
        traceback.print_exc()
        return None

def _dataframes_to_json(stats_list):
    """将build_*_sheet返回的 [(title, DataFrame), ...] 转为可序列化的JSON"""
    result = []
    for title, df in stats_list:
        if df is None or df.empty:
            continue
        rows = df.replace([np.nan, pd.NA, float('inf'), float('-inf')], None).astype(object).to_dict(orient='records')
        for row in rows:
            for k, v in list(row.items()):
                if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                    row[k] = None
        result.append({'title': title, 'columns': list(df.columns), 'rows': rows})
    return result
    model_name = model_config['info']['model_name']
    public_conf = [{'api_url': param['endpoint'], 'api_key': param['api_key'], 'model_params': param['params'], 'model': model_name, 'model_id': model_id} for param in model_config['config']['api_params_available']]
    try:
        print('***start run_min_test***')
        output_path = f'outputs/{model_id}/{task_id}'
        min_dataset_evaluator = MinDatasetEvaluator(public_conf[0], output_path, limit)
        min_dataset_evaluator.run_min_test_eval()
        print('***end run_min_test***')
    except Exception as e:
        print(f'***run_min_test error***:{e}')
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)

def run_mmlm(model_config, task_id, model_id, config):
    print(f'start run eval {config}')
    model_name = model_config['info']['model_name']
    public_conf = [{'api_url': param['endpoint'], 'model': model_name} for param in model_config['config']['api_params_available']]
    api_url = public_conf[0]['api_url']
    dataset = config['dataset']
    data_set_path = MLLM_RULER1_DATASET_PATH_BASE + dataset
    try:
        output_path = f'outputs/{model_id}/{task_id}'
        cur_model_info = {'model_name': model_name, 'model_url': api_url, 'model_id': model_id}
        subset_list = config.get('subset_list', [])
        limit = get_limit(config.get('limit', 0))
        num_workers = config.get('num_workers', 1)
        eval_info = {'input_path': data_set_path, 'output_path': output_path, 'limit': limit, 'dataset_name': dataset, 'subset_list': subset_list, 'num_workers': num_workers}
        log_dir = os.path.join(output_path, 'logs')
        if not state_exists(log_dir):
            os.makedirs(log_dir)
        evaluate_model(dataset, cur_model_info, eval_info)
        print(f'run_mmlm {data_set_path} over')
    except Exception as e:
        print(f'run_mmlm {data_set_path} error:{e}')
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)

def run_ruler2_eval(task_id, model_id, model_config, user_req, field_testcases):
    all_start_time = time.time()
    try:
        model_name = model_config['info']['model_name']
        tasks[task_id] = generate_run_task_info(user_req, model_id, model_name, model_config, task_id)
        set_tasks(tasks)
        public_conf = [{'api_url': param['endpoint'], 'api_key': param['api_key'] if param['api_key'] else 'EMPTY', 'model': model_name, 'non_openai_format': not param['is_openai_format']} for param in model_config['config']['api_params_available']]
        task_config = []
        custom_ruler2_datasets = []
        for arg in user_req['dataset_args']:
            if arg['dataset_name'] in LLM_RULER2_CUSTOM_DATASETS or any((tag in arg['testcase_tags'] for tag in RULER_2_TESTCASETAGS)):
                custom_ruler2_datasets.append(arg['dataset_name'])
                continue
            try:
                generation_config = json.loads(arg['generate_config'])
            except:
                generation_config = get_generate_config(model_config['config']['params'], model_name)
            if model_id.startswith('openpangu-2.0'):
                generation_config['thinking'] = {'type': 'disabled'}
            request_retry = user_req['request_retry'] if 'request_retry' in user_req else False
            retry_content_none = user_req['retry_content_none'] if 'retry_content_none' in user_req else False
            use_cache = user_req['use_cache'] if 'use_cache' in user_req else None
            dataset_args = get_dataset_args(model_config, field_testcases, arg['metric_list'], arg, user_req)
            iter_config = {'models': public_conf, 'model': model_id, 'stream': user_req['stream'], 'eval_type': user_req['eval_type'], 'datasets': [arg['dataset_name']], 'dataset_args': dataset_args, 'eval_batch_size': int(arg['eval_batch_size']), 'generation_config': generation_config, 'limit': get_limit(user_req['limit']), 'request_retry': request_retry, 'retry_content_none': retry_content_none, 'judge_worker_num': user_req['judge_worker_num'], 'task_id': task_id, 'use_cache': use_cache, 'seed': None, 'judge_strategy': 'auto', 'judge_model_args': [{'model_id': EVAL_JUDGE_MODEL_NAME, 'api_url': EVAL_JUDGE_MODEL_URL, 'api_key': '', 'generation_config': {'max_tokens': 4096, 'temperature': 0.01, 'request_nums': 1, 'enable_thinking': False, 'chat_template_kwargs': {'enable_thinking': False}}}]}
            task_config.append(iter_config)
        start_time = time.time()
        print('run start')
        if len(task_config) > 0:
            print('start RULER_2_EXEC')
            run_eval(RULER_2_EXEC, task_config, task_id)
        print(f"dataset_args: {user_req['dataset_args']}")
        NAME_DISPATCH = {'视觉感知': run_outfit}
        threads = []
        spawned_custom = False

        def _start_thread(target, args):
            tid = 'TASK_' + str(uuid.uuid4())
            tasks[task_id]['thread_id'] = tid
            set_tasks(tasks)
            t = threading.Thread(target=target, args=args)
            t.start()
            threads.append(t)
            return t
        tags = user_req['dataset_args'][0].get('testcase_tags', [])
        spawned_generation_config = extract_generation_config(user_req)
        for dataset_name in custom_ruler2_datasets:
            matched = False
            for tag, script in CUSTOM_RULER2_PROC_DISPATCH.items():
                if tag in tags:
                    print(f'[custom] {dataset_name} → tag="{tag}" spawn subprocess')
                    spawn_eval_proc(script, {'model_config': model_config, 'task_id': task_id, 'model_id': model_id, 'user_req': user_req, 'thread_id': 'TASK_' + str(uuid.uuid4()), 'generation_config': spawned_generation_config}, task_id)
                    spawned_custom = True
                    matched = True
                    break
            if matched:
                continue
            if dataset_name in NAME_DISPATCH:
                print(f'[custom] {dataset_name} → by dataset_name')
                _start_thread(NAME_DISPATCH[dataset_name], (model_config, task_id, model_id, get_limit(user_req.get('limit'))))
        for t in threads:
            t.join()
        print('run over')
        if not spawned_custom:
            update_eval_res(tasks, task_id, model_name, model_id)
        end_time = time.time()
        duration = end_time - start_time
        print('test time: ', duration)
    except Exception as e:
        print(f'run err: {e}')
        traceback.print_exc()
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
    all_end_time = time.time()
    tasks[task_id]['runningTime'] = all_end_time - all_start_time
    set_tasks(tasks)

def run_dev_eval(task_id, model_id, model_config, user_req, dev_testcases):
    global tasks
    all_start_time = time.time()
    try:
        model_name = model_config['info']['model_name']
        tasks[task_id] = generate_run_task_info(user_req, model_id, model_name, model_config, task_id)
        set_tasks(tasks)
        public_conf = [{'api_url': param['endpoint'], 'api_key': param['api_key'] if param['api_key'] else 'EMPTY', 'model': model_name, 'non_openai_format': not param['is_openai_format']} for param in model_config['config']['api_params_available']]
        task_config = []
        for arg in user_req['dataset_args']:
            try:
                generation_config = json.loads(arg['generate_config'])
            except:
                generation_config = get_generate_config(model_config['config']['params'], model_name)
            request_retry = user_req['request_retry'] if 'request_retry' in user_req else False
            retry_content_none = user_req['retry_content_none'] if 'retry_content_none' in user_req else False
            use_cache = user_req['use_cache'] if 'use_cache' in user_req else None
            dataset_args = get_dataset_args(model_config, dev_testcases, arg['metric_list'], arg, user_req, True)
            iter_config = {'models': public_conf, 'model': model_id, 'eval_type': user_req['eval_type'], 'datasets': [arg['dataset_name']], 'dataset_args': dataset_args, 'eval_batch_size': int(arg['eval_batch_size']), 'generation_config': generation_config, 'limit': get_limit(user_req['limit']), 'request_retry': request_retry, 'retry_content_none': retry_content_none, 'judge_worker_num': user_req['judge_worker_num'], 'task_id': task_id, 'use_cache': use_cache, 'seed': None, 'judge_strategy': 'auto', 'judge_model_args': [{'model_id': EVAL_JUDGE_MODEL_NAME, 'api_url': EVAL_JUDGE_MODEL_URL, 'api_key': '', 'generation_config': {'max_tokens': 4096, 'temperature': 0.01, 'request_nums': 1, 'enable_thinking': False, 'chat_template_kwargs': {'enable_thinking': False}}}]}
            task_config.append(iter_config)
        start_time = time.time()
        run_eval(RULER_2_EXEC, task_config, task_id)
        update_eval_res(tasks, task_id, model_name, model_id)
        end_time = time.time()
        duration = end_time - start_time
        print('test time: ', duration)
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
    all_end_time = time.time()
    tasks[task_id]['runningTime'] = all_end_time - all_start_time
    set_tasks(tasks)

def generate_task_id():
    global TEST_TASK_INDEX
    curr_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    if TEST_TASK_INDEX >= 10000:
        TEST_TASK_INDEX = 1
    task_id = curr_time + f'_{TEST_TASK_INDEX:04d}'
    TEST_TASK_INDEX += 1
    return task_id

def need_use_cache(req):
    if req.get('request_retry') is not None or req.get('retry_content_none') is not None:
        if 'use_cache' in req and req['use_cache'] != '' and (req['use_cache'] is not None):
            return True
    return False

@app.route('/v1/get_eld_statistics', methods=['GET'])
def get_eld_statistics():
    """获取儿童伴读评测的结构化统计JSON（供前端展示表格和chart）

    Query params:
        task_id: 任务ID
        model_id: 模型ID
        dataset_name: 数据集名称（可选，默认取第一个）
    """
    task_id = request.args.get('task_id')
    model_id = request.args.get('model_id', '')
    dataset_name = request.args.get('dataset_name', '')
    if not task_id or not model_id:
        return (jsonify({'error': 'task_id and model_id required'}), 400)
    if task_id in tasks:
        output_path = tasks[task_id]['taskConfig'].get('use_cache', f'outputs/{model_id}/{task_id}')
        if isinstance(output_path, list):
            output_path = output_path[0]
        dataset_args = tasks[task_id]['taskConfig'].get('dataset_args', [])
        if not dataset_name and dataset_args:
            dataset_name = dataset_args[0].get('dataset_name', '')
    else:
        output_path = f'outputs/{model_id}/{task_id}'
    model_name_safe = model_id.replace('/', '_').replace('\\', '_')
    if dataset_name:
        json_pattern = os.path.join(output_path, 'reviews', model_name_safe, f'{dataset_name}_statistics_{task_id}.json')
    else:
        json_pattern = os.path.join(output_path, 'reviews', model_name_safe, f'*_statistics_{task_id}.json')
    json_files = glob.glob(json_pattern)
    if not json_files:
        alt_pattern = os.path.join(output_path, '**', f'*_statistics_{task_id}.json')
        json_files = glob.glob(alt_pattern, recursive=True)
    if json_files:
        try:
            with open_state(json_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            return (jsonify({'data': data}), 200)
        except Exception as e:
            print(f'[get_eld_statistics] read JSON error: {e}, fallback to Excel')
    try:
        review_dir = os.path.join(output_path, 'reviews', model_name_safe)
        if not state_exists(review_dir):
            review_dir = output_path
            if not state_exists(review_dir):
                return (jsonify({'error': 'review directory not found'}), 404)
        excel_files = glob.glob(os.path.join(review_dir, '*.xlsx'))
        if not excel_files:
            return (jsonify({'error': 'no excel files found'}), 404)
        target_excel = None
        if dataset_name:
            for f in excel_files:
                if dataset_name in os.path.basename(f):
                    target_excel = f
                    break
        if not target_excel:
            target_excel = excel_files[0]
        from openpyxl import load_workbook as _load_workbook
        wb = _load_workbook(target_excel, read_only=True)
        all_sheet_names = wb.sheetnames
        wb.close()
        stat_sheet_names = all_sheet_names[1:] if len(all_sheet_names) > 1 else []
        if not stat_sheet_names:
            return (jsonify({'error': 'no statistic sheets found in excel'}), 404)
        all_stats_data = {}
        for sheet_name in stat_sheet_names:
            tables = _parse_excel_sheet_into_tables(target_excel, sheet_name)
            valid_tables = [t for t in tables if t.get('title', '').startswith('##')]
            if valid_tables:
                all_stats_data[sheet_name] = valid_tables
        if not all_stats_data:
            return (jsonify({'error': 'no data parsed from statistic sheets'}), 404)
        return (jsonify({'data': all_stats_data}), 200)
    except Exception as e:
        print(f'[get_eld_statistics] Excel parse error: {e}')
        traceback.print_exc()
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/run_testcase_ruler1', methods=['POST'])
def run_testcase_ruler1():
    user_req = request.get_json()
    required_fields = ['stream', 'model_id', 'limit', 'datasets', 'name', 'assessmentType', 'judge_worker_num', 'dataset_args']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    # users = []
    # with open_state(ADMIN_MEMBER, 'r', encoding='utf-8') as f:
    #     reader = csv.DictReader(f)
    #     for row in reader:
    #         user_value = row.get('user', '').strip()
    #         if user_value:
    #             users.append(user_value)
    # if not user_req['username'] or user_req['username'] not in users:
    #     return (jsonify({'message': f'用户无权限，请联系管理员添加'}), 400)
    model_id = user_req['model_id']
    print(os.getcwd())
    with open_state(COMMON_TESTCASE_PATH, 'r', encoding='utf-8') as f:
        opensource_testcases = json.load(f)
    model_config = get_one_model_config(model_id)
    if not model_config:
        return ({'errType': f'Model ({model_id}) not registered'}, 400)
    if need_use_cache(user_req):
        task_id = user_req['use_cache'].split('/')[-1]
    else:
        task_id = generate_task_id()
    thread = threading.Thread(target=run_ruler1_eval, args=(task_id, model_id, model_config, user_req, opensource_testcases))
    thread.start()
    return (jsonify({'task_id': task_id, 'message': '任务已启动，请通过task_id查询进度'}), 200)

@app.route('/v1/run_testcase_mcp_atlas', methods=['POST'])
def run_testcase_mcp_atlas():
    """Start MCP-Atlas evaluation in background thread."""
    user_req = request.get_json()
    required_fields = ['stream', 'model_id', 'limit', 'dataset_args']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    model_id = user_req['model_id']
    model_config = get_one_model_config(model_id)
    if not model_config:
        return ({'errType': f'Model ({model_id}) not registered'}, 400)
    task_id = generate_task_id()
    thread = threading.Thread(target=run_mcp_atlas_eval, args=(task_id, model_id, model_config, user_req))
    thread.start()
    return (jsonify({'task_id': task_id, 'message': '任务已启动，请通过task_id查询进度'}), 200)

@app.route('/v1/run_testcase_ruler2', methods=['POST'])
def run_testcase_ruler2():
    user_req = request.get_json()
    required_fields = ['stream', 'model_id', 'limit', 'datasets', 'name', 'assessmentType', 'judge_worker_num', 'dataset_args']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    users = []
    with open_state(RULER2_MEMBER, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_value = row.get('user', '').strip()
            if user_value:
                users.append(user_value)
    if not user_req['username'] or user_req['username'] not in users:
        return (jsonify({'message': f'用户无权限，请联系管理员添加'}), 400)
    print(os.getcwd())
    encodings = get_encoding(FILED_TESTCASE_PATH)
    with open_state(FILED_TESTCASE_PATH, 'r', encoding=encodings) as f:
        field_testcases = json.load(f)
    model_id = user_req['model_id']
    model_config = get_one_model_config(model_id)
    if not model_config:
        return ({'errType': f'Model ({model_id}) not registered'}, 400)
    if need_use_cache(user_req):
        task_id = user_req['use_cache'].split('/')[-1]
    else:
        task_id = generate_task_id()
    thread = threading.Thread(target=run_ruler2_eval, args=(task_id, model_id, model_config, user_req, field_testcases))
    thread.start()
    return (jsonify({'task_id': task_id, 'message': '任务已启动，请通过task_id查询进度'}), 200)

@app.route('/v1/run_testcase_dev', methods=['POST'])
def run_testcase_dev():
    user_req = request.get_json()
    required_fields = ['stream', 'model_id', 'limit', 'datasets', 'name', 'assessmentType', 'judge_worker_num', 'dataset_args', 'system_prompt', 'username']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    users = []
    with open_state(AISF_MEMBER, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_value = row.get('user', '').strip()
            if user_value:
                users.append(user_value)
    if user_req['username'] not in users:
        return (jsonify({'message': f'用户无权限，请联系管理员添加'}), 400)
    model_id = user_req['model_id']
    print(os.getcwd())
    encodings = get_encoding(DEV_TESTCASE_PATH)
    with open_state(DEV_TESTCASE_PATH, 'r', encoding=encodings) as f:
        dev_testcases = json.load(f)
    model_config = get_one_model_config(model_id)
    if not model_config:
        return (jsonify({'message': f'Model ({model_id}) not registered'}), 400)
    if need_use_cache(user_req):
        task_id = user_req['use_cache'].split('/')[-1]
    else:
        task_id = generate_task_id()
    thread = threading.Thread(target=run_dev_eval, args=(task_id, model_id, model_config, user_req, dev_testcases))
    thread.start()
    return (jsonify({'task_id': task_id, 'message': '任务已启动，请通过task_id查询进度'}), 200)

@app.route('/v1/get_result', methods=['GET'])
def get_result():
    task_id = request.args.get('task_id')
    page = request.args.get('page')
    model_id = request.args.get('model_id', '')
    assessmentType = request.args.get('assessmentType', '')
    origin_dataset = request.args.get('dataset')
    if assessmentType == 'ASR':
        origin_dataset_name = '_'.join(origin_dataset.split('/')[-2:]).replace(' ', '_') if '/' in origin_dataset else origin_dataset
    else:
        origin_dataset_name = origin_dataset.rsplit('/', 1)[-1].replace(' ', '_') if '/' in origin_dataset else origin_dataset
    origin_dataset_name = origin_dataset_name.split('.')[0]
    dataset = origin_dataset if '/' not in origin_dataset and '\\' not in origin_dataset else origin_dataset.replace('/', '_').replace('\\', '_')
    print(f'origin_dataset_name：{origin_dataset_name}\n')
    print(f'dataset：{dataset}\n')
    jsonl_pre_dir = ''
    subset = request.args.get('subset', '')
    if task_id is None:
        use_cache = './outputs/0820伴学'
    elif task_id not in tasks:
        use_cache = f'./outputs/{model_id}/{task_id}'
    else:
        use_cache = tasks[task_id]['taskConfig']['use_cache']
    files = []
    if isinstance(use_cache, str):
        path = os.path.join(use_cache, 'reviews', model_id, jsonl_pre_dir, '*.jsonl')
        print(f'path: {path}')
        files.extend(glob.glob(path))
    elif isinstance(use_cache, list):
        for cache_path in use_cache:
            path = os.path.join(cache_path, 'reviews', model_id, jsonl_pre_dir, '*.jsonl')
            print(f'path: {path}')
            files.extend(glob.glob(path))
    else:
        print("Error: 'use_cache' must be a string or a list")
    start = int(page.split(',')[0])
    end = int(page.split(',')[1])
    result = []
    idx = 0
    subsets = [os.path.basename(file).split('.')[0].split(os.sep)[-1] for file in files if dataset in os.path.basename(file)]
    result_list = []
    for file in files:
        if not state_exists(file):
            return (jsonify({'error': 'path is not exist'}), 400)
        filename = os.path.basename(file)
        if subset:
            if origin_dataset_name in filename and subset in filename:
                with jsonl.open(file, mode='r') as reader:
                    for idx, line in enumerate(reader.iter(type=dict, allow_none=True, skip_invalid=False), start=1):
                        result_list.append(line)
                    break
        elif origin_dataset_name in filename:
            print(f'找到匹配文件了：{filename}')
            with jsonl.open(file, mode='r') as reader:
                for idx, line in enumerate(reader.iter(type=dict, allow_none=True, skip_invalid=False), start=1):
                    if 'live_code_bench' == dataset:
                        if start <= idx <= end:
                            result.append(line)
                    else:
                        result_list.append(line)
                break
    if 'live_code_bench' == dataset:
        return (jsonify({'result': result, 'page_count': math.ceil(idx / 10), 'subset': subsets}), 200)
    sorted_result_list = sorted(result_list, key=lambda x: x['index'])
    return (jsonify({'result': sorted_result_list, 'page_count': math.ceil(idx / (end - start + 1)), 'subset': subsets}), 200)

@app.route('/v1/logs', methods=['GET'])
def get_logs():
    task_id = request.args.get('task_id', '')
    if task_id == '':
        return (jsonify({'error': 'param task_id must be not null'}), 400)
    use_cache = tasks[task_id]['taskConfig']['use_cache']
    if isinstance(use_cache, str):
        use_cache = [use_cache]
    full_log = []
    for cache_path in use_cache:
        if not state_exists(cache_path):
            return (jsonify({'error': f'log path: {cache_path} not exist'}), 400)
        file = os.path.join(cache_path, 'logs', 'eval_log.log')
        if not state_exists(file):
            full_log.append('LogNotFound')
            continue
        try:
            encodings = get_encoding(file)
            with open_state(file, 'r', encoding=encodings) as f:
                logs = f.read()
        except UnicodeDecodeError as e:
            print(f'UnicodeDecodeError: {str(e)}')
            try:
                with open_state(file, 'r', encoding='utf-8') as f:
                    logs = f.read()
            except:
                logs = 'not utf-8.'
        except Exception as err:
            print(f'OtherError: {str(err)}')
            logs = f'OtherError: {str(err)}'
        full_log.append(logs)
    return (jsonify({'logs': '\n'.join(full_log)}), 200)

def _build_virtual_task_from_local(task_id):
    """本地上传的结果未写入 tasks.json，据此从 evaluationResult.json + 磁盘 report json
    重建一个与在线任务同构的虚拟 task，供 update_top_chart 使用。

    仅处理「已带 tag」的本地结果（在线无 tag 结果通常存在 tasks.json，不走此逻辑）。
    榜单各 tag 的 add/modify 函数仅读取 task['createTime'] / task['taskConfig'] /
    task['result'][model_name][0]，与在线任务完全同构，故按 tag 全通解。
    """
    eval_results = get_report_tasks_from_path(EVALUATIONRESULT)
    if not isinstance(eval_results, dict):
        return None
    entry = next((v for v in eval_results.values() if isinstance(v, dict) and v.get('task_id') == task_id), None)
    if not entry:
        return None
    tag = entry.get('tag') or ''
    if not tag:
        return None
    model_id = entry.get('model_id') or ''
    dataset_name = entry.get('task_dataset') or tag
    if not model_id or not dataset_name:
        return None
    report_dir = os.path.join('outputs', model_id, task_id, 'reports', model_id)
    report_path = os.path.join(report_dir, f'{dataset_name}.json')
    if not state_exists(report_path):
        candidates = sorted(glob.glob(os.path.join(report_dir, '*.json')))
        report_path = candidates[0] if candidates else None
    if not report_path:
        return None
    with open_state(report_path, 'r', encoding='utf-8') as f:
        report_map = json.load(f)
    model_name = entry.get('model_name') or model_id
    return {'task_id': task_id, 'task_name': entry.get('task_name', f'{model_id}_{dataset_name}'), 'model_id': model_id, 'model_name': model_name, 'assessmentType': entry.get('assessmentType', '领域评估(Ruler2)'), 'createTime': entry.get('create_time', ''), 'taskConfig': {'evaluationType': entry.get('evaluationType', 'llm'), 'dataset_args': [{'testcase_tags': [tag], 'subset_list': []}]}, 'result': {model_name: [report_map]}}

@app.route('/v1/update_top_chart', methods=['GET'])
def update_top_chart():
    task_ids = request.args.getlist('task_id[]')
    testcases = request.args.getlist('testcase[]')
    if not task_ids:
        return (jsonify({'error': 'param task_ids must be not null'}), 400)
    if not testcases:
        return (jsonify({'error': 'param testcase must be not null'}), 400)
    file_tasks_map = {}
    for task_id in task_ids:
        if task_id not in tasks:
            cur_task = _build_virtual_task_from_local(task_id)
            if cur_task is None:
                return (jsonify({'error': f'task_id {task_id} not exist'}), 405)
        else:
            cur_task = tasks[task_id]
        is_common = 'ruler1' in cur_task['assessmentType'].lower()
        is_llm = 'language' in cur_task['taskConfig']['evaluationType'].lower() or 'llm' in cur_task['taskConfig']['evaluationType'].lower()
        if is_llm:
            res_file = LLM_RULER_1_RESULT if is_common else LLM_RULER_2_RESULT
        else:
            res_file = MULTI_RULER_1_RESULT if is_common else MULTI_RULER_2_RESULT
        if res_file not in file_tasks_map:
            file_tasks_map[res_file] = []
        file_tasks_map[res_file].append(cur_task)
    for res_file, cur_tasks in file_tasks_map.items():
        with open_state(res_file, 'r', encoding='utf-8') as file:
            old_res = json.load(file)
        for cur_task in cur_tasks:
            model_id = cur_task['model_id']
            model_name = cur_task['model_name']
            is_eld = '儿童伴读' in cur_task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
            is_gaixie = '改写' in cur_task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
            is_yitu = '意图' in cur_task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
            is_memory = '记忆' in cur_task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
            is_skilltican = 'skill提参' in cur_task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
            is_guican = 'GUI提参' in cur_task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
            is_banxue = '伴学提参' in cur_task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
            is_coordinator = 'Coordinator' in cur_task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
            is_common = 'ruler1' in cur_task['assessmentType'].lower()
            is_llm = 'language' in cur_task['taskConfig']['evaluationType'].lower() or 'llm' in cur_task['taskConfig']['evaluationType'].lower()
            try:
                if model_id not in old_res.keys():
                    if is_eld:
                        add_new_eld(old_res, model_id, testcases, cur_task, model_name)
                    elif is_yitu:
                        add_new_item_ruler2_yitu(old_res, model_id, testcases, cur_task, model_name)
                    elif is_memory:
                        add_new_item_ruler2_memory(old_res, model_id, testcases, cur_task, model_name)
                    elif is_gaixie:
                        add_new_item_ruler2_gaixie(old_res, model_id, testcases, cur_task, model_name)
                    elif is_skilltican:
                        add_new_item_ruler2_skilltican(old_res, model_id, testcases, cur_task, model_name)
                    elif is_guican:
                        add_new_item_ruler2_guican(old_res, model_id, testcases, cur_task, model_name)
                    elif is_banxue:
                        add_new_item_ruler2_banxue(old_res, model_id, testcases, cur_task, model_name)
                    elif is_coordinator:
                        add_new_item_ruler2_coordinator(old_res, model_id, testcases, cur_task, model_name)
                    elif is_llm and (not is_common):
                        add_new_item_ruler2(old_res, model_id, testcases, cur_task, model_name)
                    else:
                        add_new_item(old_res, model_id, testcases, cur_task, model_name)
                elif is_eld:
                    modify_test_eld(old_res, model_id, testcases, cur_task, model_name)
                elif is_yitu:
                    modify_test_res_ruler2_yitu(old_res, model_id, testcases, cur_task, model_name)
                elif is_memory:
                    modify_test_res_ruler2_memory(old_res, model_id, testcases, cur_task, model_name)
                elif is_gaixie:
                    modify_test_res_ruler2_gaixie(old_res, model_id, testcases, cur_task, model_name)
                elif is_skilltican:
                    modify_test_res_ruler2_skilltican(old_res, model_id, testcases, cur_task, model_name)
                elif is_guican:
                    modify_test_res_ruler2_guican(old_res, model_id, testcases, cur_task, model_name)
                elif is_banxue:
                    modify_test_res_ruler2_banxue(old_res, model_id, testcases, cur_task, model_name)
                elif is_coordinator:
                    modify_test_res_ruler2_coordinator(old_res, model_id, testcases, cur_task, model_name)
                elif is_llm and (not is_common):
                    modify_test_res_ruler2(old_res, model_id, testcases, cur_task, model_name)
                else:
                    modify_test_res(old_res, model_id, testcases, cur_task, model_name)
            except Exception as e:
                return (jsonify({'err': e}), 410)
        with open_state(res_file, 'w', encoding='utf-8') as file:
            json.dump(old_res, file, indent=4, ensure_ascii=False)
    return (jsonify({'info': 'success'}), 200)

def run_vlm_eval(python_file, task_config):
    python_interpreter = sys.executable
    config_str = json.dumps(task_config, ensure_ascii=False)
    if os.name == 'nt':
        import tempfile
        tmp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False)
        tmp_file.write(config_str)
        tmp_file.close()
        subprocess.run([python_interpreter, python_file, '--config', tmp_file.name], text=True, capture_output=True)
        try:
            os.unlink(tmp_file.name)
        except:
            pass
    else:
        subprocess.run([python_interpreter, python_file], input=config_str, text=True, capture_output=True)
    return

def update_android_world_res(tasks, task_id, model_name, and_score):
    tasks[task_id]['status'] = 'completed'
    tasks[task_id]['progress'] = 1.0
    for score in tasks[task_id]['result'][model_name]:
        if score['dataset_name'] == 'AndroidWorld':
            score['score'] = and_score
            score['progress'] = 1.0

def run_dataset_thread(model_config, task_id, model_id, config):
    dataset_name = config.get('dataset', None)
    if dataset_name is None or dataset_name not in MLLM_CUSTOM_DATASETS:
        print(f'Unsupported custom dataset: {dataset_name}')
        return
    thread = threading.Thread(target=run_mmlm, args=(model_config, task_id, model_id, config))
    thread.start()
    thread.join()

def run_mllm_ruler1_custom(model_config, model_id, task_id, user_req):
    for arg in user_req['dataset_args']:
        dataset_name = arg['dataset_name']
        limit = user_req['limit']
        subset_list = arg.get('subset_list', [])
        num_workers = int(arg.get('eval_batch_size', 1))
        eval_config = {'dataset': dataset_name, 'subset_list': subset_list, 'limit': limit, 'num_workers': num_workers}
        run_dataset_thread(model_config, task_id, model_id, eval_config)

def run_vlm_ruler1_eval(task_id, model_id, model_config, user_req, opensource_testcases):
    all_start_time = time.time()
    global tasks
    try:
        model_name = model_config['info']['model_name']
        tasks[task_id] = generate_run_task_info(user_req, model_id, model_name, model_config, task_id)
        with open_state(TASKS, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=4)
        if 'AndroidWorld' in user_req['datasets'] and len(user_req['datasets']) > 1:
            raise ValueError('AndroidWorld 不能与其他测试集同时运行')
        if 'AndroidWorld' in user_req['datasets']:
            limit = get_limit(user_req['limit'])
            use_cache = user_req['use_cache'] if 'use_cache' in user_req else tasks[task_id]['taskConfig']['use_cache']
            output_dir = os.path.join(use_cache, 'output_dir')
            log_dir = os.path.join(use_cache, 'logs')
            review_dir = os.path.join(use_cache, 'review', model_name)
            try:
                split_task_length = math.ceil(len(ANDROID_WORLD_ALL_TASKS[:limit]) / 10)
                split_task_end = len(ANDROID_WORLD_ALL_TASKS[:limit]) % 10
                url = model_config['config']['api_params_available'][0]['endpoint']
                finish_count = 0
                and_score = 0
                log_path = os.path.join(log_dir, f'eval_log.log')
                if not state_exists(log_dir):
                    os.makedirs(log_dir)
                if not state_exists(review_dir):
                    os.makedirs(review_dir)
                episode = True
                with open_state(log_path, 'w', encoding='utf-8') as f:
                    pass
                for i in range(split_task_length):
                    end = 10 * (i + 1)
                    if i == split_task_length - 1:
                        end = split_task_end
                    if end == 0:
                        break
                    if i == 0 and user_req['use_cache']:
                        episode = True
                    step_len = len(ANDROID_WORLD_ALL_TASKS[10 * i:end])
                    response = requests.request(method='GET', url=f"http://127.0.0.1:1/unconfigured{','.join(ANDROID_WORLD_ALL_TASKS[10 * i:end])}&use_cache={use_cache}&output_dir={output_dir}&url={url}&model={model_name}&episode={episode}")
                    data = response.json()['data']
                    pattern = '========= Average =========\\s+\\d[\\d\\.]*\\s+(\\d[\\d\\.]*)'
                    match = re.findall(pattern, data)
                    if match:
                        and_score += step_len * float(match[-1])
                    else:
                        and_score += 0
                    finish_count += 1
                    rate = round(finish_count / split_task_length, 2)
                    tasks[task_id]['progress'] = rate
                    if rate == 1.0:
                        tasks[task_id]['status'] = 'completed'
                    with open_state(log_path, 'a') as f:
                        f.write(data.replace('\\r\\n', '\r\n'))
                score = round(and_score / limit, 2)
                update_android_world_res(tasks, task_id, model_name, score)
            except Exception as e:
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['error'] = str(e)
            response = requests.request(method='GET', url=f'http://127.0.0.1:1/unconfigured{output_dir}')
            if response.status_code == 200:
                data = response.json()['data']
                for idx, file in enumerate(data):
                    response = requests.request(method='GET', url=f'http://127.0.0.1:1/unconfigured{file}', stream=True)
                    file_name = os.path.join(review_dir, os.path.basename(file))
                    if response.status_code == 200:
                        with open_state(file_name, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
        else:
            public_conf = [{'api_base': param['endpoint'], 'key': param['api_key'] if param['api_key'] else 'EMPTY', 'name': 'CustomAPIModel', 'type': model_name, 'video_llm': False, 'temperature': user_req.get('temperature', 0), 'max_tokens': get_need_model_config(param['params'], 'max_tokens') or 2048} for param in model_config['config']['api_params_available']]
            datasets = []
            local_path = {}
            for arg in user_req['dataset_args']:
                if arg['dataset_name'] not in opensource_testcases:
                    raise ValueError(f"dataset {arg['dataset_name']} not exist")
                if arg['dataset_name'] in MLLM_CUSTOM_DATASETS:
                    continue
                if arg['subset_list']:
                    datasets.extend(arg['subset_list'])
                    for subset in arg['subset_list']:
                        local_path.update({subset: opensource_testcases[arg['dataset_name']]['local_path']})
                elif arg['dataset_name']:
                    datasets.append(arg['dataset_name'])
                    local_path.update({arg['dataset_name']: opensource_testcases[arg['dataset_name']]['local_path']})
            try:
                eval_batch_size = int(user_req['eval_batch_size'])
            except:
                eval_batch_size = 1
            request_retry = user_req['request_retry'] if 'request_retry' in user_req else False
            retry_content_none = user_req['retry_content_none'] if 'retry_content_none' in user_req else False
            use_cache = user_req['use_cache'] if 'use_cache' in user_req else None
            iter_config = {'eval_backend': 'VLMEvalKit', 'eval_config': {'data': datasets, 'local_path': local_path, 'limit': get_limit(user_req['limit']), 'mode': 'all', 'model_name': model_id, 'model': public_conf, 'nproc': eval_batch_size, 'reuse': True if use_cache else False, 'verbose': True, 'request_retry': request_retry, 'retry_content_none': retry_content_none}, 'use_cache': use_cache, 'task_id': task_id}
            start_time = time.time()
            if len(datasets) > 0:
                run_eval(RULER_1_EXEC, iter_config, task_id)
            print(f"dataset_args: {user_req['dataset_args']}")
            run_mllm_ruler1_custom(model_config, model_id, task_id, user_req)
            print('run over')
            update_vlm_res(tasks, task_id, model_name, model_id)
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 1.0
            end_time = time.time()
            duration = end_time - start_time
            print('test time: ', duration)
    except Exception as e:
        print(f'run vlm err"{str(e)}')
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
    all_end_time = time.time()
    tasks[task_id]['runningTime'] = all_end_time - all_start_time
    set_tasks(tasks)

@app.route('/v1/run_vlm_ruler1', methods=['POST'])
def run_vlm_ruler1():
    user_req = request.get_json()
    required_fields = ['model_id', 'limit', 'datasets', 'name', 'dataset_args']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    users = []
    with open_state(ADMIN_MEMBER, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_value = row.get('user', '').strip()
            if user_value:
                users.append(user_value)
    if not user_req['username'] or user_req['username'] not in users:
        return (jsonify({'message': f'用户无权限，请联系管理员添加'}), 400)
    model_id = user_req['model_id']
    print(os.getcwd())
    with open_state(COMMON_TESTCASE_PATH, 'r', encoding='utf-8') as f:
        opensource_testcases = json.load(f)
    model_config = get_one_model_config(model_id)
    if not model_config:
        return ({'errType': f'Model ({model_id}) not registered'}, 400)
    if need_use_cache(user_req):
        task_id = user_req['use_cache'].split('/')[-1]
    else:
        task_id = generate_task_id()
    thread = threading.Thread(target=run_vlm_ruler1_eval, args=(task_id, model_id, model_config, user_req, opensource_testcases))
    thread.start()
    return (jsonify({'task_id': task_id, 'message': '任务已启动，请通过task_id查询进度'}), 200)

def reload_score(python_file, task_config):
    python_interpreter = sys.executable
    config_str = json.dumps(task_config, ensure_ascii=False)
    if os.name == 'nt':
        import tempfile
        tmp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False)
        tmp_file.write(config_str)
        tmp_file.close()
        proc = subprocess.run([python_interpreter, python_file, '--config', tmp_file.name], text=True, capture_output=True)
        try:
            os.unlink(tmp_file.name)
        except:
            pass
    else:
        proc = subprocess.run([python_interpreter, python_file], input=config_str, text=True, capture_output=True)
    if proc.returncode == 0:
        return
    raise Exception('错误:', proc.stderr)

@app.route('/v1/update_score', methods=['POST'])
def update_score():
    user_req = request.get_json()
    required_fields = ['task_id', 'dataset', 'sub_dataset', 'answer_id', 'index', 'result']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    if user_req['task_id'] not in tasks:
        return ({'err_info': 'task_id not exist'}, 400)
    model_id_basename = os.path.basename(tasks[user_req['task_id']]['model_id']).rstrip(os.sep)
    use_cache = tasks[user_req['task_id']]['taskConfig']['use_cache']
    try:
        reload_score(UPDATE_SCORE, {'use_cache': use_cache, 'model_id_basename': model_id_basename, 'dataset': user_req['dataset'], 'sub_dataset': user_req['sub_dataset'], 'answer_id': user_req['answer_id'], 'index': user_req['index'], 'result': user_req['result'], 'type': 'update'})
        return (jsonify({'data': '更新成功'}), 200)
    except Exception as e:
        return (jsonify({'data': f'更新失败: {e}'}), 500)

@app.route('/v1/async_score', methods=['POST'])
def async_score():
    user_req = request.get_json()
    required_fields = ['task_id', 'dataset', 'sub_dataset']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    if user_req['task_id'] not in tasks:
        return ({'err_info': 'task_id not exist'}, 400)
    dataset = user_req['dataset']
    model_id_basename = os.path.basename(tasks[user_req['task_id']]['model_id']).rstrip(os.sep)
    model_name = tasks[user_req['task_id']]['model_name']
    use_cache = tasks[user_req['task_id']]['taskConfig']['use_cache']
    metric_list = [metric_list for metric_list in tasks[user_req['task_id']]['taskConfig']['dataset_args'] if metric_list['dataset_name'] == user_req['dataset']][0]['metric_list']
    report_file = f'{use_cache}/reports/{model_id_basename}/{dataset}.json'
    try:
        reload_score(UPDATE_SCORE, {'use_cache': use_cache, 'model_id_basename': model_id_basename, 'dataset': dataset, 'sub_dataset': user_req['sub_dataset'], 'metric_list': metric_list, 'model_name': model_name, 'type': 'async'})
        with open_state(report_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for index, date_score in enumerate(tasks[user_req['task_id']]['result'][model_name]):
            if date_score['dataset_name'] == data['dataset_name']:
                tasks[user_req['task_id']]['result'][model_name][index] = data
        set_tasks(tasks)
        return (jsonify({'data': '同步成功'}), 200)
    except Exception as e:
        return (jsonify({'data': f'同步失败: {e}'}), 500)

@app.route('/v1/run_simultaneous_interpretation', methods=['POST'])
def run_simultaneous_interpretation():
    user_req = request.get_json()
    exec_list = user_req.get('exec_list', [])
    task_id = generate_task_id()
    if exec_list == ['asr']:
        thread = threading.Thread(target=run_asr_eval, args=(task_id, user_req))
    elif exec_list == ['mt']:
        thread = threading.Thread(target=run_mt_eval, args=(task_id, user_req))
    elif exec_list == ['tts']:
        thread = threading.Thread(target=run_tts_eval, args=(task_id, user_req))
    elif exec_list == ['asr', 'mt'] or exec_list == ['mt', 'asr']:
        thread = threading.Thread(target=lambda: (run_asr_eval(task_id, user_req), run_mt_eval(task_id, user_req)))
    elif sorted(exec_list) == ['asr', 'mt', 'tts'] and len(exec_list) == 3:
        thread = threading.Thread(target=lambda: (run_asr_eval(task_id, user_req), run_mt_eval(task_id, user_req), run_tts_eval(task_id, user_req)))
    else:
        return (jsonify({'message': f"同声传译任务列表必须为 asr/mt/tts 中的一个或 asr+mt 或asr+mt+tts，当前是:{','.join(exec_list)}"}), 500)
    thread.start()
    return (jsonify({'task_id': task_id, 'message': '任务已启动，请通过task_id查询进度'}), 200)

def kill_running_task(test_id: str):
    global tasks
    if test_id not in tasks:
        print(f' Test ID {test_id} not found in tasks.')
        return {'success': False, 'message': 'Test ID not found'}
    task = tasks[test_id]
    if task['status'] != 'running':
        print(f"Task {test_id} is {task['status']}, not running. No action taken.")
        return {'success': False, 'message': f"Status is {task['status']}, not running"}
    pid = task.get('process_id', None)
    if not pid:
        print(f' Task {test_id} has no process_id recorded.')
        return {'success': False, 'message': 'No process_id found for this task'}
    task['status'] = 'paused'
    task['error'] = 'last task has been paused'
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=5)
        print(f' 进程 {pid} (test_id={test_id}) 已终止。')
    except psutil.TimeoutExpired:
        proc.kill()
        print(f' 进程 {pid} (test_id={test_id}) 已被强制杀死。')
    except psutil.NoSuchProcess:
        print(f' 进程 {pid} 已不存在（可能已结束）。')
    except Exception as e:
        print(f' 终止进程 {pid} 时发生未知错误: {e}')
        return {'success': False, 'error': str(e)}
    print(f'任务 {test_id} 成功终止，PID={pid}')
    set_tasks(tasks)
    return {'success': True, 'message': f'任务 {test_id} 已终止', 'killed_pid': pid, 'test_id': test_id}

@app.route('/v1/pause_test_task', methods=['POST'])
def kill_task_endpoint():
    user_req = request.get_json()
    test_id = user_req['task_id']
    return kill_running_task(test_id)

def resume_paused_task(task_id):
    global tasks
    if task_id not in tasks:
        print(f' Task ID {task_id} not found in tasks.')
        return {'success': False, 'message': 'Task ID not found'}
    task = tasks[task_id]
    if task['status'] != 'paused':
        print(f"Task {task_id} is {task['status']}, not paused. No action taken.")
        return {'success': False, 'message': f"Status is {task['status']}, not paused"}
    return {'success': False, 'message': '当前任务不支持恢复/重启（暂停即取消本次测评），请重新发起测评。', 'task_id': task_id}

@app.route('/v1/resume_test_task', methods=['POST'])
def resume_task_endpoint():
    user_req = request.get_json()
    task_id = user_req['task_id']
    return resume_paused_task(task_id)

def internal_call_to_func(api_name, method, data, func):
    with app.test_request_context(api_name, method=method, json=data):
        response = func()
        if hasattr(response, 'get_json'):
            return response.get_json()
        else:
            return json.loads(response.data.decode('utf-8'))

def cleanup_on_exit():
    global tasks
    custom_pids = set()
    for _tid, _t in tasks.items():
        if _t.get('proc_type') == 'ruler2_custom' and _t.get('process_id'):
            custom_pids.add(_t['process_id'])
    running_tasks = []
    running_pids = []
    for task_id in tasks.keys():
        if tasks[task_id].get('proc_type') == 'ruler2_custom':
            continue
        if tasks[task_id]['status'] == 'running' and 'process_id' in tasks[task_id]:
            running_tasks.append(task_id)
            running_pids.append(tasks[task_id]['process_id'])
    for current_process in current_processes:
        if current_process and current_process.poll() is None:
            if current_process.pid in custom_pids:
                continue
            current_process.kill()
            if current_process.pid in running_pids:
                tasks[running_tasks[running_pids.index(current_process.pid)]]['process_id'] = None
    with open_state(TASKS, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

def init_task():
    global tasks
    if not state_exists(TASKS):
        tasks = {}
    else:
        tasks = get_tasks()
        cleanup_on_exit()
    set_tasks(tasks)

def run_all_aisf(user_req, model_config, task_id):
    all_start_time = time.time()
    model_name = model_config['info']['model_name']
    tasks[task_id] = generate_run_task_info(user_req, user_req['model_id'], model_name, model_config, task_id)
    set_tasks(tasks)
    public_conf = [{'api_url': param['endpoint'], 'model': model_name} for param in model_config['config']['api_params_available']]
    api_url = public_conf[0]['api_url']
    try:
        run_aisf_32b_dataset(api_url, model_name, task_id, user_req)
        run_aisf_8b_dataset(api_url, model_name, task_id, user_req)
        run_aisf_4b_dataset(api_url, model_name, task_id, user_req)
        run_aisf_no_chart(api_url, model_name, task_id, user_req)
        update_eval_res(tasks, task_id, model_name, None)
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
    all_end_time = time.time()
    tasks[task_id]['runningTime'] = all_end_time - all_start_time
    set_tasks(tasks)

@app.route('/v1/run_aisf_release', methods=['POST'])
def run_aisf_release():
    user_req = request.get_json()
    required_fields = ['model_id', 'datasets', 'assessmentType']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    model_id = user_req['model_id']
    model_config = get_one_model_config(model_id)
    if not model_config:
        return ({'errType': f'Model ({model_id}) not registered'}, 400)
    task_id = generate_task_id()
    if len(model_config['config']['api_params_available']) == 0:
        return ({'err_info': 'MODEL_NOT_EXIST'}, MODEL_NOT_EXIST)
    if not isinstance(user_req['datasets'], list):
        print('user_req datasets is not list, can not run_aisf_8b_dataset')
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    thread = threading.Thread(target=run_all_aisf, args=(user_req, model_config, task_id))
    thread.start()
    return (jsonify({'task_id': task_id, 'message': '任务已启动，请通过task_id查询进度'}), 200)

@app.route('/v1/download_aisf_release_result', methods=['GET'])
def download_aisf_release_result():
    task_id = request.args.get('task_id')
    datasets = request.args.get('datasets')
    user_name = request.args.get('username')
    if not (task_id and datasets and user_name):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    users = []
    with open_state(AISF_USER_MEMBER, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_value = row.get('user', '').strip()
            if user_value:
                users.append(user_value)
    try:
        get_report_file(datasets, task_id, user_name, users)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/generate_report', methods=['POST'])
def generate_report():
    """
    异步生成报告接口：
    - model_name: list[str], 1~3个基准模型名
    - model_id: list[str], 与 model_name 一一对应
    - compare_models: dict, 第一层key为基准模型名，第二层key为type，value为对比模型列表
      如: {"Qwen3-72B": {"0": ["A","B"], "1": ["C"]}, "DeepSeek-V3": {"0": ["D"]}}
    - compare_type: dict, 键为基准模型名，值为该模型的报告类型字符串
      如: {"Qwen3-72B": "0123", "DeepSeek-V3": "06"}
    - 立即返回 taskId
    - 后台线程执行报告生成
    - 前端通过 /v1/query_report_status 轮询状态
    """
    user_req = request.get_json()
    required_fields = ['model_id', 'model_name', 'compare_models', 'compare_type', 'userName']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    model_names = user_req['model_name']
    model_ids = user_req['model_id']
    compare_models_dict = user_req['compare_models']
    compare_type_dict = user_req['compare_type']
    report_name = user_req['report_name']
    userName = user_req['userName']
    if not isinstance(model_names, list) or len(model_names) < 1 or len(model_names) > 3:
        return (jsonify({'error': 'model_name 必须为列表，长度 1~3'}), 400)
    if not isinstance(model_ids, list) or len(model_ids) != len(model_names):
        return (jsonify({'error': 'model_id 必须为列表，且长度与 model_name 一致'}), 400)
    if not isinstance(compare_type_dict, dict):
        return (jsonify({'error': 'compare_type 必须为字典'}), 400)
    for base_model in model_names:
        if base_model not in compare_type_dict:
            return (jsonify({'error': f'compare_type 中缺少基准模型 "{base_model}" 的配置'}), 400)
    print(f'model_names:{model_names}, model_ids:{model_ids}, compare_models_dict:{compare_models_dict}, compare_type_dict:{compare_type_dict}, userName:{userName}')
    TYPE_NAME_MAP = {0: '大语言通用', 1: '视觉通用', 2: '音频通用', 3: 'AISF-改写', 6: 'AISF-伴学', 7: 'AISF-操控规划', 8: 'AISF-操控执行', 9: 'AISF-意图', 10: 'AISF-记忆'}

    def _parse_type_str(ct_str):
        """解析逗号分隔的 type 字符串为有序 int 列表，支持个位数和两位数"""
        if not isinstance(ct_str, str):
            return None
        valid_types = {'0', '1', '2', '3', '6', '7', '8', '9', '10'}
        parts = [p.strip() for p in ct_str.split(',') if p.strip()]
        if any((p not in valid_types for p in parts)):
            return None
        result = []
        for p in parts:
            t = int(p)
            if t not in result:
                result.append(t)
        return result
    ALLOWED_TYPES = {0, 1, 2, 3, 6, 7, 8, 9, 10}
    parsed_types_per_base = {}
    all_parsed_types_set = set()
    for base_model in model_names:
        ct_str = compare_type_dict[base_model]
        parsed = _parse_type_str(ct_str)
        if parsed is None:
            return (jsonify({'error': f'基准模型 "{base_model}" 的 compare_type="{ct_str}" 无效'}), 400)
        parsed_types_per_base[base_model] = parsed
        all_parsed_types_set.update(parsed)
    all_parsed_types = sorted(all_parsed_types_set)
    type_info = {}
    for base_model in model_names:
        base_type_info = {}
        for t in parsed_types_per_base[base_model]:
            type_name = TYPE_NAME_MAP.get(t, str(t))
            cur_compare_models = compare_models_dict[base_model].get(str(t), [])
            all_models = [base_model] + cur_compare_models
            base_type_info[type_name] = all_models
        type_info[base_model] = base_type_info
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    model_names_str = '&'.join(model_names)
    task_id = f"report_{model_names_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    task_info = {'report_name': report_name, 'model_names': model_names, 'model_ids': model_ids, 'task_id': task_id, 'types': type_info, 'status': 'running', 'create_time': now_str, 'complete_time': None, 'filepath': None, 'error': None, 'userName': userName}
    report_tasks = get_report_tasks()
    report_tasks[task_id] = task_info
    set_report_tasks(report_tasks)
    thread = threading.Thread(target=_generate_report_thread, args=(task_id, model_names, model_ids, compare_models_dict, parsed_types_per_base, all_parsed_types, report_name))
    thread.start()
    return (jsonify({'task_id': task_id, 'status': 'running'}), 200)

def _generate_report_thread(task_id, model_names, model_ids, compare_models_dict, parsed_types_per_base, all_parsed_types, report_name):
    """
    后台线程：执行报告生成（支持多基准模型），更新 report_tasks 文件中的状态。

    Args:
        task_id: 任务ID
        model_names: list[str], 基准模型名列表
        model_ids: list[str], 基准模型ID列表（与 model_names 一一对应）
        compare_models_dict: dict, {基准模型名: {type_str: [对比模型列表]}}
        parsed_types_per_base: dict, {基准模型名: [type_int列表]}
        all_parsed_types: list[int], 所有类型的并集（已排序）
    """
    try:
        if all_parsed_types == [5]:
            base_model = model_names[0]
            print('start fill min dataset')
            score_data = get_report_score_min_dataset(base_model)
            print(f'score_data:{score_data}')
            summary = call_judge_model(base_model, dict_to_json(score_data.get(SCORE_DICT_LLM_SUMMARY_KEY)), 'min')
            print(summary)
            ppt_data = set_to_ppt_data_v2(base_model, model_ids[0])
            prs = fill_min_dataset_content_to_ppt(ppt_data, score_data.get(SCORE_DICT_PPT_FILL_KEY), summary)
        elif isinstance(all_parsed_types, list):
            llm_types = [t for t in all_parsed_types if t in (0, 3, 9, 10)]
            mllm_types = [t for t in all_parsed_types if t in (1, 2, 6, 7, 8)]
            if not llm_types and (not mllm_types):
                raise ValueError(f'compare_type 列表中无有效类型: {all_parsed_types}')
            all_types = llm_types + mllm_types
            llm_summary_type_map = {0: 'ruler1', 3: 'ruler2', 9: 'ruler2', 10: 'ruler2'}
            all_ppt_data_list = []
            all_llm_ppt_score_list = []
            all_mllm_ppt_score_list = []
            all_llm_summary_list = []
            all_mllm_summary_list = []
            all_model_count_dict_list = []
            all_model_names_dict_list = []
            for base_model in model_names:
                base_types = parsed_types_per_base.get(base_model, [])
                base_compare_models = compare_models_dict.get(base_model, {})
                base_model_count_dict = {}
                base_model_names_dict = {}
                for t in base_types:
                    cur_models = base_compare_models.get(str(t), [])
                    if len(cur_models) > 5:
                        raise ValueError(f'基准模型 {base_model} type={t} 对比模型数量 {len(cur_models)} 超出上限（0~5）')
                    base_model_count_dict[t] = 1 + len(cur_models)
                    base_model_names_dict[t] = [base_model] + cur_models
                for t in all_types:
                    if t not in base_model_count_dict:
                        base_model_count_dict[t] = 1
                        base_model_names_dict[t] = [base_model]
                base_llm_types = [t for t in base_types if t in llm_types]
                base_llm_score_data_map = {}
                base_llm_summary_map = {}
                for t in base_llm_types:
                    cur_compare_models = base_compare_models.get(str(t), [])
                    if t == 0:
                        score_data = {}
                        get_report_score_ruler1(cur_compare_models, base_model, score_data)
                    else:
                        score_data = {}
                        get_report_score_ruler2(score_data, cur_compare_models, base_model, t)
                    base_llm_score_data_map[t] = score_data
                    summary = call_judge_model(base_model, dict_to_json(score_data.get(SCORE_DICT_LLM_SUMMARY_KEY)), llm_summary_type_map[t])
                    base_llm_summary_map[t] = summary
                    print(f'base_model={base_model} llm type={t} score_data done')
                base_llm_summary_full = []
                for t in llm_types:
                    base_llm_summary_full.append(base_llm_summary_map.get(t, ''))
                base_mllm_types = [t for t in base_types if t in mllm_types]
                base_mllm_score_data_map = {}
                base_mllm_summary_map = {}
                for t in base_mllm_types:
                    cur_compare_models = base_compare_models.get(str(t), [])
                    score_data = get_report_score_mllm_dataset(base_model, cur_compare_models, t)
                    summary = call_judge_model(base_model, dict_to_json(score_data.get(SCORE_DICT_MLLM_SUMMARY_KEY)), 'mllm')
                    base_mllm_score_data_map[t] = score_data
                    base_mllm_summary_map[t] = summary
                    print(f'base_model={base_model} mllm type={t} score_data done')
                base_mllm_summary_full = []
                for t in mllm_types:
                    base_mllm_summary_full.append(base_mllm_summary_map.get(t, ''))
                base_model_idx = model_names.index(base_model)
                base_model_id = model_ids[base_model_idx]
                ppt_data = set_to_ppt_data_v2(base_model, base_model_id)
                base_llm_ppt_score_data_list = []
                for t in llm_types:
                    if t in base_llm_types:
                        ppt_scores = base_llm_score_data_map[t].get(SCORE_DICT_PPT_FILL_KEY)
                        base_llm_ppt_score_data_list.append(handle_score_data(ppt_scores, t))
                    else:
                        base_llm_ppt_score_data_list.append(None)
                base_mllm_ppt_score_data_list = []
                for t in mllm_types:
                    if t in base_mllm_types:
                        ppt_scores = base_mllm_score_data_map[t].get(SCORE_DICT_PPT_FILL_KEY)
                        base_mllm_ppt_score_data_list.append(handle_score_data(ppt_scores, t))
                    else:
                        base_mllm_ppt_score_data_list.append(None)
                all_ppt_data_list.append(ppt_data)
                all_llm_ppt_score_list.append(base_llm_ppt_score_data_list)
                all_mllm_ppt_score_list.append(base_mllm_ppt_score_data_list)
                all_llm_summary_list.append(base_llm_summary_full)
                all_mllm_summary_list.append(base_mllm_summary_full)
                all_model_count_dict_list.append(base_model_count_dict)
                all_model_names_dict_list.append(base_model_names_dict)
            prs = fill_multi_base_unified_content_to_ppt(all_ppt_data_list, all_llm_ppt_score_list, all_mllm_ppt_score_list, all_llm_summary_list, all_mllm_summary_list, llm_types, mllm_types, all_model_count_dict_list, all_model_names_dict_list, all_base_model_names=model_names)
        else:
            raise ValueError(f'不支持的 all_parsed_types: {all_parsed_types}')
        model_id_str = '&'.join(model_ids)
        output_report_path = generate_ppt_report(prs, model_id_str, report_name)
        report_tasks = get_report_tasks()
        if task_id in report_tasks:
            report_tasks[task_id]['status'] = 'completed'
            report_tasks[task_id]['filepath'] = output_report_path
            report_tasks[task_id]['complete_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            set_report_tasks(report_tasks)
        print(f'report {task_id} completed: {output_report_path}')
    except Exception as e:
        print(f'generate_report err:{str(e)}')
        traceback.print_exc()
        report_tasks = get_report_tasks()
        if task_id in report_tasks:
            report_tasks[task_id]['status'] = 'failed'
            report_tasks[task_id]['error'] = str(e)
            report_tasks[task_id]['complete_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            set_report_tasks(report_tasks)

@app.route('/v1/query_report_status', methods=['GET'])
def query_report_status():
    """查询报告生成状态（轮询接口）"""
    task_id = request.args.get('task_id')
    if not task_id:
        return (jsonify({'error': 'param task_id must be not null'}), 400)
    report_tasks = get_report_tasks()
    task = report_tasks.get(task_id)
    if task is None:
        return (jsonify({'error': f'task_id {task_id} not found'}), 404)
    return (jsonify(task), 200)

@app.route('/v1/get_all_report_tasks', methods=['GET'])
def get_all_report_tasks():
    """返回全部生成报告任务的全部信息"""
    report_tasks = get_report_tasks()
    tasks_list = sorted(report_tasks.values(), key=lambda x: x.get('create_time', ''), reverse=True)
    return (jsonify(tasks_list), 200)

@app.route('/v1/get_report_tasks_by_name', methods=['GET'])
def get_report_tasks_by_name():
    """返回全部生成报告任务的全部信息"""
    report_tasks = get_report_tasks()
    model_name = request.args.get('model_name')
    tasks_list = sorted(report_tasks.values(), key=lambda x: x.get('create_time', ''), reverse=True)
    tasks_list = [i for i in tasks_list if i['model_name'] == model_name]
    return (jsonify(tasks_list), 200)

@app.route('/v1/delete_report_task', methods=['POST'])
def delete_report_task():
    """删除指定报告生成任务"""
    user_req = request.get_json()
    task_id = user_req.get('task_id')
    if not task_id:
        return (jsonify({'error': 'param task_id must be not null'}), 400)
    report_tasks = get_report_tasks()
    if task_id not in report_tasks:
        return (jsonify({'error': '任务不存在'}), 404)
    if report_tasks[task_id].get('status') == 'running':
        return (jsonify({'error': '任务进行中，无法删除'}), 400)
    del report_tasks[task_id]
    set_report_tasks(report_tasks)
    return (jsonify({'info': '删除成功'}), 200)

@app.route('/v1/get_latest_report', methods=['GET'])
def get_latest_report():
    """
    按 modelId 查询最新已生成的报告路径（兜底接口：前端丢失 taskId 时使用）。
    扫描 EVAL_REPORT_OUTPUT_PATH/{modelId}/ 目录，返回时间戳最新的报告。
    """
    model_id = request.args.get('model_id')
    if not model_id:
        return (jsonify({'error': 'param model_id must be not null'}), 400)
    report_dir = os.path.join(EVAL_REPORT_OUTPUT_PATH, model_id)
    if not state_exists(report_dir):
        return (jsonify({'error': f'no reports found for model_id {model_id}'}), 404)
    try:
        subdirs = sorted(os.listdir(report_dir), reverse=True)
        for subdir in subdirs:
            subdir_path = os.path.join(report_dir, subdir)
            if not os.path.isdir(subdir_path):
                continue
            pptx_files = [f for f in os.listdir(subdir_path) if f.endswith('.pptx')]
            if pptx_files:
                latest_pptx = sorted(pptx_files, reverse=True)[0]
                filepath = os.path.join(subdir_path, latest_pptx)
                return (jsonify({'filepath': filepath}), 200)
        return (jsonify({'error': f'no pptx files found for model_id {model_id}'}), 404)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/download/report', methods=['GET'])
def download_report():
    req_filepath = request.args.get('filepath')
    try:
        if state_exists(req_filepath):
            local_file_path = os.path.join(os.getcwd(), req_filepath)
            return send_file(local_file_path, as_attachment=True)
        else:
            return (jsonify({'error': 'filepath is not exist'}), 400)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/preview/report', methods=['GET'])
def preview_report():
    """
    在线预览接口：

    接口: GET /v1/preview/report?filepath=xxx
    返回: { preview_type: "pdf", url: "/v1/preview/report/pdf?filepath=xxx" }

    支持 PPT/PPTX/PDF 文件。
    PPT/PPTX 由 /v1/preview/report/pdf 接口转换为 PDF 后返回；
    PDF 由 /v1/preview/report/pdf 接口直接返回源文件。

    依赖（PPT 转换）: aspose-slides（pip install aspose-slides）
    """
    req_filepath = request.args.get('filepath')
    if not req_filepath:
        return (jsonify({'error': 'param filepath must be not null'}), 400)
    file_path = req_filepath if os.path.isabs(req_filepath) else os.path.join(os.getcwd(), req_filepath)
    if not state_exists(file_path):
        return (jsonify({'error': f'file not found: {req_filepath}'}), 404)
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ('.ppt', '.pptx', '.pdf'):
        return (jsonify({'error': 'only ppt/pptx/pdf files are supported for preview'}), 400)
    pdf_preview_url = f'/v1/preview/report/pdf?filepath={urllib.parse.quote(req_filepath)}'
    return (jsonify({'preview_type': 'pdf', 'url': pdf_preview_url}), 200)

@app.route('/v1/preview/report/pdf', methods=['GET'])
def preview_report_pdf():
    """
    将文件转换为 PDF 并返回文件流（供 iframe 内嵌）。

    支持：
      - PPT/PPTX：使用 Aspose.Slides 转换并清洗水印
      - PDF：直接返回源文件

    转换策略（双层清洗）:
      第 1 层 — PPTX 层: 用 Aspose.Slides 加载 PPTX 触发水印注入后，
                     用 python-pptx 操作底层 XML 删除水印形状节点。
      第 2 层 — PDF 层: 用 pikepdf 扫描 PDF 内容流，抹除残留水印文本。

    依赖: pip install aspose-slides python-pptx pikepdf
    """
    req_filepath = request.args.get('filepath')
    if not req_filepath:
        return (jsonify({'error': 'param filepath must be not null'}), 400)
    file_path = req_filepath if os.path.isabs(req_filepath) else os.path.join(os.getcwd(), req_filepath)
    if not state_exists(file_path):
        return (jsonify({'error': f'file not found: {req_filepath}'}), 404)
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ('.ppt', '.pptx', '.pdf'):
        return (jsonify({'error': 'only ppt/pptx/pdf files are supported for preview'}), 400)
    if ext == '.pdf':
        return send_file(file_path, mimetype='application/pdf', as_attachment=False, download_name=os.path.basename(file_path))
    import tempfile
    import re
    try:
        from aspose.slides import Presentation as AsposePresentation
        from aspose.slides.export import SaveFormat
        from aspose.slides import LoadOptions
    except ImportError:
        return (jsonify({'error': '预览失败: 服务器缺少依赖，请安装 aspose-slides（pip install aspose-slides）'}), 500)
    try:
        from pptx import Presentation as PptxPresentation
    except ImportError:
        return (jsonify({'error': '预览失败: 服务器缺少依赖，请安装 python-pptx（pip install python-pptx）'}), 500)
    try:
        import pikepdf
    except ImportError:
        return (jsonify({'error': '预览失败: 服务器缺少依赖，请安装 pikepdf（pip install pikepdf）'}), 500)
    tmp_pptx = None
    pdf_path = None
    _FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')

    def _clean_pptx_watermark(pptx_path):
        """第 1 层清洗：删除 PPTX 中的水印形状"""
        prs = PptxPresentation(pptx_path)
        WATERMARK_KEYWORDS = ['Aspose', 'Evaluation', 'Created with Aspose', 'Copyright 2004']
        removed_count = 0
        for slide in prs.slides:
            to_delete = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    if any((kw in shape.text for kw in WATERMARK_KEYWORDS)):
                        to_delete.append(shape)
            for s in to_delete:
                el = s._element
                el.getparent().remove(el)
                removed_count += 1
        if removed_count > 0:
            prs.save(pptx_path)
        return removed_count

    def _clean_pdf_watermark(pdf_path):
        """第 2 层清洗：从 PDF 内容流中抹除水印文本"""
        WATERMARK_TEXTS = [b'Evaluation only.', b'Created with Aspose.Slides for Python via .NET 26.5.', b'Copyright 2004-2026Aspose Pty Ltd.']
        with pikepdf.open(pdf_path) as pdf:
            cleaned = False
            for page in pdf.pages:
                if '/Contents' not in page:
                    continue
                contents = page['/Contents']
                if hasattr(contents, 'read_bytes'):
                    data = contents.read_bytes()
                    original_len = len(data)
                    for wt in WATERMARK_TEXTS:
                        data = data.replace(wt, b'')
                    if len(data) != original_len:
                        page['/Contents'] = pikepdf.Stream(pdf, data)
                        cleaned = True
            if cleaned:
                import tempfile as _tf
                import shutil
                with _tf.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp_pdf = tmp.name
                try:
                    pdf.save(tmp_pdf)
                finally:
                    pdf.close()
                shutil.move(tmp_pdf, pdf_path)
        return cleaned
    try:
        load_opts = LoadOptions()
        if os.path.isdir(_FONTS_DIR):
            load_opts.document_level_font_sources.font_folders = [_FONTS_DIR]
        with AsposePresentation(file_path, load_opts) as asp_prs:
            with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
                tmp_pptx = tmp.name
            asp_prs.save(tmp_pptx, SaveFormat.PPTX)
        pptx_removed = _clean_pptx_watermark(tmp_pptx)
        print(f'[preview] PPTX 层: 删除了 {pptx_removed} 个水印形状')
        with AsposePresentation(tmp_pptx, load_opts) as clean_prs:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                pdf_path = tmp.name
            clean_prs.save(pdf_path, SaveFormat.PDF)
        pdf_cleaned = _clean_pdf_watermark(pdf_path)
        if pdf_cleaned:
            print(f'[preview] PDF 层: 已清除内容流中的水印文本')
        return send_file(pdf_path, mimetype='application/pdf', as_attachment=False, download_name='preview.pdf')
    except Exception as e:
        print(f'PDF 生成失败: {e}')
        return (jsonify({'error': f'PDF 生成失败: {str(e)}'}), 500)
    finally:
        for p in (tmp_pptx, pdf_path):
            if p and state_exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass

@app.route('/v1/publish_report_from_task', methods=['POST'])
def publish_report_from_task():
    """
    从 REPORTTASKS 中读取指定任务的 filepath 并直接发布报告。
    前端传入: { task_id: string, userName: string }
    - 从 REPORTTASKS 读取任务信息，复制 filepath 对应文件到 published 目录
    - 写入 PUBLISHEDREPORTTASKS
    """
    user_req = request.get_json()
    task_id = user_req.get('task_id')
    if not task_id:
        return (jsonify({'error': '缺少 task_id 字段'}), 400)
    userName = user_req.get('userName')
    report_tasks = get_report_tasks()
    task_info = report_tasks.get(task_id)
    if not task_info:
        return (jsonify({'error': f'task_id {task_id} 在 REPORTTASKS 中不存在'}), 404)
    if not userName:
        userName = task_info['userName']
    src_filepath = task_info.get('filepath')
    if not src_filepath or not state_exists(src_filepath):
        return (jsonify({'error': f'任务 {task_id} 的报告文件不存在: {src_filepath}'}), 404)
    published_dir = os.path.join(EVAL_REPORT_OUTPUT_PATH, 'published')
    os.makedirs(published_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = os.path.splitext(src_filepath)[1]
    saved_filename = f'{task_id}_{timestamp}{ext}'
    saved_path = os.path.join(published_dir, saved_filename)
    import shutil
    shutil.copy2(src_filepath, saved_path)
    task_info['published_filepath'] = saved_path
    task_info['publisher'] = userName
    task_info['publish_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    published_tasks = get_report_tasks_from_path(PUBLISHEDREPORTTASKS)
    publish_key = task_id
    suffix = 1
    while publish_key in published_tasks:
        publish_key = f'{task_id}({suffix})'
        suffix += 1
    published_tasks[publish_key] = task_info
    set_report_tasks_to_path(PUBLISHEDREPORTTASKS, published_tasks)
    return (jsonify({'message': '发布成功', 'filepath': saved_path}), 200)

@app.route('/v1/direct_publish_report', methods=['POST'])
def direct_publish_report():
    """
    直接发布报告（不依赖 REPORTTASKS 中的任务）。
    前端传入 formData:
      - 文件字段: file（ppt/pptx/pdf文件）
      - 表单字段: userName, report_name, model_names(JSON), compare_models(JSON), compare_type(JSON)
    - 参数结构与 /v1/generate_report 一致
    - 将文件存入 EVAL_REPORT_OUTPUT_PATH/published/ 目录
    - 写入 PUBLISHEDREPORTTASKS，含完整的 types 信息
    """
    if 'file' not in request.files:
        return (jsonify({'error': '缺少 file 字段'}), 400)
    file = request.files['file']
    if file.filename == '':
        return (jsonify({'error': '文件名为空'}), 400)
    if not file.filename.lower().endswith(('.ppt', '.pptx', '.pdf')):
        return (jsonify({'error': '仅支持 ppt/pptx/pdf 格式文件'}), 400)
    userName = request.form.get('userName')
    if not userName:
        return (jsonify({'error': '缺少 userName 字段'}), 400)
    report_name = request.form.get('report_name')
    if not report_name:
        return (jsonify({'error': '缺少 report_name 字段'}), 400)
    try:
        model_names = json.loads(request.form.get('model_names', 'null'))
        compare_models_dict = json.loads(request.form.get('compare_models', 'null'))
        compare_type_dict = json.loads(request.form.get('compare_type', 'null'))
    except (json.JSONDecodeError, TypeError):
        return (jsonify({'error': 'model_names / compare_models / compare_type 格式错误，需要 JSON 字符串'}), 400)
    if not isinstance(model_names, list) or len(model_names) < 1 or len(model_names) > 3:
        return (jsonify({'error': 'model_names 必须为列表，长度 1~3'}), 400)
    if not isinstance(compare_models_dict, dict):
        return (jsonify({'error': 'compare_models 必须为字典'}), 400)
    if not isinstance(compare_type_dict, dict):
        return (jsonify({'error': 'compare_type 必须为字典'}), 400)
    for base_model in model_names:
        if base_model not in compare_type_dict:
            return (jsonify({'error': f'compare_type 中缺少基准模型 "{base_model}" 的配置'}), 400)
    TYPE_NAME_MAP = {0: '大语言通用', 1: '视觉通用', 2: '音频通用', 3: 'AISF-改写', 6: 'AISF-伴学', 7: 'AISF-操控规划', 8: 'AISF-操控执行', 9: 'AISF-意图', 10: 'AISF-记忆'}

    def _parse_type_str(ct_str):
        """解析逗号分隔的 type 字符串为有序 int 列表，支持个位数和两位数"""
        if not isinstance(ct_str, str):
            return None
        valid_types = {'0', '1', '2', '3', '6', '7', '8', '9', '10'}
        parts = [p.strip() for p in ct_str.split(',') if p.strip()]
        if any((p not in valid_types for p in parts)):
            return None
        result = []
        for p in parts:
            t = int(p)
            if t not in result:
                result.append(t)
        return result
    parsed_types_per_base = {}
    for base_model in model_names:
        ct_str = compare_type_dict[base_model]
        parsed = _parse_type_str(ct_str)
        if parsed is None:
            return (jsonify({'error': f'基准模型 "{base_model}" 的 compare_type="{ct_str}" 无效'}), 400)
        parsed_types_per_base[base_model] = parsed
    type_info = {}
    for base_model in model_names:
        base_type_info = {}
        for t in parsed_types_per_base[base_model]:
            type_name = TYPE_NAME_MAP.get(t, str(t))
            cur_compare_models = compare_models_dict[base_model].get(str(t), [])
            all_models = [base_model] + cur_compare_models
            base_type_info[type_name] = all_models
        type_info[base_model] = base_type_info
    published_dir = os.path.join(EVAL_REPORT_OUTPUT_PATH, 'published')
    os.makedirs(published_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    model_names_str = '&'.join(model_names)
    report_id = f'report_{model_names_str}_{timestamp}'
    ext = os.path.splitext(file.filename)[1]
    saved_filename = f'{report_id}{ext}'
    saved_path = os.path.join(published_dir, saved_filename)
    file.save(saved_path)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    task_info = {'report_name': report_name, 'model_names': model_names, 'published_filepath': saved_path, 'publisher': userName, 'publish_time': now_str, 'types': type_info, 'task_id': '-', 'status': 'completed', 'create_time': '-', 'complete_time': '-', 'userName': userName, 'error': '-', 'id': report_id}
    published_tasks = get_report_tasks_from_path(PUBLISHEDREPORTTASKS)
    publish_key = report_id
    suffix = 1
    while publish_key in published_tasks:
        publish_key = f'{report_id}({suffix})'
        suffix += 1
    task_info['id'] = publish_key
    published_tasks[publish_key] = task_info
    set_report_tasks_to_path(PUBLISHEDREPORTTASKS, published_tasks)
    return (jsonify({'message': '发布成功', 'filepath': saved_path}), 200)

@app.route('/v1/get_all_published_tasks', methods=['GET'])
def get_all_published_tasks():
    """获取全部 PUBLISHEDREPORTTASKS 文件中的已发布任务信息"""
    published_tasks = get_report_tasks_from_path(PUBLISHEDREPORTTASKS)
    tasks_list = []
    for task_id, task_info in published_tasks.items():
        task_info['id'] = task_id
        tasks_list.append(task_info)
    tasks_list = sorted(tasks_list, key=lambda x: x.get('publish_time', ''), reverse=True)
    return (jsonify(tasks_list), 200)

@app.route('/v1/delete_published_task', methods=['POST'])
def delete_published_task():
    """删除指定 id 的已发布报告信息"""
    user_req = request.get_json()
    id = user_req.get('id')
    if not id:
        return (jsonify({'error': '缺少 id 参数'}), 400)
    published_tasks = get_report_tasks_from_path(PUBLISHEDREPORTTASKS)
    if id not in published_tasks:
        return (jsonify({'error': f'id {id} 不存在'}), 404)
    del published_tasks[id]
    set_report_tasks_to_path(PUBLISHEDREPORTTASKS, published_tasks)
    return (jsonify({'info': '删除成功'}), 200)

@app.route('/v1/update_published_report', methods=['POST'])
def update_published_report():
    """
    更新已发布报告的文件。
    前端传入 formData:
      - 文件字段: file（ppt/pptx/pdf文件）
      - 表单字段: id, userName
    - 用新文件原地覆盖原文件（路径与文件名不变）
    - 更新 PUBLISHEDREPORTTASKS 中该记录的 publish_time 与 publisher
    """
    if 'file' not in request.files:
        return (jsonify({'error': '缺少 file 字段'}), 400)
    file = request.files['file']
    if file.filename == '':
        return (jsonify({'error': '文件名为空'}), 400)
    if not file.filename.lower().endswith(('.ppt', '.pptx', '.pdf')):
        return (jsonify({'error': '仅支持 ppt/pptx/pdf 格式文件'}), 400)
    id = request.form.get('id')
    if not id:
        return (jsonify({'error': '缺少 id 参数'}), 400)
    userName = request.form.get('userName')
    published_tasks = get_report_tasks_from_path(PUBLISHEDREPORTTASKS)
    if id not in published_tasks:
        return (jsonify({'error': f'id {id} 不存在'}), 404)
    task_info = published_tasks[id]
    saved_path = task_info.get('published_filepath')
    if not saved_path or not state_isfile(saved_path):
        return (jsonify({'error': '原报告文件不存在，无法更新'}), 404)
    saved_dir = os.path.dirname(saved_path)
    old_ext = os.path.splitext(saved_path)[1]
    new_ext = os.path.splitext(file.filename)[1]
    base_name = os.path.splitext(os.path.basename(saved_path))[0]
    new_path = os.path.join(saved_dir, f'{base_name}{new_ext}')
    try:
        if os.path.normpath(new_path) != os.path.normpath(saved_path):
            if state_exists(saved_path):
                os.remove(saved_path)
        file.save(new_path)
    except Exception as e:
        return (jsonify({'error': f'文件替换失败：{str(e)}'}), 500)
    task_info['publish_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    task_info['published_filepath'] = new_path
    if userName:
        task_info['publisher'] = userName
    published_tasks[id] = task_info
    set_report_tasks_to_path(PUBLISHEDREPORTTASKS, published_tasks)
    return (jsonify({'message': '更新成功', 'filepath': new_path, 'id': id}), 200)

@app.route('/v1/get_min_test_chart', methods=['GET'])
def get_min_test_chart():
    model_name = request.args.get('model_name')
    if not state_exists(LLM_MIN_DATASET_RESULT):
        return (jsonify({'error': 'filepath is not exist'}), 400)
    try:
        with open_state(LLM_MIN_DATASET_RESULT, 'r', encoding='utf-8') as file:
            chart = json.load(file)
            if model_name in chart:
                return (jsonify({'model': model_name, 'status': 'exist'}), 200)
            else:
                return (jsonify({'error': 'model not found'}), 200)
    except json.JSONDecodeError:
        print(f'文件 {LLM_MIN_DATASET_RESULT} 解析失败')
        return (jsonify({'error': 'json decode error'}), 500)
    except Exception as e:
        print(f'未知错误: {str(e)}')
        return (jsonify({'error': 'internal server error'}), 500)

@app.route('/v1/get_evaluation_result', methods=['GET'])
def get_evaluation_result():
    res = get_report_tasks_from_path(EVALUATIONRESULT)
    return (jsonify(res), 200)

@app.route('/v1/write_evaluation_result', methods=['POST'])
def write_evaluation_result():
    """将 TASKS 中指定任务的评测结果按(模型×测试集)拆分为独立条目写入 EVALUATIONRESULT"""
    user_req = request.get_json()
    task_id = user_req.get('task_id')
    dataset_names = user_req.get('dataset_names')
    tasks_data = get_tasks()
    if task_id not in tasks_data:
        return (jsonify({'error': f'任务 {task_id} 不存在'}), 404)
    task = tasks_data[task_id]
    if task.get('status') != 'completed':
        return (jsonify({'error': '任务未完成，无法写入评测结果'}), 400)
    is_eld = '儿童伴读' in task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
    is_yitu = '意图' in task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
    is_memory = '记忆' in task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
    memory_entries = {'画像记忆独立信息点topic_subtopic提取': '记忆萃取-信息点提取', '画像记忆更新': '记忆萃取-更新', '查询扩写': '记忆召回-查询扩写', '总结过滤': '记忆召回-总结过滤'}
    is_gaixie = '改写' in task['taskConfig']['dataset_args'][0].get('testcase_tags', '')
    model_id = task['model_id']
    result_data = task.get('result')
    if not result_data:
        return (jsonify({'error': '任务没有评测结果数据'}), 400)
    eval_results = get_report_tasks_from_path(EVALUATIONRESULT)
    if not isinstance(eval_results, dict):
        eval_results = {}
    now_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    model_type_list = task.get('modelType', [])
    model_type_str = ','.join(model_type_list) if isinstance(model_type_list, list) else str(model_type_list)
    assessmentType = task['taskConfig'].get('assessmentType', '')
    evaluationType = task['taskConfig'].get('evaluationType', '')
    create_time = task.get('createTime', '')
    running_time = task.get('runningTime', 0)
    keys_to_remove = []
    target_datasets = set(dataset_names)
    for existing_id, existing_entry in list(eval_results.items()):
        if existing_entry.get('model_id') == model_id and existing_entry.get('dataset') in target_datasets:
            keys_to_remove.append(existing_id)
    for k in keys_to_remove:
        del eval_results[k]
    new_entries = {}
    if not is_eld and (not is_memory):
        for key, datasets in result_data.items():
            for ds in datasets:
                dataset_name = ds.get('dataset_name')
                if is_gaixie:
                    gaixie_scene = ds.get('metrics')[0]['name']
                if dataset_name in dataset_names:
                    score = ds.get('score', 0)
                    entry_id = f'{model_id}_{dataset_name}_{now_ts}'
                    entry_dataset = '意图' if is_yitu else gaixie_scene if is_gaixie else dataset_name
                    new_entries[entry_id] = {'id': entry_id, 'task_id': task_id, 'task_name': task.get('name', ''), 'model_id': model_id, 'model_type': model_type_str, 'dataset': entry_dataset, 'task_dataset': dataset_name, 'score': score, 'assessmentType': assessmentType, 'evaluationType': evaluationType, 'create_time': create_time, 'running_time': running_time}
    elif is_memory:
        for key, datasets in result_data.items():
            for ds in datasets:
                dataset_name = ds.get('dataset_name')
                if dataset_name not in dataset_names:
                    continue
                metrics = ds.get('metrics', [])
                for metric in metrics:
                    categories = metric.get('categories', [])
                    for category in categories:
                        category_subsets = category.get('subsets', [])
                        subset_names = []
                        for subset in category_subsets:
                            sub_name = subset.get('name', '')
                            mapped = memory_entries.get(sub_name, sub_name)
                            subset_names.append(mapped)
                        if not subset_names:
                            continue
                        dataset_str = ','.join(subset_names)
                        old_keys = [k for k, v in eval_results.items() if v.get('model_id') == model_id and v.get('dataset') == dataset_str]
                        for k in old_keys:
                            del eval_results[k]
                        entry_id = f'{model_id}_{dataset_name}_{now_ts}'
                        new_entries[entry_id] = {'id': entry_id, 'task_id': task_id, 'task_name': task.get('name', ''), 'model_id': model_id, 'model_type': model_type_str, 'dataset': dataset_str, 'task_dataset': dataset_name, 'score': ds.get('score', 0), 'assessmentType': assessmentType, 'evaluationType': evaluationType, 'create_time': create_time, 'running_time': running_time}
    else:
        for key, datasets in result_data.items():
            for ds in datasets:
                dataset_name = ds.get('dataset_name')
                if dataset_name not in dataset_names:
                    continue
                metrics = ds.get('metrics', [])
                for metric in metrics:
                    categories = metric.get('categories', [])
                    for category in categories:
                        category_subsets = category.get('subsets', [])
                        for subset in category_subsets:
                            business_name = subset.get('name', '')
                            business_score = subset.get('score', 0)
                            old_keys = [k for k, v in eval_results.items() if v.get('model_id') == model_id and v.get('dataset') == business_name]
                            for k in old_keys:
                                del eval_results[k]
                            entry_id = f'{model_id}_{dataset_name}_{business_name}_{now_ts}'
                            new_entries[entry_id] = {'id': entry_id, 'task_id': task_id, 'task_name': task.get('name', ''), 'model_id': model_id, 'model_type': model_type_str, 'dataset': business_name, 'task_dataset': dataset_name, 'score': business_score, 'subsets': subset.get('subsets', []), 'assessmentType': assessmentType, 'evaluationType': evaluationType, 'create_time': create_time, 'running_time': running_time}
    if not new_entries:
        return (jsonify({'error': f'未找到与 dataset_name={dataset_name} 匹配的评测结果'}), 404)
    eval_results.update(new_entries)
    set_report_tasks_to_path(EVALUATIONRESULT, eval_results)
    return (jsonify({'message': f'成功写入 {len(new_entries)} 条评测结果', 'count': len(new_entries), 'entries': new_entries}), 200)

@app.route('/v1/delete_single_result', methods=['POST'])
def delete_single_result():
    """根据 id 删除 EVALUATIONRESULT 中对应的评测结果条目"""
    user_req = request.get_json()
    id = user_req.get('id')
    if not id:
        return (jsonify({'error': '缺少 id 参数'}), 400)
    eval_results = get_report_tasks_from_path(EVALUATIONRESULT)
    if not isinstance(eval_results, dict):
        return (jsonify({'error': 'EVALUATIONRESULT 数据格式异常'}), 500)
    keys_to_delete = [k for k, v in eval_results.items() if v.get('id') == id]
    if not keys_to_delete:
        return (jsonify({'error': f'未找到 id={id} 对应的评测结果'}), 404)
    for k in keys_to_delete:
        del eval_results[k]
    set_report_tasks_to_path(EVALUATIONRESULT, eval_results)
    return (jsonify({'message': f'成功删除 {len(keys_to_delete)} 条评测结果', 'count': len(keys_to_delete), 'deleted_ids': keys_to_delete}), 200)

@app.route('/v1/upload_local_result', methods=['POST'])
def upload_local_result():
    """将用户在本地测评得到的结果（已评测 Excel）上传入库。

    前端 multipart/form-data 字段：
      - tag:      CUSTOM_RULER2_PROC_DISPATCH 中的键（当前支持「儿童伴读」「记忆」
                  「伴学提参」「Coordinator」「GUI提参」「skill提参」「意图」「改写」）
      - model_id: 模型名称
      - file:     已评测的 Excel（.xlsx/.xls）——「儿童伴读」/「Coordinator」
                  /「GUI提参」/「意图」；
                  skill提参 亦为单个 file（结果 Excel，「明细结果」sheet）。
      - file_<显示名>: 已评测的 Excel ——「记忆」每个子任务对应一个，显示名如
                      `记忆萃取-信息点提取` / `记忆萃取-更新` /
                      `记忆召回-查询扩写` / `记忆召回-总结过滤`；
                      「伴学提参」每个子任务对应一个：file_提醒 / file_总结 / file_提参；
                      「改写」为单个结果 Excel（含「测试明细」sheet），走 file 字段。

    接口动作：
      1. 按 `{model_id}_{tag}_{create_time}` 生成 evaluationResult.json 的键与 id；
         task_id 采用 `{create_time}_{0001..9999}`（取当天未占用的最小序号）。
      2. 在 outputs/{model_id}/{task_id} 下创建 reports/、reviews/（各含 model_id 子目录），
         将上传 Excel 保存至 reviews/{model_id}/，并按 tag 生成 reports json 与 reviews jsonl。
    """
    tag = (request.form.get('tag') or '').strip()
    model_id = (request.form.get('model_id') or '').strip()
    if not tag:
        return (jsonify({'error': '缺少 tag 字段'}), 400)
    if tag not in CUSTOM_RULER2_PROC_DISPATCH:
        return (jsonify({'error': f'tag={tag} 不在支持范围内'}), 400)
    if tag not in ('儿童伴读', '记忆', '伴学提参', 'Coordinator', 'GUI提参', 'skill提参', '意图', '改写'):
        return (jsonify({'error': f'tag={tag} 的本地结果上传暂未实现'}), 501)
    if not model_id:
        return (jsonify({'error': '缺少 model_id 字段'}), 400)
    is_memory = tag == '记忆'
    is_banxue = tag == '伴学提参'
    is_skill = tag == 'skill提参'
    if is_memory or is_banxue:
        uploaded_files = {key[len('file_'):]: fobj for key, fobj in request.files.items() if key.startswith('file_')}
        if not uploaded_files:
            return (jsonify({'error': '缺少 file_* 字段'}), 400)
        for fobj in uploaded_files.values():
            if not fobj.filename:
                return (jsonify({'error': '文件名为空'}), 400)
            if not fobj.filename.lower().endswith(('.xlsx', '.xls')):
                return (jsonify({'error': '仅支持 xlsx/xls 格式文件'}), 400)
    else:
        if 'file' not in request.files:
            return (jsonify({'error': '缺少 file 字段'}), 400)
        file = request.files['file']
        if not file.filename:
            return (jsonify({'error': '文件名为空'}), 400)
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return (jsonify({'error': '仅支持 xlsx/xls 格式文件'}), 400)
    create_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    entry_id = f'{model_id}_{tag}_{create_time}'
    used_task_ids = set()
    eval_results = get_report_tasks_from_path(EVALUATIONRESULT)
    if isinstance(eval_results, dict):
        for entry in eval_results.values():
            if isinstance(entry, dict) and entry.get('task_id'):
                used_task_ids.add(entry['task_id'])
    model_output_dir = f'outputs/{model_id}'
    if os.path.isdir(model_output_dir):
        used_task_ids.update(os.listdir(model_output_dir))
    task_id = None
    for seq in range(1, 10000):
        candidate = f'{create_time}_{seq:04d}'
        if candidate not in used_task_ids:
            task_id = candidate
            break
    if task_id is None:
        return (jsonify({'error': 'task_id 序号已用尽（9999），请稍后重试'}), 500)
    dataset_name = tag
    task_name = f'{model_id}_{dataset_name}'
    create_time_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    task_output_dir = os.path.join(model_output_dir, task_id)
    report_dir = os.path.join(task_output_dir, 'reports', model_id)
    review_dir = os.path.join(task_output_dir, 'reviews', model_id)
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    try:
        if is_memory:
            saved_memory_files = {}
            for display_name, fobj in uploaded_files.items():
                saved_path = os.path.join(review_dir, fobj.filename)
                fobj.save(saved_path)
                saved_memory_files[display_name] = saved_path
            memory_result = build_memory_result_from_uploaded_excel(model_id, report_dir, review_dir, dataset_name, saved_memory_files)
            json_path = memory_result['report_json']
            jsonl_path = list(memory_result['review_jsonls'].values())
            score = memory_result['score']
        elif is_banxue:
            saved_banxue_files = {}
            for subtask, fobj in uploaded_files.items():
                saved_path = os.path.join(review_dir, fobj.filename)
                fobj.save(saved_path)
                saved_banxue_files[subtask] = saved_path
            banxue_result = build_banxue_result_from_uploaded_excel(tag, model_id, report_dir, review_dir, saved_banxue_files)
            json_path = banxue_result['report_json']
            jsonl_path = list(banxue_result['review_jsonls'].values())
            score = banxue_result['score']
        elif tag == '改写':
            saved_excel_path = os.path.join(review_dir, file.filename)
            file.save(saved_excel_path)
            gaixie_result = build_rewrite_result_from_uploaded_excel(tag, model_id, saved_excel_path, report_dir, review_dir)
            json_path = gaixie_result['report_json']
            jsonl_path = list(gaixie_result['review_jsonls'].values())
            score = gaixie_result['score']
        elif is_skill:
            saved_excel_path = os.path.join(review_dir, file.filename)
            file.save(saved_excel_path)
            json_path, jsonl_path, score = build_skill_result_from_uploaded_excel(tag, model_id, saved_excel_path, report_dir, review_dir)
            accuracy_dict = None
        elif tag in ('Coordinator', 'GUI提参'):
            saved_excel_path = os.path.join(review_dir, file.filename)
            file.save(saved_excel_path)
            if tag == 'Coordinator':
                json_path, jsonl_path, score = build_coordinator_result_from_uploaded_excel(tag, model_id, saved_excel_path, report_dir, review_dir)
            else:
                json_path, jsonl_path, score = build_gui_result_from_uploaded_excel(tag, model_id, saved_excel_path, report_dir, review_dir)
            accuracy_dict = None
        elif tag == '意图':
            saved_excel_path = os.path.join(review_dir, file.filename)
            file.save(saved_excel_path)
            json_path, jsonl_path, score, yitu_subsets = build_yitu_result_from_uploaded_excel(tag, model_id, saved_excel_path, report_dir, review_dir)
            accuracy_dict = None
        else:
            saved_excel_path = os.path.join(review_dir, file.filename)
            file.save(saved_excel_path)
            json_path, jsonl_path, accuracy_dict = build_result_from_uploaded_excel(tag, model_id, saved_excel_path, report_dir, review_dir)
            score = None
    except NotImplementedError as e:
        return (jsonify({'error': str(e)}), 501)
    except Exception as e:
        traceback.print_exc()
        return (jsonify({'error': f'生成结果文件失败: {e}'}), 500)
    if not isinstance(eval_results, dict):
        eval_results = {}

    def _acc_to_float(score_str):
        try:
            return float(str(score_str).rstrip('%')) / 100
        except (ValueError, TypeError):
            return None
    new_entries = {}
    if tag == '儿童伴读':
        for business, info in (accuracy_dict or {}).items():
            if not info or not info.get('num'):
                continue
            business_id = f'{model_id}_{dataset_name}_{business}_{create_time}'
            old_keys = [k for k, v in eval_results.items() if isinstance(v, dict) and v.get('model_id') == model_id and (v.get('dataset') == business)]
            for k in old_keys:
                del eval_results[k]
            new_entries[business_id] = {'id': business_id, 'task_id': task_id, 'task_name': task_name, 'model_id': model_id, 'model_type': 'LLM,MLLM', 'dataset': business, 'task_dataset': dataset_name, 'tag': tag, 'score': _acc_to_float(info.get('score')), 'subsets': info.get('subsets', []), 'assessmentType': '领域评估(Ruler2)', 'evaluationType': 'llm', 'create_time': create_time_iso, 'running_time': 0}
    elif tag == '记忆':
        dataset_str = ','.join([display for internal, display in MEMORY_BUSINESS_MAP.items() if any((s['internal_name'] == internal for s in memory_result['subsets']))])
        if not dataset_str:
            return (jsonify({'error': '未从上传结果中解析出可写入的记忆条目'}), 500)
        old_keys = [k for k, v in eval_results.items() if isinstance(v, dict) and v.get('model_id') == model_id and (v.get('dataset') == dataset_str)]
        for k in old_keys:
            del eval_results[k]
        entry_id = f'{model_id}_{dataset_name}_{create_time}'
        new_entries[entry_id] = {'id': entry_id, 'task_id': task_id, 'task_name': task_name, 'model_id': model_id, 'model_name': model_id, 'model_type': 'LLM', 'dataset': dataset_str, 'task_dataset': dataset_name, 'tag': tag, 'score': score, 'assessmentType': '领域评估(Ruler2)', 'evaluationType': 'llm', 'create_time': create_time_iso, 'running_time': 0}
    elif tag in ('伴学提参', 'Coordinator', 'GUI提参', 'skill提参'):
        entry_id = f'{model_id}_{dataset_name}_{create_time}'
        old_keys = [k for k, v in eval_results.items() if isinstance(v, dict) and v.get('model_id') == model_id and (v.get('dataset') == tag)]
        for k in old_keys:
            del eval_results[k]
        entry = {'id': entry_id, 'task_id': task_id, 'task_name': task_name, 'model_id': model_id, 'model_name': model_id, 'model_type': 'LLM,LLM', 'dataset': tag, 'task_dataset': dataset_name, 'tag': tag, 'score': score, 'assessmentType': '领域评估(Ruler2)', 'evaluationType': 'llm', 'create_time': create_time_iso, 'running_time': 0}
        if is_banxue:
            entry['subsets'] = banxue_result['subsets']
        new_entries[entry_id] = entry
    elif tag == '意图':
        entry_id = f'{model_id}_{dataset_name}_{create_time}'
        old_keys = [k for k, v in eval_results.items() if isinstance(v, dict) and v.get('model_id') == model_id and (v.get('dataset') == tag)]
        for k in old_keys:
            del eval_results[k]
        new_entries[entry_id] = {'id': entry_id, 'task_id': task_id, 'task_name': task_name, 'model_id': model_id, 'model_name': model_id, 'model_type': 'LLM', 'dataset': tag, 'task_dataset': dataset_name, 'tag': tag, 'score': score, 'subsets': yitu_subsets, 'assessmentType': '领域评估(Ruler2)', 'evaluationType': 'llm', 'create_time': create_time_iso, 'running_time': 0}
    elif tag == '改写':
        entry_id = f'{model_id}_{dataset_name}_{create_time}'
        old_keys = [k for k, v in eval_results.items() if isinstance(v, dict) and v.get('model_id') == model_id and (v.get('dataset') == tag)]
        for k in old_keys:
            del eval_results[k]
        new_entries[entry_id] = {'id': entry_id, 'task_id': task_id, 'task_name': task_name, 'model_id': model_id, 'model_name': model_id, 'model_type': 'LLM', 'dataset': tag, 'task_dataset': dataset_name, 'tag': tag, 'score': score, 'loose_score': gaixie_result['loose_score'], 'subsets': gaixie_result['subsets'], 'assessmentType': '领域评估(Ruler2)', 'evaluationType': 'llm', 'create_time': create_time_iso, 'running_time': 0}
    else:
        new_entries[entry_id] = {'id': entry_id, 'task_id': task_id, 'task_name': task_name, 'model_id': model_id, 'model_type': 'llm', 'dataset': tag, 'task_dataset': dataset_name, 'tag': tag, 'score': None, 'assessmentType': '领域评估(Ruler2)', 'evaluationType': 'llm', 'create_time': create_time_iso, 'running_time': 0}
    if not new_entries:
        return (jsonify({'error': '未从上传结果中解析出可写入的业务条目'}), 500)
    eval_results.update(new_entries)
    set_report_tasks_to_path(EVALUATIONRESULT, eval_results)
    return (jsonify({'message': '本地结果上传成功', 'task_id': task_id, 'task_name': task_name, 'model_id': model_id, 'task_dataset': dataset_name, 'entries': new_entries, 'report_json': json_path, 'review_jsonl': jsonl_path}), 201)
None
