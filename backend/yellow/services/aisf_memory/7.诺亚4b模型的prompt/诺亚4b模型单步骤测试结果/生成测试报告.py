# Private iCAP Yellow business implementation. Do not publish.
import pandas as pd
from datetime import date
df = pd.read_excel('记忆召回用例-删除上下文-522.xlsx')

def has_content(val):
    if pd.isna(val):
        return False
    return str(val).strip() not in ('', '[]', 'nan')
for c in ['episodic_memory_extract', 'episodic_memory_recall', 'core_memory_extract', 'core_memory_recall']:
    df[c + '_hit'] = df[c].apply(has_content)
ext_df = df[df['是否需要召回记忆'] == '否'].copy()
rec_df = df[df['是否需要召回记忆'] == '是'].copy()
sep_n = df['是否需要召回记忆'].isna().sum()
n_ext, n_rec = (len(ext_df), len(rec_df))
n_total = len(df)
ext_df['any_extract'] = ext_df['episodic_memory_extract_hit'] | ext_df['core_memory_extract_hit']
ext_df['any_recall'] = ext_df['episodic_memory_recall_hit'] | ext_df['core_memory_recall_hit']
rec_df['any_extract'] = rec_df['episodic_memory_extract_hit'] | rec_df['core_memory_extract_hit']
rec_df['any_recall'] = rec_df['episodic_memory_recall_hit'] | rec_df['core_memory_recall_hit']
false_recall = ext_df['any_recall'].sum()
false_recall_epi = ext_df['episodic_memory_recall_hit'].sum()
false_recall_core = ext_df['core_memory_recall_hit'].sum()
miss_recall = (~rec_df['any_recall']).sum()
miss_recall_epi = (~rec_df['episodic_memory_recall_hit']).sum()
miss_recall_core = (~rec_df['core_memory_recall_hit']).sum()
correct_extract = ext_df['any_extract'].sum()
correct_extract_epi = ext_df['episodic_memory_extract_hit'].sum()
correct_extract_core = ext_df['core_memory_extract_hit'].sum()
false_extract = rec_df['any_extract'].sum()
false_extract_epi = rec_df['episodic_memory_extract_hit'].sum()
false_extract_core = rec_df['core_memory_extract_hit'].sum()

def pct(n, total):
    return f'{n / total * 100:.1f}%'
