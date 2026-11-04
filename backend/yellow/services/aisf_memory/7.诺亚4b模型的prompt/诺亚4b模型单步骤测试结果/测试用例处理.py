# Private iCAP Yellow business implementation. Do not publish.
import pandas as pd
import os
df = pd.read_excel('记忆召回用例-删除上下文-522.xlsx')
result_col_names = ['episodic_memory_extract', 'episodic_memory_recall', 'core_memory_extract', 'core_memory_recall', 'processed_results_episode_extract', 'processed_results_episode_recall', 'processed_results_persnoa_extract', 'processed_results_persona_recall']
df = df.drop(columns=[c for c in result_col_names if c in df.columns])

def need_recall(row):
    if str(row['human']).strip() == '(删除上下文)':
        return ''
    kw = row['召回记忆关键字']
    if pd.isna(kw) or str(kw).strip() == '':
        return '否'
    return '是'
df['是否需要召回记忆'] = df.apply(need_recall, axis=1)
result_files = {'episodic_memory_extract': '测试结果20260526/processed_results_episode_extract.xlsx', 'episodic_memory_recall': '测试结果20260526/processed_results_episode_recall.xlsx', 'core_memory_extract': '测试结果20260526/processed_results_persnoa_extract.xlsx', 'core_memory_recall': '测试结果20260526/processed_results_persona_recall.xlsx'}
for col_name, path in result_files.items():
    src = pd.read_excel(path)[['original_text', 'extracted_memory']]
    src = src.rename(columns={'extracted_memory': col_name})
    src['original_text'] = src['original_text'].astype(str).str.strip()
    df['_human_key'] = df['human'].astype(str).str.strip()
    df = df.merge(src, left_on='_human_key', right_on='original_text', how='left')
    df = df.drop(columns=['_human_key', 'original_text'])
df.to_excel('记忆召回用例-删除上下文-522.xlsx', index=False)
print('处理完成，已输出到：记忆召回用例-删除上下文-522.xlsx')
