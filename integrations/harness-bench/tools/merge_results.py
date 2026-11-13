#!/usr/bin/env python3
"""合并新旧两次 HarnessBench 结果,输出完整 274 题统计。

用法:
  .venv/bin/python tools/merge_results.py <旧summary.json> <新summary.json>
"""
import json
import sys
from collections import Counter

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    old = load(sys.argv[1])
    new = load(sys.argv[2])

    # 按 task_id 合并,新结果优先(理论上无重叠)
    merged = {}
    for t in old.get("tasks", []):
        merged[t["task_id"]] = t
    for t in new.get("tasks", []):
        merged[t["task_id"]] = t

    tasks = list(merged.values())
    total = len(tasks)
    completed = [t for t in tasks if t.get("status") == "completed"]
    passed = [t for t in completed if t.get("task_success")]
    failed = [t for t in completed if not t.get("task_success")]

    scores = [t.get("outcome_score", 0.0) for t in completed]
    mean = sum(scores) / len(scores) if scores else 0.0
    median = sorted(scores)[len(scores) // 2] if scores else 0.0
    full = [s for s in scores if s >= 1.0]

    sg_failed = [t for t in completed if t.get("safety_gate_failed")]
    rf = Counter(t.get("review_flag", "") for t in failed)

    print("=" * 60)
    print("HarnessBench 合并结果(qwen3.8-27b + openjiuwen)")
    print("=" * 60)
    print(f"总题数           : {total}")
    print(f"已完成           : {len(completed)}")
    print(f"未完成/异常      : {total - len(completed)}")
    print()
    print(f"通过(task_success): {len(passed)}/{len(completed)} = {len(passed)/len(completed):.4f}" if completed else "无 completed 题")
    print(f"满分(outcome=1.0) : {len(full)}/{len(completed)} = {len(full)/len(completed):.4f}" if completed else "")
    print(f"outcome_score 均值: {mean:.4f}")
    print(f"outcome_score 中位数: {median:.4f}")
    print()
    print(f"安全闸失败(safety_gate): {len(sg_failed)} 题")
    if sg_failed:
        for t in sg_failed:
            print(f"  - {t['task_id']}")
    print()
    print("失败题 review_flag 分布:")
    for k, v in rf.most_common():
        print(f"  {k!r}: {v}")

    # 难度分层(可选)
    by_diff = Counter()
    for t in completed:
        by_diff[t.get("difficulty", "?")] += 1
    print()
    print("已完成题难度分布:")
    for k in sorted(by_diff):
        print(f"  {k}: {by_diff[k]}")

    # 输出合并后的完整 json 供后续使用
    out = {**new, "tasks": sorted(tasks, key=lambda t: t["task_id"])}
    out["counts"] = {
        "completed": len(completed),
        "total_merged": total,
    }
    with open("/tmp/hb_merged_summary.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print()
    print("完整合并 JSON 已写 /tmp/hb_merged_summary.json")

if __name__ == "__main__":
    main()
