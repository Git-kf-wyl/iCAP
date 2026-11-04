# Private iCAP Yellow business implementation. Do not publish.
import pandas as pd
import numpy as np
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
import warnings
import re
warnings.filterwarnings('ignore')
EXPECTED_COLUMNS = {'attention_big': '预期注意力大类', 'attention_small': '预期注意力小类', 'posture_big': '预期坐姿大类', 'posture_small': '预期坐姿小类', 'distance_big': '视距检测', 'distance_near': '视距检测-过近其他', 'seat': '离座检测'}
PRED_COLUMNS = ['实际注意力小类', '实际坐姿小类', 'distance_status', 'seat_status']
ACC_COLUMNS = ['attention_status_acc', 'attention_category_acc', 'sitting_posture_status_acc', 'sitting_posture_category_acc', 'distance_status_acc', 'seat_status_acc']
DOUBAO_COLUMNS = {'attention_category': '豆包-attention_category', 'sitting_posture_category': '豆包-sitting_posture_category', 'distance_status': '豆包-distance_status', 'seat_status': '豆包-seat_status'}
DOUBAO_ACC_COLUMNS = ['豆包-attention_category_acc', '豆包-sitting_posture_category_acc', '豆包-distance_status_acc', '豆包-seat_status_acc']
DYNAMIC_STATISTICS_COLS = ['L级标签']
CAMERA_POSITION_COL = '设备摆放位置'
ATTENTION_SMALL_CATEGORIES = ['集中', '睡觉', '疑似睡觉', '玩电子设备', '玩玩具', '吃零食', '东张西望', '离座', '遮挡', '其他']
POSTURE_SMALL_CATEGORIES = ['正常', '趴桌', '低头', '歪头', '斜肩', '仰躺', '仰头', '托腮', '离座', '遮挡', '其他']
IGNORE = ['遮挡', '其他', '无']
DISTANCE_BIG_STATUS = ['视距正常', '视距过近', '视线不在书本上', '视线不可见', '离座']
DISTANCE_NEAR_STATUS = ['视距过近', '其他']
SEAT_CATEGORIES = ['离座状态', '在座状态', '画面遮挡']
ATTENTION_SMALL_ABNORMAL = ['睡觉', '疑似睡觉', '玩电子设备', '玩玩具', '吃零食', '东张西望', '离座', '遮挡', '其他']
POSTURE_SMALL_ABNORMAL = ['趴桌', '低头', '歪头', '斜肩', '仰躺', '仰头', '托腮', '离座', '遮挡', '其他']
DISTANCE_BIG_ABNORMAL = ['视距过近', '视线不在书本上', '视线不可见', '离座']
ATTENTION_UNUSUAL_CATEGORIES = []
POSTURE_UNUSUAL_CATEGORIES = []
DISTANCE_UNUSUAL_STATUS = []
ATTENTION_CATEGORIES_RESULT = []
POSTURE_CATEGORIES_RESULT = []
DISTANCE_STATUS_RESULT = []
SEAT_CATEGORIES_RESULT = []
HEADER_FILL = PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')
HEADER_FONT = Font(bold=True, color='000000')
TRUE_FILL = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')
FALSE_FILL = PatternFill(start_color='FFB6C1', end_color='FFB6C1', fill_type='solid')
SCALED_ATTENTION_CONFIG = {'total': 1200, 'categories': {'集中': 600, '睡觉': 100, '疑似睡觉': 100, '玩电子设备': 100, '玩玩具': 100, '吃零食': 100, '东张西望': 100, '离座': 100}, 'alias': {'使用电子设备': '玩电子设备'}}
SCALED_POSTURE_CONFIG = {'total': 1400, 'categories': {'正常': 700, '趴桌': 100, '低头': 100, '歪头': 100, '斜肩': 100, '仰躺': 100, '仰头': 100, '托腮': 100}}
SCALED_ATTENTION_CONFIG_L2 = {'total': 300, 'categories': {'集中': 150, '睡觉': 25, '疑似睡觉': 25, '玩电子设备': 25, '玩玩具': 25, '吃零食': 25, '东张西望': 25, '离座': 25}, 'alias': {'使用电子设备': '玩电子设备'}}
SCALED_POSTURE_CONFIG_L2 = {'total': 350, 'categories': {'正常': 175, '趴桌': 25, '低头': 25, '歪头': 25, '斜肩': 25, '仰躺': 25, '仰头': 25, '托腮': 25}}

def add_all_acc_column(df):
    """新增all_acc列（只计算值，不设置格式）"""
    if 'all_acc' not in df.columns:
        df['all_acc'] = False
    acc_columns = [col for col in ACC_COLUMNS if col in df.columns]
    df['all_acc'] = df[acc_columns].all(axis=1)
    return df

def format_all_acc_column(workbook, sheet_name, df):
    """设置all_acc列的颜色格式"""
    if sheet_name not in workbook.sheetnames:
        return
    worksheet = workbook[sheet_name]
    all_acc_col = None
    header_row = 1
    for col_idx in range(1, worksheet.max_column + 1):
        cell_value = worksheet.cell(row=header_row, column=col_idx).value
        if cell_value == 'all_acc':
            all_acc_col = col_idx
            break
    if all_acc_col:
        for row_idx, value in enumerate(df['all_acc'], 2):
            cell = worksheet.cell(row=row_idx, column=all_acc_col)
            if value:
                cell.fill = TRUE_FILL
            else:
                cell.fill = FALSE_FILL

def calculate_overall_stats(df):
    """计算总体统计"""
    total_count = len(df)
    acc_columns = [col for col in ACC_COLUMNS if col in df.columns]
    all_correct_count = df[acc_columns].all(axis=1).sum()
    stats = {'指标': ['总正确率', '总数量', '全部正确数量', '平均completion_tokens', '平均prompt_tokens', '平均total_tokens', '平均cost_time'], '数值': [f'{all_correct_count / total_count * 100:.2f}%' if total_count > 0 else '0%', total_count, all_correct_count, round(df['completion_tokens'].mean(), 2) if 'completion_tokens' in df.columns else 0, round(df['prompt_tokens'].mean(), 2) if 'prompt_tokens' in df.columns else 0, round(df['total_tokens'].mean(), 2) if 'total_tokens' in df.columns else 0, f"{round(df['cost_time'].mean(), 2)}s" if 'cost_time' in df.columns else '0s']}
    return pd.DataFrame(stats)

def calculate_category_accuracy(df):
    """计算各个大小类的正确率"""
    categories = [('注意力大类', ACC_COLUMNS[0]), ('注意力小类', ACC_COLUMNS[1]), ('坐姿大类', ACC_COLUMNS[2]), ('坐姿小类', ACC_COLUMNS[3])]
    results = []
    for name, col in categories:
        if col in df.columns:
            total = len(df)
            correct = df[col].sum()
            accuracy = f'{correct / total * 100:.2f}%' if total > 0 else '0%'
            results.append([name, total, correct, accuracy])
    return pd.DataFrame(results, columns=['维度', '总数量', '正确数量', '正确率'])

def calculate_indicator_accuracy(df):
    """计算各个大小类的正确率"""
    categories = [('注意力小类', ACC_COLUMNS[1]), ('坐姿小类', ACC_COLUMNS[3])]
    results = []
    for name, col in categories:
        if col in df.columns:
            total = len(df)
            correct = df[col].sum()
            accuracy = f'{correct / total * 100:.2f}%' if total > 0 else '0%'
            results.append([name, total, correct, accuracy])
    return pd.DataFrame(results, columns=['维度', '总数量', '正确数量', '正确率'])

def calculate_indicator_accuracy_part(df):
    """计算各个大小类的正确率"""
    categories = [('注意力小类（不算遮挡和其他）', PRED_COLUMNS[0]), ('坐姿小类（不算遮挡和其他）', PRED_COLUMNS[1])]
    results = []
    for name, col in categories:
        if col in df.columns:
            filtered_df = df.dropna(subset=[col])
            if len(filtered_df) == 0:
                results.append([name, len(df), 0, '0%'])
                continue
            if col == PRED_COLUMNS[0]:
                filtered_df = filtered_df[filtered_df[EXPECTED_COLUMNS['attention_small']].isin(IGNORE) == False]
                total = len(filtered_df)
                if ACC_COLUMNS[1] in filtered_df.columns:
                    correct = filtered_df[ACC_COLUMNS[1]].sum()
                else:
                    correct = 0
            elif col == PRED_COLUMNS[1]:
                filtered_df = filtered_df[filtered_df[EXPECTED_COLUMNS['posture_small']].isin(IGNORE) == False]
                total = len(filtered_df)
                if ACC_COLUMNS[3] in filtered_df.columns:
                    correct = filtered_df[ACC_COLUMNS[3]].sum()
                else:
                    correct = 0
            elif col == PRED_COLUMNS[2]:
                total = len(filtered_df)
                correct = ((filtered_df[col] == '视距过近') & (filtered_df[EXPECTED_COLUMNS['distance_big']] == '视距过近')).sum() + ((filtered_df[col] != '视距过近') & (filtered_df[EXPECTED_COLUMNS['distance_big']] != '视距过近')).sum()
            else:
                total = len(filtered_df)
                correct = filtered_df[col].sum()
            accuracy = f'{correct / total * 100:.2f}%' if total > 0 else '0%'
            results.append([name, total, correct, accuracy])
        else:
            results.append([name, len(df), 0, '0%'])
    return pd.DataFrame(results, columns=['维度', '总数量', '正确数量', '正确率'])

