from state_storage import open_state, state_exists, state_isfile
# Private iCAP Yellow business implementation. Do not publish.
import json
import os.path
import os
import time
from io import BytesIO
import httpx
import shutil
import sys
import glob
import re
import chardet
import requests
import uuid
import atexit
import secrets
import random
import subprocess
import zipfile
import openpyxl
import threading
import jsonlines as jsonl
import numpy as np
import base64
from openai import OpenAI
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory, Response, make_response
from flask_cors import CORS
from urllib.parse import urlparse
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from json import JSONDecodeError
from call_api import get_response_chat
from werkzeug.utils import secure_filename
import datetime as dt
from datetime import datetime
from utils.consts import *
from utils.utils import *
from utils.update_lmarena import update_lmarena_csv, LM_ARENA_CSV_PATH
from services.multi_ruler2.children_study.result_evaluation import calculate_accuracy_with_styles
from services.userLogService import get_overview, get_trend, get_type_distribution, get_top_users, get_department_stats, get_details, get_user_candidates, get_model_candidates, get_type_candidates, refresh_dept_cache
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'CCNRuler1EvalScope'))
sys.path.append(os.path.join(current_dir, 'CCNRuler2EvalScope'))
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)
TEST_TASK_INDEX = 1
SUCCESS = 200
PARAM_ERR = 400
TESTCASE_ALREADY_EXIST = 408
MODEL_ALREADY_EXIST = 409
MODEL_NOT_EXIST = 410
SERVER_ERR = 500
UPLOAD_FOLDERS = os.path.expanduser(Path.home().joinpath('.cache', 'download'))
AI_MODELS_SELECT_FILE_NAME = 'AI模型汇总.xlsx'
AI_MODELS_SELECT_FILE_SHEETS = ['LLM大语言模型', '专业分析模型']
tasks = {}
admin_id = '00001'
users = {}
log_lock = threading.Lock()
OUT_WHITE_LIST = ['gemini-3-pro-preview-thinking(外网api,请注意信息安全)', 'gemini-3-pro-preview(外网api,请注意信息安全)', 'DeepSeek-V3.1-Terminus(外网api,请注意信息安全)']

def get_encoding(file_path):
    with open_state(file_path, 'rb') as f:
        result = chardet.detect(f.read(10000))
    print(result)
    encoding = result['encoding']
    return encoding

def get_latest_test_list(base_path, target_subfolder):
    folder_names = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f)) and '_' in f]
    folder_names.sort(key=lambda x: datetime.strptime(x, '%Y%m%d_%H%M%S'), reverse=True)
    for folder_name in folder_names:
        target_path = os.path.join(base_path, folder_name, target_subfolder)
        if state_exists(target_path) and os.path.isdir(target_path):
            file_list = glob.glob(os.path.join(target_path, '*'))
            if file_list:
                return file_list
    return []

def is_valid_json(json_string):
    if isinstance(json_string, dict):
        return (True, json_string)
    if not isinstance(json_string, str):
        return (False, None)
    try:
        json_object = json.loads(json_string)
    except ValueError as e:
        return (False, None)
    return (True, json_object)

def get_generate_cfg(user_req):
    if 'generation_config' not in user_req:
        return None
    cfg_str = user_req['generation_config']
    is_json, json_object = is_valid_json(cfg_str)
    if not is_json:
        return None
    return json_object

def get_filter(user_req):
    if 'filter_head' not in user_req or 'filter_tail' not in user_req:
        return None
    return {'head': user_req['filter_head'], 'tail': user_req['filter_tail']}

def get_publisher(model_name):
    if 'ds' in model_name.lower() or 'deepseek' in model_name.lower():
        publisher = 'DeepSeek'
    elif 'qwen' in model_name.lower() or model_name.lower().startswith('qwq'):
        publisher = 'Alibaba'
    elif 'pangu' in model_name.lower():
        publisher = 'Huawei'
    elif 'llama' in model_name.lower():
        publisher = 'Meta'
    else:
        publisher = 'Others'
    return publisher

def check_url_connectivity(url, api_key, timeout=0.4):
    """
    检查 URL 是否可访问
    :param url: str, 完整的 URL（如 http://example.com）
    :param api_key: str, API密钥
    :param timeout: int, 超时时间（秒）
    :return: bool, 是否连通
    """
    try:
        if api_key is not None and api_key != '' and (api_key != 'EMPTY'):
            timeout = 3
            headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json', 'Content-Type': 'application/json'}
            route_url = url if url.endswith('/chat/completions') else url + '/chat/completions'
            print('api_key: ', api_key)
            if classify_url(url):
                print('检测到IP地址形式的URL，跳过代理直连')
                response = requests.post(route_url, timeout=timeout, headers=headers, json={'model': 'test', 'messages': [{'role': 'user', 'content': 'hi'}]}, verify=True)
            else:
                proxies = {}
                print('proxies: ', proxies)
                response = requests.get(route_url, timeout=timeout, headers=headers, proxies=proxies, verify=True)
        else:
            response = requests.get(url, timeout=timeout)
        print('状态码: ', response.status_code)
        return 200 <= response.status_code < 500
    except Timeout:
        print(f'请求超时: {url}')
    except ConnectionError:
        print(f'连接错误（可能网络不通或 DNS 解析失败）: {url}')
    except HTTPError as e:
        print(f'HTTP 错误: {e} - {url}')
    except RequestException as e:
        print(f'请求异常: {e} - {url}')
    return False

def check_model_connectivity(config):
    res = False
    api_params_available = config['api_params_available']
    api_params_available.clear()
    print('api列表:', config['api_params'])
    for api in config['api_params']:
        if 'endpoint' not in api or 'api_key' not in api:
            print('api信息不完整')
            continue
        print('正在检查:', api['endpoint'], api['api_key'])
        if check_url_connectivity(api['endpoint'], api['api_key']):
            res = True
            api_params_available.append(api)
    return res

def generate_model_info(user_req, model_cfg):
    try:
        cur_cfg = user_req
        is_available = check_model_connectivity(cur_cfg['config'])
        cur_cfg['is_available'] = is_available
        for item in model_cfg:
            if item['model_id'] == cur_cfg['model_id']:
                model_cfg.remove(item)
                break
        model_cfg.append(cur_cfg)
        json_str = json.dumps(model_cfg, ensure_ascii=False, indent=4)
        with open_state(MODEL_CFG_PATH, 'w', encoding='utf-8') as f:
            f.write(json_str)
        return (jsonify(model_cfg), SUCCESS)
    except Exception as e:
        print(e)
        return ({'err_info': 'SERVER_ERR'}, SERVER_ERR)

def loginAuth(loginInfo):
    account = loginInfo['username']
    password = loginInfo['password']
    attr_list = ['hw-DepartName1', 'hw-DepartName2', 'hw-DepartName3', 'hw-DepartName4', 'hw-DepartName5', 'hw-DepartName6', 'extensionAttribute1', 'givenName', 'mobile', 'mail', 'samaccountname', 'displayname', 'title']
    search_filter = '(&(|(cn=' + account + '*)(givenName=' + account + '*)(mail=' + account + '*)(sn=' + account + '*)(samAccountName=' + account + '*)(name=' + account + '*))(!(objectClass=computer))(!(objectClass=contact)))'
    base = 'dc=china,dc=huawei,dc=com'
    try:
        server = ldap3.Server(LDAP_AUTH_URL, use_ssl=False, get_info=ldap3.ALL)
        conn = ldap3.Connection(server, auto_bind=True, client_strategy=ldap3.SYNC, user='china\\' + account, password=password, authentication=ldap3.SIMPLE)
        conn.search(base, search_filter, attributes=attr_list)
        for entry in conn.entries:
            if entry is not None:
                return True
    except Exception as e:
        print(e)
    return False

def checkUserValid(loginInfo):
    if loginInfo['username'] == 'admin':
        for key in users.keys():
            if key == admin_id:
                if users[key]['password'] == loginInfo['password']:
                    return True
                else:
                    return False
        return False
    return loginAuth(loginInfo)

def get_user_base_info(user_info):
    for id in users.keys():
        if users[id]['username'] == user_info['username']:
            return id
    return None

def get_pem(pem_file):
    with open_state(pem_file, 'rb') as f:
        key_info = f.read()
    return key_info
pem_private = None
pem_public = None

@app.route('/v1/get_pubkey', methods=['GET'])
def get_pubkey():
    return (pem_public, 200)

@app.route('/v1/login', methods=['POST'])
def login():
    global users
    ret = {'status': False, 'info': '', 'user': {'userid': '', 'username': ''}}
    user_info = request.get_json()
    encrypted_password_b64 = user_info['password']
    encrypted_password = base64.b64decode(encrypted_password_b64)
    try:
        decrypted_password = private_key.decrypt(encrypted_password, padding.PKCS1v15())
        user_info['password'] = decrypted_password.decode('utf-8')
    except Exception as e:
        ret['info'] = f'解密失败: {e}'
        return (ret, 400)
    if not checkUserValid(user_info):
        ret['info'] = '用户名或密码错误'
        return jsonify(ret)
    id = get_user_base_info(user_info)
    if id is None:
        user_id = str(uuid.uuid4())
        users[user_id] = {}
    else:
        user_id = id
    users[user_id]['login'] = {}
    ret['user']['userid'] = user_id
    ret['user']['username'] = user_info['username']
    ret['status'] = True
    return (jsonify(ret), 200)

@app.route('/v1/logout', methods=['POST'])
def logout():
    global users
    user_info = request.get_json()
    user_id = get_user_base_info(user_info)
    if not user_id:
        return jsonify({'message': '用户信息不存在'})
    users[user_id]['login'] = {}
    return jsonify({'message': '退出成功'})

@app.route('/v1/cont_online_users', methods=['GET'])
def cont_online_users():
    all_users_cont = len(users)
    onlines = []
    cont = 0
    for _, user in users.items():
        if user['login']:
            cont += 1
            onlines.append(user['username'])
    return jsonify({'all_users_cont': all_users_cont, 'online_users': onlines, 'cont': cont})

@app.route('/v1/register_model', methods=['POST'])
def register_model():
    user_req = request.get_json()
    model_cfg = get_model_info_list()
    if 'model_id' not in user_req or 'model_name' not in user_req['info'] or 'api_params' not in user_req['config']:
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    for cfg in model_cfg:
        if cfg['model_id'] == user_req['model_id']:
            return ({'model_list': [exist_model['model_id'] for exist_model in model_cfg], 'err_info': 'MODEL_ALREADY_EXIST'}, MODEL_ALREADY_EXIST)
    return generate_model_info(user_req, model_cfg)

def generate_deploy_model_info(user_req, model_to_deploy):
    try:
        cur_deploy_info = user_req
        last_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for item in model_to_deploy:
            if item['model_name'] == cur_deploy_info['model_name']:
                last_time = item['create_time']
                model_to_deploy.remove(item)
                break
        cur_deploy_info['create_time'] = last_time
        model_to_deploy.append(cur_deploy_info)
        json_str = json.dumps(model_to_deploy, ensure_ascii=False, indent=4)
        with open_state(MODEL_TO_DEPLOY_PATH, 'w', encoding='utf-8') as f:
            f.write(json_str)
        return (jsonify(model_to_deploy), SUCCESS)
    except Exception as e:
        print(e)
        return ({'err_info': 'SERVER_ERR'}, SERVER_ERR)

@app.route('/v1/apply_deploy_model', methods=['POST'])
def apply_deploy_model():
    user_req = request.get_json()
    if 'model_name' not in user_req or 'model_desc' not in user_req or 'isInternalDeployed' not in user_req:
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    encodings = get_encoding(MODEL_TO_DEPLOY_PATH)
    if encodings is not None:
        with open_state(MODEL_TO_DEPLOY_PATH, 'r', encoding=encodings) as f:
            model_to_deploy = json.load(f)
    else:
        model_to_deploy = []
    return generate_deploy_model_info(user_req, model_to_deploy)

@app.route('/v1/get_apply_deploy_list', methods=['GET'])
def get_apply_deploy_list():
    encodings = get_encoding(MODEL_TO_DEPLOY_PATH)
    if encodings is not None:
        with open_state(MODEL_TO_DEPLOY_PATH, 'r', encoding=encodings) as f:
            model_to_deploy = json.load(f)
    else:
        model_to_deploy = []
    return (jsonify(model_to_deploy), 200)

@app.route('/v1/modify_model', methods=['POST'])
def modify_model():
    user_req = request.get_json()
    model_cfg = get_model_info_list()
    if 'model_id' not in user_req or 'model_name' not in user_req['info'] or 'api_params' not in user_req['config']:
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    for cfg in model_cfg:
        if cfg['model_id'] == user_req['model_id']:
            return generate_model_info(user_req, model_cfg)
    return ({'model_list': [exist_model['model_id'] for exist_model in model_cfg], 'err_info': 'MODEL_NOT_EXIST'}, MODEL_NOT_EXIST)

@app.route('/v1/get_one_model_info', methods=['POST'])
def get_one_model_info():
    user_req = request.get_json()
    model_cfg = get_model_info_list()
    for cfg in model_cfg:
        if cfg['model_id'] == user_req['model_id']:
            return (cfg, 200)
    return ({'model_list': [exist_model['model_id'] for exist_model in model_cfg], 'err_info': 'MODEL_NOT_EXIST'}, MODEL_NOT_EXIST)

@app.route('/v1/delete_model', methods=['POST'])
def delete_model():
    user_req = request.get_json()
    try:
        model_cfg = get_model_info_list()
        del_success = False
        for model_id in user_req:
            for item in model_cfg:
                if item['model_id'] == model_id:
                    model_cfg.remove(item)
                    del_success = True
        if not del_success:
            return ({'err_info': 'MODEL_NOT_EXIST'}, MODEL_NOT_EXIST)
        print(model_cfg)
        json_str = json.dumps(model_cfg, ensure_ascii=False, indent=4)
        with open_state(MODEL_CFG_PATH, 'w', encoding='utf-8') as f:
            f.write(json_str)
        return ({'model_list': [cfg['model_id'] for cfg in model_cfg]}, SUCCESS)
    except Exception as e:
        return ({'err_info': 'SERVER_ERR'}, SERVER_ERR)

def _build_aisf_gaixie_index(few_path, few_file_list):
    """
    如果 testcase_tags 包含"改写"且 few_file_list 中有 Excel 文件，
    则运行 aisf_gaixie 的 build_jsonl.py / build_index.py 构建 FAISS 索引。
    """
    current_file_dir = Path(__file__).resolve().parent
    scripts_dir = current_file_dir / 'services' / 'aisf_gaixie'
    jsonl_script = scripts_dir / 'build_jsonl.py'
    index_script = scripts_dir / 'build_index.py'
    print(f'[aisf_gaixie] 脚本存在: {jsonl_script} / {index_script}')
    if jsonl_script.exists() and index_script.exists():
        print('[aisf_gaixie] 脚本存在，可以执行')
    else:
        print('[aisf_gaixie] 脚本不存在，请检查路径')
    few_path_obj = Path(few_path)
    few_path_obj.mkdir(parents=True, exist_ok=True)
    xlsx_file = None
    for fname in few_file_list:
        if fname.lower().endswith('.xlsx'):
            xlsx_file = fname
            break
    if not xlsx_file:
        print('[aisf_gaixie] few_file_list 中没有 .xlsx 文件，跳过')
        return
    src_xlsx = Path(os.path.join(UPLOAD_FOLDERS, xlsx_file))
    if not src_xlsx.exists():
        print(f'[aisf_gaixie] 临时路径没有 Excel 文件: {xlsx_file}')
        src_xlsx = few_path_obj / xlsx_file
        print(f'[aisf_gaixie] 修改后 Excel 文件: {xlsx_file}')
    if not src_xlsx.exists():
        print(f'[aisf_gaixie] 找不到 Excel 文件: {xlsx_file}')
        return
    target_xlsx = few_path_obj / 'few-shot.xlsx'
    shutil.copy2(str(src_xlsx), str(target_xlsx))
    shutil.copy2(str(jsonl_script), str(few_path_obj / 'build_jsonl.py'))
    shutil.copy2(str(index_script), str(few_path_obj / 'build_index.py'))
    cwd = str(few_path_obj)
    python = sys.executable
    for script_name in ['build_jsonl.py', 'build_index.py']:
        print(f'[aisf_gaixie] 运行 {script_name} in {cwd}')
        result = subprocess.run([python, script_name], cwd=cwd, capture_output=True, text=True, timeout=600)
        print(f'[aisf_gaixie] {script_name} stdout:\n{result.stdout}')
        if result.returncode != 0:
            print(f'[aisf_gaixie] {script_name} stderr:\n{result.stderr}')
        elif result.stderr:
            print(f'[aisf_gaixie] {script_name} stderr:\n{result.stderr}')
    print(f"[aisf_gaixie] 索引构建完成: {few_path_obj / 'index'}")

