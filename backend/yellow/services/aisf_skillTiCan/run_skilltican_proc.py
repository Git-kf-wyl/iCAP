# Private iCAP Yellow business implementation. Do not publish.
"""skill提参 —— 独立子进程入口（壳封装）。

由 run_test_server.py 以 subprocess 方式启动，取代service进程内运行方式，
使该测评任务的存活不再依赖 flask 服务进程（与 aisf_gaixie 等业务一致）。

设计原则：不改动原工程业务逻辑（skill/multi_test_v11.py 原样保留），
本文件仅做"壳封装"：
  1. 将项目根目录与业务源码目录加入 sys.path；
  2. 解析 --config 传入的运行参数（model_config / task_id / user_req 等）；
  3. 把前端参数注入业务模块的模块级配置（MODEL_NAME/API/EXCEL_PATH/SKILL_MD_PATH_MAP 等）；
  4. 调用 skill.multi_test_v11.main() 执行提参+判定，产出 明细excel + 逐条jsonl；
  5. 由本文件兜底生成 总体结果json 与 日志，并 finalize_task 收尾任务状态。
"""
from state_storage import open_state, state_exists, state_isfile
import os
import sys
import json
import time
import traceback
from datetime import datetime
import pandas as pd

def _find_project_root():
    """向上查找项目根目录（run_test_server.py + services 所在），供 import 项目模块。"""
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if state_isfile(os.path.join(d, 'run_test_server.py')) and os.path.isdir(os.path.join(d, 'services')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
_PROJECT_ROOT = _find_project_root()
if _PROJECT_ROOT and _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skill')
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)
from utils.consts import SKILLTICAN_DATASET_PATH
from utils.eval_utils import get_limit
from services.custom_proc_common import parse_config, finalize_task, extract_generation_config
from services.aisf_skillTiCan.skill import multi_test_v11 as skill_biz
from services.aisf_skillTiCan.skill import prompt_v18 as skill_prompt
_DEFAULT_SKILL_MD_MAP = {'iot_control_skill': os.path.join(_SKILL_DIR, 'skill_IOT_v1.md'), 'health-register': os.path.join(_SKILL_DIR, 'skill_health_registered_v5.md'), 'health_take_medicine_skill': os.path.join(_SKILL_DIR, 'skill_take_medicine_v13.md')}

def _find_dataset_xlsx(dataset_dir):
    """在数据集目录下寻找第一个 .xlsx 测试集文件。"""
    if not os.path.isdir(dataset_dir):
        return None
    for fname in os.listdir(dataset_dir):
        fpath = os.path.join(dataset_dir, fname)
        if state_isfile(fpath) and os.path.splitext(fname)[1].lower() == '.xlsx':
            return fpath
    return None

def _write_report_json(report_dir, dataset_name, model_name, summary, result_df):
    """生成总体结果 json（供前端 /v1/get_file_path / update_eval_res 读分）。"""
    os.makedirs(report_dir, exist_ok=True)
    total = int(summary.get('总用例数', 0))
    strict_acc = float(summary.get('严格通过率', 0) or 0)
    loose_acc = float(summary.get('宽松通过率', 0) or 0)
    report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': round(strict_acc, 2), 'metrics': [{'categories': [{'macro_score': round(strict_acc, 2), 'name': ['skill提参'], 'num': total, 'score': round(strict_acc, 2), 'subsets': [{'name': '宽松通过率', 'num': total, 'score': round(loose_acc, 2), 'correct_num': int(summary.get('宽松通过数', 0))}]}], 'macro_score': round(strict_acc, 2), 'name': 'skill提参', 'num': total, 'score': round(strict_acc, 2)}], 'summary': summary}
    report_file = os.path.join(report_dir, f'{dataset_name}.json')
    with open_state(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_map, f, ensure_ascii=False, indent=4)
    return report_file