def calculate_seating_accuracy(df, sub_df):
    """计算各个大小类的正确率"""
    results = []
    attention_col = ACC_COLUMNS[1]
    if attention_col in df.columns:
        total_attention = len(df)
        correct_attention = df[attention_col].sum()
        accuracy_attention = f'{correct_attention / total_attention * 100:.2f}%' if total_attention > 0 else '0.00%'
        results.append(['注意力小类', total_attention, correct_attention, accuracy_attention])
    posture_col = ACC_COLUMNS[3]
    if posture_col in sub_df.columns:
        total_posture = len(sub_df)
        correct_posture = sub_df[posture_col].sum()
        accuracy_posture = f'{correct_posture / total_posture * 100:.2f}%' if total_posture > 0 else '0.00%'
        results.append(['坐姿小类', total_posture, correct_posture, accuracy_posture])
    return pd.DataFrame(results, columns=['维度', '总数量', '正确数量', '正确率'])

def calculate_indicator_accuracy_with_scaled(df, include_scaled=False, attention_scaled_correct=None, posture_scaled_correct=None, scale_type='L1', merged_scale=False):
    """计算各个大小类的正确率（支持等比缩放信息）"""
    categories = [('注意力小类', ACC_COLUMNS[1]), ('坐姿小类', ACC_COLUMNS[3])]
    if merged_scale:
        attention_config = {'total': SCALED_ATTENTION_CONFIG['total'] + SCALED_ATTENTION_CONFIG_L2['total']}
        posture_config = {'total': SCALED_POSTURE_CONFIG['total'] + SCALED_POSTURE_CONFIG_L2['total']}
    elif scale_type == 'L2':
        attention_config = SCALED_ATTENTION_CONFIG_L2
        posture_config = SCALED_POSTURE_CONFIG_L2
    else:
        attention_config = SCALED_ATTENTION_CONFIG
        posture_config = SCALED_POSTURE_CONFIG
    results = []
    for name, col in categories:
        if col in df.columns:
            total = len(df)
            correct = df[col].sum()
            accuracy = f'{correct / total * 100:.2f}%' if total > 0 else '0%'
            if include_scaled:
                if name == '注意力小类':
                    scaled_total = attention_config['total']
                    scaled_correct = attention_scaled_correct if attention_scaled_correct is not None else 0
                else:
                    scaled_total = posture_config['total']
                    scaled_correct = posture_scaled_correct if posture_scaled_correct is not None else 0
                scaled_accuracy = f'{scaled_correct / scaled_total * 100:.2f}%' if scaled_total > 0 else '0%'
                results.append([name, total, correct, accuracy, scaled_total, scaled_correct, scaled_accuracy])
            else:
                results.append([name, total, correct, accuracy])
    if include_scaled:
        return pd.DataFrame(results, columns=['维度', '总数量', '正确数量', '正确率', '等比例缩放后总数量', '等比例缩放后正确数量', '等比例缩放后正确率'])
    else:
        return pd.DataFrame(results, columns=['维度', '总数量', '正确数量', '正确率'])

def calculate_seating_accuracy_part(df, sub_df, include_scaled=False, attention_scaled_correct=None, posture_scaled_correct=None, scale_type='L1', merged_scale=False):
    """计算各个大小类的正确率，并返回结果DataFrame和正确率字典"""
    results = []
    accuracy_dict = {}
    if merged_scale:
        attention_config = {'total': SCALED_ATTENTION_CONFIG['total'] + SCALED_ATTENTION_CONFIG_L2['total'], 'categories': {}}
        for cat, count in SCALED_ATTENTION_CONFIG['categories'].items():
            attention_config['categories'][cat] = count
        for cat, count in SCALED_ATTENTION_CONFIG_L2['categories'].items():
            attention_config['categories'][cat] = attention_config['categories'].get(cat, 0) + count
        posture_config = {'total': SCALED_POSTURE_CONFIG['total'] + SCALED_POSTURE_CONFIG_L2['total'], 'categories': {}}
        for cat, count in SCALED_POSTURE_CONFIG['categories'].items():
            posture_config['categories'][cat] = count
        for cat, count in SCALED_POSTURE_CONFIG_L2['categories'].items():
            posture_config['categories'][cat] = posture_config['categories'].get(cat, 0) + count
    elif scale_type == 'L2':
        attention_config = SCALED_ATTENTION_CONFIG_L2
        posture_config = SCALED_POSTURE_CONFIG_L2
    else:
        attention_config = SCALED_ATTENTION_CONFIG
        posture_config = SCALED_POSTURE_CONFIG
    attention_col = ACC_COLUMNS[1]
    if attention_col in df.columns:
        total_attention = len(df)
        correct_attention = df[attention_col].sum()
        accuracy_attention = f'{correct_attention / total_attention * 100:.2f}%' if total_attention > 0 else '0.00%'
        if include_scaled:
            scaled_total = attention_config['total']
            scaled_correct = attention_scaled_correct if attention_scaled_correct is not None else 0
            scaled_accuracy = f'{scaled_correct / scaled_total * 100:.2f}%' if scaled_total > 0 else '0%'
            results.append(['注意力小类', '排除注意力检测预期结果为遮挡和其他(无效用例)', total_attention, correct_attention, accuracy_attention, scaled_total, scaled_correct, scaled_accuracy])
        else:
            results.append(['注意力小类', '排除注意力检测预期结果为遮挡和其他(无效用例)', total_attention, correct_attention, accuracy_attention])
        accuracy_dict['注意力检测'] = {'num': total_attention, 'score': accuracy_attention}
    posture_col = ACC_COLUMNS[3]
    if posture_col in sub_df.columns:
        total_posture = len(sub_df)
        correct_posture = sub_df[posture_col].sum()
        accuracy_posture = f'{correct_posture / total_posture * 100:.2f}%' if total_posture > 0 else '0.00%'
        if include_scaled:
            scaled_total = posture_config['total']
            scaled_correct = posture_scaled_correct if posture_scaled_correct is not None else 0
            scaled_accuracy = f'{scaled_correct / scaled_total * 100:.2f}%' if scaled_total > 0 else '0%'
            results.append(['坐姿小类', "排除以下场景数据：a.注意力小类-单次结果取值为遮挡、其他（无效用例）b.坐姿小类 取值为 遮挡、其他、无（无效用例）c.实际注意力小类取值为'睡觉','玩电子设备','使用电子设备','玩玩具','吃零食','离座' d.实际注意力小类取值为'东张西望'并且实际坐姿小类取值不是'仰头'、'仰躺'", total_posture, correct_posture, accuracy_posture, scaled_total, scaled_correct, scaled_accuracy])
        else:
            results.append(['坐姿小类', "排除以下场景数据：a.注意力小类-单次结果取值为遮挡、其他（无效用例）b.坐姿小类 取值为 遮挡、其他、无（无效用例）c.注意力实际结果取值为'睡觉','玩电子设备','使用电子设备','玩玩具','吃零食','离座' d.注意力实际结果取值为'东张西望'并且坐姿实际结果取值不是'仰头'、'仰躺'", total_posture, correct_posture, accuracy_posture])
        accuracy_dict['坐姿检测'] = {'num': total_posture, 'score': accuracy_posture}
    if include_scaled:
        return (pd.DataFrame(results, columns=['维度', '统计说明', '总数量', '正确数量', '正确率', '等比例缩放后总数量', '等比例缩放后正确数量', '等比例缩放后正确率']), accuracy_dict)
    else:
        return (pd.DataFrame(results, columns=['维度', '统计说明', '总数量', '正确数量', '正确率']), accuracy_dict)

def calculate_image_source_stats(df):
    """统计不同图片来源的总的正确率和各个小类的正确率"""
    category_order = ['总正确率', '注意力大类', '注意力小类', '坐姿大类', '坐姿小类']
    category_columns = {'注意力大类': ACC_COLUMNS[0], '注意力小类': ACC_COLUMNS[1], '坐姿大类': ACC_COLUMNS[2], '坐姿小类': ACC_COLUMNS[3]}
    columns_order = ['图片来源']
    for category in category_order:
        columns_order.extend([f'{category}_总数量', f'{category}_正确数量', f'{category}_正确率'])
    if '图片来源' not in df.columns:
        return pd.DataFrame(columns=columns_order)
    all_results = []
    df_copy = df.copy()
    df_copy['图片来源'] = df_copy['图片来源'].fillna('无')
    sources = df_copy['图片来源'].unique()
    for source in sources:
        source_df = df_copy[df_copy['图片来源'] == source]
        total_count = len(source_df)
        source_row = {'图片来源': source}
        acc_columns = [col for col in ACC_COLUMNS if col in df.columns]
        total_correct = source_df[acc_columns].all(axis=1).sum()
        total_accuracy = f'{total_correct / total_count * 100:.2f}%' if total_count > 0 else '0.00%'
        source_row['总正确率_总数量'] = total_count
        source_row['总正确率_正确数量'] = total_correct
        source_row['总正确率_正确率'] = total_accuracy
        for category_name in category_order[1:]:
            col_name = category_columns.get(category_name)
            if col_name and col_name in source_df.columns:
                correct = source_df[col_name].sum()
                accuracy = f'{correct / total_count * 100:.2f}%' if total_count > 0 else '0.00%'
                source_row[f'{category_name}_总数量'] = total_count
                source_row[f'{category_name}_正确数量'] = correct
                source_row[f'{category_name}_正确率'] = accuracy
            else:
                source_row[f'{category_name}_总数量'] = total_count
                source_row[f'{category_name}_正确数量'] = 0
                source_row[f'{category_name}_正确率'] = '0.00%'
        all_results.append(source_row)
    if not all_results:
        return pd.DataFrame(columns=columns_order)
    result_df = pd.DataFrame(all_results)
    final_columns = [col for col in columns_order if col in result_df.columns]
    return result_df[final_columns]