def generate_testcase_info(user_req, testcase_cfg, test_case_file):
    if not isinstance(user_req['few_shot_num'], int) or user_req['few_shot_num'] < 0:
        return ({'err_info': 'few_shot_num is not valid!'}, SERVER_ERR)
    if not isinstance(user_req['testcase_tags'], list):
        return ({'err_info': 'testcase_tags is not list!'}, SERVER_ERR)
    if not isinstance(user_req['metric_list'], list):
        return ({'err_info': 'metric_list is not list!'}, SERVER_ERR)
    header_path = './testsuite/TestSuite/'
    few_header_path = './testsuite/TestSuite_few/'
    path_name = 'local_path'
    if test_case_file == FILED_TESTCASE_PATH:
        header_path = './testsuite/TestSuiteRulerII/'
        few_header_path = './testsuite/TestSuiteRulerII_few/'
        path_name = 'input_path'
    elif test_case_file == DEV_TESTCASE_PATH:
        header_path = './testsuite/TestSuiteDev/'
        few_header_path = './testsuite/TestSuiteDev_few/'
        path_name = 'input_path'
    is_memory = '记忆' in user_req.get('testcase_tags', [])
    if is_memory:
        if 'memory_business_list' not in user_req or not user_req['memory_business_list']:
            return ({'err_info': '记忆模式下 memory_business_list 不能为空'}, SERVER_ERR)
        local_path = header_path + user_req['dataset_id']
        if state_exists(local_path):
            shutil.rmtree(local_path)
        os.makedirs(local_path, exist_ok=True)
        for business in user_req['memory_business_list']:
            biz_name = business['name']
            biz_dir = os.path.join(local_path, biz_name)
            os.makedirs(biz_dir, exist_ok=True)
            prompt_files = business.get('prompt_file', [])
            if isinstance(prompt_files, str):
                prompt_files = [prompt_files]
            for pf in prompt_files:
                if pf:
                    try:
                        src = os.path.join(UPLOAD_FOLDERS, pf)
                        dst = os.path.join(biz_dir, os.path.basename(pf))
                        shutil.move(src, dst)
                    except Exception as e:
                        return ({'error': f'移动业务 [{biz_name}] prompt文件失败：{str(e)}'}, 500)
            test_files = business.get('test_file', [])
            if isinstance(test_files, str):
                test_files = [test_files]
            for tf in test_files:
                if tf:
                    try:
                        src = os.path.join(UPLOAD_FOLDERS, tf)
                        dst = os.path.join(biz_dir, os.path.basename(tf))
                        shutil.move(src, dst)
                    except Exception as e:
                        return ({'error': f'移动业务 [{biz_name}] 测试集文件失败：{str(e)}'}, 500)
    else:
        if not isinstance(user_req.get('subset_list'), list):
            return ({'err_info': 'subset_list is not list!'}, SERVER_ERR)
        local_path = header_path + user_req['dataset_id']
        few_path = few_header_path + user_req['dataset_id']
        if not state_exists(local_path):
            os.makedirs(local_path)
        for file in user_req.get('file_list', []):
            try:
                file_name = os.path.basename(file)
                shutil.move(os.path.join(UPLOAD_FOLDERS, file), os.path.join(local_path, file_name))
            except Exception as e:
                return ({'error': '移动文件失败：' + str(e)}, 500)
        if not state_exists(few_path):
            os.makedirs(few_path)
        for file in user_req.get('few_file_list', []):
            try:
                file_name = os.path.basename(file)
                shutil.move(os.path.join(UPLOAD_FOLDERS, file), os.path.join(few_path, file_name))
            except Exception as e:
                return ({'error': '移动文件失败：' + str(e)}, 500)
    testcase_cfg[user_req['dataset_id']] = {'dataset_name': user_req['dataset_name'], path_name: header_path + user_req['dataset_id'], 'few_shot_num': user_req['few_shot_num'], 'few_shot_file_path': [], 'description': user_req['description'], 'subset_list': user_req.get('subset_list', []), 'default_subsets': user_req.get('default_subsets', []), 'testcase_tags': user_req['testcase_tags'], 'metric_list': user_req['metric_list'], 'establish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'is_open_source': user_req['is_open_source'], 'need_llmjudge': user_req.get('need_llmjudge', False), 'file_list': user_req.get('file_list', []), 'few_file_list': user_req.get('few_file_list', []), 'is_field': user_req['is_field'], 'system_prompt': user_req.get('system_prompt', ''), 'user_prompt': user_req.get('user_prompt', ''), 'is_published': user_req.get('is_published', False), 'viewer_users': user_req.get('viewer_users', []), 'editor_users': user_req.get('editor_users', []), 'register': user_req.get('register', 'admin'), 'in_use': False, 'status': 1, 'is_published': user_req.get('is_published', False), 'viewer_users': user_req.get('viewer_users', []), 'editor_users': user_req.get('editor_users', [])}
    if is_memory:
        testcase_cfg[user_req['dataset_id']]['memory_business_list'] = user_req['memory_business_list']
    with open_state(test_case_file, 'w', encoding='utf-8') as f:
        json.dump(testcase_cfg, f, indent=4, ensure_ascii=False)
    if '改写' in user_req.get('testcase_tags', []):
        few_file_list = user_req.get('few_file_list', [])
        if few_file_list:
            _build_aisf_gaixie_index(few_path, few_file_list)
    return ({'status': 'success'}, 200)

def refresh_file(old_file_list, path, user_req):
    os.makedirs(path, exist_ok=True)
    for old in set(old_file_list) - set(user_req):
        target = Path(path) / os.path.basename(old)
        if target.is_file():
            target.unlink()
    for new in set(user_req) - set(old_file_list):
        source = Path(UPLOAD_FOLDERS) / new
        if not source.is_file():
            raise ValueError('新上传的文件不存在，请重新上传')
        shutil.move(str(source), str(Path(path) / os.path.basename(new)))

def edit_testcase_info(user_req, testcase_cfg, test_case_file):
    if not isinstance(user_req['few_shot_num'], int) or user_req['few_shot_num'] < 0:
        return ({'err_info': 'few_shot_num is not valid!'}, SERVER_ERR)
    if not isinstance(user_req['testcase_tags'], list):
        return ({'err_info': 'testcase_tags is not list!'}, SERVER_ERR)
    if not isinstance(user_req['metric_list'], list):
        return ({'err_info': 'metric_list is not list!'}, SERVER_ERR)
    header_path = './testsuite/TestSuite/'
    few_header_path = './testsuite/TestSuite_few/'
    path_name = 'local_path'
    if test_case_file == FILED_TESTCASE_PATH:
        header_path = './testsuite/TestSuiteRulerII/'
        few_header_path = './testsuite/TestSuiteRulerII_few/'
        path_name = 'input_path'
    elif test_case_file == DEV_TESTCASE_PATH:
        header_path = './testsuite/TestSuiteDev/'
        few_header_path = './testsuite/TestSuiteDev_few/'
        path_name = 'input_path'
    is_memory = '记忆' in user_req.get('testcase_tags', [])
    if is_memory:
        if 'memory_business_list' not in user_req or not user_req['memory_business_list']:
            return ({'err_info': '记忆模式下 memory_business_list 不能为空'}, SERVER_ERR)
        local_path = header_path + user_req['dataset_id']
        if not state_exists(local_path):
            os.makedirs(local_path, exist_ok=True)
        old_cfg = testcase_cfg.get(user_req['dataset_id'], {})
        old_biz_list = old_cfg.get('memory_business_list', [])
        old_biz_names = {b['name'] for b in old_biz_list}
        new_biz_names = {b['name'] for b in user_req['memory_business_list']}
        for removed_biz in old_biz_names - new_biz_names:
            removed_dir = os.path.join(local_path, removed_biz)
            if state_exists(removed_dir):
                shutil.rmtree(removed_dir)
        for business in user_req['memory_business_list']:
            biz_name = business['name']
            biz_dir = os.path.join(local_path, biz_name)
            os.makedirs(biz_dir, exist_ok=True)
            prompt_files = business.get('prompt_file', [])
            if isinstance(prompt_files, str):
                prompt_files = [prompt_files]
            for pf in prompt_files:
                if pf:
                    src_prompt = os.path.join(UPLOAD_FOLDERS, pf)
                    if state_exists(src_prompt):
                        try:
                            dst_prompt = os.path.join(biz_dir, os.path.basename(pf))
                            shutil.move(src_prompt, dst_prompt)
                        except Exception as e:
                            return ({'error': f'移动业务 [{biz_name}] prompt文件失败：{str(e)}'}, 500)
            test_files = business.get('test_file', [])
            if isinstance(test_files, str):
                test_files = [test_files]
            for tf in test_files:
                if tf:
                    src_test = os.path.join(UPLOAD_FOLDERS, tf)
                    if state_exists(src_test):
                        try:
                            dst_test = os.path.join(biz_dir, os.path.basename(tf))
                            shutil.move(src_test, dst_test)
                        except Exception as e:
                            return ({'error': f'移动业务 [{biz_name}] 测试集文件失败：{str(e)}'}, 500)
    else:
        if not isinstance(user_req.get('subset_list'), list):
            return ({'err_info': 'subset_list is not list!'}, SERVER_ERR)
        local_path = header_path + user_req['dataset_id']
        few_path = few_header_path + user_req['dataset_id']
        old_file_list = testcase_cfg[user_req['dataset_id']].get('file_list', [])
        old_few_file_list = testcase_cfg[user_req['dataset_id']].get('few_file_list', [])
        if 'file_list' in user_req:
            refresh_file(old_file_list, local_path, user_req['file_list'])
        if 'few_file_list' in user_req:
            refresh_file(old_few_file_list, few_path, user_req['few_file_list'])
    testcase_cfg[user_req['dataset_id']].update({k: v for k, v in user_req.items() if k != 'dataset_id' and k != 'download_count' and (k != 'view_count')})
    testcase_cfg[user_req['dataset_id']].update({path_name: header_path + user_req['dataset_id'], 'establish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'status': 1})
    with open_state(test_case_file, 'w', encoding='utf-8') as f:
        json.dump(testcase_cfg, f, indent=4, ensure_ascii=False)
    if '改写' in user_req.get('testcase_tags', []):
        few_file_list = user_req.get('few_file_list', [])
        if few_file_list:
            _build_aisf_gaixie_index(few_path, few_file_list)
    return ({'status': 'success'}, 200)

@app.route('/v1/register_testcase_ruler', methods=['POST'])
def register_testcase_ruler():
    user_req = request.get_json()
    test_case_file = COMMON_TESTCASE_PATH
    if 'is_field' in user_req.keys():
        if user_req['is_field'] == 2 or user_req['is_field'] == '2':
            test_case_file = FILED_TESTCASE_PATH
        elif user_req['is_field'] == 3 or user_req['is_field'] == '3':
            test_case_file = DEV_TESTCASE_PATH
    required_fields = ['dataset_id', 'dataset_name', 'testcase_tags', 'description', 'few_shot_num', 'is_open_source', 'is_field']
    is_memory = '记忆' in user_req.get('testcase_tags', [])
    if not is_memory:
        required_fields.append('subset_list')
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    encodings = get_encoding(test_case_file)
    with open_state(test_case_file, 'r', encoding='UTF-8') as f:
        testcase_cfg = {key: value for key, value in json.load(f).items() if value.get('status') == 1}
    if 'dataset_id' not in user_req or 'dataset_name' not in user_req or 'few_shot_num' not in user_req:
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    if not is_memory and (not user_req.get('file_list')):
        return ({'err_info': '请上传测试集文件'}, 400)
    if not user_req['dataset_id']:
        return ({'err_info': 'dataset_id is null!'}, 400)
    if user_req['dataset_id'] in testcase_cfg.keys():
        return ({'model_list': list(testcase_cfg.keys()), 'err_info': 'TESTCASE_ALREADY_EXIST'}, TESTCASE_ALREADY_EXIST)
    return generate_testcase_info(user_req, testcase_cfg, test_case_file)

@app.route('/v1/edit_testcase_ruler', methods=['POST'])
def edit_testcase_ruler():
    user_req = request.get_json()
    test_case_file = COMMON_TESTCASE_PATH
    if 'is_field' in user_req.keys():
        if user_req['is_field'] == 2 or user_req['is_field'] == '2':
            test_case_file = FILED_TESTCASE_PATH
        elif user_req['is_field'] == 3 or user_req['is_field'] == '3':
            test_case_file = DEV_TESTCASE_PATH
    required_fields = ['dataset_id', 'dataset_name', 'testcase_tags', 'description', 'few_shot_num', 'is_open_source', 'is_field']
    is_memory = '记忆' in user_req.get('testcase_tags', [])
    if not is_memory:
        required_fields.append('subset_list')
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    encodings = get_encoding(test_case_file)
    with open_state(test_case_file, 'r', encoding=encodings) as f:
        testcase_cfg = json.load(f)
    if 'dataset_id' not in user_req or 'dataset_name' not in user_req or 'few_shot_num' not in user_req:
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    if user_req['dataset_id'] not in testcase_cfg.keys():
        return ({'err_info': f"{user_req['dataset_id']} is not exist"}, PARAM_ERR)
    if is_memory and ('memory_business_list' not in user_req or not user_req['memory_business_list']):
        return ({'err_info': '记忆模式下 memory_business_list 不能为空'}, PARAM_ERR)
    return edit_testcase_info(user_req, testcase_cfg, test_case_file)

@app.route('/v1/delete_testcase_ruler', methods=['POST'])
def delete_testcase_ruler():
    user_req = request.get_json()
    test_case_file = COMMON_TESTCASE_PATH
    path_name = 'local_path'
    if 'is_field' in user_req.keys():
        if user_req['is_field'] == 2 or user_req['is_field'] == '2':
            test_case_file = FILED_TESTCASE_PATH
            path_name = 'input_path'
        elif user_req['is_field'] == 3 or user_req['is_field'] == '3':
            test_case_file = DEV_TESTCASE_PATH
            path_name = 'input_path'
    required_fields = ['dataset_id']
    if any((field not in user_req for field in required_fields)):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    encodings = get_encoding(test_case_file)
    with open_state(test_case_file, 'r', encoding=encodings if encodings else 'UTF-8') as f:
        testcase_cfg = json.load(f)
    if user_req['dataset_id'] not in testcase_cfg.keys():
        return ({'err_info': f"{user_req['dataset_id']} is not exist"}, PARAM_ERR)
    target_name = user_req['dataset_id']
    if state_exists(testcase_cfg[target_name][path_name]):
        testcase_cfg[target_name]['status'] = 0
        with open_state(test_case_file, 'w', encoding='utf-8') as f:
            json.dump(testcase_cfg, f, indent=4, ensure_ascii=False)
        try:
            shutil.rmtree(testcase_cfg[target_name][path_name])
        except Exception as e:
            return ({'status': 'success', 'warning': f'已标记删除，但测试集文件删除失败：{str(e)}'}, 200)
    else:
        del testcase_cfg[target_name]
        with open_state(test_case_file, 'w', encoding='utf-8') as f:
            json.dump(testcase_cfg, f, indent=4, ensure_ascii=False)
        return ({'status': 'success', 'warning': f'{target_name} 测试集文件不存在，已直接从配置中删除该记录'}, 200)
    return ({'status': 'success'}, 200)

@app.route('/v1/update_testcase_in_use', methods=['POST'])
def update_testcase_in_use():
    user_req = request.get_json()
    test_case_file = COMMON_TESTCASE_PATH
    if 'is_field' in user_req.keys():
        if user_req['is_field'] == 2 or user_req['is_field'] == '2':
            test_case_file = FILED_TESTCASE_PATH
        elif user_req['is_field'] == 3 or user_req['is_field'] == '3':
            test_case_file = DEV_TESTCASE_PATH
    if not user_req.get('dataset_id'):
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    encodings = get_encoding(test_case_file)
    with open_state(test_case_file, 'r', encoding=encodings if encodings else 'UTF-8') as f:
        testcase_cfg = json.load(f)
    if user_req['dataset_id'] not in testcase_cfg.keys():
        return ({'err_info': f"{user_req['dataset_id']} is not exist"}, PARAM_ERR)
    in_use = user_req.get('in_use')
    if not isinstance(in_use, bool):
        return ({'err_info': 'PARAM_ERR, in_use must be bool'}, PARAM_ERR)
    testcase_cfg[user_req['dataset_id']]['in_use'] = in_use
    with open_state(test_case_file, 'w', encoding='utf-8') as f:
        json.dump(testcase_cfg, f, indent=4, ensure_ascii=False)
    return ({'status': 'success', 'in_use': in_use}, 200)

def get_generate_config(cfg_list):
    res = {}
    for cfg in cfg_list:
        res[cfg['key']] = cfg['value']
    return res

def get_limit(user_limit):
    if isinstance(user_limit, int) and user_limit > 0:
        return user_limit
    if isinstance(user_limit, str):
        try:
            int_limit = int(user_limit)
            if int_limit > 0:
                return int_limit
        except:
            return None
    return None

def read_jsonl(file_path):
    data = []
    with open_state(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            data.append(json.loads(line))
    return data

def is_over_30_days(date_str: str, date_format: str='%Y-%m-%d'):
    if not date_str:
        return False
    if len(date_str) > 10:
        date_str = date_str[:10]
    input_date = datetime.strptime(date_str, date_format)
    current_time = datetime.now()
    delta = current_time - input_date
    return delta.days <= 30

def check_model_new(model_name, model_cfg):
    for model in model_cfg:
        if model_name.lower() == model['model_id'].lower():
            return is_over_30_days(model['info']['creation_date'])
    return False

def get_model_create_time(model_name, model_cfg):
    for model in model_cfg:
        if model_name.lower() == model['info']['model_name'].lower():
            return model['info']['creation_date']
    return 'xxxx-xx-xx'

def get_model_update_test_time(test_record_list):
    try:
        test_time_list = [i['test_time'] for i in test_record_list]
        time_format = '%Y-%m-%d %H:%M:%S'
        latest_time = max([datetime.strptime(time_str, time_format) for time_str in test_time_list])
        return latest_time.strftime('%Y-%m-%d')
    except:
        return 'xxxx-xx-xx'

def update_isnew(ret):
    update = {}
    model_cfg = get_model_info_list()
    for ruler in ret.keys():
        update[ruler] = {}
        for model in ret[ruler].keys():
            update[ruler][model] = {'is_new': check_model_new(model, model_cfg), 'result': ret[ruler][model], 'publisher': get_publisher(model), 'creation_date': get_model_create_time(model, model_cfg), 'update_date': get_model_update_test_time(ret[ruler][model])}
    return update

@app.route('/v1/get_current_full_res', methods=['GET'])
def get_current_full_res():
    with open_state(LLM_RULER_1_RESULT, 'r', encoding='utf-8') as file:
        ret_ruler1 = json.load(file)
    with open_state(LLM_RULER_2_RESULT, 'r', encoding='utf-8') as file:
        ret_ruler2 = json.load(file)
    ret = {'ruler1': ret_ruler1, 'ruler2': ret_ruler2}
    update_ret = update_isnew(ret)
    return (jsonify(update_ret), 200)

@app.route('/v1/get_current_multi_full_res', methods=['GET'])
def get_current_multi_full_res():
    with open_state(MULTI_RULER_1_RESULT, 'r', encoding='utf-8') as file:
        ret_ruler1 = json.load(file)
    with open_state(MULTI_RULER_2_RESULT, 'r', encoding='utf-8') as file:
        ret_ruler2 = json.load(file)
    ret = {'ruler1': ret_ruler1, 'ruler2': ret_ruler2}
    update_ret = update_isnew(ret)
    return (jsonify(update_ret), 200)

@app.route('/v1/get_model_info', methods=['GET'])
def get_model_info():
    model_cfg = get_model_info_list()
    return (jsonify(model_cfg), 200)

@app.route('/v1/get_testcase_info', methods=['GET'])
def get_testcase_info():
    is_field = request.args.get('is_field', '')
    test_case_file = COMMON_TESTCASE_PATH
    if is_field == 2 or is_field == '2':
        test_case_file = FILED_TESTCASE_PATH
    elif is_field == 3 or is_field == '3':
        test_case_file = DEV_TESTCASE_PATH
    encodings = get_encoding(test_case_file)
    if encodings is not None:
        with open_state(test_case_file, 'r', encoding=encodings) as f:
            testcase = {key: value for key, value in json.load(f).items() if value.get('status') == 1}
    else:
        testcase = {}
    return (jsonify(testcase), 200)

@app.route('/v1/register_special_model', methods=['POST'])
def register_special_model():
    user_req = request.get_json()
    encodings = get_encoding(SPECIAL_MODEL_LIST_PATH)
    if encodings is not None:
        with open_state(SPECIAL_MODEL_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    ids = set((d['ID'] for d in info if isinstance(d['ID'], int)))
    new_id = 1
    if ids:
        sorted_ids = sorted(ids)
        for current_id in sorted_ids:
            if current_id == new_id:
                new_id += 1
            elif current_id > new_id:
                break
    user_req['ID'] = new_id
    user_req['edit_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    info.append(user_req)
    json_str = json.dumps(info, ensure_ascii=False, indent=4)
    with open_state(SPECIAL_MODEL_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(info), 200)

@app.route('/v1/get_special_model_info', methods=['GET'])
def get_special_model_info():
    encodings = get_encoding(SPECIAL_MODEL_LIST_PATH)
    if encodings is not None:
        with open_state(SPECIAL_MODEL_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    return (jsonify(info), 200)

@app.route('/v1/delete_special_model_info', methods=['POST'])
def delete_special_model_info():
    user_req = request.get_json()
    encodings = get_encoding(SPECIAL_MODEL_LIST_PATH)
    if encodings is not None:
        with open_state(SPECIAL_MODEL_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    new_info = [d for d in info if d.get('ID') not in user_req]
    json_str = json.dumps(new_info, ensure_ascii=False, indent=4)
    with open_state(SPECIAL_MODEL_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(new_info), 200)

@app.route('/v1/modify_special_model_info', methods=['POST'])
def modify_special_model_info():
    user_req = request.get_json()
    encodings = get_encoding(SPECIAL_MODEL_LIST_PATH)
    if encodings is not None:
        with open_state(SPECIAL_MODEL_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    if user_req['ID'] not in [d.get('ID') for d in info]:
        return ({'err_info': 'MODEL_NOT_EXIST'}, MODEL_NOT_EXIST)
    for idx in range(len(info)):
        if info[idx]['ID'] == user_req['ID']:
            info[idx] = user_req
            info[idx]['edit_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            break
    json_str = json.dumps(info, ensure_ascii=False, indent=4)
    with open_state(SPECIAL_MODEL_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(info), 200)

@app.route('/v1/chat', methods=['POST'])
def chat():
    try:
        user_req = request.get_json()
        model_path = user_req['model']
        req_cfg = None
        if 'config' in user_req:
            req_cfg = user_req['config']
        model_config = get_one_model_config(model_path)
        if not model_config:
            return ({'errType': f'Model ({model_path}) not registered'}, 400)
        query = [user_req['query']]
        model_resp = get_response_chat(model_config, [{'role': 'user', 'content': query}], req_cfg)
        answer = model_resp
        think = ''
        if model_config['config']['filter']['tail']:
            answer = model_resp.split(model_config['config']['filter']['tail'])[-1]
            think = model_resp.split(model_config['config']['filter']['tail'])[0].split(model_config['config']['filter']['head'])[-1]
        res = {'thinking': think, 'result': answer}
    except Exception as e:
        print(e)
        res = {}
    return (jsonify(res), 200)

def is_ip_address(host):
    ipv4_pattern = re.compile('^(\\d{1,3}\\.){3}\\d{1,3}$')
    if ipv4_pattern.match(host):
        parts = host.split('.')
        return all((0 <= int(part) <= 255 for part in parts))
    ipv6_pattern = re.compile('^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::|^::1|^([0-9a-fA-F]{1,4})?::')
    if ipv6_pattern.match(host):
        return True
    return False

def classify_url(url):
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if is_ip_address(host):
            return True
        else:
            return False
    except Exception as e:
        return False
proxy_url = ''
proxies = {}
transport = httpx.HTTPTransport(retries=3, verify=True)
http_client = httpx.Client(transport=transport, timeout=10)

def self_deploy_model_stream_chat(url, payload, headers):
    with requests.post(url, json=payload, headers=headers, stream=True) as r:
        if r.status_code != 200:
            yield f"data: {json.dumps({'error': f'query model failed: {r.status_code} {r.text}'})}\n\n"
            return
        if_think = False
        for line in r.iter_lines():
            if line:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    data = line[6:].strip()
                else:
                    data = line
                if data == '[DONE]':
                    yield 'data: [DONE]\n\n'
                    break
                try:
                    chunk = json.loads(data)
                    if 'choices' in chunk and len(chunk['choices']) > 0:
                        content = chunk['choices'][0].get('delta', {}).get('content', '')
                        if content:
                            if if_think:
                                if_think = False
                                yield f'data: </think>\n\n'
                            yield f'data: {content}\n\n'
                        reasoning = chunk['choices'][0].get('delta', {}).get('reasoning', '')
                        if not reasoning:
                            reasoning = chunk['choices'][0].get('delta', {}).get('reasoning_content', '')
                        if reasoning:
                            if not if_think:
                                if_think = True
                                yield f'data: <think>\n\n'
                            yield f'data: {reasoning}\n\n'
                except json.JSONDecodeError:
                    continue

def yunai_stream_chat(query, url, api_key, model_name, method='generateContent'):
    payload = {'contents': [{'role': 'user', 'parts': [{'text': query}]}], 'generationConfig': {'temperature': 1, 'topP': 1, 'thinkingConfig': {'includeThoughts': True, 'thinkingBudget': 26240}}}
    headers = {'Content-Type': 'application/json'}
    full_url = f'{url}{model_name}:{method}?key={api_key}&alt=sse'
    try:
        with requests.post(full_url, json=payload, headers=headers, proxies=proxies, verify=True) as r:
            if r.status_code != 200:
                error_msg = r.text
                try:
                    error_msg = json.loads(error_msg)['error']['message']
                    error_msg = error_msg.encode('latin1').decode('utf-8')
                except:
                    pass
                yield f'data: Failed to connect: {r.status_code}\n\n'
                yield f'data: Error Msg: {error_msg}\n\n'
                raise ConnectionError
            for line in r.iter_lines():
                if line:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        line = line[6:]
                    try:
                        chunk = json.loads(line)
                        if 'candidates' in chunk and len(chunk['candidates']) > 0:
                            delta = chunk['candidates'][0]
                            if 'content' in delta:
                                content = delta['content']['parts'][0]['text']
                                all_content = content.split('\n')
                                next_line_is_think = False
                                in_answer_phase = False
                                for iter_content in all_content:
                                    if len(iter_content) == 0 or iter_content in ['\n', '\r']:
                                        continue
                                    if in_answer_phase:
                                        yield f'data: <answer>{iter_content}</answer>\n\n'
                                    elif iter_content.startswith('**'):
                                        yield f'data: <think>{iter_content}</think>\n\n'
                                        next_line_is_think = True
                                    elif next_line_is_think:
                                        yield f'data: <think>{iter_content}</think>\n\n'
                                        next_line_is_think = False
                                    else:
                                        yield f'data: <answer>{iter_content}</answer>\n\n'
                                        in_answer_phase = True
                    except json.JSONDecodeError:
                        if line == '[DONE]':
                            break
            yield 'data: [DONE]\n\n'
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f'Request failed')

def huggingface_stream_chat(url, headers, query, model_name):

    def make_query(payload):
        response = requests.post(url, headers=headers, json=payload, proxies=proxies, verify=True)
        for line in response.iter_lines():
            if not line.startswith(b'data:'):
                continue
            if line.strip() == b'data: [DONE]':
                return
            yield json.loads(line.decode('utf-8').lstrip('data:').rstrip('/n'))
    chunks = make_query({'messages': [{'role': 'user', 'content': query}], 'model': model_name, 'stream': True})
    for chunk in chunks:
        if 'choices' in chunk and len(chunk['choices']) > 0 and ('content' in chunk['choices'][0]['delta']):
            yield f"data: {chunk['choices'][0]['delta']['content']}\n\n"

def openai_stream_chat(url, config_available, payload):
    if url.endswith('/chat/completions'):
        url = url.replace('/chat/completions', '')
    client = OpenAI(api_key=config_available['api_key'], base_url=url, http_client=http_client)
    standard_params = {'model': payload['model'], 'messages': payload['messages'], 'stream': payload['stream'], 'temperature': payload.get('temperature', 0.5)}
    extra = {}
    if 'enable_thinking' in payload:
        extra['enable_thinking'] = payload['enable_thinking']
    response = client.chat.completions.create(**standard_params, extra_body=extra)
    if_think = False
    for chunk in response:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            if content is not None:
                if if_think:
                    if_think = False
                    yield f'data: </think>\n\n'
                yield f'data: {content}\n\n'
        if chunk.choices[0].delta.model_extra:
            content = chunk.choices[0].delta.model_extra['reasoning_content']
            if content is not None:
                if not if_think:
                    if_think = True
                    yield f'data: <think>\n\n'
                yield f'data: {content}\n\n'
        if chunk.choices[0].finish_reason == 'stop':
            yield 'data: [DONE]\n\n'
            break

def generate_llm_payload(model_name, isThink, query, textMessages):
    payload = {'model': model_name, 'stream': True}
    if isThink:
        payload['enable_thinking'] = True
        payload['chat_template_kwargs'] = {'thinking': True, 'enable_thinking': True, 'reasoning_effort': 'max'}
    elif re.match('^qwen3-\\d+b', model_name.lower()):
        query = f'{query}/no_think'
    else:
        payload['enable_thinking'] = False
        payload['chat_template_kwargs'] = {'thinking': False, 'enable_thinking': False}
    textMessages.append({'role': 'user', 'content': query})
    payload['messages'] = textMessages
    return payload

def generate_self_deploy_payload(file_path, model_name, query, textMessages, isThink):
    if file_path:
        print('file_path-:', file_path)
        if is_image_file(file_path):
            file_str = image_to_base64_url(file_path)
            if len(file_str) == 0:
                raise RuntimeError(f"data: {json.dumps({'error': f'image format is err.'})}\n\n")
            payload = {'model': model_name, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': query}, {'type': 'image_url', 'image_url': {'url': file_str}}]}], 'stream': True}
            print('is image file')
        elif is_audio_file(file_path):
            file_str = audio_to_base64_url(file_path)
            if len(file_str) == 0:
                raise RuntimeError(f"data: {json.dumps({'error': f'audio format is err.'})}\n\n")
            payload = {'model': model_name, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': query}, {'type': 'audio_url', 'audio_url': {'url': file_str}}]}], 'stream': True}
            print('is audio file')
        elif is_video_file(file_path):
            file_str = video_to_base64_url(file_path)
            if len(file_str) == 0:
                raise RuntimeError(f"data: {json.dumps({'error': f'video format is err.'})}\n\n")
            payload = {'model': model_name, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': query}, {'type': 'video_url', 'video_url': {'url': file_str}}]}], 'stream': True}
            print('is video file')
        else:
            payload = generate_llm_payload(model_name, isThink, query, textMessages)
    else:
        payload = generate_llm_payload(model_name, isThink, query, textMessages)
    return payload

def generate_self_deploy_headers(config_available):
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    if config_available['api_key'] and config_available['api_key'] != 'EMPTY':
        headers['Authorization'] = f"Bearer {config_available['api_key']}"
    return headers

def generate_stream(model, query, file_path, textMessages, isThink):
    model_cfg = get_model_info_list()
    target_cfg = None
    for cfg in model_cfg:
        if cfg['model_id'] == model:
            target_cfg = cfg
            break
    if not target_cfg:
        yield f"data: {json.dumps({'error': f'model is not registered.'})}\n\n"
    config_available_list = target_cfg['config']['api_params_available']
    if len(config_available_list) == 0:
        yield f"data: {json.dumps({'error': f'model is not available.'})}\n\n"
    config_available = random.choice(config_available_list)
    url = config_available['endpoint']
    is_ip_port = classify_url(url)
    model_name = target_cfg['info']['model_name']
    payload = generate_self_deploy_payload(file_path, model_name, query, textMessages, isThink)
    headers = generate_self_deploy_headers(config_available)
    try:
        if is_ip_port or 'namo-execute-access.rnd.huawei.com' in url:
            yield from self_deploy_model_stream_chat(url, payload, headers)
        elif ('feiai.chat' in url or 'yunai.chat' in url) and 'gemini' in model_name:
            yield from yunai_stream_chat(query, url, config_available['api_key'], model_name)
        elif 'router.huggingface' in url:
            yield from huggingface_stream_chat(url, headers, query, model)
        else:
            yield from openai_stream_chat(url, config_available, payload)
    except Exception as e:
        print('exception query abnormal')
        yield f"data: {json.dumps({'error': f'query abnormal: {str(e)}'})}\n\n"

def _wrapped_generate_stream(data):
    chat_id = data.get('chat_id', '').strip()
    user_id = data.get('user_id', 'admin').strip()
    config = data.get('config', '')
    model_id = data.get('model', '').strip()
    query = data.get('query', '').strip()
    file_path = data.get('file_path', '').strip()
    isDeepResearch = data.get('isDeepResearch', False)
    deepResearchType = data.get('deepResearchType', 'fast')
    isThink = data.get('isThink', False)
    user_log_path = os.path.join(LOG_PATH, f'{user_id}.txt')
    full_response = ''
    research_content = ''
    deep_search_result = ''
    if isDeepResearch:
        task_id = str(int(time.time() * 1000))
        yield f'data: <deepResearch>\n\n'
        payload = {'task_id': task_id, 'question': query, 'summary': False if deepResearchType == 'fast' else True}
        try:
            generator = deep_search_stream(DEEP_RESEARCH_SERVER, payload, 2400)
            for chunk in generator:
                yield (chunk + '\n\n')
                if chunk.startswith('data: '):
                    json_str = chunk[6:]
                    try:
                        chunk_data = json.loads(json_str)
                        if 'error' in chunk_data:
                            return (jsonify({'error': f"深度研究服务错误：{chunk_data['error']}"}), 500)
                        if 'text' in chunk_data:
                            deep_search_result += chunk_data['text']
                    except json.JSONDecodeError:
                        deep_search_result += json_str
        except Exception as e:
            return (jsonify({'error': f'深度研究请求失败：{str(e)}'}), 500)
        yield f'data: </deepResearch>\n\n'
        start_tag = '<research_report>'
        end_tag = '</research_report>'
        start_idx = deep_search_result.find(start_tag)
        end_idx = deep_search_result.find(end_tag)
        if start_idx != -1 and end_idx != -1 and (start_idx < end_idx):
            content_start = start_idx + len(start_tag)
            research_content = deep_search_result[content_start:end_idx].strip()
            fullQuery = f"{data['query']}\n回答请参考：{research_content}"
        else:
            research_content = ''
            fullQuery = f"{data['query']}\n"
        print(f'更新后的查询：{fullQuery}')
    else:
        fullQuery = data['query']
    if model_id in OUT_WHITE_LIST:
        current_date = datetime.utcnow().strftime('%Y-%m-%d')
        count = 0
        with log_lock:
            if state_exists(user_log_path):
                try:
                    with open_state(user_log_path, 'a', encoding='utf-8') as log_file:
                        for line in log_file:
                            try:
                                entry = json.loads(line)
                                log_timestamp = entry.get('timestamp', 0)
                                log_date = datetime.utcfromtimestamp(log_timestamp / 1000).strftime('%Y-%m-%d')
                                if entry.get('user_id') == user_id and entry.get('model_id') == model_id and (log_date == current_date):
                                    count += 1
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    print(f'日志读取失败: {str(e)}')
        print(f'count: {count}')
        if count >= 30:
            error_msg = json.dumps({'error': '本日使用次数已达上限'}, ensure_ascii=False)
            yield f'data: {error_msg}\n\n'
            yield 'data: [DONE]\n\n'
            return
    chatType = 'text'
    if file_path:
        if is_image_file(file_path):
            chatType = 'image'
        elif is_audio_file(file_path):
            chatType = 'audio'
        elif is_video_file(file_path):
            chatType = 'video'
    get_log_params = {'user_id': user_id, 'type': chatType, 'chat_id': chat_id, 'limit': 5, 'active': True}
    logJSON = _get_log_data_internal(get_log_params)
    logData = logJSON.get('data', [])
    messages = []
    for log in logData:
        messages.append({'role': 'user', 'content': log['query']})
        messages.append({'role': 'assistant', 'content': log['response']})
    response_parts = []
    start_time = time.time() * 1000
    try:
        for chunk in generate_stream(model_id, fullQuery, file_path, messages, isThink):
            yield chunk
            if not chunk.startswith('data: ') or not chunk.endswith('\n\n'):
                continue
            payload = chunk[6:-2]
            print(f'{payload}')
            if payload == '[DONE]':
                continue
            try:
                data_obj = json.loads(payload)
                if isinstance(data_obj, dict) and 'error' in data_obj:
                    response_parts.append(json.dumps(data_obj, ensure_ascii=False))
                elif isinstance(data_obj, dict) and 'content' in data_obj:
                    content_val = data_obj['content']
                    response_parts.append(str(content_val) if not isinstance(content_val, str) else content_val)
                else:
                    response_parts.append(json.dumps(data_obj, ensure_ascii=False))
            except JSONDecodeError:
                response_parts.append(payload)
    except Exception as e:
        error_msg = json.dumps({'error': f'生成流异常: {str(e)}'})
        yield f'data: {error_msg}\n\n'
        response_parts.append(error_msg)
    finally:
        end_time = time.time() * 1000
        duration_ms = round(end_time - start_time, 2)
        generated_response = ''.join(response_parts)
        if isDeepResearch:
            full_response = f'<deepResearch>{research_content}</deepResearch>{generated_response}'
        else:
            full_response = generated_response
        log_entry = {'chat_id': chat_id, 'user_id': user_id, 'model_id': model_id, 'config': {key: value for key, value in config.items() if key != 'messages'}, 'type': chatType, 'query': query, 'file_path': file_path, 'timestamp': start_time, 'end_time': end_time, 'duration_ms': duration_ms, 'response': f'{full_response}', 'active': True}
        with log_lock:
            try:
                os.makedirs(os.path.dirname(user_log_path), exist_ok=True)
                with open_state(user_log_path, 'a', encoding='utf-8') as log_file:
                    log_file.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            except Exception as e:
                print(f'日志写入失败: {str(e)}')

@app.route('/v1/stream_chat', methods=['POST'])
def stream_chat():
    data = request.get_json()
    query = data.get('query', '').strip()
    file_path = data.get('file_path', '').strip()
    if not query:
        return (jsonify({'error': '缺少 query 参数'}), 400)
    return Response(_wrapped_generate_stream(data), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})

@app.route('/v1/download/file', methods=['GET'])
def download_file():
    req_filepath = request.args.get('filepath')
    local_file_path = os.path.join(os.getcwd(), req_filepath)
    try:
        return send_file(local_file_path, as_attachment=True)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/download/dataset_zip', methods=['GET'])
def download_dataset_zip():
    filepaths = request.args.getlist('filepaths') or request.args.getlist('filepaths[]')
    zip_name = request.args.get('zip_name', 'dataset')
    if not filepaths:
        return (jsonify({'error': '缺少filepaths参数'}), 400)
    try:
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filepath in filepaths:
                full_path = os.path.join(os.getcwd(), filepath)
                if state_isfile(full_path):
                    arcname = os.path.basename(filepath)
                    zf.write(full_path, arcname)
                elif os.path.isdir(full_path):
                    for root, dirs, files in os.walk(full_path):
                        for file in files:
                            abs_file = os.path.join(root, file)
                            rel_path = os.path.relpath(abs_file, os.path.dirname(full_path))
                            zf.write(abs_file, rel_path)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f'{zip_name}.zip', mimetype='application/zip')
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/upload/file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return (jsonify({'error': '没有找到文件'}), 400)
    file = request.files['file']
    if not file:
        return (jsonify({'error': '没有选择文件'}), 400)
    try:
        uuid_val = str(uuid.uuid4())
        filename = file.filename
        upload_dir = os.path.join(UPLOAD_FOLDERS, uuid_val)
        if not state_exists(upload_dir):
            os.makedirs(upload_dir)
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        return (jsonify({'message': '文件上传成功', 'filename': os.path.join(uuid_val, filename)}), 200)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/delete/folder', methods=['POST', 'OPTIONS'])
def delete_folder():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'POST'
        return response
    try:
        data = request.get_json()
        if not data or 'uuid_val' not in data:
            return (jsonify({'error': '缺少uuid_val参数'}), 400)
        uuid_val = data['uuid_val']
        folder_path = os.path.join(UPLOAD_FOLDERS, uuid_val)
        real_path = os.path.realpath(folder_path)
        base_path = os.path.realpath(UPLOAD_FOLDERS)
        if not real_path.startswith(base_path + os.sep):
            return (jsonify({'error': '非法路径访问'}), 403)
        if not state_exists(folder_path):
            return (jsonify({'error': '文件夹不存在'}), 404)
        shutil.rmtree(folder_path)
        return (jsonify({'message': f'文件夹 {uuid_val} 删除成功'}), 200)
    except Exception as e:
        return (jsonify({'error': f'删除失败: {str(e)}'}), 500)

@app.route('/v1/edit/file', methods=['POST'])
def edit_file():
    if 'uuid_val' not in request.form:
        return (jsonify({'error': '缺少路径标识符'}), 400)
    if 'file' not in request.files:
        return (jsonify({'error': '没有找到文件'}), 400)
    uuid_val = request.form['uuid_val']
    new_file = request.files['file']
    if not new_file or new_file.filename == '':
        return (jsonify({'error': '未选择有效文件'}), 400)
    try:
        target_dir = os.path.join(UPLOAD_FOLDERS, uuid_val)
        if not os.path.isdir(target_dir):
            return (jsonify({'error': '指定路径不存在'}), 404)
        files = [f for f in os.listdir(target_dir) if state_isfile(os.path.join(target_dir, f))]
        if not files:
            return (jsonify({'error': '目标目录为空'}), 404)
        first_file = sorted(files)[0]
        target_path = os.path.join(target_dir, first_file)
        os.remove(target_path)
        new_file.save(target_path)
        return (jsonify({'message': '文件替换成功', 'filename': os.path.join(uuid_val, first_file)}), 200)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/retrieve/files', methods=['POST'])
def retrieve_files():
    data = request.get_json()
    if not data or 'uuid_val' not in data:
        return (jsonify({'错误': '缺少uuid_val参数'}), 400)
    uuid_val = data['uuid_val']
    target_dir = os.path.join(UPLOAD_FOLDERS, uuid_val)
    if not state_exists(target_dir):
        return (jsonify({'错误': '文件夹不存在'}), 404)
    if not os.path.isdir(target_dir):
        return (jsonify({'错误': '路径不是有效文件夹'}), 400)
    file_data = []
    try:
        for filename in os.listdir(target_dir):
            file_path = os.path.join(target_dir, filename)
            if os.path.isdir(file_path):
                continue
            with open_state(file_path, 'rb') as f:
                file_content = f.read()
                base64_encoded = base64.b64encode(file_content).decode('utf-8')
                file_data.append({'filename': filename, 'data': base64_encoded})
        return (jsonify({'fileList': file_data}), 200)
    except Exception as e:
        return (jsonify({'错误': f'文件读取失败: {str(e)}'}), 500)

@app.route('/v1/download_models_file', methods=['GET'])
def download_models_file():
    local_file_path = os.path.join(UPLOAD_FOLDERS, AI_MODELS_SELECT_FILE_NAME)
    if not state_exists(local_file_path) or not state_isfile(local_file_path):
        return (jsonify({'error': '没有找到文件'}), 400)
    try:
        return send_file(local_file_path, as_attachment=True)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/upload_models_file', methods=['POST'])
def upload_models_file():
    if 'file' not in request.files:
        return (jsonify({'error': '没有找到文件'}), 400)
    file = request.files['file']
    if not file or file.filename != AI_MODELS_SELECT_FILE_NAME:
        return (jsonify({'error': '没有找到模型列表文件'}), 400)
    try:
        file_path = os.path.join(UPLOAD_FOLDERS, AI_MODELS_SELECT_FILE_NAME)
        file.save(file_path)
        return (jsonify({'message': '文件上传成功', 'filename': os.path.join(UPLOAD_FOLDERS, AI_MODELS_SELECT_FILE_NAME)}), 200)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/get_models_file_data', methods=['POST'])
def get_models_file_data():
    try:
        file_path = os.path.join(UPLOAD_FOLDERS, AI_MODELS_SELECT_FILE_NAME)
        if not state_exists(file_path) or not state_isfile(file_path):
            return (jsonify({'error': '没有找到文件'}), 400)
        user_req = request.get_json()
        file_sheet = user_req['file_sheet'] if 'file_sheet' in user_req else AI_MODELS_SELECT_FILE_SHEETS[0]
        print(f'file_sheet: {file_sheet}')
        if file_sheet not in AI_MODELS_SELECT_FILE_SHEETS:
            return (jsonify({'error': '文件sheet名称不正确'}), 400)
        df = pd.read_excel(file_path, sheet_name=file_sheet, engine='openpyxl')
        data = df.replace([np.nan, pd.NA, ''], None).astype(object).to_dict(orient='records')
        return (jsonify({'data': data}), 200)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)
DOWNLOAD_VIEW_COUNT_FILE_PATH = 'backend/config/dataset_download_view_count.json'

def update_dataset_counts(dataset, is_field, count_type):
    from state_storage import increment_dataset_counter
    increment_dataset_counter(DOWNLOAD_VIEW_COUNT_FILE_PATH,is_field,dataset,count_type)

@app.route('/v1/get_dataset_file_path', methods=['GET'])
def get_dataset_file_path():
    local_path = request.args.get('local_path', '')
    is_field = request.args.get('is_field', '')
    dataset = request.args.get('dataset', '')
    if local_path == '' or dataset == '' or is_field == '':
        return (jsonify({'error': 'param local_path, is_field, dataset must be not null'}), 400)
    path = os.path.join(local_path, '*')
    all_file = glob.glob(path)
    files = []
    try:
        if all_file:
            for file in all_file:
                files.append(file)
            update_dataset_counts(dataset, is_field, 'download_count')
            return files
        else:
            return (jsonify({'error': '没有可下载的文件'}), 400)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

def convert_value_for_json(v):
    """将无法被 json 序列化的类型转为字符串"""
    if isinstance(v, (dt.time, dt.date, dt.datetime, pd.Timestamp)):
        return str(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        v = float(v)
        if v != v or v == float('inf') or v == float('-inf'):
            return None
        return v
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, bytes):
        return v.decode('utf-8', errors='replace')
    if isinstance(v, float) and (v != v or v == float('inf') or v == float('-inf')):
        return None
    return v

def convert_records_for_json(records):
    """递归转换 records 中所有不可序列化的值"""
    if isinstance(records, list):
        return [convert_records_for_json(r) for r in records]
    if isinstance(records, dict):
        return {k: convert_records_for_json(v) for k, v in records.items()}
    return convert_value_for_json(records)

@app.route('/v1/get_dataset_file_data', methods=['GET'])
def get_dataset_file_data():
    local_path = request.args.get('local_path', '')
    is_field = request.args.get('is_field', '')
    dataset = request.args.get('dataset', '')
    file_path = request.args.get('file_path', '')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 100, type=int)
    if local_path == '' or dataset == '' or is_field == '':
        return (jsonify({'error': 'param local_path, is_field, dataset must be not null'}), 400)
    if file_path:
        file_path = file_path.replace('\\', '/')
        all_file = [file_path]
    else:
        path = os.path.join(local_path, '*')
        all_file = glob.glob(path)
    result = {'excel_files': [], 'txt_files': [], 'json_files': [], 'other_files': [], 'directories': []}
    try:
        if all_file:
            for file_path in all_file:
                file_name = os.path.basename(file_path)
                if os.path.isdir(file_path):
                    try:
                        children = os.listdir(file_path)
                        result['directories'].append({'file_name': file_name, 'children': children, 'child_count': len(children)})
                    except Exception as e:
                        result['directories'].append({'file_name': file_name, 'error': str(e)})
                    continue
                file_extension = os.path.splitext(file_name)[1].lower()
                if file_extension == '.xlsx':
                    try:
                        xls = pd.ExcelFile(file_path)
                        sheet_names = xls.sheet_names
                        sheets = []
                        for sheet_name in sheet_names:
                            df_header = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0)
                            columns = df_header.columns.tolist()
                            df_count = pd.read_excel(file_path, sheet_name=sheet_name, usecols=[0])
                            total_rows = len(df_count)
                            skip_rows = (page - 1) * page_size
                            df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=range(1, skip_rows + 1) if skip_rows > 0 else None, nrows=page_size, header=0)
                            if len(df.columns) == len(columns):
                                df.columns = columns
                            sheets.append({'sheet_name': sheet_name, 'data': convert_records_for_json(df.to_dict('records')), 'row_count': len(df), 'total_rows': total_rows, 'column_order': columns})
                        result['excel_files'].append({'file_name': file_name, 'sheets': sheets, 'sheet_names': sheet_names})
                    except Exception as e:
                        result['excel_files'].append({'file_name': file_name, 'error': str(e)})
                elif file_extension == '.txt':
                    try:
                        with open_state(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        lines = content.split('\n')
                        lines = [line for line in lines if line.strip()]
                        result['txt_files'].append({'file_name': file_name, 'content': content, 'lines': lines, 'line_count': len(lines)})
                    except Exception as e:
                        result['txt_files'].append({'file_name': file_name, 'error': str(e)})
                elif file_extension in ('.json', '.jsonl'):
                    try:
                        all_rows = []
                        if file_extension == '.json':
                            with open_state(file_path, 'r', encoding='utf-8') as f:
                                parsed = json.load(f)
                            if isinstance(parsed, list):
                                all_rows = parsed
                            elif isinstance(parsed, dict):
                                all_rows = [parsed]
                            else:
                                all_rows = [{'value': str(parsed)}]
                        else:
                            with open_state(file_path, 'r', encoding='utf-8') as f:
                                for line in f:
                                    line = line.strip()
                                    if line:
                                        all_rows.append(json.loads(line))
                        columns = []
                        seen = set()
                        for row in all_rows:
                            if isinstance(row, dict):
                                for k in row:
                                    if k not in seen:
                                        columns.append(k)
                                        seen.add(k)
                        total_rows = len(all_rows)
                        skip = (page - 1) * page_size
                        page_data = all_rows[skip:skip + page_size]

                        def ensure_dict(r):
                            if isinstance(r, dict):
                                return r
                            return {'__value__': str(r)}
                        page_data = [ensure_dict(r) for r in page_data]
                        for row in page_data:
                            for col in columns:
                                if col not in row:
                                    row[col] = None
                        result.setdefault('json_files', []).append({'file_name': file_name, 'data': convert_records_for_json(page_data), 'columns': columns, 'total_rows': total_rows, 'row_count': len(page_data), 'page': page, 'page_size': page_size})
                    except Exception as e:
                        result.setdefault('json_files', []).append({'file_name': file_name, 'error': str(e)})
                else:
                    result['other_files'].append({'file_name': file_name, 'file_extension': file_extension if file_extension else '(无后缀)'})
            if not result['excel_files'] and (not result['txt_files']) and (not result.get('json_files')) and (not result['other_files']) and (not result['directories']):
                return (jsonify({'error': '没有找到可读取的文件'}), 400)
            return jsonify(result)
        else:
            return (jsonify({'error': '没有可读取的文件'}), 400)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/get_dataset_tree', methods=['GET'])
def get_dataset_tree():
    """递归扫描目录树，返回最多3层的文件结构，不含文件数据内容"""
    local_path = request.args.get('local_path', '')
    is_field = request.args.get('is_field', '')
    dataset = request.args.get('dataset', '')
    if local_path == '' or dataset == '' or is_field == '':
        return (jsonify({'error': 'param local_path, is_field, dataset must be not null'}), 400)
    max_depth = 3

    def scan_dir(dir_path, current_depth):
        if current_depth > max_depth:
            return []
        entries = []
        try:
            names = sorted(os.listdir(dir_path))
        except Exception as e:
            return [{'file_name': os.path.basename(dir_path), 'error': str(e), '_type': 'directory'}]
        for name in names:
            full = os.path.join(dir_path, name)
            if os.path.isdir(full):
                children = scan_dir(full, current_depth + 1)
                entries.append({'file_name': name, '_type': 'directory', 'children': children, 'child_count': len(children)})
            else:
                ext = os.path.splitext(name)[1].lower()
                if ext == '.xlsx':
                    ftype = 'excel'
                elif ext == '.txt':
                    ftype = 'txt'
                elif ext in ('.json', '.jsonl'):
                    ftype = 'json'
                else:
                    ftype = 'other'
                entry = {'file_name': name, '_type': ftype}
                if ftype == 'other':
                    entry['file_extension'] = ext if ext else '(无后缀)'
                entries.append(entry)
        return entries
    try:
        if not os.path.isdir(local_path):
            return (jsonify({'error': '目录不存在: ' + local_path}), 400)
        tree = scan_dir(local_path, 1)
        return jsonify({'tree': tree, 'total': len(tree)})
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/dataset/counts', methods=['GET'])
def get_dataset_views_dls_count():
    try:
        with open_state(DOWNLOAD_VIEW_COUNT_FILE_PATH, 'r', encoding='utf-8') as f:
            counts = json.load(f)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)
    return (jsonify(counts), 200)

@app.route('/v1/dataset/update/view', methods=['POST'])
def update_view_count():
    user_req = request.get_json()
    is_field = user_req['is_field']
    dataset = user_req['dataset']
    if dataset is None or is_field is None:
        return (jsonify({'error': 'param is_field, dataset must be not null'}), 400)
    try:
        update_dataset_counts(dataset, is_field, 'view_count')
        return (jsonify({'message': '成功'}), 200)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/get_eval_report', methods=['GET'])
def get_eval_report():
    encodings = get_encoding(EVAL_REPORT_LIST_PATH)
    if encodings is not None:
        with open_state(EVAL_REPORT_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    return (jsonify(info), 200)

@app.route('/v1/modify_eval_report', methods=['POST'])
def modify_eval_report():
    user_req = request.get_json()
    encodings = get_encoding(EVAL_REPORT_LIST_PATH)
    if encodings is not None:
        with open_state(EVAL_REPORT_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    if user_req['ID'] not in [d.get('ID') for d in info]:
        return ({'err_info': 'MODEL_NOT_EXIST'}, MODEL_NOT_EXIST)
    for idx in range(len(info)):
        if info[idx]['ID'] == user_req['ID']:
            info[idx] = user_req
            break
    json_str = json.dumps(info, ensure_ascii=False, indent=4)
    with open_state(EVAL_REPORT_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(info), 200)

@app.route('/v1/get_eval_model_list', methods=['GET'])
def get_eval_model_list():
    encodings = get_encoding(EVAL_MODEL_LIST_PATH)
    if encodings is not None:
        with open_state(EVAL_MODEL_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    return (jsonify(info), 200)

@app.route('/v1/download_huggingface_file', methods=['POST'])
def download_huggingface_file():
    """
    下载数据集接口，输入：
    ①下载类别，即模型--model 或 数据集--datasets
    ②下载仓库名称，要求格式：Anthropic/AnthropicInterviewer 或完整链接：https://huggingface.co/datasets/Anthropic/AnthropicInterviewer
    """
    user_req = request.get_json()
    download_type = user_req.get('type', 'datasets')
    download_dataset_name = user_req.get('dataset_name')
    download_tasks = get_hg_download_tasks()
    server_id = None
    current_task = None
    for key, task in download_tasks:
        if task['is_available']:
            server_id = key
            task['is_available'] = False
            task['task_type'] = download_type
            task['task_name'] = download_dataset_name
            set_hg_download_tasks(download_tasks)
            current_task = task
            break
    if not server_id:
        return (jsonify({'info': '当前没有可用的下载服务'}), 400)
    ip = HUGGINGFACE_DOWNLOAD_SERVER[server_id]['ip']
    port = HUGGINGFACE_DOWNLOAD_SERVER[server_id]['port']
    server_url = f'http://{ip}:{port}/v1/download_huggingface_file'

    def download_hg_file(dataset_name, server_url, server_id):
        payload = {'type': 'datasets', 'repo_base': dataset_name}
        resp = requests.request(method='POST', url=server_url, json=payload)
        all_tasks = get_hg_download_tasks()
        if server_id not in download_tasks:
            all_tasks[server_id] = {}
        all_tasks[server_id]['is_available'] = True
        all_tasks[server_id]['task_type'] = ''
        all_tasks[server_id]['task_name'] = ''
        set_hg_download_tasks(all_tasks)
        if resp.status_code == 200:
            dataset_info = {dataset_name: {'dataset_name': dataset_name, 'server_id': server_id, 'server_local_path': '', 'local_path': '', 'dataset_size': 0, 'file_list': [], 'is_open_source': True, 'establish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}
    thread = threading.Thread(target=download_hg_file, args=(download_dataset_name, server_url, server_id))
    thread.start()
    thread.join()
    return (jsonify({'info': '已启动下载，请前往数据集广场查看是否已完成'}), 200)

@app.route('/v1/modify_eval_model_list', methods=['POST'])
def modify_eval_model_list():
    user_req = request.get_json()
    encodings = get_encoding(EVAL_MODEL_LIST_PATH)
    if encodings is not None:
        with open_state(EVAL_MODEL_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    if user_req['ID'] not in [d.get('ID') for d in info]:
        return ({'err_info': 'MODEL_NOT_EXIST'}, MODEL_NOT_EXIST)
    for idx in range(len(info)):
        if info[idx]['ID'] == user_req['ID']:
            info[idx] = user_req
            break
    json_str = json.dumps(info, ensure_ascii=False, indent=4)
    with open_state(EVAL_MODEL_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(info), 200)

@app.route('/v1/image/view/<file_uuid>/<file_path>', methods=['GET'])
def image_view(file_uuid, file_path):
    if not file_uuid or not file_path:
        return (jsonify({'error': 'file_uuid or file_path is not exists'}), 400)
    if file_uuid in DATASET_MLLM_FILE_PATH.keys():
        file_path = file_path.replace('$', '/')
        print(f'image_view cur dir: {os.getcwd()}')
        file = os.path.join(DATASET_MLLM_FILE_PATH.get(file_uuid), file_path)
        print(f'image_view file: {file}')
        if not state_exists(file):
            return (jsonify({'error': 'MLLM图片不存在'}), 500)
        return send_file(file)
    else:
        encodings = get_encoding(FILED_TESTCASE_PATH)
        with open_state(FILED_TESTCASE_PATH, 'r', encoding=encodings) as f:
            field_testcases = json.load(f)
        if '儿童伴读' in field_testcases[file_uuid]['testcase_tags']:
            file_path = file_path.replace('$', '/')
            print(f'image_view cur dir: {os.getcwd()}')
            file = os.path.join(ELD_DATASET_PATH_BASE, file_uuid, file_path)
            print(f'image_view file: {file}')
            if not state_exists(file):
                return (jsonify({'error': 'MLLM图片不存在'}), 500)
            return send_file(file)
    file = os.path.join(UPLOAD_FOLDERS, file_uuid, file_path)
    if not state_exists(file):
        return (jsonify({'error': '图片不存在'}), 500)
    try:
        return send_from_directory(os.path.join(UPLOAD_FOLDERS, file_uuid), file_path)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'webm', 'ogg'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'ogg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_AUDIO_EXTENSIONS).union(ALLOWED_VIDEO_EXTENSIONS)

def is_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_IMAGE_EXTENSIONS

def is_audio_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_AUDIO_EXTENSIONS

def is_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_VIDEO_EXTENSIONS

def image_to_base64_url(filepath):
    with open_state(filepath, 'rb') as curFile:
        base64_encoded = base64.b64encode(curFile.read()).decode('utf-8')
    if filepath.rsplit('.', 1)[-1].lower() == 'png':
        return f'data:image/png;base64,{base64_encoded}'
    elif filepath.rsplit('.', 1)[-1].lower() == 'jpg' or filepath.rsplit('.', 1)[-1].lower() == 'jpeg':
        return f'data:image/jpeg;base64,{base64_encoded}'
    elif filepath.rsplit('.', 1)[-1].lower() == 'gif':
        return f'data:image/gif;base64,{base64_encoded}'
    else:
        return ''

def audio_to_base64_url(filepath):
    with open_state(filepath, 'rb') as curFile:
        base64_encoded = base64.b64encode(curFile.read()).decode('utf-8')
    if filepath.rsplit('.', 1)[-1].lower() == 'mp3':
        return f'data:audio/mpeg;base64,{base64_encoded}'
    elif filepath.rsplit('.', 1)[-1].lower() == 'wav':
        return f'data:audio/wav;base64,{base64_encoded}'
    elif filepath.rsplit('.', 1)[-1].lower() == 'webm':
        return f'data:audio/webm;base64,{base64_encoded}'
    elif filepath.rsplit('.', 1)[-1].lower() == 'ogg':
        return f'data:audio/ogg;base64,{base64_encoded}'
    else:
        return ''

def video_to_base64_url(filepath):
    with open_state(filepath, 'rb') as curFile:
        base64_encoded = base64.b64encode(curFile.read()).decode('utf-8')
    if filepath.rsplit('.', 1)[-1].lower() == 'mp4':
        return f'data:video/mp4;base64,{base64_encoded}'
    elif filepath.rsplit('.', 1)[-1].lower() == 'webm':
        return f'data:video/webm;base64,{base64_encoded}'
    elif filepath.rsplit('.', 1)[-1].lower() == 'ogg':
        return f'data:video/ogg;base64,{base64_encoded}'
    else:
        return ''

@app.route('/v1/chat/upload_file', methods=['POST'])
def upload_chat_file():
    if 'image' not in request.files and 'audio' not in request.files and ('video' not in request.files):
        return (jsonify({'error': 'No file part'}), 400)
    file = None
    if 'image' in request.files:
        file = request.files['image']
    elif 'audio' in request.files:
        file = request.files['audio']
    elif 'video' in request.files:
        file = request.files['video']
    if file.filename == '':
        return (jsonify({'error': 'No selected file'}), 400)
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f'{timestamp}_{filename}'
            filepath = os.path.join(UPLOAD_FOLDERS, unique_filename)
            file.save(filepath)
            return (jsonify({'message': 'File successfully uploaded and processed', 'filename': unique_filename, 'filepath': filepath}), 200)
        except Exception as e:
            return (jsonify({'error': str(e)}), 500)
    else:
        return (jsonify({'error': 'Allowed file types are png, jpg, jpeg, gif, mp3, wav, ogg'}), 400)

def generate_excel(dataset, files):
    from test_data_cal import total_count, model_prob_cal_new, process_excel, save_file
    try:
        uuid_val = str(uuid.uuid4())
        generate_path = os.path.join(os.path.expanduser('~'), 'generateExcel', uuid_val)
        if not state_exists(generate_path):
            os.makedirs(generate_path)
        task_type, total_token, query, intent, ex_app, ex_time, input_token, output_token, message, correct_answer, LLM_answer, Result, answer, instruction, final_result, content, system_prompt, user_prompt, field, category, reason, source_response = [[] for _ in range(22)]
        df_dict = {}
        for file in files:
            name = os.path.basename(file).split('.')[0].split(dataset)[-1].strip('_')
            with jsonl.open(file, mode='r') as reader:
                for line in reader.iter(type=dict, allow_none=True, skip_invalid=False):
                    ex_time.append(line.get('response_time', 0))
                    input_token.append(line['usage'].get('prompt_tokens', 0))
                    output_token.append(line['usage'].get('completion_tokens', 0))
                    total_token.append(line['usage'].get('total_tokens', 0))
                    message.append(line.get('parsed_request', {}).get('messages'))
                    correct_answer.append(line['choices'][0]['review']['gold'])
                    LLM_answer.append(line['choices'][0]['review']['pred'])
                    Result.append(line['choices'][0]['review']['result'])
                    if 'aisf_box_classify_dev' in dataset:
                        task_type.append(line['raw_input'].get('task_type', ''))
                        query.append(line['raw_input'].get('query', ''))
                    elif 'aisf_intent_dev' in dataset:
                        task_type.append(line['raw_input'].get('任务类型', ''))
                        query.append(line['raw_input'].get('query', ''))
                        ex_app.append(line['raw_input'].get('app', ''))
                    elif 'aisf_function_call_dev' in dataset:
                        query.append(line['raw_input'].get('query', ''))
                        field.append(line['raw_input'].get('field', ''))
                        answer.append(line['raw_input'].get('answer', ''))
                    elif 'aisf_box_tool_dev' in dataset:
                        query.append(line['raw_input'].get('query', ''))
                        intent.append(line['raw_input'].get('intent', ''))
                        answer.append(line['raw_input'].get('answer', ''))
                    elif 'aisf_memory' in dataset:
                        query.append(line['raw_input'].get('column1', ''))
                        answer.append(line['raw_input'].get('column3', ''))
                    elif 'aisf_clarify_dev' in dataset:
                        instruction.append(line['raw_input'].get('instructions', ''))
                        final_result.append(line['choices'][0]['message']['content'][-1])
                        content.append(line['choices'][0]['message']['content'])
                        reason.append(line['raw_input'].get('judge_output', ''))
                        source_response.append(line.get('source_response', []))
                    elif 'aisf_box_dev' in dataset:
                        query.append(line['raw_input'].get('query', ''))
                        system_prompt.append(line['raw_input'].get('system_prompt', ''))
                        user_prompt.append(line['raw_input'].get('user_prompt', ''))
                        intent.append(line['raw_input'].get('intent', ''))
                        answer.append(line['raw_input'].get('answer', ''))
                        field.append(line['raw_input'].get('field', ''))
                        category.append(line['raw_input'].get('category', ''))
            if 'aisf_intent_dev' in dataset:
                dic = {'time': ex_time, 'input token': input_token, 'output token': output_token, 'message': message, 'correct answer': correct_answer, 'LLM answer': LLM_answer, 'Result': Result}
                dic = {'任务类型': task_type, 'query': query, 'app': ex_app, **dic}
                df_dict[name] = dic
                task_type, total_token, query, intent, ex_app, ex_time, input_token, output_token, message, correct_answer, LLM_answer, Result, answer, instruction, final_result, content, system_prompt, user_prompt, field, category, reason, source_response = [[] for _ in range(22)]
            elif 'aisf_clarify_dev' in dataset:
                dic = {'instruction': instruction, 'final_result': final_result, 'judge': Result, 'reason': reason, 'time': ex_time, 'prompt_token': input_token, 'comp_token': output_token}
                max_columns = max((len(row) for row in instruction + content))
                result = {}
                for col_idx in range(max_columns):
                    instruction_values = []
                    for row in instruction:
                        if col_idx < len(row):
                            instruction_values.append(row[col_idx])
                        else:
                            instruction_values.append('')
                    result[f'instruction_{col_idx + 1}'] = instruction_values
                    content_values = []
                    for row in content:
                        if col_idx < len(row):
                            content_values.append(row[col_idx])
                        else:
                            content_values.append('')
                    result[f'result_{col_idx + 1}'] = content_values
                    source_value = []
                    for row in source_response:
                        if col_idx < len(row):
                            source_value.append(row[col_idx])
                        else:
                            source_value.append('')
                    if source_response:
                        result[f'response_{col_idx + 1}'] = source_value
                dic.update(result)
                df_dict[name] = dic
                task_type, total_token, query, intent, ex_app, ex_time, input_token, output_token, message, correct_answer, LLM_answer, Result, answer, instruction, final_result, content, system_prompt, user_prompt, field, category, reason, source_response = [[] for _ in range(22)]
        dic = {'time': ex_time, 'input token': input_token, 'output token': output_token, 'message': message, 'correct answer': correct_answer, 'LLM answer': LLM_answer, 'Result': Result}
        if 'aisf_box_classify_dev' in dataset:
            dic = {'任务类型': task_type, 'query': query, **dic}
            df = pd.DataFrame(dic)
            file_name = os.path.join(generate_path, f'{dataset}.xlsx')
            stats_df = process_excel(df)
            save_file(df, stats_df, file_name)
            return file_name
        elif 'aisf_intent_dev' in dataset:
            kk = {}
            for x, y in df_dict.items():
                for key, value in y.items():
                    if key in kk:
                        kk[key] = kk[key] + value
                    else:
                        kk[key] = value
            file_name = os.path.join(generate_path, f'{dataset}.xlsx')
            stats_df = process_excel(pd.DataFrame(kk))
            save_file(pd.DataFrame(kk), stats_df, file_name, df_dict)
            return file_name
        elif 'aisf_function_call_dev' in dataset:
            dic = {'QUERY': query, 'THINK': LLM_answer, 'ANSWER': answer, 'FIELD': field, 'TIME': ex_time, 'PROMPT_TOKEN': input_token, 'COMP_TOKEN': output_token, 'TOTAL_TOKENS': total_token, 'RESULT': Result}
        elif 'aisf_box_tool_dev' in dataset:
            dic = {'query': query, 'eval': Result, 'intent': intent, 'answer': answer, 'model_resp': LLM_answer, 'time': ex_time, 'prompt_token': input_token, 'comp_token': output_token, 'total_tokens': total_token}
        elif 'aisf_memory' in dataset:
            dic = {'Input': query, 'Answer': answer, 'LLM Output': LLM_answer, 'Result': Result, 'Time_Used': ex_time, 'Prompt_Token': input_token, 'Completions_Token': output_token}
        elif 'aisf_clarify_dev' in dataset:
            kk = {}
            score, arg_time, arg_in_token, arg_out_token, count = (0, 0, 0, 0, 0)
            all_score, all_time, all_in_token, all_out_token, all_count = (0, 0, 0, 0, 0)
            for x, y in df_dict.items():
                count = len(next(iter(y.values())))
                all_count += count
                for key, value in y.items():
                    if 'time' in key:
                        arg_time = round(sum(value) / len(value), 3)
                        all_time += sum(value)
                    elif 'prompt_token' in key:
                        arg_in_token = round(sum(value) / len(value))
                        all_in_token += sum(value)
                    elif 'comp_token' in key:
                        arg_out_token = round(sum(value) / len(value))
                        all_out_token += sum(value)
                    elif 'judge' in key:
                        score = f'{round(sum(value) * 100 / len(value), 0)}%'
                        all_score += sum(value)
                kk.setdefault('Subset', []).extend([x] * 5)
                kk.setdefault('指标', []).extend(['用例总数', '准确率', 'Prompt_token', 'Complete_token', '时延'])
                kk.setdefault('值', []).extend([count, score, arg_in_token, arg_out_token, arg_time])
            kk['Subset'].extend(['total'] * 5)
            kk['指标'].extend(['用例总数', '准确率', 'Prompt_token', 'Complete_token', '时延'])
            kk['值'].extend([all_count, f'{round(all_score * 100 / all_count, 2)}%', round(all_in_token / all_count), round(all_out_token / all_count), round(all_time / all_count, 3)])
            file_name = os.path.join(generate_path, f'{dataset}.xlsx')
            with pd.ExcelWriter(file_name, engine='openpyxl', mode='w') as writer:
                pd.DataFrame(kk).to_excel(writer, index=False, sheet_name='统计结果')
                for sheet_name, sheet_data in df_dict.items():
                    pd.DataFrame(sheet_data).to_excel(writer, index=False, sheet_name=sheet_name)
            return file_name
        elif 'aisf_box_dev' in dataset:
            dic = {'query': query, 'system_prompt': system_prompt, 'user_prompt': user_prompt, 'intent': intent, 'answer': answer, 'field': field, 'category': category, 'model_resp': LLM_answer, 'eval': ['T' if re == 1 else 'F' for re in Result]}
            df = pd.DataFrame(dic)
            total_df = total_count(df)
            category_list = ['场景分类', '参数提取', '裁决']
            new_df = pd.DataFrame({})
            for each_category in category_list:
                each_df = model_prob_cal_new(df, 'category', each_category)
                new_df = pd.concat([new_df, each_df], ignore_index=True, axis=0)
            new_df = pd.concat([new_df, total_df], ignore_index=True, axis=0)
            file_name = os.path.join(generate_path, f'{dataset}.xlsx')
            with pd.ExcelWriter(file_name, engine='openpyxl', mode='w') as writer:
                df.to_excel(writer, index=False, sheet_name='sheet1')
                new_df.to_excel(writer, index=False, sheet_name='sheet2')
            return file_name
        df = pd.DataFrame(dic)
        file_name = os.path.join(generate_path, f'{dataset}.xlsx')
        with pd.ExcelWriter(file_name, engine='openpyxl', mode='w') as writer:
            df.to_excel(writer, index=False)
        return file_name
    except Exception as e:
        raise RuntimeError(f'Error generating Excel file: {e}')

def zip_file(files):
    try:
        uuid_val = str(uuid.uuid4())
        generate_path = os.path.join(os.path.expanduser('~'), 'generateExcel', uuid_val)
        if not state_exists(generate_path):
            os.makedirs(generate_path)
        file_name = os.path.join(generate_path, f'{uuid_val}.zip')
        with zipfile.ZipFile(file_name, 'w') as z:
            for file in files:
                z.write(file, arcname=os.path.basename(file))
        return file_name
    except Exception as e:
        raise RuntimeError(f'Error zip file: {e}')

@app.route('/v1/get_excel_file', methods=['GET'])
def get_excel_file():
    task_id = request.args.get('task_id', '')
    datasets = request.args.get('datasets', '').split(',')
    if task_id == '' or len(datasets) == 0:
        return (jsonify({'error': 'param task_id, dataset must be not null'}), 400)
    files = []
    try:
        for dataset in datasets:
            tasks = get_tasks()
            model_id_basename = os.path.basename(tasks[task_id]['model_id']).rstrip(os.sep)
            path = os.path.join(tasks[task_id]['taskConfig']['use_cache'], 'reviews', model_id_basename, f'{dataset}*.jsonl')
            all_file = glob.glob(path)
            if len(all_file) > 0:
                files.append(generate_excel(dataset, all_file))
            else:
                continue
        if len(files) > 1:
            file = zip_file(files)
            return send_file(file, as_attachment=True)
        elif len(files) == 1:
            return send_file(files[0], as_attachment=True)
        return (jsonify({'error': '没有可下载的文件'}), 400)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/get_simultaneous_interpretation_cases', methods=['GET'])
def get_simultaneous_interpretation_cases():
    simu_interpretation_data = [SIMU_INTERPRETATION_ASR, SIMU_INTERPRETATION_ASR_LABEL, SIMU_INTERPRETATION_MT, SIMU_INTERPRETATION_TTS]
    for data in simu_interpretation_data:
        if not state_exists(data):
            return (jsonify({'error': f'同声传译测试集路径不存在，请联系管理员: {os.path.basename(data)}'}), 500)
    asr_data = build_directory_tree(SIMU_INTERPRETATION_ASR, depth=4)
    asr_label = build_directory_tree(SIMU_INTERPRETATION_ASR_LABEL, depth=4)
    mt_data = build_directory_tree(SIMU_INTERPRETATION_MT, depth=3)
    tts_data = build_directory_tree(SIMU_INTERPRETATION_TTS, depth=3)
    all_cases = merge_dicts(asr_data, asr_label, mt_data, tts_data)
    levels = collect_keys_and_flatten_leaf_values(all_cases)
    directoryA, directoryB, directoryC, directoryD = levels[:4]
    return (jsonify({'ASRAllData': asr_data, 'ASRTagging': asr_label, 'MTAllData': mt_data, 'TTSAllData': tts_data, 'directoryA': directoryA, 'directoryB': directoryB, 'directoryC': directoryC, 'directoryD': [item for item in list(set(directoryD)) if 'db' in item], 'directoryDlabel': [item for item in list(set(directoryD)) if 'db' not in item]}), 200)

@app.route('/v1/get_feedback_info', methods=['POST'])
def get_feedback_info():
    try:
        user_req = request.get_json()
        if not user_req or 'userName' not in user_req:
            return (jsonify({'error': '请求中缺少userName字段'}), 400)
        encodings = get_encoding(FEEDBACK_LIST_PATH)
        try:
            with open_state(FEEDBACK_LIST_PATH, 'r', encoding=encodings if encodings else 'utf-8') as f:
                full_info = json.load(f)
        except Exception as e:
            return (jsonify({'error': f'文件读取失败: {str(e)}'}), 500)
        if user_req['userName'] == 'admin':
            return (jsonify(full_info), 200)
        filtered_info = [item for item in full_info if item.get('userName') == user_req['userName']]
        return (jsonify(filtered_info), 200)
    except Exception as e:
        return (jsonify({'error': f'服务器内部错误: {str(e)}'}), 500)

@app.route('/v1/register_feedback_info', methods=['POST'])
def register_feedback_info():
    user_req = request.get_json()
    encodings = get_encoding(FEEDBACK_LIST_PATH)
    if encodings is not None:
        with open_state(FEEDBACK_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    user_req['id'] = int(time.time() * 1000)
    info.append(user_req)
    json_str = json.dumps(info, ensure_ascii=False, indent=4)
    with open_state(FEEDBACK_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(info), 200)

@app.route('/v1/delete_feedback_info', methods=['POST'])
def delete_feedback_info():
    user_req = request.get_json()
    encodings = get_encoding(FEEDBACK_LIST_PATH)
    if encodings is not None:
        with open_state(FEEDBACK_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    new_info = [d for d in info if d.get('id') not in user_req]
    json_str = json.dumps(new_info, ensure_ascii=False, indent=4)
    with open_state(FEEDBACK_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(new_info), 200)

@app.route('/v1/modify_feedback_info', methods=['POST'])
def modify_feedback_info():
    user_req = request.get_json()
    encodings = get_encoding(FEEDBACK_LIST_PATH)
    if encodings is not None:
        with open_state(FEEDBACK_LIST_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    if 'id' not in user_req or user_req['id'] not in [d.get('id') for d in info]:
        return ({'err_info': 'PARAM_ERR'}, PARAM_ERR)
    for idx in range(len(info)):
        if info[idx]['id'] == user_req['id']:
            if 'status' in user_req and user_req['status'] == 'completed':
                user_req['endTime'] = int(time.time() * 1000)
            info[idx] = user_req
            break
    json_str = json.dumps(info, ensure_ascii=False, indent=4)
    with open_state(FEEDBACK_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(info), 200)

@app.route('/v1/upload_mos_file', methods=['POST'])
def upload_mos_file():
    if 'file' not in request.files:
        return (jsonify({'error': '没有找到文件'}), 400)
    task_id = request.form.get('task_id')
    if not task_id:
        return (jsonify({'error': '缺少task_id参数'}), 400)
    file = request.files['file']
    task = get_one_task(task_id)
    model_id = task['model_id'].split(';')[-1]
    model_id_basename = os.path.basename(model_id).rstrip(os.sep)
    try:
        review_path = f'outputs/{model_id}/{task_id}/reviews/{model_id_basename}'
        os.makedirs(review_path, exist_ok=True)
        file_path = os.path.join(review_path, 'mos.xlsx')
        file.save(file_path)
        if task['assessmentType'] == 'TTS':
            language = task['datasets'][0].split('/')[1]
            jsonl_res_file = task['datasets'][0].replace('\\', '').replace('/', '') + f'_{language}_出租车_男_1_50.jsonl'
        else:
            language = task['taskConfig']['language'].split(';')[-1]
            jsonl_res_file = task_id.replace('_', '') + f'_{language}_出租车_男_1_50.jsonl'
        jsonl_name = os.path.join(review_path, jsonl_res_file)
        if not state_exists(jsonl_name):
            return (jsonify({'error': '对应的JSONL文件不存在'}), 400)
        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active
        mos_column_index = None
        for idx, cell in enumerate(sheet[1], start=1):
            if str(cell.value).strip().lower() == 'mos':
                mos_column_index = idx
                break
        if mos_column_index is None:
            return (jsonify({'error': 'Excel文件中未找到MOS列'}), 400)
        mos_values = []
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if len(row) >= mos_column_index:
                value = row[mos_column_index - 1]
                mos_values.append((row_idx, value))
        with open_state(jsonl_name, 'r', encoding='utf-8') as f:
            jsonl_line_count = sum((1 for _ in f))
        if len(mos_values) != jsonl_line_count:
            return (jsonify({'error': f'行数不匹配: Excel有{len(mos_values)}行数据，JSONL有{jsonl_line_count}行记录', 'solution': '请确保Excel行数与JSONL记录数完全一致'}), 400)
        valid_mos_values = []
        error_lines = []
        for row_idx, value in mos_values:
            if value is None or value == '':
                continue
            try:
                num_value = float(value)
                valid_mos_values.append((row_idx, num_value))
            except (TypeError, ValueError):
                error_lines.append(row_idx)
        if error_lines:
            return (jsonify({'error': f"Excel中包含无效MOS值（行号: {', '.join(map(str, error_lines))}）", 'solution': '请确保MOS列为数字类型'}), 400)
        updated_lines = []
        with open_state(jsonl_name, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f):
                data = json.loads(line.strip())
                current_mos = None
                if line_idx < len(mos_values):
                    row_idx, cell_value = mos_values[line_idx]
                    if cell_value is not None and cell_value != '':
                        try:
                            current_mos = float(cell_value)
                        except:
                            pass
                if current_mos is not None:
                    data['choices'][0]['review']['mos'] = current_mos
                updated_lines.append(data)
        with open_state(jsonl_name, 'w', encoding='utf-8') as f:
            for data in updated_lines:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        total_mos = 0
        valid_count = 0
        with open_state(jsonl_name, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                try:
                    mos_val = float(data['choices'][0]['review'].get('mos', 0))
                    total_mos += mos_val
                    valid_count += 1
                except (TypeError, ValueError, KeyError):
                    continue
        avg_mos = total_mos / valid_count if valid_count > 0 else 0
        if model_id in task['result'] and task['result'][model_id]:
            task['result'][model_id][0]['mos'] = avg_mos
        else:
            task['result'][model_id] = [{'mos': avg_mos}]
        tasks = get_tasks()
        tasks[task_id] = task
        set_tasks(tasks)
        return (jsonify({'message': 'MOS数据更新成功', 'details': {'更新行数': len(valid_mos_values), '无效行数': len(error_lines), '最终平均分': round(avg_mos, 2)}, 'file_path': f'outputs/{model_id}/{task_id}/reviews/{model_id_basename}/mos.xlsx'}), 200)
    except Exception as e:
        return (jsonify({'error': f'处理失败: {str(e)}'}), 500)

@app.route('/v1/add_interpretation_file', methods=['POST'])
def add_interpretation_file():
    if 'files' not in request.files:
        return (jsonify({'error': '没有找到文件'}), 400)
    uploaded_files = request.files.getlist('files')
    if len(uploaded_files) == 0:
        return (jsonify({'error': '文件列表为空'}), 400)
    directory = request.form.get('directory')
    if not directory:
        return (jsonify({'error': '缺少目录参数'}), 400)
    target_dir = os.path.join(SIMU_INTERPRETATION, directory)
    target_dir = os.path.normpath(target_dir)
    if not target_dir.startswith(os.path.normpath(SIMU_INTERPRETATION)):
        return (jsonify({'error': '非法目录路径'}), 400)
    if not state_exists(target_dir):
        return (jsonify({'error': f'目录不存在: {target_dir}，{directory}'}), 400)
    if not os.path.isdir(target_dir):
        return (jsonify({'error': f'路径不是目录: {directory}'}), 400)
    saved_files = []
    failed_files = []
    for file in uploaded_files:
        try:
            if file.filename == '':
                failed_files.append({'filename': '空文件名', 'error': '无效的文件名'})
                continue
            filename = secure_filename(file.filename)
            save_path = os.path.join(target_dir, filename)
            file.save(save_path)
            saved_files.append({'filename': filename, 'path': save_path})
        except Exception as e:
            failed_files.append({'filename': file.filename, 'error': f'文件保存失败: {str(e)}'})
    if len(saved_files) == len(uploaded_files):
        return (jsonify({'message': '所有文件上传成功', 'saved_count': len(saved_files), 'saved_files': saved_files, 'directory': directory}), 200)
    elif len(saved_files) > 0:
        return (jsonify({'message': '部分文件上传成功', 'saved_count': len(saved_files), 'failed_count': len(failed_files), 'saved_files': saved_files, 'failed_files': failed_files, 'directory': directory}), 207)
    else:
        return (jsonify({'error': '所有文件上传失败', 'failed_files': failed_files}), 400)

@app.route('/v1/add_interpretation_directory', methods=['POST'])
def add_interpretation_directory():
    try:
        user_req = request.get_json()
        directory = user_req['directory']
        parts = directory.split('/')
        new_dir = parts[-1]
        directory = '/'.join(parts[:-1])
        target_dir = os.path.join(SIMU_INTERPRETATION, directory)
        target_dir = os.path.normpath(target_dir)
        print(f'target_dir:{target_dir}')
        if not target_dir.startswith(os.path.normpath(SIMU_INTERPRETATION)):
            return (jsonify({'error': '非法目录路径'}), 400)
        full_new_dir = os.path.join(target_dir, new_dir)
        if not state_exists(target_dir):
            return (jsonify({'error': '目标路径不存在'}), 400)
        if state_exists(full_new_dir):
            return (jsonify({'error': '文件夹已存在'}), 400)
        os.mkdir(full_new_dir)
        res = {'success': '文件夹创建成功'}
    except Exception as e:
        print(e)
        res = {'error': '服务器内部错误: ' + str(e)}
        return (jsonify(res), 500)
    return (jsonify(res), 200)

@app.route('/v1/delete_interpretation_directory', methods=['POST'])
def delete_interpretation_directory():
    try:
        user_req = request.get_json()
        directory = user_req['directory']
        target_path = os.path.join(SIMU_INTERPRETATION, directory)
        target_path = os.path.normpath(target_path)
        print(f'删除目标路径: {target_path}')
        if not target_path.startswith(os.path.normpath(SIMU_INTERPRETATION)):
            return (jsonify({'error': '非法目录路径'}), 400)
        if not state_exists(target_path):
            return (jsonify({'error': '路径不存在'}), 404)
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
            res = {'success': f'文件夹 {directory} 已成功删除'}
        else:
            os.remove(target_path)
            res = {'success': f'文件 {directory} 已成功删除'}
    except Exception as e:
        print(f'删除操作出错: {str(e)}')
        res = {'error': f'删除失败: {str(e)}'}
        return (jsonify(res), 500)
    return (jsonify(res), 200)

def check_all_model_connectivity():
    try:
        model_cfg = get_model_info_list()
        for i in range(len(model_cfg)):
            print(model_cfg[i]['model_id'])
            model_cfg[i]['is_available'] = check_model_connectivity(model_cfg[i]['config'])
        json_str = json.dumps(model_cfg, ensure_ascii=False, indent=4)
        with open_state(MODEL_CFG_PATH, 'w', encoding='utf-8') as f:
            f.write(json_str)
    except RequestException as e:
        pass

@app.route('/v1/add_log_data', methods=['POST'])
def add_log_data():
    try:
        user_req = request.get_json()
        user_id = user_req.get('user_id', 'admin').strip()
        timestamp = user_req.get('timestamp', '')
        type = user_req.get('type', '').strip()
        content = user_req.get('content', '')
        if type in AI_SCHOOL_TYPES:
            update_aischool_online_dashboard(user_id, type, content)
        user_log_path = os.path.join(LOG_PATH, f'{user_id}.txt')
        log_entry = {'user_id': user_id, 'type': type, 'timestamp': timestamp, 'content': content, 'active': True}
        with log_lock:
            try:
                os.makedirs(os.path.dirname(user_log_path), exist_ok=True)
                with open_state(user_log_path, 'a', encoding='utf-8') as log_file:
                    log_file.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                    return (jsonify({'message': '日志记录成功', 'data': log_entry}), 200)
            except Exception as e:
                return (jsonify({'error': '日志记录失败', 'data': str(e)}), 500)
    except Exception as e:
        return (jsonify({'error': '无效的JSON数据', 'data': str(e)}), 400)

def _get_log_data_internal(get_log_params):
    try:
        user_id = get_log_params.get('user_id', 'admin').strip()
        log_type = get_log_params.get('type', '').strip()
        chat_id = get_log_params.get('chat_id', '').strip()
        limit = max(1, min(int(get_log_params.get('limit', 100)), 10000))
        active = get_log_params.get('active', None)
        user_log_path = os.path.join(LOG_PATH, f'{user_id}.txt')
        if not state_exists(user_log_path):
            with open_state(user_log_path, 'w') as f:
                pass
            return {'status': 'success', 'count': 0, 'data': []}
        matched_logs = []
        with open_state(user_log_path, 'r', encoding='utf-8') as log_file:
            for line in log_file:
                line = line
                if not line:
                    continue
                try:
                    log_entry = json.loads(line)
                    current_user_id = log_entry.get('user_id')
                    current_type = log_entry.get('type')
                    current_chat_id = log_entry.get('chat_id', '')
                    current_active = log_entry.get('active', None)
                    user_match = current_user_id == user_id
                    if log_type == 'text':
                        type_match = current_type in ['text', 'image', 'audio', 'video']
                    else:
                        type_match = log_type == '' or current_type == log_type
                    chat_match = chat_id == '' or current_chat_id == chat_id
                    active_match = True
                    if active is not None:
                        active_match = current_active == active
                    if user_match and type_match and chat_match and active_match:
                        if 'response' in log_entry and isinstance(log_entry['response'], dict):
                            log_entry['response'] = json.dumps(log_entry['response'], ensure_ascii=False)
                        matched_logs.append(log_entry)
                except json.JSONDecodeError:
                    continue
        matched_logs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        if 0 < limit < len(matched_logs):
            matched_logs = matched_logs[:limit]
        matched_logs.reverse()
        for log_entry in matched_logs:
            file_path = log_entry.get('file_path')
            current_type = log_entry.get('type')
            if file_path and state_exists(file_path):
                if current_type == 'image':
                    try:
                        base64_image = image_to_base64_url(file_path)
                        log_entry['file_base64'] = base64_image
                    except Exception as e:
                        log_entry['file_base64'] = f'文件转换失败: {str(e)}'
                elif current_type == 'audio':
                    try:
                        base64_audio = audio_to_base64_url(file_path)
                        log_entry['file_base64'] = base64_audio
                    except Exception as e:
                        log_entry['file_base64'] = f'文件转换失败: {str(e)}'
                elif current_type == 'video':
                    try:
                        base64_video = video_to_base64_url(file_path)
                        log_entry['file_base64'] = base64_video
                    except Exception as e:
                        log_entry['file_base64'] = f'文件转换失败: {str(e)}'
            elif file_path:
                log_entry['file_base64'] = '文件不存在'
        return {'status': 'success', 'count': len(matched_logs), 'data': matched_logs}
    except Exception as e:
        return {'error': f'查询日志失败: {str(e)}', 'data': []}

@app.route('/v1/get_log_data', methods=['POST'])
def get_log_data():
    try:
        user_req = request.get_json()
        result = _get_log_data_internal(user_req)
        if 'error' in result:
            return (jsonify(result), 404 if '不存在' in result['error'] else 500)
        return (jsonify(result), 200)
    except Exception as e:
        return (jsonify({'error': f'请求处理失败: {str(e)}', 'data': []}), 500)

@app.route('/v1/modify_log_data', methods=['POST'])
def modify_log_data():
    user_req = request.get_json()
    user_id = user_req.get('user_id', 'admin').strip()
    chat_id = user_req.get('chat_id')
    os.makedirs(LOG_PATH, exist_ok=True)
    user_log_path = os.path.join(LOG_PATH, f'{user_id}.txt')
    temp_path = user_log_path + '.tmp'
    if not chat_id:
        return ({'status': '错误', 'message': '缺少chat_id参数'}, 400)
    if not state_exists(user_log_path):
        with open_state(user_log_path, 'w', encoding='utf-8') as f:
            pass
    try:
        max_timestamp = 0
        max_timestamp_count = 0
        with open_state(user_log_path, 'r', encoding='utf-8') as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('chat_id') == chat_id:
                        ts = entry.get('timestamp', 0)
                        if ts > max_timestamp:
                            max_timestamp = ts
                            max_timestamp_count = 1
                        elif ts == max_timestamp:
                            max_timestamp_count += 1
                except json.JSONDecodeError:
                    continue
        if max_timestamp == 0:
            return ({'status': '错误', 'message': '未找到匹配的chat_id'}, 404)
        modified = False
        current_count = 0
        with open_state(user_log_path, 'r', encoding='utf-8') as input_file, open_state(temp_path, 'w', encoding='utf-8') as output_file:
            for line in input_file:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('chat_id') == chat_id:
                        modified = True
                        ts = entry.get('timestamp', 0)
                        if ts == max_timestamp:
                            current_count += 1
                            if current_count == max_timestamp_count:
                                if 'query' in entry and isinstance(entry['query'], str) and (len(entry['query']) > 200):
                                    entry['query'] = entry['query'][:200] + '...'
                                entry['response'] = ''
                                entry['active'] = False
                            else:
                                entry['query'] = ''
                                entry['response'] = ''
                                entry['active'] = False
                        else:
                            entry['query'] = ''
                            entry['response'] = ''
                            entry['active'] = False
                    if entry.get('file_path'):
                        if state_exists(entry['file_path']):
                            os.remove(entry['file_path'])
                        entry['file_path'] = ''
                    output_file.write(json.dumps(entry, ensure_ascii=False) + '\n')
                except json.JSONDecodeError:
                    output_file.write(line)
        if modified:
            os.replace(temp_path, user_log_path)
            return ({'status': '成功', 'message': '日志数据修改成功'}, 200)
        else:
            if state_exists(temp_path):
                os.remove(temp_path)
            return ({'status': '错误', 'message': '未找到匹配的chat_id'}, 404)
    except Exception as e:
        if state_exists(temp_path):
            os.remove(temp_path)
        return ({'status': '错误', 'message': f'处理失败: {str(e)}'}, 500)

@app.route('/v1/get_model_progress', methods=['GET'])
def get_model_progress():
    encodings = get_encoding(EVAL_PROGRESS_PATH)
    if encodings is not None:
        with open_state(EVAL_PROGRESS_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    return (jsonify(info), 200)

@app.route('/v1/add_model_progress', methods=['POST'])
def add_model_progress():
    user_req = request.get_json()
    encodings = get_encoding(EVAL_PROGRESS_PATH)
    if encodings is not None:
        with open_state(EVAL_PROGRESS_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    ids = set((d['ID'] for d in info if isinstance(d['ID'], int)))
    new_id = 1
    if ids:
        sorted_ids = sorted(ids)
        for current_id in sorted_ids:
            if current_id == new_id:
                new_id += 1
            elif current_id > new_id:
                break
    user_req['ID'] = new_id
    info.append(user_req)
    json_str = json.dumps(info, ensure_ascii=False, indent=4)
    with open_state(EVAL_PROGRESS_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(info), 200)

@app.route('/v1/modify_model_progress', methods=['POST'])
def modify_model_progress():
    user_req = request.get_json()
    encodings = get_encoding(EVAL_PROGRESS_PATH)
    if encodings is not None:
        with open_state(EVAL_PROGRESS_PATH, 'r', encoding=encodings) as f:
            info = json.load(f)
    else:
        info = []
    if user_req['ID'] not in [d.get('ID') for d in info]:
        return ({'err_info': 'MODEL_NOT_EXIST'}, MODEL_NOT_EXIST)
    for idx in range(len(info)):
        if info[idx]['ID'] == user_req['ID']:
            info[idx] = user_req
            break
    json_str = json.dumps(info, ensure_ascii=False, indent=4)
    with open_state(EVAL_PROGRESS_PATH, 'w', encoding='utf-8') as f:
        f.write(json_str)
    return (jsonify(info), 200)

@app.route('/v1/upload_test_result', methods=['POST'])
def upload_test_result():
    if 'file' not in request.files:
        return (jsonify({'error': '没有找到文件'}), 400)
    task_id = request.form.get('task_id')
    if not task_id:
        return (jsonify({'error': '缺少task_id参数'}), 400)
    dataset_name = request.form.get('dataset_name')
    file = request.files['file']
    task = get_one_task(task_id)
    model_id = task['model_id'].split(';')[-1]
    model_id_basename = os.path.basename(model_id).rstrip(os.sep)
    try:
        review_path = f'outputs/{model_id}/{task_id}/reviews/{model_id_basename}'
        os.makedirs(review_path, exist_ok=True)
        file_path = os.path.join(review_path, f'{dataset_name}报告_{task_id}.xlsx')
        excel_data = file.read()
        workbook = openpyxl.load_workbook(BytesIO(excel_data))
        sheet = workbook.active
        column_names = [cell.value.strip() for cell in sheet[1] if cell.value and str(cell.value).strip()]
        required_columns = ['注意力大类-单次结果', '注意力小类-单次结果', '坐姿大类', '坐姿小类', 'attention_status', 'attention_category', 'sitting_posture_status', 'sitting_posture_category', 'model_output']
        missing_cols = [col for col in required_columns if col not in column_names]
        if missing_cols:
            return (jsonify({'error': f"Excel缺少必要列: {', '.join(missing_cols)}"}), 400)
        dataset = task['datasets'][0]
        jsonl_path = os.path.join(review_path, dataset + '_default.jsonl')
        if not state_exists(jsonl_path):
            return (jsonify({'error': '对应的JSONL文件不存在'}), 400)
        jsonl_lines = []
        with open_state(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                jsonl_lines.append(json.loads(line))
        total_jsonl_lines = len(jsonl_lines)
        if sheet.max_row - 1 < total_jsonl_lines:
            return (jsonify({'error': f'Excel行数不足，需要至少{total_jsonl_lines + 1}行（含表头）'}), 400)
        try:
            for idx in range(total_jsonl_lines):
                excel_row = idx + 2
                row = sheet[excel_row]
                row_values = [cell.value for cell in row]
                row_data = dict(zip(column_names, row_values))
                gold_attention_status = row_data.get('注意力大类', '')
                gold_attention_category = row_data.get('注意力小类', '')
                gold_sitting_posture_status = row_data.get('坐姿大类', '')
                gold_sitting_posture_category = row_data.get('坐姿小类', '')
                gold_distance_status = row_data.get('视距检测', '')
                gold_seat_status = row_data.get('离座检测', '')
                pred_attention_status = row_data.get('attention_status', '')
                pred_attention_category = row_data.get('attention_category', '')
                pred_sitting_posture_status = row_data.get('sitting_posture_status', '')
                pred_sitting_posture_category = row_data.get('sitting_posture_category', '')
                pred_distance_status = row_data.get('distance_status', '')
                pred_seat_status = row_data.get('seat_status', '')
                model_output = row_data.get('model_output', '')
                obj = jsonl_lines[idx]
                if not obj.get('choices'):
                    obj['choices'] = [{}]
                if 'review' not in obj['choices'][0]:
                    obj['choices'][0]['review'] = {}
                obj['choices'][0]['review']['gold'] = {'attention_status': gold_attention_status, 'attention_category': gold_attention_category, 'sitting_posture_status': gold_sitting_posture_status, 'sitting_posture_category': gold_sitting_posture_category, 'distance_status': gold_distance_status, 'seat_status': gold_seat_status}
                obj['choices'][0]['review']['pred'] = {'attention_status': pred_attention_status, 'attention_category': pred_attention_category, 'sitting_posture_status': pred_sitting_posture_status, 'sitting_posture_category': pred_sitting_posture_category, 'distance_status': pred_distance_status, 'seat_status': pred_seat_status}
                attention_correct = 1 if gold_attention_status == pred_attention_status and gold_attention_category == pred_attention_category else 0
                sitting_posture_correct = 1 if gold_sitting_posture_status == pred_sitting_posture_status and gold_sitting_posture_category == pred_sitting_posture_category else 0
                distance_correct = 1 if gold_distance_status == pred_distance_status else 0
                seat_correct = 1 if gold_seat_status == pred_seat_status else 0
                overall_correct = 1 if attention_correct and sitting_posture_correct and distance_correct and seat_correct else 0
                obj['choices'][0]['review']['result'] = overall_correct
                if 'message' not in obj['choices'][0]:
                    obj['choices'][0]['message'] = {}
                obj['choices'][0]['message']['content'] = model_output
        except Exception as e:
            return jsonify(f'处理Excel数据失败: {str(e)}', 400)
        with open_state(jsonl_path, 'w', encoding='utf-8') as f:
            for obj in jsonl_lines:
                f.write(json.dumps(obj, ensure_ascii=False) + '\n')
        with open_state(file_path, 'wb') as f:
            f.write(excel_data)
        calculate_accuracy_with_styles(file_path)
        return (jsonify({'message': '测试结果更新成功'}), 200)
    except Exception as e:
        return (jsonify({'error': f'处理失败: {str(e)}'}), 500)

@app.route('/v1/lmarena/leaderboard', methods=['GET'])
def get_lmarena_leaderboard():
    """
    为前端提供LM Arena排行榜数据
    """
    try:
        df = pd.read_csv(LM_ARENA_CSV_PATH)
        df = df.sort_values(by='rank', ascending=True).reset_index(drop=True)
        data = df.to_dict(orient='records')
        VARIANT_SUFFIXES = ['think', 'thinking', 'high', 'instant', 'Instant', '\\d+', 'latest']
        suffix_pattern = re.compile('[-_.\\s]?(' + '|'.join(VARIANT_SUFFIXES) + ')$', re.IGNORECASE)

        def strip_suffix(name):
            """去除已知后缀变体（最多去除两层）"""
            name = str(name).strip()
            for _ in range(2):
                m = suffix_pattern.search(name)
                if m:
                    name = name[:m.start()].strip()
                else:
                    break
            return name

        def normalize_key(name):
            """先去后缀，再对模型名称做lower()处理，再去掉所有的.-以及空格，得到规范化名称用于去重判断"""
            name = strip_suffix(name)
            return re.sub('[.\\- ]', '', name).lower()
        import math
        clean_data = []
        for row in data:
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, float) and math.isnan(v):
                    clean_row[k] = 0
                elif isinstance(v, (np.integer,)):
                    clean_row[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    clean_row[k] = float(v)
                elif isinstance(v, (np.bool_,)):
                    clean_row[k] = bool(v)
                else:
                    clean_row[k] = v
            clean_data.append(clean_row)
        groups = {}
        for row in clean_data:
            model_name = str(row.get('model_name', ''))
            base_key = normalize_key(model_name)
            elo = float(row.get('elo', 0))
            groups.setdefault(base_key, []).append((elo, row))
        keep = set()
        for base_key, members in groups.items():
            scores = [m[0] for m in members]
            max_score = max(scores)
            min_score = min(scores)
            if max_score - min_score < 20:
                for elo, row in members:
                    if abs(elo - max_score) < 1e-09:
                        keep.add(id(row))
            else:
                for _, row in members:
                    keep.add(id(row))
        filtered = [row for row in clean_data if id(row) in keep]
        return (jsonify(filtered), 200)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

def deep_search_stream(target_url, params, timeout):
    try:
        with requests.post(target_url, json=params, stream=True, timeout=timeout) as r:
            if r.status_code != 200:
                error_msg = json.dumps({'error': f'上游服务错误: {r.status_code}'})
                yield f'data: {error_msg}\n\n'
                return
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8', errors='ignore')
                    print(decoded, end='', flush=True)
                    yield f'data: {decoded}\n\n'
    except requests.exceptions.Timeout:
        error_msg = 'Connection to target_url timed out'
        raise Exception(f"{json.dumps({'error': error_msg})}\n\n")
    except Exception as e:
        error_msg = f'Error occurred: {str(e)}'
        raise Exception(f"{json.dumps({'error': error_msg})}\n\n")

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response
None
None
None
None
None

@app.route('/v1/user_statistics/overview', methods=['GET'])
def user_statistics_overview():
    try:
        data = get_overview(start_date=request.args.get('start_date'), end_date=request.args.get('end_date'))
        return jsonify(code=0, data=data, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/trend', methods=['GET'])
def user_statistics_trend():
    try:
        data = get_trend(start_date=request.args.get('start_date'), end_date=request.args.get('end_date'), type_filter=request.args.get('type') or None)
        return jsonify(code=0, data=data, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/type_distribution', methods=['GET'])
def user_statistics_type_distribution():
    try:
        data = get_type_distribution(start_date=request.args.get('start_date'), end_date=request.args.get('end_date'))
        return jsonify(code=0, data=data, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/top_users', methods=['GET'])
def user_statistics_top_users():
    try:
        top_n = request.args.get('top_n', 10, type=int)
        data = get_top_users(start_date=request.args.get('start_date'), end_date=request.args.get('end_date'), top_n=top_n)
        return jsonify(code=0, data=data, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/department_stats', methods=['GET'])
def user_statistics_department_stats():
    try:
        top_n = request.args.get('top_n', 15, type=int)
        data = get_department_stats(start_date=request.args.get('start_date'), end_date=request.args.get('end_date'), top_n=top_n)
        return jsonify(code=0, data=data, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/details', methods=['GET'])
def user_statistics_details():
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        data = get_details(start_date=request.args.get('start_date'), end_date=request.args.get('end_date'), user_id=request.args.get('user_id') or None, type_filter=request.args.get('type') or None, model_id=request.args.get('model_id') or None, keyword=request.args.get('keyword') or None, types=request.args.get('types') or None, page=page, page_size=page_size)
        return jsonify(code=0, data=data, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/user_candidates', methods=['GET'])
def user_statistics_user_candidates():
    try:
        keyword = request.args.get('keyword', '')
        users = {}
        return jsonify(code=0, data={'users': users}, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/type_candidates', methods=['GET'])
def user_statistics_type_candidates():
    try:
        types = get_type_candidates()
        return jsonify(code=0, data={'types': types}, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/model_candidates', methods=['GET'])
def user_statistics_model_candidates():
    try:
        models = get_model_candidates()
        return jsonify(code=0, data={'models': models}, message='success')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)

@app.route('/v1/user_statistics/refresh_dept_cache', methods=['POST'])
def user_statistics_refresh_dept_cache():
    """手动触发部门缓存刷新"""
    try:
        refresh_dept_cache()
        return jsonify(code=0, data=None, message='部门缓存刷新成功')
    except Exception as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)
API_KEY_APPLY_URL = ''

def _apply_api_key(work_id):
    """
    调用外部 API Key 申请服务
    """
    try:
        resp = requests.post(API_KEY_APPLY_URL, json={'work_id': work_id}, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f'外部服务返回异常状态码: {resp.status_code}')
        data = resp.json()
        api_key = data.get('api_key')
        if not api_key:
            raise RuntimeError('外部服务未返回 api_key')
        return (api_key, data.get('work_id', work_id), data.get('message', ''))
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f'请求外部服务失败: {str(e)}')
    except Exception as e:
        raise RuntimeError(f'处理申请 Key 失败: {str(e)}')

@app.route('/v1/user_statistics/apply_api_key', methods=['POST'])
def user_statistics_apply_api_key():
    """
    申请 API Key
    请求体: {"work_id": "xxxx"}
    """
    try:
        data = request.get_json()
        if not data or not data.get('work_id'):
            return (jsonify(code=1, data=None, message='缺少 work_id 参数'), 400)
        work_id = data['work_id'].strip()
        if not work_id:
            return (jsonify(code=1, data=None, message='work_id 不能为空'), 400)
        api_key, _, _ = _apply_api_key(work_id)
        return jsonify(code=0, data={'api_key': api_key}, message='success')
    except RuntimeError as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)
    except Exception as e:
        return (jsonify(code=1, data=None, message=f'服务器内部错误: {str(e)}'), 500)

@app.route('/v1/user_statistics/get_api_key', methods=['GET'])
def user_statistics_get_api_key():
    """
    获取当前用户 API Key（GET 方式，work_id 通过查询参数传递）
    """
    try:
        work_id = request.args.get('work_id', '').strip()
        if not work_id:
            return (jsonify(code=1, data=None, message='缺少 work_id 参数'), 400)
        api_key, _, _ = _apply_api_key(work_id)
        return jsonify(code=0, data={'api_key': api_key}, message='success')
    except RuntimeError as e:
        return (jsonify(code=1, data=None, message=str(e)), 500)
    except Exception as e:
        return (jsonify(code=1, data=None, message=f'服务器内部错误: {str(e)}'), 500)
None
None
