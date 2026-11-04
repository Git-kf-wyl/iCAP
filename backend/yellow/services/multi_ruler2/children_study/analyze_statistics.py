# Private iCAP Yellow business implementation. Do not publish.
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
import argparse
import os

def analyze_cost_time(excel_file):
    df = pd.read_excel(excel_file)
    cost_time = df['cost_time'].dropna()
    avg_time = cost_time.mean()
    bins = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, float('inf')]
    labels = ['0~1s', '1~2s', '2~3s', '3~4s', '4~5s', '5~6s', '6~7s', '7~8s', '8~9s', '9~10s', '10s以上']
    cost_time_binned = pd.cut(cost_time, bins=bins, labels=labels, right=False)
    distribution = cost_time_binned.value_counts().sort_index()
    total = len(cost_time)
    result_data = []
    for label in labels:
        count = distribution.get(label, 0)
        ratio = count / total * 100 if total > 0 else 0
        result_data.append([label, count, f'{ratio:.2f}%'])
    return (result_data, avg_time, total)

def analyze_stability(files):
    dfs = []
    for i, f in enumerate(files):
        df = pd.read_excel(f)
        df['run'] = i + 1
        dfs.append(df)
    merged = pd.concat(dfs, ignore_index=True)
    num_runs = len(files)
    attention_categories = ['集中', '东张西望', '睡觉', '疑似睡觉', '玩电子设备', '使用电子设备', '玩玩具', '吃零食', '离座', '遮挡', '其他']
    posture_categories = ['正常', '低头', '歪头', '斜肩', '仰躺', '仰头', '托腮', '趴桌', '离座', '遮挡', '其他']
    attention_result = []
    attention_total_count = 0
    attention_stable_count = 0
    attention_counts = [0] * num_runs
    for cat in attention_categories:
        cat_df = merged[merged['attention_category'] == cat]
        if len(cat_df) == 0:
            continue
        counts = [len(cat_df[cat_df['run'] == run]) for run in range(1, num_runs + 1)]
        unique_cases = cat_df['用例编号'].unique()
        total = len(unique_cases)
        stable = len([uid for uid in unique_cases if len(cat_df[cat_df['用例编号'] == uid]) == num_runs])
        rate = stable / total * 100 if total > 0 else 0
        row = [cat] + counts + [total, stable, f'{rate:.2f}%']
        attention_result.append(row)
        attention_total_count += total
        attention_stable_count += stable
        for i, c in enumerate(counts):
            attention_counts[i] += c
    attention_stability_rate = attention_stable_count / attention_total_count * 100 if attention_total_count > 0 else 0
    attention_result.append(['注意力总计'] + attention_counts + [attention_total_count, attention_stable_count, f'{attention_stability_rate:.2f}%'])
    posture_result = []
    posture_total_count = 0
    posture_stable_count = 0
    posture_counts = [0] * num_runs
    for cat in posture_categories:
        cat_df = merged[merged['sitting_posture_category'] == cat]
        if len(cat_df) == 0:
            continue
        counts = [len(cat_df[cat_df['run'] == run]) for run in range(1, num_runs + 1)]
        unique_cases = cat_df['用例编号'].unique()
        total = len(unique_cases)
        stable = len([uid for uid in unique_cases if len(cat_df[cat_df['用例编号'] == uid]) == num_runs])
        rate = stable / total * 100 if total > 0 else 0
        row = [cat] + counts + [total, stable, f'{rate:.2f}%']
        posture_result.append(row)
        posture_total_count += total
        posture_stable_count += stable
        for i, c in enumerate(counts):
            posture_counts[i] += c
    posture_stability_rate = posture_stable_count / posture_total_count * 100 if posture_total_count > 0 else 0
    posture_result.append(['坐姿总计'] + posture_counts + [posture_total_count, posture_stable_count, f'{posture_stability_rate:.2f}%'])
    combined_counts = [attention_counts[i] + posture_counts[i] for i in range(num_runs)]
    combined_total = attention_total_count + posture_total_count
    combined_stable = attention_stable_count + posture_stable_count
    combined_stability_rate = combined_stable / combined_total * 100 if combined_total > 0 else 0
    summary_result = ['汇总'] + combined_counts + [combined_total, combined_stable, f'{combined_stability_rate:.2f}%']
    return (attention_result, posture_result, summary_result, num_runs)