def calculate_resolution_stats(df):
    """统计不同分辨率的总的正确率"""
    if '分辨率' not in df.columns:
        return pd.DataFrame(columns=['分辨率', '总数量', '正确数量', '正确率'])
    df_copy = df.copy()
    df_copy['分辨率'] = df_copy['分辨率'].fillna('无')
    results = []
    for resolution in df_copy['分辨率'].unique():
        res_df = df_copy[df_copy['分辨率'] == resolution]
        acc_columns = [col for col in ACC_COLUMNS if col in df.columns]
        total_correct = res_df[acc_columns].all(axis=1).sum()
        total_count = len(res_df)
        accuracy = f'{total_correct / total_count * 100:.2f}%' if total_count > 0 else '0%'
        results.append([resolution, total_count, total_correct, accuracy])
    return pd.DataFrame(results, columns=['分辨率', '总数量', '正确数量', '正确率'])

def sanitize_sheet_name(name, existing_names):
    """
    将任意字符串转换为合法的Excel工作表名称

    Args:
        name: 原始名称
        existing_names: 当前工作簿中已存在的sheet名称集合（用于处理重名）

    Returns:
        合法的sheet名称
    """
    if not name:
        name = 'Sheet'
    illegal_chars_pattern = '[\\\\/*?:\\[\\]]'
    name = re.sub(illegal_chars_pattern, '_', name)
    name = name.replace('<', '_').replace('>', '_')
    if len(name) > 31:
        name = name[:31]
    if existing_names:
        existing_lower = {n.lower() for n in existing_names}
        original_name = name
        counter = 1
        while name.lower() in existing_lower:
            suffix = str(counter)
            max_base_len = 31 - len(suffix)
            base_name = original_name[:max_base_len]
            name = f'{base_name}{suffix}'
            counter += 1
    return name

def write_dataframes_to_sheet(writer, dataframes, sheet_name):
    """将多个DataFrame写入同一个sheet，之间空两行"""
    workbook = writer.book
    sheet_name = sanitize_sheet_name(sheet_name, None)
    if sheet_name in workbook.sheetnames:
        workbook.remove(workbook[sheet_name])
    worksheet = workbook.create_sheet(sheet_name)
    RED_FILL = PatternFill(start_color='FFB6C1', end_color='FFB6C1', fill_type='solid')
    GREEN_FILL = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
    current_row = 1
    for i, (title, df) in enumerate(dataframes):
        if df.empty:
            continue
        worksheet.cell(row=current_row, column=1, value=title)
        worksheet.cell(row=current_row, column=1).font = Font(bold=True, size=12)
        current_row += 1
        for col_idx, col_name in enumerate(df.columns, 1):
            cell = worksheet.cell(row=current_row, column=col_idx, value=col_name)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal='center', vertical='center')
        data_start_row = current_row + 1
        for row_idx, row_data in enumerate(df.values, data_start_row):
            for col_idx, value in enumerate(row_data, 1):
                cell = worksheet.cell(row=row_idx, column=col_idx, value=value)
                if isinstance(value, (int, float)):
                    cell.alignment = Alignment(horizontal='right')
                else:
                    cell.alignment = Alignment(horizontal='left')
        if '混淆矩阵' in title:
            if hasattr(df, 'attrs') and 'red_marks' in df.attrs:
                for row_offset, col_offset in df.attrs['red_marks']:
                    actual_row = data_start_row + row_offset
                    actual_col = col_offset + 1
                    cell = worksheet.cell(row=actual_row, column=actual_col)
                    cell.fill = RED_FILL
            if hasattr(df, 'attrs') and 'green_marks' in df.attrs:
                for row_offset, col_offset in df.attrs['green_marks']:
                    actual_row = data_start_row + row_offset
                    actual_col = col_offset + 1
                    cell = worksheet.cell(row=actual_row, column=actual_col)
                    cell.fill = GREEN_FILL
        current_row += len(df) + 3
        for col_idx, col_name in enumerate(df.columns, 1):
            column_letter = get_column_letter(col_idx)
            max_length = len(col_name)
            for value in df.iloc[:, col_idx - 1].astype(str):
                max_length = max(max_length, len(str(value)))
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
            worksheet.column_dimensions[column_letter].width = 15

def calculate_attention_difficulty(df):
    """统计注意力的难易度正确率"""
    difficulties = ['简单', '中等', '困难']
    metrics = {'总正确率': [ACC_COLUMNS[1], ACC_COLUMNS[0]], '注意力大类': [ACC_COLUMNS[0]], '注意力小类': [ACC_COLUMNS[1]]}
    result_columns = ['难易程度-注意力']
    for metric in metrics:
        result_columns.extend([f'{metric}_总数量', f'{metric}_正确数量', f'{metric}_正确率'])
    if '难易程度-注意力' not in df.columns:
        return pd.DataFrame(columns=result_columns)
    results = []
    for diff in difficulties:
        diff_df = df[df['难易程度-注意力'] == diff]
        total_count = len(diff_df)
        result_row = {'难易程度-注意力': diff}
        for metric, acc_cols in metrics.items():
            valid_cols = [col for col in acc_cols if col in diff_df.columns]
            if not valid_cols:
                correct_count = 0
            elif len(valid_cols) > 1:
                correct_count = diff_df[valid_cols].all(axis=1).sum()
            else:
                correct_count = diff_df[valid_cols[0]].sum()
            accuracy = f'{correct_count / total_count * 100:.2f}%' if total_count > 0 else '0.00%'
            result_row.update({f'{metric}_总数量': total_count, f'{metric}_正确数量': correct_count, f'{metric}_正确率': accuracy})
        results.append(result_row)
    existing_diffs = {res['难易程度-注意力'] for res in results}
    for diff in set(difficulties) - existing_diffs:
        results.append({'难易程度-注意力': diff, **{f'{metric}_总数量': 0 for metric in metrics}, **{f'{metric}_正确数量': 0 for metric in metrics}, **{f'{metric}_正确率': '0.00%' for metric in metrics}})
    return pd.DataFrame(results)

def calculate_posture_difficulty(df):
    """统计坐姿的难易度正确率"""
    difficulties = ['简单', '中等', '困难']
    metrics = {'总正确率': [ACC_COLUMNS[2], ACC_COLUMNS[3]], '坐姿大类': [ACC_COLUMNS[2]], '坐姿小类': [ACC_COLUMNS[3]]}
    result_columns = ['难易程度-坐姿']
    for metric in metrics:
        result_columns.extend([f'{metric}_总数量', f'{metric}_正确数量', f'{metric}_正确率'])
    if '难易程度-坐姿' not in df.columns:
        return pd.DataFrame(columns=result_columns)
    results = []
    for diff in difficulties:
        diff_df = df[df['难易程度-坐姿'] == diff]
        total_count = len(diff_df)
        result_row = {'难易程度-坐姿': diff}
        for metric, acc_cols in metrics.items():
            valid_cols = [col for col in acc_cols if col in diff_df.columns]
            if not valid_cols:
                correct_count = 0
            elif len(valid_cols) > 1:
                correct_count = diff_df[valid_cols].all(axis=1).sum()
            else:
                correct_count = diff_df[valid_cols[0]].sum()
            accuracy = f'{correct_count / total_count * 100:.2f}%' if total_count > 0 else '0.00%'
            result_row.update({f'{metric}_总数量': total_count, f'{metric}_正确数量': correct_count, f'{metric}_正确率': accuracy})
        results.append(result_row)
    existing_diffs = {res['难易程度-坐姿'] for res in results}
    for diff in set(difficulties) - existing_diffs:
        results.append({'难易程度-坐姿': diff, **{f'{metric}_总数量': 0 for metric in metrics}, **{f'{metric}_正确数量': 0 for metric in metrics}, **{f'{metric}_正确率': '0.00%' for metric in metrics}})
    return pd.DataFrame(results)

def calculate_cost_time(df):
    """
    统计cost_time列的区间分布
    参数:
        df: 包含cost_time列的DataFrame
    返回:
        包含区间统计的DataFrame
    """
    if 'cost_time' not in df.columns:
        print("警告：数据中无'cost_time'列")
        return pd.DataFrame(columns=['区间', '数量', '占比'])
    bins = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, float('inf')]
    labels = ['0s~1s', '1s~2s', '2s~3s', '3s~4s', '4s~5s', '5s~6s', '6s~7s', '7s~8s', '8s~9s', '9s~10s', '10s以上']
    cost_time_series = pd.cut(df['cost_time'], bins=bins, right=False, labels=labels, include_lowest=True)
    interval_counts = cost_time_series.value_counts().reindex(labels, fill_value=0)
    total_count = len(df.dropna(subset=['cost_time']))
    percentage_values = (interval_counts / total_count * 100).round(2)
    percentage_str = percentage_values.apply(lambda x: f'{x:.2f}%')
    result_df = pd.DataFrame({'耗时': interval_counts.index, '数量': interval_counts.values, '占比': percentage_str.values}).reset_index(drop=True)
    return result_df

def _fold_label(true_label, pred_label, standard_categories):
    """折叠标签的辅助函数（向量化操作）"""
    if pd.isna(true_label):
        return np.nan
    if true_label in standard_categories:
        return true_label
    sub_categories = [c.strip() for c in str(true_label).replace('，', ',').split(',')]
    return pred_label if pred_label in sub_categories else sub_categories[0]

