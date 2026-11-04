# Private iCAP Yellow business implementation. Do not publish.
import pandas as pd
import numpy as np
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
import warnings
import sys
import os
warnings.filterwarnings('ignore')

def calculate_accuracy_with_styles(EXCEL_FILE):
    """
    计算测评结果正确率并添加样式
    参数直接在函数内配置
    """
    if not os.path.exists(EXCEL_FILE):
        print(f'错误: 文件不存在: {EXCEL_FILE}')
        sys.exit(1)
    print(f'正在处理文件: {EXCEL_FILE}')
    try:
        df = pd.read_excel(EXCEL_FILE)
        print(f'成功读取数据，共 {len(df)} 行记录')
    except Exception as e:
        print(f'错误: 无法读取Excel文件: {str(e)}')
        sys.exit(1)
    required_expected_columns = ['注意力大类-单次结果', '注意力小类-单次结果', '坐姿大类', '坐姿小类']
    required_actual_columns = ['attention_status', 'attention_category', 'sitting_posture_status', 'sitting_posture_category']
    doubao_actual_columns = ['豆包API-attention_category', '豆包API-sitting_posture_category', '豆包API-distance_status', '豆包API-seat_status']
    missing_expected = [col for col in required_expected_columns if col not in df.columns]
    missing_actual = [col for col in required_actual_columns if col not in df.columns]
    has_doubao = all((col in df.columns for col in doubao_actual_columns))
    doubao_accuracy_columns = []
    if missing_expected:
        print(f'错误: 缺少预期结果列: {missing_expected}')
        sys.exit(1)
    if missing_actual:
        print(f'错误: 缺少实测结果列: {missing_actual}')
        sys.exit(1)

    def check_attention_status(row):
        if pd.isna(row[required_expected_columns[0]]) or pd.isna(row[required_actual_columns[0]]):
            return False
        expected_values = str(row[required_expected_columns[0]])
        actual_value = str(row[required_actual_columns[0]]).strip()
        return actual_value in expected_values
    df['attention_status_acc'] = df.apply(check_attention_status, axis=1)

    def check_attention_category(row):
        if pd.isna(row[required_expected_columns[1]]) or pd.isna(row[required_actual_columns[1]]):
            return False
        expected_values = str(row[required_expected_columns[1]])
        actual_value = str(row[required_actual_columns[1]]).strip()
        return actual_value in expected_values
    df['attention_category_acc'] = df.apply(check_attention_category, axis=1)

    def check_sitting_posture_status(row):
        if pd.isna(row[required_expected_columns[2]]) or pd.isna(row[required_actual_columns[2]]):
            return False
        expected_values = str(row[required_expected_columns[2]])
        actual_value = str(row[required_actual_columns[2]]).strip()
        return actual_value in expected_values
    df['sitting_posture_status_acc'] = df.apply(check_sitting_posture_status, axis=1)

    def check_sitting_posture_category(row):
        if pd.isna(row[required_expected_columns[3]]) or pd.isna(row[required_actual_columns[3]]):
            return False
        expected_values = str(row[required_expected_columns[3]])
        actual_value = str(row[required_actual_columns[3]]).strip()
        return actual_value in expected_values
    df['sitting_posture_category_acc'] = df.apply(check_sitting_posture_category, axis=1)
    if has_doubao:

        def check_doubao_attention_category(row):
            if pd.isna(row[required_expected_columns[1]]) or pd.isna(row[doubao_actual_columns[0]]):
                return False
            expected_values = str(row[required_expected_columns[1]])
            actual_value = str(row[doubao_actual_columns[0]]).strip()
            return actual_value in expected_values
        df['豆包API-attention_category_acc'] = df.apply(check_doubao_attention_category, axis=1)
        doubao_accuracy_columns.append('豆包API-attention_category_acc')

        def check_doubao_sitting_posture_category(row):
            if pd.isna(row[required_expected_columns[3]]) or pd.isna(row[doubao_actual_columns[1]]):
                return False
            expected_values = str(row[required_expected_columns[3]])
            actual_value = str(row[doubao_actual_columns[1]]).strip()
            return actual_value in expected_values
        df['豆包API-sitting_posture_category_acc'] = df.apply(check_doubao_sitting_posture_category, axis=1)
        doubao_accuracy_columns.append('豆包API-sitting_posture_category_acc')
        df['豆包API-all_acc'] = df[doubao_accuracy_columns].all(axis=1)
        doubao_accuracy_columns.append('豆包API-all_acc')
        print('✓ 豆包API正确率计算完成')
    print('✓ 所有正确率计算完成')
    total_rows = len(df)
    accuracy_columns = ['attention_status_acc', 'attention_category_acc', 'sitting_posture_status_acc', 'sitting_posture_category_acc']
    df['all_acc'] = df[accuracy_columns].all(axis=1)
    print('正在保存结果到Excel文件...')
    try:
        book = load_workbook(EXCEL_FILE)
        sheet = book.worksheets[0]
        red_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
        green_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
        false_font = Font(color='9C0006', bold=True)
        true_font = Font(color='006100', bold=True)
        center_alignment = Alignment(horizontal='center', vertical='center')
        existing_accuracy_cols = {}
        accuracy_headers = ['attention_status_acc', 'attention_category_acc', 'sitting_posture_status_acc', 'sitting_posture_category_acc', 'all_acc']
        if has_doubao:
            accuracy_headers += [''] + doubao_accuracy_columns
        for col_idx in range(1, sheet.max_column + 1):
            header_cell = sheet.cell(row=1, column=col_idx)
            if header_cell.value in accuracy_headers:
                existing_accuracy_cols[header_cell.value] = col_idx
        if existing_accuracy_cols:
            print(f'发现 {len(existing_accuracy_cols)} 个已存在的正确率列，将刷新数据')
            for acc_col, col_idx in existing_accuracy_cols.items():
                header_cell = sheet.cell(row=1, column=col_idx)
                header_cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
                header_cell.font = Font(color='FFFFFF', bold=True)
                header_cell.alignment = center_alignment
                for row_idx in range(2, len(df) + 2):
                    cell = sheet.cell(row=row_idx, column=col_idx)
                    value = df.at[row_idx - 2, acc_col]
                    cell.value = 'TRUE' if value else 'FALSE'
                    if value:
                        cell.fill = green_fill
                        cell.font = true_font
                    else:
                        cell.fill = red_fill
                        cell.font = false_font
                    cell.alignment = center_alignment
            missing_headers = [h for h in accuracy_headers if h not in existing_accuracy_cols and h != '']
            if missing_headers:
                print(f'新增 {len(missing_headers)} 个正确率列')
                max_column = sheet.max_column
                for i, header in enumerate(missing_headers, 1):
                    if header == '':
                        col_letter = get_column_letter(max_column + i)
                        sheet.column_dimensions[col_letter].width = 2
                        continue
                    col_letter = get_column_letter(max_column + i)
                    header_cell = sheet[f'{col_letter}1']
                    header_cell.value = header
                    for row_idx in range(2, len(df) + 2):
                        cell = sheet.cell(row=row_idx, column=max_column + i)
                        value = df.at[row_idx - 2, header]
                        cell.value = 'TRUE' if value else 'FALSE'
                        if value:
                            cell.fill = green_fill
                            cell.font = true_font
                        else:
                            cell.fill = red_fill
                            cell.font = false_font
                        cell.alignment = center_alignment
        else:
            print('未发现已存在的正确率列，将新增所有列')
            max_column = sheet.max_column
            for i, header in enumerate(accuracy_headers, 1):
                if header == '':
                    col_letter = get_column_letter(max_column + i)
                    sheet.column_dimensions[col_letter].width = 2
                    continue
                col_letter = get_column_letter(max_column + i)
                header_cell = sheet[f'{col_letter}1']
                header_cell.value = header
                for row_idx in range(2, len(df) + 2):
                    cell = sheet.cell(row=row_idx, column=max_column + i)
                    value = df.at[row_idx - 2, header]
                    cell.value = 'TRUE' if value else 'FALSE'
                    if value:
                        cell.fill = green_fill
                        cell.font = true_font
                    else:
                        cell.fill = red_fill
                        cell.font = false_font
                    cell.alignment = center_alignment
        accuracy_col_indices = []
        for col_idx in range(1, sheet.max_column + 1):
            header_cell = sheet.cell(row=1, column=col_idx)
            if header_cell.value in accuracy_headers:
                accuracy_col_indices.append(col_idx)
        for col_idx in accuracy_col_indices:
            col_letter = get_column_letter(col_idx)
            max_length = 0
            check_rows = min(sheet.max_row, 100)
            for row in range(1, check_rows + 1):
                cell = sheet.cell(row=row, column=col_idx)
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            adjusted_width = min(max_length + 2, 12)
            sheet.column_dimensions[col_letter].width = adjusted_width
        book.save(EXCEL_FILE)
        print('\n' + '=' * 50)
        print('处理完成!')
        print('=' * 50)
        print(f'\n文件已保存: {EXCEL_FILE}')
        print(f'总记录数: {total_rows}')
        print('\n=== 正确率统计 ===')
        for col in accuracy_columns:
            correct_count = df[col].sum()
            accuracy = correct_count / total_rows * 100
            print(f'{col:30}: {correct_count:4}/{total_rows} = {accuracy:6.2f}%')
        all_acc_count = df['all_acc'].sum()
        all_acc_accuracy = all_acc_count / total_rows * 100
        print(f"{'所有项都正确':30}: {all_acc_count:4}/{total_rows} = {all_acc_accuracy:6.2f}%")
        if has_doubao:
            print('\n=== 豆包API正确率统计 ===')
            for col in doubao_accuracy_columns[:-1]:
                correct_count = df[col].sum()
                accuracy = correct_count / total_rows * 100
                print(f'{col:30}: {correct_count:4}/{total_rows} = {accuracy:6.2f}%')
            all_acc_count = df['豆包API-all_acc'].sum()
            all_acc_accuracy = all_acc_count / total_rows * 100
            print(f"{'豆包所有项都正确':30}: {all_acc_count:4}/{total_rows} = {all_acc_accuracy:6.2f}%")
        token_columns = ['completion_tokens', 'prompt_tokens', 'total_tokens', 'cost_time']
        print('\n=== Token和耗时统计 ===')
        for col in token_columns:
            if col in df.columns:
                avg_value = df[col].mean()
                print(f'{col:20} 平均值: {avg_value:.2f}')
        print(f'\n处理结果:')
        if existing_accuracy_cols:
            print(f'- 刷新了 {len(existing_accuracy_cols)} 个已存在的正确率列')
        if 'missing_headers' in locals() and missing_headers:
            print(f"- 新增了 {len(missing_headers)} 个正确率列: {', '.join(missing_headers)}")
        print('- FALSE结果已标记为红色，TRUE结果已标记为绿色')
    except Exception as e:
        print(f'错误: 保存Excel文件失败 - {str(e)}')
        sys.exit(1)
