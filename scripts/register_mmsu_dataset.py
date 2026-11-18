"""把 MMSU 注册进 Yellow 的公开数据集清单（seed + 现有工作空间）。

做三件事，全部幂等：
1. 在 `backend/yellow/seed/common_testcase_cfg.json` 增加/更新 `mmsu` 条目；
2. 把同一条目写入当前管理员工作空间的 `backend/config/common_testcase_cfg.json`
   （该文件在 `.state.sqlite3` 里，必须走 state_storage 读写）；
3. 在 `testsuite/TestSuite/mmsu` 建一个指向官方数据目录的 junction，避免复制 1.4GB。
   已存在同名目录/链接时跳过。

用法：
    python scripts/register_mmsu_dataset.py --data-root "F:\\AI lab\\mmsu\\data"
    python scripts/register_mmsu_dataset.py --data-root ... --no-link   # 只注册不建链接
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / 'backend'
WORKSPACE = BACKEND / 'data' / 'yellow' / 'users' / '8c6976e5b5410415bde908bd'

MMSU_ENTRY = {
    "dataset_name": "mmsu",
    "local_path": "./testsuite/TestSuite/mmsu",
    "few_shot_num": 0,
    "few_shot_file_path": [],
    "description": "MMSU 语音理解基准（ICLR 2026）：5000 道四选一听觉题，覆盖 47 个子任务，Perception 2580 + Reasoning 2420。题目需听取音频作答，仅支持音频输入的模型可评测。",
    "subset_list": [],
    "default_subsets": [],
    "metric_list": ["AverageAccuracy"],
    "testcase_tags": ["语音", "多模态"],
    "content": "",
    "establish_time": "2026-11-18 10:00:00",
    "is_open_source": True,
    "need_llmjudge": False,
    "file_list": [
        "train-00000-of-00003.parquet",
        "train-00001-of-00003.parquet",
        "train-00002-of-00003.parquet",
    ],
    "few_file_list": [],
    "is_field": "1",
    "status": 1,
    "dataSet_cases": "5000",
    "system_prompt": "",
    "user_prompt": "",
    "viewer_users": [],
    "editor_users": [],
    "register": "admin",
    "is_published": True,
    "availability": "ready",
}


def update_json_file(path: Path, entry: dict) -> str:
    cfg = json.loads(path.read_text('utf-8'))
    action = 'updated' if entry['dataset_name'] in cfg else 'added'
    cfg[entry['dataset_name']] = entry
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return action


def update_workspace(entry: dict) -> str:
    sys.path.insert(0, str(BACKEND))
    import state_storage as ss

    base = BACKEND / 'data' / 'yellow'
    ss.register_state_root(base)
    target = WORKSPACE / 'backend' / 'config' / 'common_testcase_cfg.json'
    cfg = ss.read_document(target)
    action = 'updated' if entry['dataset_name'] in cfg else 'added'
    cfg[entry['dataset_name']] = entry
    ss.write_document(target, cfg)
    return action


def ensure_link(data_root: Path) -> str:
    target = WORKSPACE / 'testsuite' / 'TestSuite' / 'mmsu'
    if target.exists() or target.is_symlink():
        return f'exists ({target})'
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(target), str(data_root)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            return f'FAILED: {result.stderr.strip() or result.stdout.strip()}'
        return f'junction -> {data_root}'
    target.symlink_to(data_root, target_is_directory=True)
    return f'symlink -> {data_root}'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', default=r'F:\AI lab\mmsu\data')
    parser.add_argument('--no-link', action='store_true')
    args = parser.parse_args()

    seed = BACKEND / 'yellow' / 'seed' / 'common_testcase_cfg.json'
    print(f'seed      : {update_json_file(seed, MMSU_ENTRY)} -> {seed}')
    print(f'workspace : {update_workspace(MMSU_ENTRY)} -> {WORKSPACE}')

    if not args.no_link:
        print(f'data link : {ensure_link(Path(args.data_root))}')

    # 回读校验
    cfg = json.loads(seed.read_text('utf-8'))
    print(f'校验      : seed 共 {len(cfg)} 个数据集，mmsu={"mmsu" in cfg}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