def calculate_confusion_matrix(df, scenario):
    """统计注意力/坐姿/视距/离座检测的混淆矩阵（优化版）"""
    config = {'attention': {'true_col': EXPECTED_COLUMNS['attention_small'], 'pred_col': PRED_COLUMNS[0], 'first_col_name': '注意力小类', 'standard': ATTENTION_SMALL_CATEGORIES, 'pred': ATTENTION_CATEGORIES_RESULT}, 'posture': {'true_col': EXPECTED_COLUMNS['posture_small'], 'pred_col': PRED_COLUMNS[1], 'first_col_name': '坐姿小类', 'standard': POSTURE_SMALL_CATEGORIES, 'pred': POSTURE_CATEGORIES_RESULT}}
    if scenario not in config:
        raise ValueError(f'无效场景: {scenario}')
    cfg = config[scenario]
    true_col, pred_col = (cfg['true_col'], cfg['pred_col'])
    first_col_name = cfg['first_col_name']
    standard_categories = cfg['standard']
    pred_categories = cfg['pred']
    if true_col not in df.columns or pred_col not in df.columns:
        return pd.DataFrame(columns=[first_col_name] + pred_categories)
    df = df.copy()
    df['标签'] = df.apply(lambda x: _fold_label(x[true_col], x[pred_col], standard_categories), axis=1)
    valid_df = df.dropna(subset=['标签'])
    confusion_matrix = pd.crosstab(index=valid_df['标签'], columns=valid_df[pred_col], dropna=False)
    confusion_matrix = confusion_matrix.reindex(index=standard_categories, columns=pred_categories, fill_value=0)
    result_df = confusion_matrix.reset_index()
    result_df.rename(columns={'index': first_col_name}, inplace=True)
    green_marks = []
    for i, true_val in enumerate(standard_categories):
        j = result_df.columns.get_loc(true_val) if true_val in result_df.columns else -1
        if j > 0:
            green_marks.append((i, j))
    result_df.attrs['green_marks'] = green_marks
    return result_df

def calculate_confusion_matrix_metrics(df, business_type):
    """
    计算指定业务类型的混淆矩阵相关指标并返回一个包含九列的表格。
    此版本支持多标签真实标签，例如一行的真实标签可以是 ['正常', '轻微低头']。

    参数:
        df (pd.DataFrame): 包含预测标签和真实标签的DataFrame。
        business_type (str): 业务类型，'attention', 'posture', 'distance' 或 'seat'。

    返回:
        pd.DataFrame: 一个包含九列指标的DataFrame，如果输入无效则返回空DataFrame。
    """
    params_map = {'attention': {'pred_col': PRED_COLUMNS[0], 'true_col': EXPECTED_COLUMNS['attention_small'], 'cat_list': ATTENTION_SMALL_CATEGORIES}, 'posture': {'pred_col': PRED_COLUMNS[1], 'true_col': EXPECTED_COLUMNS['posture_small'], 'cat_list': POSTURE_SMALL_CATEGORIES}}
    if business_type not in params_map:
        raise ValueError(f'不支持的 business_type: {business_type}')
    params = params_map[business_type]
    pred_col = params['pred_col']
    true_col = params['true_col']
    categories = params['cat_list']
    if pred_col not in df.columns or true_col not in df.columns:
        empty_df = pd.DataFrame(columns=['小类名', 'TP', 'TN', 'FP', 'FN', '精确率', '召回率', '漏报率', '误发现率'])
        print(f"警告: DataFrame中缺少必要列。检查 '{pred_col}' 和 '{true_col}'。")
        return empty_df
    df_working = df.copy()

    def fold_label_vectorized(true_label, pred_label):
        return _fold_label(true_label, pred_label, categories)
    df_working['真实标签'] = df_working.apply(lambda row: fold_label_vectorized(row[true_col], row[pred_col]), axis=1)
    all_results = []
    for category in categories:
        predicted_is_category = df_working[pred_col] == category
        true_is_category = df_working['真实标签'] == category
        tp = (predicted_is_category & true_is_category).sum()
        fp = (predicted_is_category & ~true_is_category).sum()
        fn = (~predicted_is_category & true_is_category).sum()
        tn = (~predicted_is_category & ~true_is_category).sum()
        predicted_positives = tp + fp
        actual_positives = tp + fn
        if predicted_positives > 0:
            precision = tp / predicted_positives
        else:
            precision = 0.0
        if actual_positives > 0:
            recall = tp / actual_positives
        else:
            recall = 0.0
        miss_rate = 1.0 - recall
        if predicted_positives > 0:
            fdr = fp / predicted_positives
        else:
            fdr = 0.0
        all_results.append({'小类名': category, 'TP': int(tp), 'TN': int(tn), 'FP': int(fp), 'FN': int(fn), '精确率': f'{precision:.2%}', '召回率': f'{recall:.2%}', '漏报率': f'{miss_rate:.2%}', '误发现率': f'{fdr:.2%}'})
    final_df = pd.DataFrame(all_results)
    return final_df

def calculate_indicators(df, business_type, include_scaled=False, scale_type='L1', merged_scale=False):
    """
    计算指定业务类型的混淆矩阵相关指标并返回一个包含多列的表格。
    在精确率前添加分数形式的精确率列，在召回率前添加分数形式的召回率列。

    参数:
        df (pd.DataFrame): 包含预测标签和真实标签的DataFrame。
        business_type (str): 业务类型，'attention', 'posture', 'distance' 或 'seat'。
        include_scaled (bool): 是否包含等比缩放列。
        scale_type (str): 缩放类型，'L1'或'L2'，默认为'L1'。
        merged_scale (bool): 是否使用L1和L2合并后的配置进行等比缩放计算，默认为False。

    返回:
        pd.DataFrame: 包含指标结果的DataFrame，如果输入无效则返回空DataFrame。
    """
    params_map = {'attention': {'pred_col': PRED_COLUMNS[0], 'true_col': EXPECTED_COLUMNS['attention_small'], 'cat_list': ATTENTION_SMALL_CATEGORIES, 'normal_tag': '集中'}, 'posture': {'pred_col': PRED_COLUMNS[1], 'true_col': EXPECTED_COLUMNS['posture_small'], 'cat_list': POSTURE_SMALL_CATEGORIES, 'normal_tag': '正常'}}
    if business_type not in params_map:
        raise ValueError(f'不支持的 business_type: {business_type}')
    params = params_map[business_type]
    pred_col = params['pred_col']
    true_col = params['true_col']
    categories = params['cat_list']
    normal_tag = params['normal_tag']
    if pred_col not in df.columns or true_col not in df.columns:
        empty_df = pd.DataFrame(columns=['小类名', 'TP', 'TN', 'FP', 'FN', '精确率分数', '精确率', '召回率分数', '召回率'])
        empty_df.attrs = {'red_marks': []}
        return empty_df
    df_working = df.copy()

    def fold_label_vectorized(true_label, pred_label):
        return _fold_label(true_label, pred_label, categories)
    df_working['真实标签'] = df_working.apply(lambda row: fold_label_vectorized(row[true_col], row[pred_col]), axis=1)
    all_results = []
    red_marks = []
    if merged_scale:
        attention_l1_config = SCALED_ATTENTION_CONFIG
        attention_l2_config = SCALED_ATTENTION_CONFIG_L2
        posture_l1_config = SCALED_POSTURE_CONFIG
        posture_l2_config = SCALED_POSTURE_CONFIG_L2
        if business_type == 'attention':
            merged_categories = attention_l1_config['categories'].copy()
            for cat, count in attention_l2_config['categories'].items():
                merged_categories[cat] = merged_categories.get(cat, 0) + count
            scaled_config = {'total': attention_l1_config['total'] + attention_l2_config['total'], 'categories': merged_categories, 'alias': attention_l1_config.get('alias', {})}
        else:
            merged_categories = posture_l1_config['categories'].copy()
            for cat, count in posture_l2_config['categories'].items():
                merged_categories[cat] = merged_categories.get(cat, 0) + count
            scaled_config = {'total': posture_l1_config['total'] + posture_l2_config['total'], 'categories': merged_categories}
        alias_map = scaled_config.get('alias', {})
    elif scale_type == 'L2':
        scaled_config = SCALED_ATTENTION_CONFIG_L2 if business_type == 'attention' else SCALED_POSTURE_CONFIG_L2
        alias_map = scaled_config.get('alias', {})
    else:
        scaled_config = SCALED_ATTENTION_CONFIG if business_type == 'attention' else SCALED_POSTURE_CONFIG
        alias_map = scaled_config.get('alias', {})
    for idx, category in enumerate(categories):
        alias = alias_map.get(category, category)
        predicted_is_category = df_working[pred_col] == category
        true_is_category = df_working['真实标签'] == category
        tp = (predicted_is_category & true_is_category).sum()
        fp = (predicted_is_category & ~true_is_category).sum()
        fn = (~predicted_is_category & true_is_category).sum()
        tn = (~predicted_is_category & ~true_is_category).sum()
        precision = tp / (tp + fp) if tp + fp > 0 else 0.0
        recall = tp / (tp + fn) if tp + fn > 0 else 0.0
        precision_fraction = f'{tp}/{tp + fp}' if tp + fp > 0 else '0/0'
        recall_fraction = f'{tp}/{tp + fn}' if tp + fn > 0 else '0/0'
        precision_str = f'{precision:.2%}'
        recall_str = f'{recall:.2%}'
        scaled_ratio = scaled_config['categories'].get(alias, 0)
        if tp + fn > 0 and scaled_ratio > 0:
            scaled_recall = f'{round(tp * scaled_ratio / (tp + fn))}/{scaled_ratio}'
        else:
            scaled_recall = '0/0'
        f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
        f1_str = f'{f1:.2%}'
        if category == normal_tag:
            red_marks.append((idx, '召回率'))
        else:
            red_marks.append((idx, '精确率'))
        if include_scaled:
            all_results.append({'小类名': category, '真实样本数': int(tp + fn), 'TP': int(tp), 'TN': int(tn), 'FP': int(fp), 'FN': int(fn), '精确率计算TP/TP+FP': precision_fraction, '精确率': precision_str, '召回率计算TP/TP+FN': recall_fraction, '召回率': recall_str, '召回率等比例缩放后': scaled_recall, 'F1-score': f1_str})
        else:
            all_results.append({'小类名': category, '真实样本数': int(tp + fn), 'TP': int(tp), 'TN': int(tn), 'FP': int(fp), 'FN': int(fn), '精确率计算TP/TP+FP': precision_fraction, '精确率': precision_str, '召回率计算TP/TP+FN': recall_fraction, '召回率': recall_str})
    final_df = pd.DataFrame(all_results)
    final_df.attrs['red_marks'] = red_marks
    return final_df