md = f"""# 诺亚 4B 记忆系统测试报告\n\n**测试日期**：{date.today()}\n\n---\n\n## 数据概览\n\n| 分类 | 条数 |\n|------|-----:|\n| 总用例数 | {n_total} |\n| 萃取阶段（不应召回）| {n_ext} |\n| 召回阶段（不应萃取）| {n_rec} |\n| 分隔行（删除上下文）| {sep_n} |\n\n---\n\n## 一、该萃取的，萃取了吗？\n\n**萃取阶段共 {n_ext} 条**，模型正确触发萃取的有 **{correct_extract} 条（{pct(correct_extract, n_ext)}）**。\n\n| 记忆类型 | 正确萃取 | 未萃取 | 萃取率 |\n|---------|--------:|------:|------:|\n| 情景记忆 | {correct_extract_epi} | {n_ext - correct_extract_epi} | {pct(correct_extract_epi, n_ext)} |\n| 画像记忆 | {correct_extract_core} | {n_ext - correct_extract_core} | {pct(correct_extract_core, n_ext)} |\n| **合计（任意一个）** | **{correct_extract}** | **{n_ext - correct_extract}** | **{pct(correct_extract, n_ext)}** |\n\n> 画像记忆萃取率（{pct(correct_extract_core, n_ext)}）明显高于情景记忆（{pct(correct_extract_epi, n_ext)}），情景记忆在注入阶段被大量遗漏。\n\n---\n\n## 二、不该召回的，召回了吗？\n\n**萃取阶段共 {n_ext} 条，模型不应触发召回**，但实际召回了 **{false_recall} 条（{pct(false_recall, n_ext)}）**。\n\n| 记忆类型 | 误召回 | 未误召回 | 误召回率 |\n|---------|------:|--------:|--------:|\n| 情景记忆 | {false_recall_epi} | {n_ext - false_recall_epi} | {pct(false_recall_epi, n_ext)} |\n| 画像记忆 | {false_recall_core} | {n_ext - false_recall_core} | {pct(false_recall_core, n_ext)} |\n| **合计（任意一个）** | **{false_recall}** | **{n_ext - false_recall}** | **{pct(false_recall, n_ext)}** |\n\n> ⚠️ 这是最严重的问题。萃取阶段 {pct(false_recall, n_ext)} 的轮次都触发了召回，模型几乎没有能力区分"应当写入记忆"与"应当检索记忆"两种模式。\n\n---\n\n## 三、该召回的，召回了吗？\n\n**召回阶段共 {n_rec} 条**，模型正确触发召回的有 **{rec_df['any_recall'].sum()} 条（{pct(rec_df['any_recall'].sum(), n_rec)}）**，未能召回的有 **{miss_recall} 条（{pct(miss_recall, n_rec)}）**。\n\n| 记忆类型 | 正确召回 | 未召回 | 召回率 |\n|---------|--------:|------:|------:|\n| 情景记忆 | {rec_df['episodic_memory_recall_hit'].sum()} | {miss_recall_epi} | {pct(rec_df['episodic_memory_recall_hit'].sum(), n_rec)} |\n| 画像记忆 | {rec_df['core_memory_recall_hit'].sum()} | {miss_recall_core} | {pct(rec_df['core_memory_recall_hit'].sum(), n_rec)} |\n| **合计（任意一个）** | **{rec_df['any_recall'].sum()}** | **{miss_recall}** | **{pct(rec_df['any_recall'].sum(), n_rec)}** |\n\n> 画像记忆召回率（{pct(rec_df['core_memory_recall_hit'].sum(), n_rec)}）远高于情景记忆（{pct(rec_df['episodic_memory_recall_hit'].sum(), n_rec)}），情景记忆在检索侧同样存在明显缺失。\n\n---\n\n## 四、不该萃取的，萃取了吗？\n\n**召回阶段共 {n_rec} 条，模型不应触发萃取**，但实际萃取了 **{false_extract} 条（{pct(false_extract, n_rec)}）**。\n\n| 记忆类型 | 误萃取 | 未误萃取 | 误萃取率 |\n|---------|------:|--------:|--------:|\n| 情景记忆 | {false_extract_epi} | {n_rec - false_extract_epi} | {pct(false_extract_epi, n_rec)} |\n| 画像记忆 | {false_extract_core} | {n_rec - false_extract_core} | {pct(false_extract_core, n_rec)} |\n| **合计（任意一个）** | **{false_extract}** | **{n_rec - false_extract}** | **{pct(false_extract, n_rec)}** |\n\n> 召回阶段近一半轮次仍在写入记忆，查询行为与写入行为边界不清。\n\n---\n\n## 总结\n\n| 问题 | 涉及条数 | 比率 | 严重程度 |\n|------|--------:|-----:|---------|\n| 萃取阶段误召回（不该召回却召回）| {false_recall}/{n_ext} | {pct(false_recall, n_ext)} | 🔴 最严重 |\n| 召回阶段误萃取（不该萃取却萃取）| {false_extract}/{n_rec} | {pct(false_extract, n_rec)} | 🟠 严重 |\n| 情景记忆萃取不足（该萃取未萃取）| {n_ext - correct_extract_epi}/{n_ext} | {pct(n_ext - correct_extract_epi, n_ext)} | 🟡 中 |\n| 情景记忆召回不足（该召回未召回）| {miss_recall_epi}/{n_rec} | {pct(miss_recall_epi, n_rec)} | 🟡 中 |\n\n**核心问题**：模型对"萃取模式"和"召回模式"没有明确区分，两种行为在两个阶段几乎同时触发。情景记忆的萃取和召回能力均显著弱于画像记忆，需专项优化。\n"""
with open('测试报告.md', 'w', encoding='utf-8') as f:
    f.write(md)
print('报告已生成：测试报告.md')