def run_skilltican_proc(model_config, task_id, model_id, user_req, thread_id):
    model_name = model_config['info']['model_name']
    api_params = model_config['config']['api_params_available'][0]
    api_url = api_params['endpoint']
    api_key = api_params.get('api_key') or 'EMPTY'
    limit = get_limit(user_req.get('limit'))
    generate_config = extract_generation_config(user_req)
    gen_temperature = generate_config.get('temperature')
    temperature = gen_temperature if gen_temperature is not None else user_req.get('temperature')
    eval_batch_size = user_req.get('eval_batch_size')
    dataset_args = user_req['dataset_args']
    output_path = f'outputs/{model_id}/{task_id}'
    log_dir = os.path.join(output_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    def log(msg):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
    try:
        log(f'skill提参 process 启动 (model={model_name}, task_id={task_id})')
        log(f'  api_url:      {api_url}')
        log(f'  api_key:      {api_key[:8]}...')
        log(f'  temperature:  {temperature}')
        log(f'  limit:        {limit}')
        for arg in dataset_args:
            dataset_name = arg['dataset_name']
            dataset_dir = os.path.join(SKILLTICAN_DATASET_PATH, dataset_name)
            excel_path = _find_dataset_xlsx(dataset_dir)
            if not excel_path:
                raise FileNotFoundError(f'在数据集目录 {dataset_dir} 下未找到 xlsx 测试集文件')
            review_dir = os.path.join(output_path, 'reviews', model_id)
            report_dir = os.path.join(output_path, 'reports', model_id)
            os.makedirs(review_dir, exist_ok=True)
            os.makedirs(report_dir, exist_ok=True)
            output_xlsx = os.path.join(review_dir, f'{dataset_name}_{task_id}.xlsx')
            jsonl_path = os.path.join(review_dir, f'{dataset_name}.jsonl')
            skill_md_map = dict(_DEFAULT_SKILL_MD_MAP)
            skill_md_map.update(generate_config.get('skill_md_path_map', {}) or {})
            skill_biz.MODEL_NAME = model_name
            skill_biz.API_BASE_URL = api_url
            skill_biz.API_KEY = api_key or skill_biz.API_KEY
            skill_biz.TEMPERATURE = temperature if temperature is not None else skill_biz.TEMPERATURE
            skill_biz.LIMIT = limit
            skill_biz.EXCEL_PATH = excel_path
            skill_biz.OUTPUT_PATH = output_xlsx
            skill_biz.SKILL_MD_PATH_MAP = skill_md_map
            if eval_batch_size is not None:
                try:
                    skill_biz.MAX_WORKERS = int(eval_batch_size)
                except (ValueError, TypeError):
                    pass
            if 'sheet_name' in generate_config:
                skill_biz.SHEET_NAME = generate_config['sheet_name']
            for opt in ('MAX_WORKERS', 'MOCK_MODE', 'FLATTEN_TOOL_MESSAGES', 'TIMEOUT', 'ENABLE_IOT_SEMANTIC_JUDGE', 'JUDGE_TEMPERATURE', 'DEBUG_PRINT_MESSAGES', 'PRINT_MODEL_OUTPUT', 'PRINT_EACH_RESULT', 'PRINT_FAILED_DETAIL', 'JUDGE_API_BASE_URL', 'JUDGE_API_KEY', 'JUDGE_MODEL_NAME'):
                if opt in generate_config:
                    setattr(skill_biz, opt, generate_config[opt])
            skill_biz.SAVE_JSONL_EVERY_CASE = True
            skill_biz.JSONL_LOG_PATH = jsonl_path
            if state_exists(jsonl_path):
                os.remove(jsonl_path)
            log(f'export: excel={output_xlsx}')
            log(f'export: jsonl(raw→review 同文件)={jsonl_path}')
            log(f'export: skill_md_map={json.dumps(skill_md_map, ensure_ascii=False)}')
            log('开始执行业务 main() ...')
            start = time.time()
            skill_biz.main()
            elapsed = time.time() - start
            log(f'业务 main() 执行完成，耗时 {elapsed:.2f}s')
            _convert_to_review_jsonl(jsonl_path, dataset_name=dataset_name)
            log(f'export: jsonl(review)={jsonl_path}')
            summary = _build_summary(output_xlsx, jsonl_path)
            log(f'summary: {json.dumps(summary, ensure_ascii=False)}')
            report_file = _write_report_json(report_dir, dataset_name, model_name, summary, None)
            log(f'export: report json={report_file}')
        finalize_task(task_id, model_name, model_id)
    except Exception as e:
        log(f'run_skilltican_proc error: {e}')
        traceback.print_exc()
        finalize_task(task_id, model_name, model_id, error=str(e))

def _sanitize(value):
    """递归地把 NaN / nan / None / inf 等非 JSON 合法值清理掉。

    Excel 对应列无值时，pandas 读入的是 NaN（np.nan / float('nan')），
    业务按原样写入 jsonl，导致 json.dumps 序列化成 NaN 引发 JSON 解析失败。
    此处对 float 类型的 NaN/inf 与 Python None 统一转为 ""；list/dict 递归处理。
    """
    if value is None:
        return ''
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            return ''
        return value
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    return value

def _convert_to_review_jsonl(jsonl_path, dataset_name=''):
    """把业务产出的原始记录 jsonl 原位转换为前端使用的逐条 review jsonl。

    业务以 append 模式把每条原始记录（含 Excel 整行字段）写入 jsonl_path，
    本函数读取全部后再原地覆盖为 review 格式（因此不再单独产出 _raw.jsonl 中间文件）。

    格式与 aisf_gaixie/multi_test.py 生成的 review jsonl 基本一致：
      - raw_input: {Question, expected, prompt, context, No}
      - choices:   [{review: {gold, pred, result, <skill额外字段>...}, message: {content}}]
      - index / dialogue_round / subset_name / usage / response_time
      - excel_info: 原测试集 Excel 中该用例对应列的值：记忆信息/当前位置/当前日期/
                    skill选择结果/上游查询结果
    额外想记录的东西都放进 choices[0].review / excel_info，方便前端和后续统计读取。

    原始记录里没有 token / 时延，usage 与 response_time 置为 0（缺失字段不会破坏兼容）。
    """
    if not state_exists(jsonl_path):
        raise FileNotFoundError(f'找不到业务原始 jsonl: {jsonl_path}')

    def _first_msg(messages):
        return (messages or [{}])[0].get('content', '')
    review_lines = []
    idx = 0
    with open_state(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rec = _sanitize(rec)
            try:
                messages = json.loads(rec.get('messages') or '[]')
            except Exception:
                messages = []
            system_prompt = _first_msg(messages)
            message_context = '\n'.join((f"[{m.get('role')}]: {m.get('content')}" for m in messages[1:] if isinstance(m, dict)))
            query_assistant_pairs = []
            for i in range(1, 6):
                q = rec.get(f'query{i}')
                a = rec.get(f'assistant{i}')
                if q:
                    query_assistant_pairs.append(f'[user]: {q}')
                if a:
                    query_assistant_pairs.append(f'[assistant]: {a}')
            explicit_pairs = '\n'.join(query_assistant_pairs)
            if explicit_pairs:
                context = (explicit_pairs + '\n' + message_context).strip()
            else:
                context = message_context
            current_input = str(rec.get('当前用户输入') or rec.get('Query') or '')
            expected = rec.get('期望输出') or rec.get('期望结果') or ''
            excel_info = {'记忆信息': rec.get('记忆信息', ''), '当前位置': rec.get('当前位置', ''), '当前日期': rec.get('当前日期', ''), 'skill选择结果': rec.get('skill选择结果', ''), '上游查询结果': rec.get('上游查询结果', '')}
            model_output = rec.get('model_output') or ''
            is_pass = bool(rec.get('是否通过', False))
            loose_pass = bool(rec.get('是否宽松通过', False))
            case_id = str(rec.get('case_id') or '')
            row_index = rec.get('row_index', idx)
            review_lines.append({'raw_input': {'Question': current_input, 'expected': str(expected), 'prompt': system_prompt, 'context': context, 'No': row_index}, 'excel_info': excel_info, 'choices': [{'review': {'gold': expected, 'pred': model_output, 'result': '1' if is_pass else '0', 'loose_result': '1' if loose_pass else '0', '判定结果': rec.get('判定结果', '不通过'), '宽松判定结果': rec.get('宽松判定结果', '不通过'), 'error_reason': rec.get('error_reason', ''), 'loose_error_reason': rec.get('loose_error_reason', ''), 'model_json': rec.get('model_json', ''), '是否经过模型阅卷': rec.get('是否经过模型阅卷', '否'), 'case_id': case_id}, 'message': {'content': model_output}}], 'index': row_index if isinstance(row_index, int) else idx, 'dialogue_round': case_id or str(row_index if isinstance(row_index, int) else idx), 'subset_name': dataset_name or 'skill提参', 'usage': {'prompt_tokens': rec.get('input_tokens', 0) or 0, 'completion_tokens': rec.get('output_tokens', 0) or 0, 'total_tokens': rec.get('total_tokens', 0) or 0}, 'response_time': rec.get('model_elapsed_time', 0) or 0})
            idx += 1
    with open_state(jsonl_path, 'w', encoding='utf-8') as f:
        for line in review_lines:
            f.write(json.dumps(line, ensure_ascii=False) + '\n')

def _build_summary(output_xlsx, jsonl_path):
    """从 review jsonl（每用例一条记录，格式与 aisf_gaixie 一致）统计总体指标。

    优先读 jsonl（结果在 choices[0].review 的 result / loose_result 逐条字段）；
    若缺失则退回到 excel。
    返回 dict：{总用例数, 严格通过数, 严格通过率, 宽松通过数, 宽松通过率}
    """
    total = strict_ok = loose_ok = 0
    if state_exists(jsonl_path):
        with open_state(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                total += 1
                choice = (rec.get('choices') or [{}])[0]
                review = choice.get('review') or {}
                if review.get('result') == '1':
                    strict_ok += 1
                if review.get('loose_result') == '1':
                    loose_ok += 1
        if total > 0:
            return {'总用例数': total, '严格通过数': strict_ok, '严格通过率': round(strict_ok / total, 4), '宽松通过数': loose_ok, '宽松通过率': round(loose_ok / total, 4)}
    if state_exists(output_xlsx):
        try:
            df = pd.read_excel(output_xlsx, sheet_name='明细结果', dtype=str)
            total = len(df)
            strict_ok = int(df.get('是否通过', pd.Series([False])).fillna(False).astype(bool).sum())
            loose_ok = int(df.get('是否宽松通过', pd.Series([False])).fillna(False).astype(bool).sum())
            return {'总用例数': total, '严格通过数': strict_ok, '严格通过率': round(strict_ok / total, 4) if total else 0, '宽松通过数': loose_ok, '宽松通过率': round(loose_ok / total, 4) if total else 0}
        except Exception:
            pass
    return {'总用例数': 0, '严格通过数': 0, '严格通过率': 0, '宽松通过数': 0, '宽松通过率': 0}

if __name__ == '__main__':
    cfg = parse_config()
    run_skilltican_proc(model_config=cfg.get('model_config'), task_id=cfg.get('task_id'), model_id=cfg.get('model_id'), user_req=cfg.get('user_req'), thread_id=cfg.get('thread_id'))
