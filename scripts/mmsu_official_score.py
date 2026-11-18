"""用官方算法对 MMSU 预测结果复算分数，保证与官方口径完全同分母。

背景：官方 `mmsu_evaluation.py` 对「无法解析出 A/B/C/D」的回复直接 `continue`，
**不计入分母**；而 evalscope 的 AverageAccuracy 会把这类样本按 0 分计入分母。
两者在模型格式遵循度差的时候会给出不同数值。

本脚本按官方实现逐行复刻，输入是官方格式的 JSONL（每条至少含
response / choice_a / choice_b / choice_c / choice_d / answer_gt / category / sub-category），
输出整体准确率、按大类（category）与按子类（sub-category）的准确率，以及被丢弃的条数。

用法：
    python scripts/mmsu_official_score.py predictions.jsonl
    python scripts/mmsu_official_score.py predictions.jsonl --json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys

LETTERS = ('A', 'B', 'C', 'D')


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path, 'r', encoding='utf-8') as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f'[WARN] 第 {lineno} 行不是合法 JSON，已跳过：{exc}', file=sys.stderr)
    return records


def score(records: list[dict]) -> dict:
    """完全按官方 mmsu_evaluation.py 的逻辑计分。"""
    by_task = collections.defaultdict(lambda: collections.defaultdict(lambda: {'correct': 0, 'total': 0}))
    task_avg = collections.defaultdict(lambda: {'total_correct': 0, 'total_count': 0})
    total_correct = 0
    total_count = 0
    dropped = 0

    for record in records:
        task = record.get('category', '')
        category = record.get('sub-category', '')
        response = record.get('response', '')
        predict = str(response).strip().replace('\n', '')
        model_predict = None

        if predict != 'None' and predict:
            if predict[0] in LETTERS:
                model_predict = predict[0]
            elif len(predict) > 1:
                if predict[-2] in LETTERS:
                    model_predict = predict[-2]
                else:
                    dropped += 1
                    continue
            else:
                dropped += 1
                continue
        # 注意：空回复与字面量 'None' 不丢弃——官方会照常计入分母（但不得分）。
        # 只有「无法解析出 A/B/C/D」的格式错误才 continue 丢弃。

        choices = {'A': record.get('choice_a', ''), 'B': record.get('choice_b', ''),
                   'C': record.get('choice_c', ''), 'D': record.get('choice_d', '')}
        answer_gt = record.get('answer_gt', '')

        by_task[task][category]['total'] += 1
        task_avg[task]['total_count'] += 1
        total_count += 1
        if model_predict and choices[model_predict] == answer_gt:
            by_task[task][category]['correct'] += 1
            task_avg[task]['total_correct'] += 1
            total_correct += 1

    task_category_accuracy = {}
    for task, categories in by_task.items():
        task_category_accuracy[task] = {}
        for category, counts in categories.items():
            task_category_accuracy[task][category] = (counts['correct'] / counts['total']
                                                      if counts['total'] else 0.0)

    task_average_accuracy = {}
    for task, counts in task_avg.items():
        task_average_accuracy[task] = (counts['total_correct'] / counts['total_count']
                                       if counts['total_count'] else 0.0)

    overall = total_correct / total_count if total_count else 0.0
    return {
        'overall_accuracy': overall,
        'total_count': total_count,
        'total_correct': total_correct,
        'dropped_unparseable': dropped,
        'category_accuracy': task_average_accuracy,
        'task_category_accuracy': task_category_accuracy,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('jsonl')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出')
    args = parser.parse_args()

    result = score(load_jsonl(args.jsonl))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    for task, acc in result['category_accuracy'].items():
        print(f'Category: {task}, Average Accuracy: {acc:.4f}')
    for task, categories in result['task_category_accuracy'].items():
        for category, acc in categories.items():
            print(f'Category: {task}, Sub-category: {category}, Accuracy: {acc:.4f}')
    print(f"Overall Accuracy: {result['overall_accuracy']:.4f}")
    print(f"Total count: {result['total_count']}"
          f"（另有 {result['dropped_unparseable']} 条格式错误被丢弃，与官方一致）")
    return 0


if __name__ == '__main__':
    sys.exit(main())