def calculate_indicators_mixed(df, business_type, metric='recall'):
    """
    计算指定业务类型的混淆矩阵相关指标。

    参数:
        df (pd.DataFrame): 包含预测标签和真实标签的DataFrame。
        business_type (str): 业务类型，'attention' 或 'posture'。
        metric (str): 计算的指标类型，'precision'(精确率) 或 'recall'(召回率)。

    返回:
        pd.DataFrame: 包含指标结果的DataFrame，如果输入无效则返回空DataFrame。
        当 metric='recall' 时，额外返回一个dict，包含每个子类的召回率数值。
    """
    params_map = {'attention': {'pred_col': PRED_COLUMNS[0], 'true_col': EXPECTED_COLUMNS['attention_small'], 'cat_list': ATTENTION_SMALL_CATEGORIES, 'cat_list_pre': ATTENTION_CATEGORIES_RESULT, 'normal_tag': '集中'}, 'posture': {'pred_col': PRED_COLUMNS[1], 'true_col': EXPECTED_COLUMNS['posture_small'], 'cat_list': POSTURE_SMALL_CATEGORIES, 'cat_list_pre': POSTURE_CATEGORIES_RESULT, 'normal_tag': '正常'}}
    if business_type not in params_map:
        raise ValueError(f'不支持的 business_type: {business_type}')
    if metric not in ('precision', 'recall'):
        raise ValueError(f"不支持的 metric: {metric}，请使用 'precision' 或 'recall'")
    params = params_map[business_type]
    pred_col = params['pred_col']
    true_col = params['true_col']
    normal_tag = params['normal_tag']
    categories = params.get('cat_list_pre' if metric == 'precision' else 'cat_list')
    if pred_col not in df.columns or true_col not in df.columns:
        empty_df = pd.DataFrame(columns=['小类名', 'TP', 'TN', 'FP', 'FN', '精确率分数', '精确率', '召回率分数', '召回率'])
        empty_df.attrs = {'red_marks': []}
        if metric == 'recall':
            return (empty_df, {})
        return empty_df
    df_working = df.copy()
    df_working['真实标签'] = df_working[true_col].fillna('').apply(lambda x: str(x).replace('，', ',').split(',')[0].strip() if pd.notna(x) else '')
    all_results = []
    red_marks = []
    for idx, category in enumerate(categories):
        if metric == 'precision' and category == '无':
            continue
        predicted_is_category = df_working[pred_col] == category
        true_is_category = df_working['真实标签'] == category
        tp = (predicted_is_category & true_is_category).sum()
        fp = (predicted_is_category & ~true_is_category).sum()
        fn = (~predicted_is_category & true_is_category).sum()
        tn = (~predicted_is_category & ~true_is_category).sum()
        precision = tp / (tp + fp) if tp + fp > 0 else 0.0
        recall = tp / (tp + fn) if tp + fn > 0 else 0.0
        precision_fraction = f'{tp}/{tp + fp}' if tp + fp > 0 else '0/0'
        recall_fraction = f'{tp}/{tp + fn}' if tp + fn > 0 else '0/0'
        precision_str = f'{precision:.2%}'
        recall_str = f'{recall:.2%}'
        if category == normal_tag:
            red_marks.append((idx, '召回率'))
        else:
            red_marks.append((idx, '精确率'))
        if metric == 'precision':
            all_results.append({'小类名': category, 'TP': int(tp), 'TN': int(tn), 'FP': int(fp), 'FN': int(fn), '精确率计算TP/TP+FP': precision_fraction, '精确率': precision_str})
        else:
            all_results.append({'小类名': category, 'TP': int(tp), 'TN': int(tn), 'FP': int(fp), 'FN': int(fn), '召回率计算TP/TP+FN': recall_fraction, '召回率': recall_str})
    final_df = pd.DataFrame(all_results)
    final_df.attrs['red_marks'] = red_marks
    if metric == 'recall':
        recall_dict = {}
        for entry in all_results:
            cat_name = entry['小类名']
            recall_val = float(entry['召回率'].rstrip('%')) / 100
            recall_dict[cat_name] = recall_val
        return (final_df, recall_dict)
    return final_df

def get_sorted_unique_labels(df, column_name, default_order_list):
    """
    获取自定义排序后的唯一标签列表。

    步骤：
    1. 从列中提取所有由逗号分割的唯一标签。
    2. 首先输出 `default_order_list` 中的标签，并保持该列表的顺序。
    3. 然后输出不在 `default_order_list` 中的标签，并保持它们在数据中首次出现的顺序。

    Args:
        df (pd.DataFrame): 输入的数据框。
        column_name (str): 要处理的列名。
        default_order_list (list): 默认标签及其期望的顺序。

    Returns:
        list: 排序后的唯一标签列表。
    """
    if column_name not in df.columns:
        return []
    all_labels = df[column_name].dropna().astype(str).str.split('[，,]').explode().str.strip()
    unique_other_labels = all_labels.unique().tolist()
    default_order_set = set(default_order_list)
    ordered_labels = [tag for tag in default_order_list if tag in unique_other_labels]
    other_labels = [tag for tag in unique_other_labels if tag not in default_order_set]
    final_sorted_list = ordered_labels + other_labels
    return final_sorted_list

def doubao_accuracy(sub_dataframes):
    """计算各个大小类的正确率"""
    DIMENSION_MAPPING = {ACC_COLUMNS[1]: (ACC_COLUMNS[1], '注意力小类'), ACC_COLUMNS[3]: (ACC_COLUMNS[3], '坐姿小类'), ACC_COLUMNS[4]: (ACC_COLUMNS[4], '视距检测'), ACC_COLUMNS[5]: (ACC_COLUMNS[5], '离座检测')}
    results = []
    for key, (col, dimension_name) in DIMENSION_MAPPING.items():
        df = sub_dataframes.get(key)
        if df is not None and col in df.columns:
            total = len(df)
            correct = df[col].sum()
            accuracy = f'{correct / total * 100:.2f}%' if total > 0 else '0%'
            results.append([dimension_name, total, correct, accuracy])
    return pd.DataFrame(results, columns=['维度', '总数量', '正确数量', '正确率'])

def get_global_variables_from_df(df):
    """从DataFrame获取并设置全局变量基准标签"""
    global ATTENTION_SMALL_CATEGORIES, POSTURE_SMALL_CATEGORIES, DISTANCE_BIG_STATUS, SEAT_CATEGORIES
    global ATTENTION_CATEGORIES_RESULT, POSTURE_CATEGORIES_RESULT, DISTANCE_STATUS_RESULT, SEAT_CATEGORIES_RESULT
    global ATTENTION_UNUSUAL_CATEGORIES, POSTURE_UNUSUAL_CATEGORIES, DISTANCE_UNUSUAL_STATUS
    ATTENTION_SMALL_CATEGORIES = get_sorted_unique_labels(df, EXPECTED_COLUMNS['attention_small'], ATTENTION_SMALL_CATEGORIES)
    POSTURE_SMALL_CATEGORIES = get_sorted_unique_labels(df, EXPECTED_COLUMNS['posture_small'], POSTURE_SMALL_CATEGORIES)
    ATTENTION_UNUSUAL_CATEGORIES = [cat for cat in ATTENTION_SMALL_CATEGORIES if cat != '集中'] if ATTENTION_SMALL_CATEGORIES else ATTENTION_SMALL_ABNORMAL
    POSTURE_UNUSUAL_CATEGORIES = [cat for cat in POSTURE_SMALL_CATEGORIES if cat != '正常'] if POSTURE_SMALL_CATEGORIES else POSTURE_SMALL_ABNORMAL
    ATTENTION_CATEGORIES_RESULT = get_sorted_unique_labels(df, PRED_COLUMNS[0], ATTENTION_SMALL_CATEGORIES)
    POSTURE_CATEGORIES_RESULT = get_sorted_unique_labels(df, PRED_COLUMNS[1], POSTURE_SMALL_CATEGORIES)