def write_to_excel(output_file, cost_time_data=None, cost_time_summary=None, stability_data=None, sheet_name='稳定性统计结果'):
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    center_align = Alignment(horizontal='center', vertical='center')
    section_font = Font(bold=True, size=12)
    bold_font = Font(bold=True)
    if os.path.exists(output_file):
        wb = load_workbook(output_file)
    else:
        from openpyxl import Workbook
        wb = Workbook()
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name)
    row = 1
    if cost_time_data:
        ws.cell(row=row, column=1, value='##时延分布统计')
        ws.cell(row=row, column=1).font = section_font
        row += 1
        headers = ['耗时', '数量', '占比']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
        row += 1
        for r in cost_time_data:
            for col, val in enumerate(r, 1):
                ws.cell(row=row, column=col, value=val)
            row += 1
        row += 1
        ws.cell(row=row, column=1, value='平均时延')
        ws.cell(row=row, column=2, value=f'{cost_time_summary[0]:.2f}s')
        ws.cell(row=row, column=1).font = bold_font
        row += 1
        ws.cell(row=row, column=1, value='总样本数')
        ws.cell(row=row, column=2, value=cost_time_summary[1])
        ws.cell(row=row, column=1).font = bold_font
        row += 1
    if cost_time_data and stability_data:
        row += 1
    if stability_data:
        num_runs = stability_data[3]
        headers = ['稳定性'] + [f'第{i + 1}次数量' for i in range(num_runs)] + ['总数量', '稳定数量', '稳定性率']
        ws.cell(row=row, column=1, value='##注意力稳定性分布')
        ws.cell(row=row, column=1).font = section_font
        row += 1
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
        row += 1
        for r in stability_data[0]:
            for col, val in enumerate(r, 1):
                ws.cell(row=row, column=col, value=val)
            row += 1
        row += 1
        ws.cell(row=row, column=1, value='##坐姿稳定性分布')
        ws.cell(row=row, column=1).font = section_font
        row += 1
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
        row += 1
        for r in stability_data[1]:
            for col, val in enumerate(r, 1):
                ws.cell(row=row, column=col, value=val)
            row += 1
        row += 1
        for col, val in enumerate(stability_data[2], 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.font = bold_font
    max_cols = 7 if not stability_data else stability_data[3] + 6
    for col in range(1, max_cols + 1):
        ws.column_dimensions[chr(64 + col)].width = 15
    wb.save(output_file)

def merge_excel_files(files, output_file):
    dfs = [pd.read_excel(f, sheet_name=0) for f in files]
    common_cols = ['用例编号', 't-1.0预览', '当前帧t预览', '预期agent返回大类', '预期agent返回小类', '注意力大类-单次结果', '注意力小类-单次结果', '坐姿大类', '坐姿小类', 't-1.0路径', '当前帧t路径', '设备摆放角度', 'L级标签（置信等级）']
    result = dfs[0][common_cols].copy()
    for i, df in enumerate(dfs, 1):
        suffix = f'_{i}' if i > 1 else ''
        if 'model_output' in df.columns:
            model_df = df[['用例编号', 'model_output']].copy()
            model_df = model_df.rename(columns={'model_output': f'model_output{suffix}' if suffix else 'model_output'})
            result = result.merge(model_df, on='用例编号', how='left')
        if 'attention_category' in df.columns:
            att_df = df[['用例编号', 'attention_category']].copy()
            att_df = att_df.rename(columns={'attention_category': f'attention_category{suffix}' if suffix else 'attention_category'})
            result = result.merge(att_df, on='用例编号', how='left')
        if 'sitting_posture_category' in df.columns:
            sit_df = df[['用例编号', 'sitting_posture_category']].copy()
            sit_df = sit_df.rename(columns={'sitting_posture_category': f'sitting_posture_category{suffix}' if suffix else 'sitting_posture_category'})
            result = result.merge(sit_df, on='用例编号', how='left')
    attention_cols = [c for c in result.columns if c.startswith('attention_category')]
    sitting_cols = [c for c in result.columns if c.startswith('sitting_posture_category')]

    def check_consistent(row, cols):
        values = [row[c] for c in cols if pd.notna(row[c])]
        return 'TRUE' if len(set(values)) <= 1 else 'FALSE'
    result['attention_consistent'] = result.apply(lambda row: check_consistent(row, attention_cols), axis=1)
    result['sitting_consistent'] = result.apply(lambda row: check_consistent(row, sitting_cols), axis=1)
    result = result.sort_values('用例编号').reset_index(drop=True)
    result.to_excel(output_file, index=False, engine='openpyxl')
    print(f'合并完成，结果已保存至: {output_file}')
    print(f'总行数: {len(result)}')
    print(f"attention_consistent: {result['attention_consistent'].value_counts().to_dict()}")
    print(f"sitting_consistent: {result['sitting_consistent'].value_counts().to_dict()}")

def run_stability(stability_xlsx_list, out_file=None):
    stability_data = analyze_stability(stability_xlsx_list)
    output_stability_file = out_file
    if not output_stability_file:
        output_stability_file = stability_xlsx_list[0].replace('.xlsx', '_out.xlsx')
    merge_excel_files(stability_xlsx_list, output_stability_file)
    write_to_excel(output_stability_file, stability_data=stability_data)

def run_time_delay(time_delay_xlsx_list):
    for _time_delay in time_delay_xlsx_list:
        cos_data, avg_time, total = analyze_cost_time(_time_delay)
        write_to_excel(_time_delay, cos_data, (avg_time, total), sheet_name='时延分布统计')

def stability_main():
    parser = argparse.ArgumentParser(description='模型评测统计分析工具')
    parser.add_argument('--cost-time', dest='cost_time_file', type=str, help='时延统计的Excel文件路径')
    parser.add_argument('--stability', dest='stability_files', nargs='+', type=str, help='稳定性统计的Excel文件路径（至少一个）')
    parser.add_argument('--output', dest='output_file', type=str, required=True, help='输出Excel文件路径')
    parser.add_argument('--stat', dest='stat_type', type=str, default='all', choices=['all', 'cost_time', 'stability'], help='统计类型: all(默认), cost_time, stability')
    args = parser.parse_args()
    cost_time_data = None
    cost_time_summary = None
    stability_data = None
    if args.stat_type in ['all', 'cost_time']:
        if not args.cost_time_file:
            print('错误: 请提供时延统计文件路径 (--cost-time)')
            return
        print(f'正在统计时延数据: {args.cost_time_file}')
        cost_time_data, avg_time, total = analyze_cost_time(args.cost_time_file)
        cost_time_summary = (avg_time, total)
        print(f'时延统计完成: 平均时延={avg_time:.2f}s, 总样本数={total}')
    if args.stat_type in ['all', 'stability']:
        if not args.stability_files:
            print('错误: 请提供稳定性统计的文件路径 (--stability)')
            return
        print(f'正在统计稳定性数据，共{len(args.stability_files)}个文件')
        stability_data = analyze_stability(args.stability_files)
        print('稳定性统计完成')
    write_to_excel(args.output_file, cost_time_data, cost_time_summary, stability_data)
    print(f'\n结果已保存至: {args.output_file}')
