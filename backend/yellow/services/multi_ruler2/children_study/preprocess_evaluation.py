# Private iCAP Yellow business implementation. Do not publish.
import pandas as pd
from openpyxl import load_workbook
import argparse

def preprocess_excel(input_file, output_file=None):
    """预处理Excel文件，添加预期和实际列
    
    Args:
        input_file: 输入Excel文件路径
        output_file: 输出Excel文件路径，None时覆盖输入文件
    
    Returns:
        输出文件路径
    """
    print(f'开始预处理文件: {input_file}')
    if output_file is None:
        output_file = input_file
    df = pd.read_excel(input_file, sheet_name=0)
    attention_small_orig_col = '注意力小类-单次结果'
    posture_small_orig_col = '坐姿小类'
    attention_status_col = 'attention_status'
    attention_category_col = 'attention_category'
    sitting_posture_status_col = 'sitting_posture_status'
    sitting_posture_category_col = 'sitting_posture_category'
    new_cols = {'预期注意力小类': [], '预期注意力大类': [], '预期坐姿小类': [], '预期坐姿大类': [], '实际注意力大类': [], '实际注意力小类': [], '实际坐姿大类': [], '实际坐姿小类': []}
    for idx in df.index:
        attention_small_orig = str(df.at[idx, attention_small_orig_col]) if pd.notna(df.at[idx, attention_small_orig_col]) else ''
        posture_small_orig = str(df.at[idx, posture_small_orig_col]) if pd.notna(df.at[idx, posture_small_orig_col]) else ''
        attention_status_val = str(df.at[idx, attention_status_col]) if pd.notna(df.at[idx, attention_status_col]) else ''
        attention_category_val = str(df.at[idx, attention_category_col]) if pd.notna(df.at[idx, attention_category_col]) else ''
        sitting_posture_status_val = str(df.at[idx, sitting_posture_status_col]) if pd.notna(df.at[idx, sitting_posture_status_col]) else ''
        sitting_posture_category_val = str(df.at[idx, sitting_posture_category_col]) if pd.notna(df.at[idx, sitting_posture_category_col]) else ''
        if ',' in attention_small_orig or '，' in attention_small_orig:
            attention_small_list = [x.strip() for x in attention_small_orig.replace('，', ',').split(',') if x.strip()]
            if attention_category_val in attention_small_list:
                expected_attention_small = attention_category_val
            else:
                expected_attention_small = attention_small_list[0] if attention_small_list else ''
        else:
            expected_attention_small = attention_small_orig
        if expected_attention_small == '离座':
            expected_attention_big = '离座'
        elif expected_attention_small == '遮挡':
            expected_attention_big = '遮挡'
        elif expected_attention_small == '集中':
            expected_attention_big = '注意力集中'
        else:
            expected_attention_big = '注意力不集中'
        if ',' in posture_small_orig or '，' in posture_small_orig:
            posture_small_list = [x.strip() for x in posture_small_orig.replace('，', ',').split(',') if x.strip()]
            if sitting_posture_category_val in posture_small_list:
                expected_posture_small = sitting_posture_category_val
            else:
                expected_posture_small = posture_small_list[0] if posture_small_list else ''
        else:
            expected_posture_small = posture_small_orig
        if expected_posture_small == '离座':
            expected_posture_big = '离座'
        elif expected_posture_small == '遮挡':
            expected_posture_big = '遮挡'
        elif expected_posture_small == '正常':
            expected_posture_big = '坐姿正常'
        else:
            expected_posture_big = '坐姿异常'
        new_cols['预期注意力小类'].append(expected_attention_small)
        new_cols['预期注意力大类'].append(expected_attention_big)
        new_cols['预期坐姿小类'].append(expected_posture_small)
        new_cols['预期坐姿大类'].append(expected_posture_big)
        new_cols['实际注意力大类'].append(attention_status_val)
        new_cols['实际注意力小类'].append(attention_category_val)
        new_cols['实际坐姿大类'].append(sitting_posture_status_val)
        new_cols['实际坐姿小类'].append(sitting_posture_category_val)
    for col_name, values in new_cols.items():
        df[col_name] = values
    wb = load_workbook(input_file)
    ws = wb.worksheets[0]
    for col_idx, col_name in enumerate(df.columns, 1):
        ws.cell(row=1, column=col_idx, value=col_name)
    for row_idx in range(len(df)):
        for col_idx, col_name in enumerate(df.columns, 1):
            ws.cell(row=row_idx + 2, column=col_idx, value=df.at[df.index[row_idx], col_name])
    wb.save(output_file)
    print(f'预处理完成，结果已保存至: {output_file}')
    print(f'新增列: {list(new_cols.keys())}')
    return output_file
