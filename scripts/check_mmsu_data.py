"""MMSU 数据集完整性校验（只读，不修改任何数据）。

对齐官方 mmsu_inference.py / mmsu_evaluation.py 的假设，逐条验证：
1. 三个 parquet 分片行数合计是否为 5000；
2. task_name / category 分布是否与 mmsu_task_counts.csv、论文一致；
3. answer_gt 是否能唯一映射到 A/B/C/D（官方按「选项文本相等」判分，映射失败即无法计分）；
4. choice_c / choice_d 是否有空值（官方用 .get(..., '') 兜底）；
5. 同一题内是否存在重复选项文本（会造成两个字母都对，影响口径）；
6. audio 字节是否非空，以及文件头真实格式分布（上游扩展名不可信）。

用法：
    python scripts/check_mmsu_data.py --root "F:\\AI lab\\mmsu"
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import struct
import sys
from pathlib import Path

import pyarrow.parquet as pq

LETTERS = ('A', 'B', 'C', 'D')


def sniff_audio(data: bytes) -> str:
    """按文件头判断真实音频容器，而不是相信扩展名。"""
    if len(data) < 12:
        return 'too-short'
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return 'wav'
    if data[:3] == b'ID3':
        return 'mp3'
    if data[:4] == b'fLaC':
        return 'flac'
    if data[:4] == b'OggS':
        return 'ogg'
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return 'mp3-frames'
    return 'unknown'


def wav_sample_rate(data: bytes) -> int | None:
    """从 RIFF/WAVE 的 fmt 块读采样率。"""
    if len(data) < 28 or data[:4] != b'RIFF':
        return None
    pos = 12
    while pos + 8 <= len(data):
        chunk_id = data[pos:pos + 4]
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        if chunk_id == b'fmt ' and pos + 8 + 16 <= len(data):
            return struct.unpack('<I', data[pos + 8 + 4:pos + 8 + 8])[0]
        pos += 8 + size + (size & 1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=r'F:\AI lab\mmsu')
    parser.add_argument('--audio-sample', type=int, default=200, help='抽样检查音频的条数')
    args = parser.parse_args()

    root = Path(args.root)
    parquets = sorted((root / 'data').glob('train-*.parquet'))
    if not parquets:
        print(f'[FAIL] 没找到 parquet: {root / "data"}')
        return 1

    text_cols = ['id', 'task_name', 'question', 'choice_a', 'choice_b', 'choice_c', 'choice_d',
                 'answer_gt', 'category', 'sub-category']
    total = 0
    task_counter = collections.Counter()
    category_counter = collections.Counter()
    unmappable: list[tuple[str, str, str]] = []
    empty_c = 0
    empty_d = 0
    dup_choice = 0
    ids: set[str] = set()
    dup_id = 0
    audio_paths = 0
    audio_formats = collections.Counter()
    sample_rates = collections.Counter()
    audio_bytes_total = 0
    missing_cols: set[str] = set()

    for path in parquets:
        pf = pq.ParquetFile(path)
        names = set(pf.schema_arrow.names)
        missing_cols |= {c for c in text_cols if c not in names}
        for group in range(pf.metadata.num_row_groups):
            table = pf.read_row_group(group, columns=[c for c in text_cols if c in names])
            for row in table.to_pylist():
                total += 1
                task_counter[row.get('task_name')] += 1
                category_counter[row.get('category')] += 1
                rid = row.get('id') or ''
                if rid in ids:
                    dup_id += 1
                ids.add(rid)
                if not row.get('choice_c'):
                    empty_c += 1
                if not row.get('choice_d'):
                    empty_d += 1
                choices = [row.get('choice_a'), row.get('choice_b'), row.get('choice_c'), row.get('choice_d')]
                texts = [c for c in choices if c]
                if len(set(texts)) != len(texts):
                    dup_choice += 1
                gt = row.get('answer_gt')
                if gt not in texts:
                    unmappable.append((rid, str(gt), ' | '.join(str(t) for t in texts)))

    # 音频抽样：读首个行组，抽 N 条
    for path in parquets[:1]:
        pf = pq.ParquetFile(path)
        table = pf.read_row_group(0, columns=['audio'])
        for row in table.to_pylist()[: args.audio_sample]:
            audio = row.get('audio') or {}
            data = audio.get('bytes') or b''
            if audio.get('path'):
                audio_paths += 1
            audio_bytes_total += len(data)
            fmt = sniff_audio(data)
            audio_formats[fmt] += 1
            if fmt == 'wav':
                sr = wav_sample_rate(data)
                if sr:
                    sample_rates[sr] += 1

    print('=' * 62)
    print(f'parquet 分片      : {len(parquets)}  ({", ".join(p.name for p in parquets)})')
    print(f'总行数            : {total}')
    print(f'唯一 id           : {len(ids)}   重复 id: {dup_id}')
    print(f'task_name 数量    : {len(task_counter)}')
    print(f'category 分布     : {dict(category_counter)}')
    print(f'choice_c 为空     : {empty_c}')
    print(f'choice_d 为空     : {empty_d}')
    print(f'题内重复选项文本  : {dup_choice}')
    print(f'answer_gt 无法映射: {len(unmappable)}')
    if missing_cols:
        print(f'[WARN] 缺列        : {sorted(missing_cols)}')
    print(f'音频抽样          : {sum(audio_formats.values())} 条, path 非空 {audio_paths}, '
          f'平均 {audio_bytes_total / max(1, sum(audio_formats.values())) / 1024:.0f} KB')
    print(f'音频真实格式      : {dict(audio_formats)}')
    if sample_rates:
        print(f'WAV 采样率        : {dict(sample_rates)}')

    # 与官方 task_counts.csv 对照
    csv_path = root / 'mmsu_task_counts.csv'
    if csv_path.is_file():
        with csv_path.open(encoding='utf-8-sig') as fh:
            expected = {r['task_name']: int(r['count']) for r in csv.DictReader(fh)}
        diff = {k: (expected.get(k), task_counter.get(k)) for k in set(expected) | set(task_counter)
                if expected.get(k) != task_counter.get(k)}
        print(f'与 task_counts.csv 差异: {diff if diff else "无"}')

    print('=' * 62)
    ok = True
    if total != 5000:
        print(f'[FAIL] 行数应为 5000，实际 {total}')
        ok = False
    if len(task_counter) != 47:
        print(f'[FAIL] task_name 应为 47，实际 {len(task_counter)}')
        ok = False
    if unmappable:
        print(f'[FAIL] 有 {len(unmappable)} 条 answer_gt 无法映射到选项，官方口径无法计分，示例：')
        for rid, gt, texts in unmappable[:5]:
            print(f'   {rid}: answer_gt={gt!r} choices={texts!r}')
        ok = False
    if dup_id:
        print(f'[WARN] 存在 {dup_id} 个重复 id')
    if ok:
        print('[PASS] 数据可用于官方口径评测')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
