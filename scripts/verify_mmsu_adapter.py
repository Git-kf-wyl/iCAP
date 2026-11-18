"""MMSU 适配器与官方口径的一致性验证（不调用任何模型，不产生评测费用）。

验证五件事：
1. 适配器能被 evalscope 自动发现并注册为 benchmark `mmsu`；
2. `load()` 合并三个分片后是 5000 条（父类实现只会留最后一个分片的 1666 条）；
3. 提示词与官方 `mmsu_inference.py` 逐字符一致；
4. 端到端判分与官方 `mmsu_evaluation.py` 完全一致——包括**分母**（格式错误丢弃、
   空回复计错）；
5. 音频按官方口径转成 16kHz 单声道 WAV；subset 拆分可用。

用法：
    python scripts/verify_mmsu_adapter.py --root "F:\\AI lab\\mmsu"
"""
from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALSCOPE_ROOT = REPO / 'backend' / 'yellow' / 'CCNRuler1EvalScope'
sys.path.insert(0, str(EVALSCOPE_ROOT))

LETTERS = ('A', 'B', 'C', 'D')


def official_prompt(item: dict) -> str:
    question_prompts = ('Choose the most suitable answer from options A, B, C, and D. '
                        'You must respond with only A, B, C, or D.')
    choices = (f"A. {item.get('choice_a', '')}\n"
               f"B. {item.get('choice_b', '')}\n"
               f"C. {item.get('choice_c', '')}\n"
               f"D. {item.get('choice_d', '')}")
    return f"{question_prompts}\n\nQuestion: {item.get('question', '')}\n\n{choices}"


def official_parse(response: str) -> tuple[str, bool]:
    """复刻官方解析，返回 (字母或 '', 是否被判为格式错误丢弃)。"""
    predict = str(response).strip().replace('\n', '')
    if predict != 'None' and predict:
        if predict[0] in LETTERS:
            return predict[0], False
        if len(predict) > 1:
            if predict[-2] in LETTERS:
                return predict[-2], False
            return '', True
        return '', True
    return '', False  # 空/None：计入分母但不得分


def official_score(records: list[dict]) -> tuple[float, int]:
    """复刻 mmsu_evaluation.py，返回 (准确率, 计入分母的条数)。"""
    correct = 0
    counted = 0
    for record in records:
        letter, dropped = official_parse(record.get('response', ''))
        if dropped:
            continue
        choices = {'A': record.get('choice_a', ''), 'B': record.get('choice_b', ''),
                   'C': record.get('choice_c', ''), 'D': record.get('choice_d', '')}
        counted += 1
        if letter and choices[letter] == record.get('answer_gt', ''):
            correct += 1
    return (correct / counted if counted else 0.0), counted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=r'F:\AI lab\mmsu')
    args = parser.parse_args()

    from evalscope.benchmarks import Benchmark

    failures: list[str] = []

    # 1) 注册
    meta = Benchmark.get('mmsu')
    print(f'[1] 注册名={meta.name} dataset_id={meta.dataset_id} '
          f'metric={meta.metric_list} split={meta.eval_split}')
    if meta.dataset_id != 'ddwang2000/MMSU':
        failures.append('dataset_id 与官方仓库不一致')

    # 2) 加载
    adapter = meta.get_data_adapter({})
    loaded = adapter.load(str(Path(args.root) / 'data'), ['default'])
    rows = loaded['default']['train']
    print(f'[2] 载入条数={len(rows)}')
    if len(rows) != 5000:
        failures.append(f'载入条数应为 5000，实际 {len(rows)}')

    # 3) 提示词逐字比对
    mismatched = 0
    for row in rows[:200]:
        if adapter.gen_prompt(row, 'default', [])['data'][0] != official_prompt(row):
            mismatched += 1
    print(f'[3] 提示词不一致条数={mismatched} / 200')
    if mismatched:
        failures.append('提示词与官方不一致')

    # 4) 端到端判分 + 分母差分
    responses = ['A', 'B', 'B.', 'The answer is C.', 'answer is D', ' A ', 'None', '', 'E', 'AB',
                 'C', 'D.', 'I think D', '2', 'The correct choice is A because ...', 'B\n', 'D is right']
    sample_rows = rows[:300]
    reviews = []
    records = []
    for row in sample_rows:
        for response in responses:
            pred = adapter.parse_pred_result(response, row)
            reviews.append(adapter.match(adapter.get_gold_answer(row), pred))
            record = dict(row)
            record['response'] = response
            records.append(record)
    metrics = adapter.compute_metric(reviews)
    ours_score = next(m['score'] for m in metrics if m['metric_name'] == 'AverageAccuracy')
    ours_num = next(m['num'] for m in metrics if m['metric_name'] == 'AverageAccuracy')
    ref_score, ref_num = official_score(records)
    print(f'[4] 分母差分：我们 {ours_score:.6f} / n={ours_num}；官方 {ref_score:.6f} / n={ref_num}')
    if abs(ours_score - ref_score) > 1e-9 or ours_num != ref_num:
        failures.append('判分或分母与官方不一致')

    # 5a) 音频口径：应转成 16000Hz
    import numpy as np
    import soundfile as sf

    prompt = adapter.gen_prompt(rows[0], 'default', [])
    audio_part = next(p['input_audio'] for p in prompt['messages'][0]['content']
                      if p['type'] == 'input_audio')
    wav = base64.b64decode(audio_part['data'])
    array, rate = sf.read(io.BytesIO(wav), dtype='float32')
    print(f'[5] 音频：format={audio_part["format"]} 采样率={rate} 时长={len(array)/rate:.2f}s '
          f'（base64 {len(audio_part["data"])/1024:.0f}KB）')
    if audio_part['format'] != 'wav' or rate != 16000:
        failures.append('音频未按官方口径转为 16kHz WAV')
    if array.ndim != 1:
        failures.append('音频不是单声道')

    # 5b) subset 拆分
    keys = sorted({adapter.group_key(row) for row in rows})
    pick = keys[:3]
    split = adapter.load(str(Path(args.root) / 'data'), pick)
    counts = {k: len(v['train']) for k, v in split.items()}
    total_split = sum(counts.values())
    print(f'[5b] 分组键共 {len(keys)} 个，抽查 {pick} -> {counts}，合计 {total_split}')
    if set(split) != set(pick):
        failures.append('subset 拆分键不匹配')

    print('=' * 62)
    if failures:
        for item in failures:
            print(f'[FAIL] {item}')
        return 1
    print('[PASS] 适配器与官方口径完全一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
