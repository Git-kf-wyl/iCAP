# Private iCAP Yellow business implementation. Do not publish.
"""儿童伴读 —— 独立子进程入口。

由 run_test_server.py 以 subprocess 方式启动，取代原先在服务进程内运行的
run_eld 线程，使得该测评任务的存活不再依赖 flask 服务进程。
"""
import json
import os
import sys
import time
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
from services.custom_proc_common import parse_config, update_task, finalize_task, extract_generation_config
from utils.consts import ELD_DATASET_PATH
from utils.utils import unzip_if_needed
from utils.eval_utils import get_limit
from services.multi_ruler2.children_study.children_study import run_custom_posture_eval

def _parse_excel_sheet_into_tables(excel_file, sheet_name):
    """解析Excel中一个统计sheet，将其中的多个 (title, DataFrame) 分离为 [{title, columns, rows}, ...]"""
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
            if consecutive_empty >= 2:
                if current_title is not None:
                    tables.append({'title': current_title, 'columns': current_headers, 'rows': current_rows})
                    current_title = None
                    current_headers = []
                    current_rows = []
                state = 0
            continue
        consecutive_empty = 0
        if state == 0:
            if isinstance(first_val, str) and first_val.startswith('##'):
                current_title = first_val.lstrip('#').strip()
                state = 1
        elif state == 1:
            current_headers = [str(v) if v is not None else '' for v in values]
            state = 2
        elif state == 2:
            row_dict = {}
            for i, v in enumerate(values):
                col = current_headers[i] if i < len(current_headers) else f'col{i}'
                row_dict[col] = v
            current_rows.append(row_dict)
    if current_title is not None:
        tables.append({'title': current_title, 'columns': current_headers, 'rows': current_rows})
    wb.close()
    return tables

def _build_eld_statistics_json(output_path, model_name_safe, dataset_name, task_id, subset_list, limit):
    """在儿童伴读评测完成后，读取输出的Excel文件，生成结构化统计JSON"""
    import glob as glob_mod
    review_dir = os.path.join(output_path, 'reviews', model_name_safe)
    if not os.path.exists(review_dir):
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
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_stats_data, f, ensure_ascii=False, indent=2)
        print(f'[_build_eld_statistics_json] saved: {json_file} (sheets: {list(all_stats_data.keys())})')
        return (json_file, all_stats_data)
    except Exception as e:
        print(f'[_build_eld_statistics_json] error: {e}')
        traceback.print_exc()
        return None

def run_eld_proc(model_config, task_id, model_id, user_req, thread_id):
    """原 run_test_server.run_eld 的独立进程版本。"""
    model_name = model_config['info']['model_name']
    api_url = model_config['config']['api_params_available'][0]['endpoint']
    limit = get_limit(user_req.get('limit'))
    eval_batch_size = user_req.get('eval_batch_size')
    dataset_args = user_req['dataset_args']
    api_key = (model_config['config']['api_params_available'][0]['api_key'] if model_config['config']['api_params_available'][0]['api_key'] else 'EMPTY',)
    gen_cfg = extract_generation_config(user_req)
    gen_temperature = gen_cfg.get('temperature')
    temperature = gen_temperature if gen_temperature is not None else user_req.get('temperature')
    retry_content_none = user_req.get('retry_content_none')
    use_cache = user_req.get('use_cache')
    retry_enabled = retry_content_none is not None and bool(use_cache)
    try:
        output_path = f'outputs/{model_id}/{task_id}'
        for arg in dataset_args:
            dataset_name = arg['dataset_name']
            user_prompt = arg['user_prompt']
            sys_prompt = arg['system_prompt']
            subset_list = arg['subset_list']
            arg_gen = extract_generation_config({'dataset_args': [arg]})
            max_tokens = arg_gen.get('max_tokens', gen_cfg.get('max_tokens', 8192))
            dataset_dir = os.path.join(ELD_DATASET_PATH, dataset_name)
            image_zip_path = None
            excel_path = None
            if os.path.exists(dataset_dir):
                for filename in os.listdir(dataset_dir):
                    filepath = os.path.join(dataset_dir, filename)
                    if os.path.isfile(filepath):
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in ('.zip', '.rar'):
                            image_zip_path = filepath
                        elif ext == '.xlsx':
                            excel_path = filepath
            if image_zip_path is None:
                raise FileNotFoundError(f'在数据集目录 {dataset_dir} 中未找到压缩包文件')
            if excel_path is None:
                raise FileNotFoundError(f'在数据集目录 {dataset_dir} 中未找到Excel文件')
            unzip_if_needed(image_zip_path, dataset_dir)
            task_config = {'model_name': model_name, 'api_url': api_url, 'body': model_config['config']['api_params_available'][0]['body'] if not model_config['config']['api_params_available'][0]['is_openai_format'] else '', 'excel_path': excel_path, 'output_path': output_path, 'user_prompt': user_prompt, 'sys_prompt': sys_prompt, 'task_id': task_id, 'eval_batch_size': eval_batch_size, 'subset_list': subset_list, 'api_key': api_key, 'retry_content_none': retry_content_none if retry_enabled else False, 'retry_enabled': retry_enabled, 'top_p': arg_gen.get('top_p', gen_cfg.get('top_p')), 'top_k': arg_gen.get('top_k', gen_cfg.get('top_k')), 'chat_template_kwargs': arg_gen.get('chat_template_kwargs', gen_cfg.get('chat_template_kwargs'))}
            run_custom_posture_eval(task_config, dataset_name, limit, thread_id, temperature, max_tokens)
            model_name_safe = model_name.replace('/', '_').replace('\\', '_')
            _build_eld_statistics_json(output_path, model_name_safe, dataset_name, task_id, subset_list, limit)
        finalize_task(task_id, model_name, model_id)
        print('run_eld_proc over')
    except Exception as e:
        print(f'run_eld_proc error:{e}')
        traceback.print_exc()
        finalize_task(task_id, model_name, model_id, error=str(e))

if __name__ == '__main__':
    cfg = parse_config()
    run_eld_proc(model_config=cfg.get('model_config'), task_id=cfg.get('task_id'), model_id=cfg.get('model_id'), user_req=cfg.get('user_req'), thread_id=cfg.get('thread_id'))
