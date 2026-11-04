# Private iCAP Yellow business implementation. Do not publish.
"""
总结过滤 Prompt 评测脚本
支持 v1.0 / v2.0 / v3.0 / v3.1 多版本对比评测

每条 case 按严重程度归入恰好一个桶：
  - 格式错误：输出无法解析
  - 漏提（严重）：该提的没提 (FN>0)，无论是否同时多提
  - 多提但提全：提全了但多带了无关记忆 (FN=0 且 FP>0)
  - 完全匹配：预测与参考答案完全一致
"""
import os, sys, re, json
import pandas as pd
input_path = '测试用例.xlsx'
EVAL_MODELS = ['qwen3-8b']
EVAL_VERSIONS = ['v1.0', 'v2.0', 'v3.0', 'v3.1']
RUN_SOURCES = None
BUCKET_LABELS = ['格式错误', '漏提（严重）', '多提但提全', '完全匹配']
DISPLAY_BUCKETS = BUCKET_LABELS

def col_name(model: str, ver: str) -> str:
    return f'answer_{model}_{ver}'

def parse_id_list(raw: str):
    """从模型输出中提取 ID 列表。返回 (id_list, is_valid)"""
    if raw is None or not isinstance(raw, str):
        return (None, False)
    text = raw.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            if all((isinstance(x, (int, float)) for x in obj)):
                return ([int(x) for x in obj], True)
            return (None, False)
        if isinstance(obj, dict):
            for key in ['输出', 'output', 'answer', 'ids']:
                if key in obj:
                    val = obj[key]
                    if isinstance(val, list):
                        if all((isinstance(x, (int, float)) for x in val)):
                            return ([int(x) for x in val], True)
                    if isinstance(val, str):
                        parsed = _extract_array_from_str(val)
                        if parsed is not None:
                            return (parsed, True)
            if 'memory_list' in obj:
                ids = []
                for item in obj['memory_list']:
                    if isinstance(item, dict) and 'id' in item:
                        ids.append(item['id'])
                if ids:
                    return (ids, True)
        return (None, False)
    except (json.JSONDecodeError, ValueError):
        pass
    lines = text.strip().split('\n')
    for line in reversed(lines):
        parsed = _extract_array_from_str(line.strip())
        if parsed is not None:
            return (parsed, True)
    parsed = _extract_array_from_str(text)
    if parsed is not None:
        return (parsed, True)
    return (None, False)

def _extract_array_from_str(s: str):
    """从字符串中提取 [数字,数字,...] 或 []"""
    match = re.search('\\[([0-9,\\s]*)\\]', s)
    if match:
        inner = match.group(1).strip()
        if inner == '':
            return []
        try:
            return [int(x.strip()) for x in inner.split(',') if x.strip() != '']
        except ValueError:
            return None
    return None

def classify(pred_ids, ref_ids, is_valid, has_run):
    """
    将单条 case 归入一个桶。
    has_run: bool, 该条是否已运行（raw 非 NaN）
    """
    if not has_run:
        return ('未运行', {'fn': 0, 'fp': 0, 'exact_match': False})
    if not is_valid or pred_ids is None:
        return ('格式错误', {'fn': len(ref_ids), 'fp': 0, 'exact_match': False})
    pred_set = set(pred_ids)
    ref_set = set(ref_ids)
    fn = len(ref_set - pred_set)
    fp = len(pred_set - ref_set)
    exact_match = pred_set == ref_set
    if fn > 0:
        return ('漏提（严重）', {'fn': fn, 'fp': fp, 'exact_match': False})
    elif fp > 0:
        return ('多提但提全', {'fn': 0, 'fp': fp, 'exact_match': True})
    else:
        return ('完全匹配', {'fn': 0, 'fp': 0, 'exact_match': True})

def build_stats(results_df: pd.DataFrame) -> dict:
    """对评测结果做桶分布统计（排除未运行的 case）"""
    valid_df = results_df[results_df['分类'] != '未运行']
    total = len(valid_df)
    if total == 0:
        return {}
    bucket_counts = valid_df['分类'].value_counts()
    stats = {'总样本数': total}
    not_run = len(results_df[results_df['分类'] == '未运行'])
    if not_run > 0:
        stats['未运行数'] = not_run
    for label in BUCKET_LABELS:
        count = int(bucket_counts.get(label, 0))
        stats[f'{label}数'] = count
        stats[f'{label}率'] = count / total
    leak_mask = valid_df['分类'] == '漏提（严重）'
    over_mask = valid_df['分类'] == '多提但提全'
    stats['漏提样本平均漏条数'] = valid_df.loc[leak_mask, 'fn'].mean() if leak_mask.any() else 0
    stats['多提样本平均多条数'] = valid_df.loc[over_mask, 'fp'].mean() if over_mask.any() else 0
    return stats

def build_source_stats(results_df: pd.DataFrame) -> pd.DataFrame:
    """按用例来源分组统计"""
    rows = []
    for source in sorted(results_df['用例来源'].dropna().unique()):
        subset = results_df[results_df['用例来源'] == source]
        total = len(subset)
        if total == 0:
            continue
        row = {'用例来源': source, '样本数': total}
        for label in BUCKET_LABELS:
            count = int((subset['分类'] == label).sum())
            row[label] = f'{count} ({count / total:.0%})'
        rows.append(row)
    return pd.DataFrame(rows)

