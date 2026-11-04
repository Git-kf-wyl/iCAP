# Private iCAP Yellow business implementation. Do not publish.
"""
记忆删除意图识别评测脚本
基于标准答案的指标计算（准确率/精确率/召回率/F1）

输出格式：数字 0/1/2
  - 0: 无删除意图
  - 1: 有删除特定记忆的意图
  - 2: 有删除全部记忆的意图

统计维度：用例维度 × 模型 × 版本
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
import pandas as pd
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
EVAL_COLUMNS = ['answer_qwen3-32b_v1.0', 'answer_qwen3-8b_v1.0']
RUN_SOURCES = None
STANDARD_COL = '标准答案'
DIMENSION_COL = '用例维度'

def strip_json_wrapper(text):
    """剥离模型输出的 ```json ... ``` 包裹"""
    if text is None:
        return text
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()

def parse_label(raw) -> int:
    """解析模型输出为 0/1/2 标签"""
    if raw is None or pd.isna(raw):
        return None
    text = strip_json_wrapper(str(raw)).strip()
    for ch in text:
        if ch in ('0', '1', '2'):
            return int(ch)
    return None

def calc_metrics(labels: list, predictions: list) -> dict:
    """计算分类指标。正类 = 有删除意图（1 或 2）"""
    n = len(labels)
    correct = sum((p == l for p, l in zip(predictions, labels)))
    accuracy = correct / n if n > 0 else 0
    tp = sum((p >= 1 and l >= 1 for p, l in zip(predictions, labels)))
    fp = sum((p >= 1 and l == 0 for p, l in zip(predictions, labels)))
    fn = sum((p == 0 and l >= 1 for p, l in zip(predictions, labels)))
    tn = sum((p == 0 and l == 0 for p, l in zip(predictions, labels)))
    precision = tp / (tp + fp) if tp + fp > 0 else 0.0
    recall = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    return {'n': n, 'correct': correct, 'accuracy': accuracy, 'precision': precision, 'recall': recall, 'f1': f1, 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn}

def print_metrics(label: str, m: dict):
    print(f'\n--- {label} ---')
    print(f"样本数  : {m['n']}")
    print(f"准确率  : {m['accuracy']:.1%} ({m['correct']}/{m['n']})")
    print(f"精确率  : {m['precision']:.1%}")
    print(f"召回率  : {m['recall']:.1%}")
    print(f"F1      : {m['f1']:.3f}")
    print(f"混淆    : TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']}")

def main():
    df = pd.read_excel(input_path, sheet_name='Sheet1')
    if STANDARD_COL not in df.columns:
        print(f"错误：标准答案列 '{STANDARD_COL}' 不存在")
        return
    if RUN_SOURCES is not None and DIMENSION_COL in df.columns:
        df = df[df[DIMENSION_COL].isin(RUN_SOURCES)]
    print(f'评测样本数：{len(df)}')
    if DIMENSION_COL in df.columns:
        print(f'用例维度：{list(df[DIMENSION_COL].unique())}')
    print(f'标准答案分布：{df[STANDARD_COL].value_counts().to_dict()}')
    print(f'评测列：{EVAL_COLUMNS}')
    print()
    all_summaries = []
    for ans_col in EVAL_COLUMNS:
        if ans_col not in df.columns:
            print(f'[跳过] 列 {ans_col} 不存在')
            continue
        eval_col = 'eval_' + ans_col
        if eval_col not in df.columns:
            df[eval_col] = None
        print(f"{'=' * 60}")
        print(f'=== {ans_col} ===')
        print(f"{'=' * 60}")
        labels, predictions = ([], [])
        parse_errors = 0
        records = []
        for idx in df.index:
            raw = df.at[idx, ans_col]
            label = int(df.at[idx, STANDARD_COL])
            pred = parse_label(raw)
            if pred is None:
                parse_errors += 1
                pred = 0
            labels.append(label)
            predictions.append(pred)
            is_correct = pred == label
            df.at[idx, eval_col] = json.dumps({'正确': is_correct, '原因': f'预测={pred} 真实={label}'}, ensure_ascii=False)
            dim = df.at[idx, DIMENSION_COL] if DIMENSION_COL in df.columns else ''
            records.append({'idx': idx, '维度': dim, '状态': '✓' if is_correct else '✗', '预测': pred, '真实': label})
        m = calc_metrics(labels, predictions)
        print_metrics('总体', m)
        if parse_errors > 0:
            print(f'  (解析失败: {parse_errors} 条)')
        if DIMENSION_COL in df.columns:
            print('\n--- 按用例维度 ---')
            dim_metrics = []
            for dim in sorted(df[DIMENSION_COL].unique()):
                mask = df[DIMENSION_COL] == dim
                dim_labels = [labels[i] for i in range(len(labels)) if mask.iloc[i]]
                dim_preds = [predictions[i] for i in range(len(predictions)) if mask.iloc[i]]
                dm = calc_metrics(dim_labels, dim_preds)
                dim_metrics.append({'维度': dim, **dm})
            dim_df = pd.DataFrame(dim_metrics)
            for _, row in dim_df.iterrows():
                print(f"  {row['维度']}: acc={row['accuracy']:.1%} P={row['precision']:.1%} R={row['recall']:.1%} F1={row['f1']:.3f} ({row['correct']}/{row['n']})")
        errors = [r for r in records if r['状态'] == '✗']
        if errors:
            print(f'\n--- 错误 case（{len(errors)} 条）---')
            for r in errors[:20]:
                print(f"  [{r['idx']}] {r['维度']} 预测={r['预测']} 真实={r['真实']}")
            if len(errors) > 20:
                print(f'  ... 还有 {len(errors) - 20} 条')
        all_summaries.append({'列名': ans_col, '样本数': m['n'], '正确数': m['correct'], '准确率': m['accuracy'], '精确率': m['precision'], '召回率': m['recall'], 'F1': m['f1']})
        df.to_excel(output_path, index=False, engine='openpyxl')
        print()
    if len(all_summaries) > 1:
        print(f"{'=' * 60}")
        print('======= 多版本对比 =======')
        print(f"{'=' * 60}")
        cmp = pd.DataFrame(all_summaries)
        for col in ['准确率', '精确率', '召回率', 'F1']:
            cmp[col] = cmp[col].apply(lambda x: f'{x:.1%}' if col != 'F1' else f'{x:.3f}')
        print(cmp.to_string(index=False))
