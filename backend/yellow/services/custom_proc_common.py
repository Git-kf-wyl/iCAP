# Private iCAP Yellow business implementation. Do not publish.
"""独立子进程通用引导模块。

供 run_eld_proc.py / run_yitu_proc.py / run_memory_proc.py / run_gaixie_proc.py
这类由 run_test_server.py 以 subprocess 方式启动的特殊业务进程共用。

职责：
  1. 将项目根目录加入 sys.path，使子进程可以 import services.* / utils.* / call_api。
  2. 读取 --config <tmp.json> 传入的运行参数。
  3. 通过 backend/config/tasks.json 跨进程读写任务状态（与上层 RULER 子进程一致）。
"""
from state_storage import open_state, state_exists, state_isfile
import json
import os
import platform
import sys
import time
_PROC_START = time.time()

def _find_import_root():
    """向上查找 backend 目录（services/utils/call_api 所在），供子进程 import 项目模块。"""
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(d, 'services')) and state_isfile(os.path.join(d, 'run_test_server.py')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
_IMPORT_ROOT = _find_import_root()
if _IMPORT_ROOT and _IMPORT_ROOT not in sys.path:
    sys.path.insert(0, _IMPORT_ROOT)
from utils.utils import get_tasks, set_tasks
from utils.eval_utils import update_eval_res

def parse_config():
    """解析 --config <tmp.json>，返回运行参数字典。

    兼容 Windows（--config 临时文件）与非 Windows（stdin）两种传递方式，
    与 run_test_server.py 中 run_eval 的传参保持一致。
    """
    if len(sys.argv) < 3 or sys.argv[1] != '--config':
        raise ValueError('Usage: python script.py --config <config_file>')
    config_file = sys.argv[2]
    with open_state(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    return json.loads(content)

def extract_generation_config(user_req, default=None):
    """从 user_req 中提取并解析模型生成超参 dict。

    兼容 dataset_args[0] 上的 generate_config / generation_config 两种键，
    且兼容字符串与 dict 两种形态（前端以 JSON 字符串传入，例如
    {"max_tokens":40000,"chat_template_kwargs":{"enable_thinking":false},
     "top_p":1,"top_k":40,"temperature":0.7}）。

    返回 dict；未配置或解析失败时返回 default（默认 {}）。
    """
    if default is None:
        default = {}
    if not isinstance(user_req, dict):
        return dict(default)
    try:
        di = (user_req.get('dataset_args') or [{}])[0]
    except Exception:
        di = {}
    if not isinstance(di, dict):
        di = {}
    raw = di.get('generate_config')
    if raw is None:
        raw = di.get('generation_config')
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    if isinstance(raw, dict):
        return raw
    return dict(default)

def update_task(task_id, **kwargs):
    """读取 tasks.json，更新指定 task 的若干字段后写回。

    子进程的进度/状态都通过该函数落盘，供 Flask 服务端 /v1/get_test_tasks 轮询。
    """
    tasks = get_tasks()
    if task_id not in tasks:
        return
    tasks[task_id].update(kwargs)
    set_tasks(tasks)

def finalize_task(task_id, model_name, model_id, error=None):
    """子进程完成/失败时收尾任务条目。

    - 失败：置 status=failed + error。
    - 成功：置 progress=1.0，并通过 update_eval_res 从报告 JSON 反填各数据集分数、
      将 status 置为 completed。逻辑与原 run_ruler2_eval 末尾调用的 update_eval_res 一致，
      保证独立进程环境下前端仍能拿到分数。
    """
    if error:
        update_task(task_id, status='failed', error=str(error), runningTime=time.time() - _PROC_START)
        return
    tasks = get_tasks()
    if task_id not in tasks:
        return
    update_eval_res(tasks, task_id, model_name, model_id)
    update_task(task_id, runningTime=time.time() - _PROC_START)
