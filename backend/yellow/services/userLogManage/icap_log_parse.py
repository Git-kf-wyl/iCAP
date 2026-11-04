# Private iCAP Yellow business implementation. Do not publish.
import json
import xlsxwriter
import sys
import os
from datetime import datetime, timezone, timedelta
CHINA_TZ = timezone(timedelta(hours=8))

def safe_str(value):
    """安全转为字符串，None 或其他类型也处理"""
    if value is None:
        return ''
    return str(value)

def parse_timestamp(ts):
    """
    自动识别时间戳是秒级还是毫秒级，并转换为中国时区的格式化字符串
    """
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        return safe_str(ts)
    if ts > 10000000000.0:
        dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
    else:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    dt_beijing = dt.astimezone(CHINA_TZ)
    return dt_beijing.strftime('%Y-%m-%d %H:%M:%S')

def parse_jsonl_to_excel(input_path, output_path, max_config_len=1000):
    if not os.path.isfile(input_path):
        print(f'❌ 错误：输入文件不存在: {input_path}')
        return
    workbook = xlsxwriter.Workbook(output_path, {'strings_to_urls': False})
    worksheet = workbook.add_worksheet()
    headers = ['user_id', 'timestamp', 'type', 'content', 'model_id', 'query', 'response', 'config']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    row = 1
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f'⚠️ 第 {line_num} 行 JSON 解析失败，跳过。错误: {e}')
                    continue
                user_id = safe_str(record.get('user_id', ''))
                raw_ts = record.get('timestamp', '')
                type_val = safe_str(record.get('type', ''))
                ts_formatted = parse_timestamp(raw_ts)
                content = safe_str(record.get('content', ''))
                model_id = safe_str(record.get('model_id', ''))
                query = record.get('query', '')
                response = record.get('response', '')
                config = record.get('config', '')
                if config is None:
                    config_str = ''
                elif isinstance(config, str):
                    config_str = config
                else:
                    try:
                        config_str = json.dumps(config, ensure_ascii=False)
                    except Exception:
                        config_str = str(config)
                if len(config_str) > max_config_len:
                    config_str = config_str[:max_config_len]
                worksheet.write(row, 0, user_id)
                worksheet.write(row, 1, ts_formatted)
                worksheet.write(row, 2, type_val)
                worksheet.write(row, 3, content)
                worksheet.write(row, 4, model_id)
                worksheet.write(row, 5, query)
                worksheet.write(row, 6, response)
                worksheet.write(row, 7, config_str)
                row += 1
                if row % 100000 == 1:
                    print(f'✅ 已处理 {row - 1} 行...')
    except Exception as e:
        print(f'❌ 处理过程中出错: {e}')
        import traceback
        traceback.print_exc()
    finally:
        workbook.close()
    print(f'🎉 完成！结果已保存至: {output_path}')
import pandas as pd
import os
from typing import List
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def merge_excel_files(file_paths: List[str], output_path: str='merged_output.xlsx'):
    """
    合并多个Excel文件，并根据指定列去重，最后按timestamp排序。

    :param file_paths: Excel文件路径列表
    :param output_path: 输出文件路径（可选）
    """
    all_data = []
    for file_path in file_paths:
        try:
            if not os.path.exists(file_path):
                logging.warning(f'文件不存在: {file_path}')
                continue
            df = pd.read_excel(file_path)
            logging.info(f'读取文件: {file_path}, 行数: {len(df)}')
            dedup_columns = ['user_id', 'timestamp', 'type']
            if not all((col in df.columns for col in dedup_columns)):
                logging.error(f'文件 {file_path} 缺少去重列: {dedup_columns}')
                continue
            all_data.append(df)
        except Exception as e:
            logging.error(f'读取文件失败: {file_path}, 错误: {e}')
            continue
    if not all_data:
        logging.error('没有成功读取任何文件，无法合并。')
        return
    merged_df = pd.concat(all_data, ignore_index=True)
    logging.info(f'合并后总行数: {len(merged_df)}')
    dedup_columns = ['user_id', 'timestamp', 'type', 'model_id']
    merged_df.drop_duplicates(subset=dedup_columns, keep='first', inplace=True)
    logging.info(f'去重后行数: {len(merged_df)}')
    if 'timestamp' in merged_df.columns:
        try:
            merged_df['timestamp'] = pd.to_datetime(merged_df['timestamp'], errors='coerce')
            merged_df.sort_values(by='timestamp', inplace=True)
            logging.info('已按 timestamp 从早到晚排序。')
        except Exception as e:
            logging.warning(f'无法将 timestamp 转换为时间类型，可能无法正确排序: {e}')
            merged_df.sort_values(by='timestamp', inplace=True)
            logging.info('按 timestamp 字符串排序（可能不准确）。')
    else:
        logging.error("合并后的数据中缺少 'timestamp' 列，无法排序。")
    try:
        merged_df.to_excel(output_path, index=False)
        logging.info(f'合并去重并排序结果已保存至: {output_path}')
    except Exception as e:
        logging.error(f'保存文件失败: {output_path}, 错误: {e}')