def print_stats(stats: dict, prefix: str=''):
    """打印统计结果"""
    run = stats.get('未运行数', 0)
    total = stats['总样本数']
    if run > 0:
        print(f'{prefix}已运行：{total}，未运行：{run}')
    else:
        print(f'{prefix}总样本数：{total}')
    for label in BUCKET_LABELS:
        n = stats.get(f'{label}数', 0)
        r = stats.get(f'{label}率', 0)
        print(f'{prefix}{label}：{n} ({r:.1%})')
    print(f"{prefix}漏提样本平均漏 {stats['漏提样本平均漏条数']:.1f} 条/例")
    print(f"{prefix}多提样本平均多 {stats['多提样本平均多条数']:.1f} 条/例")

def main():
    df = pd.read_excel(input_path, sheet_name='Sheet1')
    if RUN_SOURCES is not None:
        df = df[df['用例来源'].isin(RUN_SOURCES)]
    print(f'评测样本数：{len(df)}')
    print(f"用例来源：{list(df['用例来源'].unique())}")
    print(f'评测模型：{EVAL_MODELS}，版本：{EVAL_VERSIONS}')
    print()
    all_versions = []
    for model in EVAL_MODELS:
        for ver in EVAL_VERSIONS:
            col = col_name(model, ver)
            if col not in df.columns:
                print(f'[跳过] {model} | {ver}，列 {col} 不存在')
                continue
            print(f"{'=' * 60}")
            print(f'=== {model} | {ver} ===')
            print(f"{'=' * 60}")
            records = []
            for idx in df.index:
                raw = df.at[idx, col]
                ref_raw = df.at[idx, '参考答案']
                has_run = pd.notna(raw)
                pred_ids, is_valid = parse_id_list(raw) if has_run else (None, False)
                ref_ids, _ = parse_id_list(str(ref_raw)) if pd.notna(ref_raw) else ([], True)
                bucket, detail = classify(pred_ids, ref_ids, is_valid, has_run)
                records.append({'index': idx, '用例来源': df.at[idx, '用例来源'], 'user_query': str(df.at[idx, 'user_query'])[:300], '参考答案': ref_raw, '原始输出': raw if has_run else '', '预测ID': str(pred_ids) if is_valid and pred_ids is not None else 'PARSE_ERROR' if has_run else '未运行', '参考ID': str(ref_ids), '分类': bucket, 'fn': detail['fn'], 'fp': detail['fp'], 'exact_match': detail['exact_match']})
            results_df = pd.DataFrame(records)
            stats = build_stats(results_df)
            stats['模型'] = model
            stats['版本'] = ver
            all_versions.append(stats)
            print()
            print_stats(stats)
            print()
            source_stats = build_source_stats(results_df)
            if not source_stats.empty:
                print('--- 按用例来源 ---')
                print(source_stats.to_string(index=False))
                print()
            bad = results_df[results_df['分类'].isin(['漏提（严重）', '格式错误'])]
            if len(bad) > 0:
                print(f'--- 需关注 case（{len(bad)} 条）---')
                for _, bc in bad.iterrows():
                    print(f"  [{bc['index']}] {bc['用例来源']} | {bc['分类']}")
                    print(f"    参考: {bc['参考ID']}  预测: {bc['预测ID']}  FN={int(bc['fn'])}, FP={int(bc['fp'])}")
                    print(f"    原始输出: {str(bc['原始输出'])[:200]}")
                    print()
            print()
    if len(all_versions) > 1:
        print(f"{'=' * 60}")
        print('======= 多版本对比 =======')
        print(f"{'=' * 60}")
        compare_cols = ['版本', '总样本数', '完全匹配率', '漏提（严重）率', '多提但提全率', '格式错误率', '漏提样本平均漏条数', '多提样本平均多条数']
        cmp = pd.DataFrame(all_versions)[compare_cols]
        for col in ['完全匹配率', '漏提（严重）率', '多提但提全率', '格式错误率']:
            cmp[col] = cmp[col].apply(lambda x: f'{x:.1%}')
        for col in ['漏提样本平均漏条数', '多提样本平均多条数']:
            cmp[col] = cmp[col].apply(lambda x: f'{x:.1f}')
        print(cmp.to_string(index=False))
        detail_path = '评测详细结果.xlsx'
        with pd.ExcelWriter(detail_path, engine='openpyxl') as writer:
            cmp.to_excel(writer, sheet_name='版本对比', index=False)
            for model in EVAL_MODELS:
                for ver in EVAL_VERSIONS:
                    col = col_name(model, ver)
                    if col not in df.columns:
                        continue
                    sheet_name = f'{model}_{ver}'[:31]
                    records = []
                    for idx in df.index:
                        raw = df.at[idx, col]
                        ref_raw = df.at[idx, '参考答案']
                        has_run = pd.notna(raw)
                        pred_ids, is_valid = parse_id_list(raw) if has_run else (None, False)
                        ref_ids, _ = parse_id_list(str(ref_raw)) if pd.notna(ref_raw) else ([], True)
                        bucket, detail = classify(pred_ids, ref_ids, is_valid, has_run)
                        records.append({'用例来源': df.at[idx, '用例来源'], 'user_query': str(df.at[idx, 'user_query'])[:300], '参考答案': ref_raw, '原始输出': raw if pd.notna(raw) else '', '预测ID': str(pred_ids) if is_valid and pred_ids is not None else 'PARSE_ERROR' if has_run else '未运行', '参考ID': str(ref_ids), '分类': bucket, 'FN': detail['fn'], 'FP': detail['fp']})
                    pd.DataFrame(records).to_excel(writer, sheet_name=sheet_name, index=False)
        print(f'\n详细结果已保存至：{detail_path}')
