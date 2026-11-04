# Private iCAP Yellow business implementation. Do not publish.
import pandas as pd
df = pd.read_excel('记忆召回用例-删除上下文-522.xlsx')

def has_content(val):
    if pd.isna(val):
        return False
    return str(val).strip() not in ('', '[]', 'nan')
for c in ['episodic_memory_extract', 'episodic_memory_recall', 'core_memory_extract', 'core_memory_recall']:
    df[c + '_hit'] = df[c].apply(has_content)
ext_df = df[df['是否需要召回记忆'] == '否'].copy()
rec_df = df[df['是否需要召回记忆'] == '是'].copy()
n_ext, n_rec = (len(ext_df), len(rec_df))
ext_df['any_extract'] = ext_df['episodic_memory_extract_hit'] | ext_df['core_memory_extract_hit']
ext_df['any_recall'] = ext_df['episodic_memory_recall_hit'] | ext_df['core_memory_recall_hit']
rec_df['any_extract'] = rec_df['episodic_memory_extract_hit'] | rec_df['core_memory_extract_hit']
rec_df['any_recall'] = rec_df['episodic_memory_recall_hit'] | rec_df['core_memory_recall_hit']
ext_df['行为'] = '都未触发'
ext_df.loc[ext_df['any_extract'] & ~ext_df['any_recall'], '行为'] = '仅萃取（正确）'
ext_df.loc[~ext_df['any_extract'] & ext_df['any_recall'], '行为'] = '仅召回（误触发）'
ext_df.loc[ext_df['any_extract'] & ext_df['any_recall'], '行为'] = '同时触发萃取+召回'
rec_df['行为'] = '都未触发'
rec_df.loc[~rec_df['any_extract'] & rec_df['any_recall'], '行为'] = '仅召回（正确）'
rec_df.loc[rec_df['any_extract'] & ~rec_df['any_recall'], '行为'] = '仅萃取（误触发）'
rec_df.loc[rec_df['any_extract'] & rec_df['any_recall'], '行为'] = '同时触发萃取+召回'

def rate(df_, col):
    return (df_[col].sum(), len(df_), df_[col].mean())
sep = '=' * 60
print(sep)
print('  记忆系统单步骤测试结果分析报告')
print(sep)
print(f'  萃取阶段（不应召回）：{n_ext} 条')
print(f'  召回阶段（不应萃取）：{n_rec} 条')
print(sep)
print('\n【一】萃取阶段行为分布')
print('-' * 40)
for label, cnt in ext_df['行为'].value_counts().items():
    print(f'  {label:<18} {cnt:>4} 条  {cnt / n_ext:>6.1%}')
print('\n【二】召回阶段行为分布')
print('-' * 40)
for label, cnt in rec_df['行为'].value_counts().items():
    print(f'  {label:<18} {cnt:>4} 条  {cnt / n_rec:>6.1%}')
print('\n【三】核心指标汇总')
print('-' * 40)
metrics = [('萃取阶段 · 综合萃取触发率（正向）', ext_df, 'any_extract'), ('萃取阶段 · 综合误召回率（问题）', ext_df, 'any_recall'), ('萃取阶段 · 情景记忆萃取率', ext_df, 'episodic_memory_extract_hit'), ('萃取阶段 · 画像记忆萃取率', ext_df, 'core_memory_extract_hit'), ('萃取阶段 · 情景记忆误召回率', ext_df, 'episodic_memory_recall_hit'), ('萃取阶段 · 画像记忆误召回率', ext_df, 'core_memory_recall_hit'), ('召回阶段 · 综合召回触发率（正向）', rec_df, 'any_recall'), ('召回阶段 · 综合误萃取率（问题）', rec_df, 'any_extract'), ('召回阶段 · 情景记忆召回率', rec_df, 'episodic_memory_recall_hit'), ('召回阶段 · 画像记忆召回率', rec_df, 'core_memory_recall_hit'), ('召回阶段 · 情景记忆误萃取率', rec_df, 'episodic_memory_extract_hit'), ('召回阶段 · 画像记忆误萃取率', rec_df, 'core_memory_extract_hit')]
for name, ddf, col in metrics:
    cnt = ddf[col].sum()
    tot = len(ddf)
    print(f'  {name:<30} {cnt:>4}/{tot}  {cnt / tot:>6.1%}')
print('\n【四】结论')
print('-' * 40)
ext_recall_rate = ext_df['any_recall'].mean()
ext_extract_rate = ext_df['any_extract'].mean()
rec_recall_rate = rec_df['any_recall'].mean()
rec_extract_rate = rec_df['any_extract'].mean()
epi_ext_rate = ext_df['episodic_memory_extract_hit'].mean()
cor_ext_rate = ext_df['core_memory_extract_hit'].mean()
epi_rec_rate = rec_df['episodic_memory_recall_hit'].mean()
cor_rec_rate = rec_df['core_memory_recall_hit'].mean()
print(f'\n1. 最严重问题：模型在萃取阶段几乎无差别触发召回\n   萃取阶段误召回率高达 {ext_recall_rate:.1%}，\n   而正确萃取率为 {ext_extract_rate:.1%}——两者几乎同步触发（93.4% 行为为"同时触发"），\n   说明模型在记忆写入阶段完全没有屏蔽召回逻辑。\n\n2. 召回阶段整体表现尚可，但误萃取问题不可忽视\n   综合召回触发率 {rec_recall_rate:.1%}，说明召回能力本身没问题。\n   但误萃取率达 {rec_extract_rate:.1%}，约一半的查询对话里\n   模型仍在尝试写入记忆，召回与萃取边界混乱。\n\n3. 情景记忆 vs 画像记忆：情景记忆问题更突出\n   - 萃取阶段：画像萃取率 {cor_ext_rate:.1%} >> 情景萃取率 {epi_ext_rate:.1%}\n     情景记忆在注入阶段被大量遗漏，可能是模型对情景类信息的感知能力不足。\n   - 召回阶段：画像召回率 {cor_rec_rate:.1%} >> 情景召回率 {epi_rec_rate:.1%}\n     情景记忆的召回率仅约一半，说明情景记忆在检索侧也存在明显缺失。\n\n4. 优化建议\n   - 优先级最高：在 prompt/流程中明确区分"萃取模式"和"召回模式"，\n     在萃取阶段应禁止触发召回动作。\n   - 其次：提升情景记忆的萃取和召回能力（当前画像记忆两端均明显优于情景记忆）。\n   - 最后：减少召回阶段的误萃取行为，召回时不应再写入新记忆。\n')
print(sep)
