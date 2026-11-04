# Private iCAP Yellow business implementation. Do not publish.
"""改写 —— 独立子进程入口。

由 run_test_server.py 以 subprocess 方式启动，取代原先在服务进程内运行的
run_gaixie 线程，使得该测评任务的存活不再依赖 flask 服务进程。
"""
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
from utils.consts import GAIXIE_DATASET_PATH
from utils.eval_utils import get_limit
from services.custom_proc_common import parse_config, finalize_task, extract_generation_config
from services.aisf_gaixie.multi_test import process as gaixie_process

def run_gaixie_proc(model_config, task_id, model_id, user_req, thread_id):
    """改写评测入口 —— 委托 process() 执行（独立进程版）。"""
    model_name = model_config['info']['model_name']
    api_url = model_config['config']['api_params_available'][0]['endpoint']
    api_key = model_config['config']['api_params_available'][0]['api_key'] or 'EMPTY'
    generate_config = extract_generation_config(user_req)
    gen_temperature = generate_config.get('temperature')
    temperature = gen_temperature if gen_temperature is not None else user_req.get('temperature')
    limit = get_limit(user_req.get('limit'))
    dataset_args = user_req['dataset_args']
    retry_content_none = user_req.get('retry_content_none')
    use_cache = user_req.get('use_cache')
    retry_enabled = retry_content_none is not None and bool(use_cache)
    try:
        output_path = f'outputs/{model_id}/{task_id}'
        for arg in dataset_args:
            dataset_name = arg['dataset_name']
            dataset_dir = os.path.join(GAIXIE_DATASET_PATH, dataset_name)
            excel_path = None
            if os.path.exists(dataset_dir):
                for fname in os.listdir(dataset_dir):
                    fpath = os.path.join(dataset_dir, fname)
                    if os.path.isfile(fpath) and os.path.splitext(fname)[1].lower() == '.xlsx':
                        excel_path = fpath
                        break
            if not excel_path:
                raise FileNotFoundError(f'在 {dataset_dir} 下未找到 xlsx 测试集文件')
            os.makedirs(output_path, exist_ok=True)
            review_dir = os.path.join(output_path, 'reviews', model_id)
            report_dir = os.path.join(output_path, 'reports', model_id)
            os.makedirs(review_dir, exist_ok=True)
            os.makedirs(report_dir, exist_ok=True)
            output_xlsx = os.path.join(review_dir, f'{dataset_name}_{task_id}.xlsx')
            few_base = GAIXIE_DATASET_PATH.rstrip('/\\') + '_few'
            index_dir = os.path.join(few_base, dataset_name, 'index')
            if not os.path.exists(index_dir):
                index_dir = None
            generate_config = user_req.get('generate_config')
            fewshot_retrieval_mode = generate_config.get('fewshot_retrieval_mode', 'query')
            fewshot_example_field = generate_config.get('fewshot_example_field', 'no_thought_example')
            enable_fewshot = generate_config.get('enable_fewshot', True)
            enable_fixed_fewshot = generate_config.get('enable_fixed_fewshot', True)
            fewshot_top_k = generate_config.get('fewshot_top_k', 5)
            fewshot_score_threshold = generate_config.get('fewshot_score_threshold', 0.61)
            max_fewshot_examples = generate_config.get('max_fewshot_examples', 5)
            max_context_turns = generate_config.get('max_context_turns', 5)
            log_dir = os.path.join(output_path, 'logs')
            gaixie_process(report_dir=report_dir, file_path=excel_path, output_xlsx=output_xlsx, model_url=api_url, model_name=model_name, fewshot_index_dir=index_dir, fewshot_retrieval_mode=fewshot_retrieval_mode, fewshot_example_field=fewshot_example_field, enable_fewshot=enable_fewshot, enable_fixed_fewshot=enable_fixed_fewshot, fewshot_top_k=fewshot_top_k, fewshot_score_threshold=fewshot_score_threshold, max_fewshot_examples=max_fewshot_examples, max_context_turns=max_context_turns, dataset_name=dataset_name, log_dir=log_dir, limit=limit, temperature=temperature, api_key=api_key, task_id=task_id, model_id=model_id, retry_content_none=retry_content_none if retry_enabled else False, retry_enabled=retry_enabled)
        finalize_task(task_id, model_name, model_id)
    except Exception as e:
        print(f'run_gaixie_proc error: {e}')
        traceback.print_exc()
        finalize_task(task_id, model_name, model_id, error=str(e))

if __name__ == '__main__':
    cfg = parse_config()
    run_gaixie_proc(model_config=cfg.get('model_config'), task_id=cfg.get('task_id'), model_id=cfg.get('model_id'), user_req=cfg.get('user_req'), thread_id=cfg.get('thread_id'))