def build_evaluation_statistics_sheet(df, excel_file_path, include_scaled=False, scale_type='L1', use_merged_scale=False):
    """构建评测结果统计工作表（返回数据，不写入文件）"""
    all_stats = []
    category_acc_part = calculate_indicator_accuracy_part(df)
    all_stats.append(('##各个业务整体准确率交付指标', category_acc_part))
    attention_scaled_correct = 0
    posture_scaled_correct = 0
    if include_scaled:
        attention_indicator_temp = calculate_indicators(df, 'attention', include_scaled, scale_type, merged_scale=use_merged_scale)
        posture_indicator_temp = calculate_indicators(df, 'posture', include_scaled, scale_type, merged_scale=use_merged_scale)
        for val in attention_indicator_temp['召回率等比例缩放后']:
            if val != '0/0' and '/' in str(val):
                attention_scaled_correct += float(val.split('/')[0])
        attention_scaled_correct = round(attention_scaled_correct)
        for val in posture_indicator_temp['召回率等比例缩放后']:
            if val != '0/0' and '/' in str(val):
                posture_scaled_correct += float(val.split('/')[0])
        posture_scaled_correct = round(posture_scaled_correct)
    category_acc = calculate_indicator_accuracy_with_scaled(df, include_scaled, attention_scaled_correct, posture_scaled_correct, scale_type, use_merged_scale)
    all_stats.append(('##各个业务整体准确率交付指标', category_acc))
    attention_indicator = calculate_indicators(df, 'attention', include_scaled, scale_type, merged_scale=use_merged_scale)
    all_stats.append(('##注意力交付指标', attention_indicator))
    posture_indicator = calculate_indicators(df, 'posture', include_scaled, scale_type, merged_scale=use_merged_scale)
    all_stats.append(('##坐姿交付指标', posture_indicator))
    overall_stats = calculate_overall_stats(df)
    all_stats.append(('##总的正确率', overall_stats))
    category_acc = calculate_category_accuracy(df)
    all_stats.append(('##各个大小类的正确率', category_acc))
    cost_time_data = calculate_cost_time(df)
    all_stats.append(('##时延分布统计', cost_time_data))
    image_source_stats = calculate_image_source_stats(df)
    if not image_source_stats.empty:
        all_stats.append(('##不同图片来源统计', image_source_stats))
    resolution_stats = calculate_resolution_stats(df)
    if not resolution_stats.empty:
        all_stats.append(('##不同分辨率统计', resolution_stats))
    attention_difficulty = calculate_attention_difficulty(df)
    all_stats.append(('##注意力难易度准确率', attention_difficulty))
    attention_result = calculate_confusion_matrix_metrics(df, 'attention')
    all_stats.append(('##注意力统计_模型', attention_result))
    attention_cms = calculate_confusion_matrix(df, 'attention')
    all_stats.append(('##注意力混淆矩阵_模型', attention_cms))
    posture_difficulty = calculate_posture_difficulty(df)
    all_stats.append(('##坐姿难易度准确率', posture_difficulty))
    posture_result = calculate_confusion_matrix_metrics(df, 'posture')
    all_stats.append(('##坐姿统计_模型', posture_result))
    posture_cms = calculate_confusion_matrix(df, 'posture')
    all_stats.append(('##坐姿混淆矩阵_模型', posture_cms))
    return all_stats

def build_product_acceptance_sheet(df, excel_file_path, title, include_scaled=False, scale_type='L1', use_merged_scale=False):
    """构建与产品验收维度工作表的数据（返回数据和accuracy_dict，不写入文件）"""
    attention_small_col = EXPECTED_COLUMNS['attention_small']
    sitting_small_col = EXPECTED_COLUMNS['posture_small']
    attention_filter_list = ['遮挡', '其他', '无']
    posture_filter_list = ['遮挡', '其他', '无']
    attention_abnormal_list = ['睡觉', '疑似睡觉', '玩电子设备', '使用电子设备', '玩玩具', '吃零食', '离座', '遮挡', '其他']
    filtered_attention_df = df[~df[attention_small_col].isin(attention_filter_list)].copy()

    def sitting_filter_condition(s):
        return s[attention_small_col].isin(attention_filter_list) | s[sitting_small_col].isin(posture_filter_list) | s['实际注意力小类'].isin(attention_abnormal_list) | (s['实际注意力小类'] == '东张西望') & ~s['实际坐姿小类'].isin(['仰头', '仰躺'])
    filtered_sitting_df = df[~sitting_filter_condition(df)].copy()
    print(f'产品验收筛选出注意力有效数据{len(filtered_attention_df)}行')
    print(f'产品验收筛选出坐姿有效数据{len(filtered_sitting_df)}行')
    attention_posture_stats = []
    accuracy_dict = {}
    if include_scaled:
        attention_indicator = calculate_indicators(filtered_attention_df, 'attention', include_scaled, scale_type, merged_scale=use_merged_scale)
        posture_indicator = calculate_indicators(filtered_sitting_df, 'posture', include_scaled, scale_type, merged_scale=use_merged_scale)
        attention_scaled_correct = 0
        for val in attention_indicator['召回率等比例缩放后']:
            if val != '0/0' and '/' in str(val):
                attention_scaled_correct += float(val.split('/')[0])
        attention_scaled_correct = round(attention_scaled_correct)
        posture_scaled_correct = 0
        for val in posture_indicator['召回率等比例缩放后']:
            if val != '0/0' and '/' in str(val):
                posture_scaled_correct += float(val.split('/')[0])
        posture_scaled_correct = round(posture_scaled_correct)
        attention_posture_accuracy_part, accuracy_dict = calculate_seating_accuracy_part(filtered_attention_df, filtered_sitting_df, include_scaled, attention_scaled_correct, posture_scaled_correct, scale_type, merged_scale=use_merged_scale)
    else:
        attention_indicator = calculate_indicators(filtered_attention_df, 'attention')
        posture_indicator = calculate_indicators(filtered_sitting_df, 'posture')
        attention_posture_accuracy_part, accuracy_dict = calculate_seating_accuracy_part(filtered_attention_df, filtered_sitting_df)
    attention_posture_stats.append(('##各个业务的正确率', attention_posture_accuracy_part))
    attention_posture_stats.append(('##注意力交付指标', attention_indicator))
    attention_posture_stats.append(('##坐姿交付指标', posture_indicator))
    attention_cms_part = calculate_confusion_matrix(filtered_attention_df, 'attention')
    attention_posture_stats.append(('##注意力混淆矩阵', attention_cms_part))
    posture_cms_part = calculate_confusion_matrix(filtered_sitting_df, 'posture')
    attention_posture_stats.append(('##坐姿混淆矩阵', posture_cms_part))
    return (attention_posture_stats, accuracy_dict)

def build_evaluation_statistics_sheet_with_merged_scaled(df, excel_file_path, include_scaled=False, scale_type='L1', use_merged_scale=False, l1_attention_indicator=None, l1_posture_indicator=None, l2_attention_indicator=None, l2_posture_indicator=None):
    """构建评测结果统计工作表，使用L1和L2合并后的等比例缩放后指标"""
    all_stats = []
    category_acc_part = calculate_indicator_accuracy_part(df)
    all_stats.append(('##各个业务整体准确率交付指标', category_acc_part))
    attention_indicator = calculate_indicators(df, 'attention', include_scaled, 'L1', merged_scale=use_merged_scale)
    posture_indicator = calculate_indicators(df, 'posture', include_scaled, 'L1', merged_scale=use_merged_scale)
    if l1_attention_indicator is not None and l2_attention_indicator is not None:
        for idx, row in attention_indicator.iterrows():
            category = row['小类名']
            l1_val = l1_attention_indicator[l1_attention_indicator['小类名'] == category]['召回率等比例缩放后'].values
            l2_val = l2_attention_indicator[l2_attention_indicator['小类名'] == category]['召回率等比例缩放后'].values
            l1_numerator, l1_denominator = (0, 0)
            l2_numerator, l2_denominator = (0, 0)
            if len(l1_val) > 0 and l1_val[0] != '0/0' and ('/' in str(l1_val[0])):
                parts = l1_val[0].split('/')
                l1_numerator, l1_denominator = (float(parts[0]), float(parts[1]))
            if len(l2_val) > 0 and l2_val[0] != '0/0' and ('/' in str(l2_val[0])):
                parts = l2_val[0].split('/')
                l2_numerator, l2_denominator = (float(parts[0]), float(parts[1]))
            merged_numerator = l1_numerator + l2_numerator
            merged_denominator = l1_denominator + l2_denominator
            if merged_denominator > 0:
                attention_indicator.at[idx, '召回率等比例缩放后'] = f'{int(merged_numerator)}/{int(merged_denominator)}'
            else:
                attention_indicator.at[idx, '召回率等比例缩放后'] = '0/0'
    if l1_posture_indicator is not None and l2_posture_indicator is not None:
        for idx, row in posture_indicator.iterrows():
            category = row['小类名']
            l1_val = l1_posture_indicator[l1_posture_indicator['小类名'] == category]['召回率等比例缩放后'].values
            l2_val = l2_posture_indicator[l2_posture_indicator['小类名'] == category]['召回率等比例缩放后'].values
            l1_numerator, l1_denominator = (0, 0)
            l2_numerator, l2_denominator = (0, 0)
            if len(l1_val) > 0 and l1_val[0] != '0/0' and ('/' in str(l1_val[0])):
                parts = l1_val[0].split('/')
                l1_numerator, l1_denominator = (float(parts[0]), float(parts[1]))
            if len(l2_val) > 0 and l2_val[0] != '0/0' and ('/' in str(l2_val[0])):
                parts = l2_val[0].split('/')
                l2_numerator, l2_denominator = (float(parts[0]), float(parts[1]))
            merged_numerator = l1_numerator + l2_numerator
            merged_denominator = l1_denominator + l2_denominator
            if merged_denominator > 0:
                posture_indicator.at[idx, '召回率等比例缩放后'] = f'{int(merged_numerator)}/{int(merged_denominator)}'
            else:
                posture_indicator.at[idx, '召回率等比例缩放后'] = '0/0'
    attention_scaled_correct = 0
    attention_scaled_total = 0
    for val in attention_indicator['召回率等比例缩放后']:
        if val != '0/0' and '/' in str(val):
            parts = val.split('/')
            attention_scaled_correct += float(parts[0])
            attention_scaled_total += float(parts[1])
    attention_scaled_correct = round(attention_scaled_correct)
    attention_scaled_total = round(attention_scaled_total)
    posture_scaled_correct = 0
    posture_scaled_total = 0
    for val in posture_indicator['召回率等比例缩放后']:
        if val != '0/0' and '/' in str(val):
            parts = val.split('/')
            posture_scaled_correct += float(parts[0])
            posture_scaled_total += float(parts[1])
    posture_scaled_correct = round(posture_scaled_correct)
    posture_scaled_total = round(posture_scaled_total)
    category_acc = calculate_indicator_accuracy_with_scaled(df, include_scaled, attention_scaled_correct, posture_scaled_correct, 'L1', use_merged_scale)
    all_stats.append(('##各个业务整体准确率交付指标', category_acc))
    all_stats.append(('##注意力交付指标', attention_indicator))
    all_stats.append(('##坐姿交付指标', posture_indicator))
    overall_stats = calculate_overall_stats(df)
    all_stats.append(('##总的正确率', overall_stats))
    category_acc = calculate_category_accuracy(df)
    all_stats.append(('##各个大小类的正确率', category_acc))
    cost_time_data = calculate_cost_time(df)
    all_stats.append(('##时延分布统计', cost_time_data))
    image_source_stats = calculate_image_source_stats(df)
    if not image_source_stats.empty:
        all_stats.append(('##不同图片来源统计', image_source_stats))
    resolution_stats = calculate_resolution_stats(df)
    if not resolution_stats.empty:
        all_stats.append(('##不同分辨率统计', resolution_stats))
    attention_difficulty = calculate_attention_difficulty(df)
    all_stats.append(('##注意力难易度准确率', attention_difficulty))
    attention_result = calculate_confusion_matrix_metrics(df, 'attention')
    all_stats.append(('##注意力统计_模型', attention_result))
    attention_cms = calculate_confusion_matrix(df, 'attention')
    all_stats.append(('##注意力混淆矩阵_模型', attention_cms))
    posture_difficulty = calculate_posture_difficulty(df)
    all_stats.append(('##坐姿难易度准确率', posture_difficulty))
    posture_result = calculate_confusion_matrix_metrics(df, 'posture')
    all_stats.append(('##坐姿统计_模型', posture_result))
    posture_cms = calculate_confusion_matrix(df, 'posture')
    all_stats.append(('##坐姿混淆矩阵_模型', posture_cms))
    return all_stats

