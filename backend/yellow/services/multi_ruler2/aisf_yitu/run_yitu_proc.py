# Private iCAP Yellow business implementation. Do not publish.
"""意图 —— 独立子进程入口。

由 run_test_server.py 以 subprocess 方式启动，取代原先在服务进程内运行的
run_yitu 线程，使得该测评任务的存活不再依赖 flask 服务进程。
"""
import json
import os
import sys
import traceback

def _find_project_root():
    """向上查找项目根目录，使其下的 backend 包可被 import（backend.xxx 前缀导入）。"""
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(d, 'run_test_server.py')) and os.path.isdir(os.path.join(d, 'services')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
_PROJECT_ROOT = _find_project_root()
if _PROJECT_ROOT and _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from services.custom_proc_common import parse_config, finalize_task, extract_generation_config
from utils.consts import YITU_DATASET_PATH
from utils.eval_utils import get_limit
from services.multi_ruler2.aisf_yitu.aisf_yitu_test import run_pipeline

def run_yitu_proc(model_config, task_id, model_id, user_req, thread_id):
    model_name = model_config['info']['model_name']
    api_url = model_config['config']['api_params_available'][0]['endpoint']
    limit = get_limit(user_req.get('limit'))
    gen_cfg = extract_generation_config(user_req)
    gen_temperature = gen_cfg.get('temperature')
    temperature = gen_temperature if gen_temperature is not None else user_req.get('temperature')
    eval_batch_size = user_req.get('eval_batch_size')
    dataset_args = user_req['dataset_args']
    api_key = (model_config['config']['api_params_available'][0]['api_key'] if model_config['config']['api_params_available'][0]['api_key'] else 'EMPTY',)
    retry_content_none = user_req.get('retry_content_none')
    use_cache = user_req.get('use_cache')
    retry_enabled = retry_content_none is not None and bool(use_cache)
    try:
        output_path = f'outputs/{model_id}/{task_id}'
        for arg in dataset_args:
            dataset_name = arg['dataset_name']
            sys_prompt = arg['system_prompt']
            dataset_dir = os.path.join(YITU_DATASET_PATH, dataset_name)
            print('run_yitu_proc 1')
            excel_path = None
            if os.path.exists(dataset_dir):
                for filename in os.listdir(dataset_dir):
                    filepath = os.path.join(dataset_dir, filename)
                    if os.path.isfile(filepath):
                        ext = os.path.splitext(filename)[1].lower()
                        if ext == '.xlsx':
                            excel_path = filepath
            print('run_yitu_proc 2')
            run_pipeline(task_id=task_id, input_path=excel_path, output_path=output_path, url=api_url, model_name=model_name, model_id=model_id, api_key=api_key, system_prompt=sys_prompt, temp=temperature, dataset_name=dataset_name, MAX_WORKERS=eval_batch_size, LIMIT=limit, thread_id=thread_id, retry_content_none=retry_content_none if retry_enabled else False, retry_enabled=retry_enabled)
            print('run_yitu_proc over')
        finalize_task(task_id, model_name, model_id)
    except Exception as e:
        print(f'run_yitu_proc error:{e}')
        traceback.print_exc()
        finalize_task(task_id, model_name, model_id, error=str(e))

if __name__ == '__main__':
    cfg = parse_config()
    run_yitu_proc(model_config=cfg.get('model_config'), task_id=cfg.get('task_id'), model_id=cfg.get('model_id'), user_req=cfg.get('user_req'), thread_id=cfg.get('thread_id'))