def build_product_acceptance_sheet_with_merged_scaled(df, excel_file_path, title, include_scaled=False, use_merged_scale=False, l1_attention_indicator=None, l1_posture_indicator=None, l2_attention_indicator=None, l2_posture_indicator=None):
    """构建与产品验收维度工作表的数据，通过合并L1和L2的等比例缩放后指标，并添加Weighted F1-score"""
    attention_small_col = EXPECTED_COLUMNS['attention_small']
    sitting_small_col = EXPECTED_COLUMNS['posture_small']
    attention_filter_list = ['遮挡', '其他', '无']
    posture_filter_list = ['遮挡', '其他', '无']
    attention_abnormal_list = ['睡觉', '疑似睡觉', '玩电子设备', '使用电子设备', '玩玩具', '吃零食', '离座', '遮挡', '其他']
    filtered_attention_df = df[~df[attention_small_col].isin(attention_filter_list)].copy()

    def sitting_filter_condition(s):
        return s[attention_small_col].isin(attention_filter_list) | s[sitting_small_col].isin(posture_filter_list) | s['实际注意力小类'].isin(attention_abnormal_list) | (s['实际注意力小类'] == '东张西望') & ~s['实际坐姿小类'].isin(['仰头', '仰躺'])
    filtered_sitting_df = df[~sitting_filter_condition(df)].copy()
    print(f'产品验收筛选出注意力有效数据{len(filtered_attention_df)}行')
    print(f'产品验收筛选出坐姿有效数据{len(filtered_sitting_df)}行')
    attention_posture_stats = []
    attention_indicator = calculate_indicators(filtered_attention_df, 'attention', include_scaled, 'L1', merged_scale=use_merged_scale)
    posture_indicator = calculate_indicators(filtered_sitting_df, 'posture', include_scaled, 'L1', merged_scale=use_merged_scale)
    accuracy_dict = {}
    if l1_attention_indicator is not None and l2_attention_indicator is not None:
        for idx, row in attention_indicator.iterrows():
            category = row['小类名']
            l1_val = l1_attention_indicator[l1_attention_indicator['小类名'] == category]['召回率等比例缩放后'].values
            l2_val = l2_attention_indicator[l2_attention_indicator['小类名'] == category]['召回率等比例缩放后'].values
            l1_numerator, l1_denominator = (0, 0)
            l2_numerator, l2_denominator = (0, 0)
            if len(l1_val) > 0 and l1_val[0] != '0/0' and ('/' in str(l1_val[0])):
                parts = l1_val[0].split('/')
                l1_numerator, l1_denominator = (float(parts[0]), float(parts[1]))
            if len(l2_val) > 0 and l2_val[0] != '0/0' and ('/' in str(l2_val[0])):
                parts = l2_val[0].split('/')
                l2_numerator, l2_denominator = (float(parts[0]), float(parts[1]))
            merged_numerator = l1_numerator + l2_numerator
            merged_denominator = l1_denominator + l2_denominator
            if merged_denominator > 0:
                attention_indicator.at[idx, '召回率等比例缩放后'] = f'{int(merged_numerator)}/{int(merged_denominator)}'
            else:
                attention_indicator.at[idx, '召回率等比例缩放后'] = '0/0'
    if l1_posture_indicator is not None and l2_posture_indicator is not None:
        for idx, row in posture_indicator.iterrows():
            category = row['小类名']
            l1_val = l1_posture_indicator[l1_posture_indicator['小类名'] == category]['召回率等比例缩放后'].values
            l2_val = l2_posture_indicator[l2_posture_indicator['小类名'] == category]['召回率等比例缩放后'].values
            l1_numerator, l1_denominator = (0, 0)
            l2_numerator, l2_denominator = (0, 0)
            if len(l1_val) > 0 and l1_val[0] != '0/0' and ('/' in str(l1_val[0])):
                parts = l1_val[0].split('/')
                l1_numerator, l1_denominator = (float(parts[0]), float(parts[1]))
            if len(l2_val) > 0 and l2_val[0] != '0/0' and ('/' in str(l2_val[0])):
                parts = l2_val[0].split('/')
                l2_numerator, l2_denominator = (float(parts[0]), float(parts[1]))
            merged_numerator = l1_numerator + l2_numerator
            merged_denominator = l1_denominator + l2_denominator
            if merged_denominator > 0:
                posture_indicator.at[idx, '召回率等比例缩放后'] = f'{int(merged_numerator)}/{int(merged_denominator)}'
            else:
                posture_indicator.at[idx, '召回率等比例缩放后'] = '0/0'
    attention_scaled_correct = 0
    attention_scaled_total = 0
    for val in attention_indicator['召回率等比例缩放后']:
        if val != '0/0' and '/' in str(val):
            parts = val.split('/')
            attention_scaled_correct += float(parts[0])
            attention_scaled_total += float(parts[1])
    attention_scaled_correct = round(attention_scaled_correct)
    attention_scaled_total = round(attention_scaled_total)
    posture_scaled_correct = 0
    posture_scaled_total = 0
    for val in posture_indicator['召回率等比例缩放后']:
        if val != '0/0' and '/' in str(val):
            parts = val.split('/')
            posture_scaled_correct += float(parts[0])
            posture_scaled_total += float(parts[1])
    posture_scaled_correct = round(posture_scaled_correct)
    posture_scaled_total = round(posture_scaled_total)
    attention_posture_accuracy_part, accuracy_dict = calculate_seating_accuracy_part(filtered_attention_df, filtered_sitting_df, include_scaled, attention_scaled_correct, posture_scaled_correct, 'L1', merged_scale=use_merged_scale)
    if attention_posture_accuracy_part is not None and len(attention_posture_accuracy_part) >= 2:
        for idx, row in attention_posture_accuracy_part.iterrows():
            if row['维度'] == '注意力小类':
                attention_posture_accuracy_part.at[idx, '等比例缩放后总数量'] = attention_scaled_total
                attention_posture_accuracy_part.at[idx, '等比例缩放后正确数量'] = attention_scaled_correct
                attention_posture_accuracy_part.at[idx, '等比例缩放后正确率'] = f'{attention_scaled_correct / attention_scaled_total * 100:.2f}%' if attention_scaled_total > 0 else '0%'
            elif row['维度'] == '坐姿小类':
                attention_posture_accuracy_part.at[idx, '等比例缩放后总数量'] = posture_scaled_total
                attention_posture_accuracy_part.at[idx, '等比例缩放后正确数量'] = posture_scaled_correct
                attention_posture_accuracy_part.at[idx, '等比例缩放后正确率'] = f'{posture_scaled_correct / posture_scaled_total * 100:.2f}%' if posture_scaled_total > 0 else '0%'
    attention_posture_stats.append(('##各个业务的正确率', attention_posture_accuracy_part))
    attention_posture_stats.append(('##注意力交付指标', attention_indicator))
    attention_posture_stats.append(('##坐姿交付指标', posture_indicator))
    if l1_attention_indicator is not None and l2_attention_indicator is not None and ('F1-score' in attention_indicator.columns):
        weighted_f1_scores = []
        for idx, row in attention_indicator.iterrows():
            category = row['小类名']
            l1_f1 = l1_attention_indicator[l1_attention_indicator['小类名'] == category]['F1-score'].values
            l2_f1 = l2_attention_indicator[l2_attention_indicator['小类名'] == category]['F1-score'].values
            try:
                l1_val = float(str(l1_f1[0]).replace('%', '')) / 100 if len(l1_f1) > 0 else 0.0
            except (ValueError, IndexError):
                l1_val = 0.0
            try:
                l2_val = float(str(l2_f1[0]).replace('%', '')) / 100 if len(l2_f1) > 0 else 0.0
            except (ValueError, IndexError):
                l2_val = 0.0
            weighted_f1 = l1_val * 0.8 + l2_val * 0.2
            weighted_f1_scores.append(f'{weighted_f1:.2%}')
        attention_indicator['Weighted F1-score'] = weighted_f1_scores
    if l1_posture_indicator is not None and l2_posture_indicator is not None and ('F1-score' in posture_indicator.columns):
        weighted_f1_scores = []
        for idx, row in posture_indicator.iterrows():
            category = row['小类名']
            l1_f1 = l1_posture_indicator[l1_posture_indicator['小类名'] == category]['F1-score'].values
            l2_f1 = l2_posture_indicator[l2_posture_indicator['小类名'] == category]['F1-score'].values
            try:
                l1_val = float(str(l1_f1[0]).replace('%', '')) / 100 if len(l1_f1) > 0 else 0.0
            except (ValueError, IndexError):
                l1_val = 0.0
            try:
                l2_val = float(str(l2_f1[0]).replace('%', '')) / 100 if len(l2_f1) > 0 else 0.0
            except (ValueError, IndexError):
                l2_val = 0.0
            weighted_f1 = l1_val * 0.8 + l2_val * 0.2
            weighted_f1_scores.append(f'{weighted_f1:.2%}')
        posture_indicator['Weighted F1-score'] = weighted_f1_scores
    attention_cms_part = calculate_confusion_matrix(filtered_attention_df, 'attention')
    attention_posture_stats.append(('##注意力混淆矩阵', attention_cms_part))
    posture_cms_part = calculate_confusion_matrix(filtered_sitting_df, 'posture')
    attention_posture_stats.append(('##坐姿混淆矩阵', posture_cms_part))
    return (attention_posture_stats, accuracy_dict)

def processExcel(excel_file_path, limit):
    """主函数（覆盖原文件）"""
    try:
        print(f'开始处理文件: {excel_file_path}')
        nrows = None
        if limit is not None:
            try:
                limit_int = int(limit)
                if limit_int > 0:
                    nrows = limit_int
                    print(f'将读取 {nrows} 行数据 (不包括表头)。')
                else:
                    print('limit为0或负数，将读取完整文件。')
            except (ValueError, TypeError):
                print(f"limit参数 '{limit}' 无效，将读取完整文件。")
        df = pd.read_excel(excel_file_path, nrows=nrows)
        print(f'成功读取数据，共{len(df)}行')
        if df.empty:
            print('数据为空，终止处理流程')
            return {}
        get_global_variables_from_df(df)
        df = add_all_acc_column(df)
        all_sheets_data = {}
        l1_df = df[df['L级标签'].str.startswith('L1', na=False)].copy()
        l2_mask = df['L级标签'].apply(lambda x: str(x).startswith('L2') if pd.notna(x) else False)
        l2_df = df[l2_mask].copy()
        l1_product_stats, _ = build_product_acceptance_sheet(l1_df, excel_file_path, 'L级标签列L1统计', include_scaled=True)
        l2_product_stats, _ = build_product_acceptance_sheet(l2_df, excel_file_path, 'L级标签列L2汇总统计', include_scaled=True, scale_type='L2')
        l1_attention_indicator = None
        l1_posture_indicator = None
        l2_attention_indicator = None
        l2_posture_indicator = None
        for title, data in l1_product_stats:
            if '注意力交付指标' in title:
                l1_attention_indicator = data
            elif '坐姿交付指标' in title:
                l1_posture_indicator = data
        for title, data in l2_product_stats:
            if '注意力交付指标' in title:
                l2_attention_indicator = data
            elif '坐姿交付指标' in title:
                l2_posture_indicator = data
        evaluation_stats = build_evaluation_statistics_sheet_with_merged_scaled(df, excel_file_path, include_scaled=True, use_merged_scale=True, l1_attention_indicator=l1_attention_indicator, l1_posture_indicator=l1_posture_indicator, l2_attention_indicator=l2_attention_indicator, l2_posture_indicator=l2_posture_indicator)
        all_sheets_data['评测结果统计'] = evaluation_stats
        product_acceptance_stats, accuracy_dict = build_product_acceptance_sheet_with_merged_scaled(df, excel_file_path, '与产品验收维度保持一致', include_scaled=True, use_merged_scale=True, l1_attention_indicator=l1_attention_indicator, l1_posture_indicator=l1_posture_indicator, l2_attention_indicator=l2_attention_indicator, l2_posture_indicator=l2_posture_indicator)
        all_sheets_data['与产品验收维度保持一致'] = product_acceptance_stats
        all_sheets_data['L级标签列L1统计'] = l1_product_stats
        all_sheets_data['L级标签列L2汇总统计'] = l2_product_stats
        if CAMERA_POSITION_COL in df.columns:
            camera_front_df = df[df[CAMERA_POSITION_COL].str.contains('正', na=False)].copy()
            print(f'筛选出正视角数据{len(camera_front_df)}行')
            all_sheets_data['正视角数据统计'], _ = build_product_acceptance_sheet(camera_front_df, excel_file_path, '正视角数据统计')
            camera_side_df = df[~df[CAMERA_POSITION_COL].str.contains('正', na=False)].copy()
            print(f'筛选出侧视角数据{len(camera_side_df)}行')
            all_sheets_data['侧视角数据统计'], _ = build_product_acceptance_sheet(camera_side_df, excel_file_path, '侧视角数据统计')
            camera_right_df = df[df[CAMERA_POSITION_COL].str.contains('右', na=False)].copy()
            print(f'筛选出右视角数据{len(camera_right_df)}行')
            all_sheets_data['右视角数据统计'], _ = build_product_acceptance_sheet(camera_right_df, excel_file_path, '右视角数据统计')
            camera_left_df = df[df[CAMERA_POSITION_COL].str.contains('左', na=False)].copy()
            print(f'筛选出左视角数据{len(camera_left_df)}行')
            all_sheets_data['左视角数据统计'], _ = build_product_acceptance_sheet(camera_left_df, excel_file_path, '左视角数据统计')
        for col in DYNAMIC_STATISTICS_COLS:
            unique_values = df[col].dropna().unique()
            for value in unique_values:
                sub_df = df[df[col] == value].copy()
                print(f'列[{col}] 值[{value}] 筛选出{len(sub_df)}行数据')
                is_l1 = col == 'L级标签' and str(value).startswith('L1')
                sheet_name = f'{col}列{value}统计'
                all_sheets_data[sheet_name], _ = build_product_acceptance_sheet(sub_df, excel_file_path, sheet_name, include_scaled=is_l1)
        with pd.ExcelWriter(excel_file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            workbook = writer.book
            format_all_acc_column(workbook, 'Sheet1', df)
            for sheet_name, stats in all_sheets_data.items():
                write_dataframes_to_sheet(writer, stats, sheet_name)
        print(f'统计完成！结果已保存到原文件中。')
        print('- 已添加all_acc列，并设置了红/绿色填充')
        print('- 已创建多个统计sheet')
        return accuracy_dict
    except Exception as e:
        print(f'处理过程中出现错误: {str(e)}')
        import traceback
        traceback.print_exc()

def processReferenceDoubao(excel_file_path: str, limit=None):
    try:
        print(f'开始处理文件: {excel_file_path}')
        nrows = None
        if limit is not None:
            try:
                limit_int = int(limit)
                if limit_int > 0:
                    nrows = limit_int
                    print(f'将读取 {nrows} 行数据 (不包括表头)。')
                else:
                    print('limit为0或负数，将读取完整文件。')
            except (ValueError, TypeError):
                print(f"limit参数 '{limit}' 无效，将读取完整文件。")
        df = pd.read_excel(excel_file_path, nrows=nrows)
        print(f'成功读取数据，共{len(df)}行')
        if df.empty:
            print('数据为空，终止处理流程')
            return []
        sub_dataframes = {}
        valid_columns = []
        for col in DOUBAO_ACC_COLUMNS:
            if col in df.columns:
                sub_df = df[df[col] == True].copy()
                sub_name = col.replace('豆包-', '')
                sub_dataframes[sub_name] = sub_df
                valid_columns.append(sub_name)
                print(f"根据'{col}'条件筛选出{len(sub_df)}行数据")
            else:
                print(f"警告：列 '{col}' 不存在，跳过该子表创建")
        all_stats = []
        if sub_dataframes:
            category_acc = doubao_accuracy(sub_dataframes)
            all_stats.append(('##各个业务的正确率', category_acc))
        else:
            print('警告：无有效子表，跳过正确率计算')
        indicator_mapping = {'attention_category_acc': ('attention', '##注意力交付指标'), 'sitting_posture_category_acc': ('posture', '##坐姿交付指标')}
        for col_name, (indicator_type, title) in indicator_mapping.items():
            if col_name in valid_columns:
                try:
                    indicator = calculate_indicators(sub_dataframes[col_name], indicator_type)
                    all_stats.append((title, indicator))
                except KeyError as e:
                    print(f"计算错误：子表 '{col_name}' 处理失败 - {str(e)}")
            else:
                print(f"跳过：子表 '{col_name}' 不存在，不计算 {title}")
        with pd.ExcelWriter(excel_file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            write_dataframes_to_sheet(writer, all_stats, '根据豆包正确项统计结果')
        print('根据豆包正确项统计完成！结果和子表已保存到原文件中。')
    except Exception as e:
        print(f'处理过程中出现错误: {str(e)}')
        import traceback
        traceback.print_exc()
