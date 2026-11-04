from state_storage import open_state, state_exists, state_isfile
# Private iCAP Yellow business implementation. Do not publish.
import base64
import csv
import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from collections import deque
from copy import deepcopy
from datetime import datetime
import chardet
import pandas as pd
from bs4 import BeautifulSoup
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Pt, Inches
from utils.consts import *

def get_encoding(file_path):
    with open_state(file_path, 'rb') as f:
        result = chardet.detect(f.read(1024))
    print(f'{file_path} encoding info: {result}')
    return result['encoding']

def get_tasks():
    encodings = get_encoding(TASKS)
    with open_state(TASKS, 'r', encoding=encodings) as f:
        tasks = json.load(f)
    return tasks

def set_tasks(tasks):
    with open_state(TASKS, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

def get_report_tasks():
    if not state_exists(REPORTTASKS):
        return {}
    encodings = get_encoding(REPORTTASKS)
    with open_state(REPORTTASKS, 'r', encoding=encodings) as f:
        return json.load(f)

def set_report_tasks(report_tasks):
    with open_state(REPORTTASKS, 'w', encoding='utf-8') as f:
        json.dump(report_tasks, f, ensure_ascii=False, indent=4)

def get_report_tasks_from_path(file_path):
    """从指定路径读取 JSON 任务文件"""
    if not state_exists(file_path):
        return {}
    encodings = get_encoding(file_path)
    with open_state(file_path, 'r', encoding=encodings) as f:
        return json.load(f)

def set_report_tasks_to_path(file_path, report_tasks):
    """将任务字典写入指定路径的 JSON 文件"""
    dir_name = os.path.dirname(file_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open_state(file_path, 'w', encoding='utf-8') as f:
        json.dump(report_tasks, f, ensure_ascii=False, indent=4)

def get_one_task(task_id):
    tasks = get_tasks()
    for id, task in tasks.items():
        if id == task_id:
            return task
    return {}

def get_hg_download_tasks():
    if not state_exists(HUGGINGFACE_DOWNLOAD_TASKS):
        with open_state(HUGGINGFACE_DOWNLOAD_TASKS, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        print(f'[INFO] Created new JSON file: {HUGGINGFACE_DOWNLOAD_TASKS}')
    encodings = get_encoding(HUGGINGFACE_DOWNLOAD_TASKS)
    with open_state(HUGGINGFACE_DOWNLOAD_TASKS, 'r', encoding=encodings) as f:
        download_tasks = json.load(f)
    return download_tasks

def set_hg_download_tasks(download_tasks):
    with open_state(HUGGINGFACE_DOWNLOAD_TASKS, 'w', encoding='utf-8') as f:
        json.dump(download_tasks, f, ensure_ascii=False, indent=4)

def build_directory_tree(root_path, depth=4):
    """
    递归构建目录树结构，支持最多 depth 层。
    特殊处理：.xlsx 文件作为虚拟目录，其子节点为工作表名称列表
    """
    if depth == 0:
        return os.listdir(root_path) if os.path.isdir(root_path) else []
    tree = {}
    try:
        entries = os.listdir(root_path)
    except (OSError, PermissionError):
        return tree
    for entry in entries:
        full_path = os.path.join(root_path, entry)
        if os.path.isdir(full_path):
            tree[entry] = build_directory_tree(full_path, depth - 1)
        elif entry.lower().endswith('.xlsx') and state_isfile(full_path):
            try:
                import openpyxl
                workbook = openpyxl.load_workbook(full_path, read_only=True)
                sheet_names = workbook.sheetnames
                tree[entry] = sheet_names
                workbook.close()
            except ImportError:
                print(f'未安装openpyxl时当作普通文件处理')
                pass
            except Exception:
                print(f'文件损坏或其他错误时跳过')
                pass
    return tree

def collect_keys_and_flatten_leaf_values(data):
    if not isinstance(data, dict):
        return []
    levels = []
    queue = deque([(data, 0)])
    all_leaf_values = []
    while queue:
        current, level = queue.popleft()
        while len(levels) <= level:
            levels.append([])
        if isinstance(current, dict):
            keys = list(current.keys())
            levels[level].extend(keys)
            for key in keys:
                queue.append((current[key], level + 1))
        elif isinstance(current, list):
            all_leaf_values.extend(current)
        else:
            all_leaf_values.append(current)
    if levels:
        levels[-1] = all_leaf_values
    else:
        levels = [all_leaf_values]
    return levels

def merge_dicts(*dicts):

    def merge_two_dicts(dict_a, dict_b):
        for key in dict_b:
            if key not in dict_a:
                dict_a[key] = deepcopy(dict_b[key])
            elif isinstance(dict_a[key], dict) and isinstance(dict_b[key], dict):
                merge_two_dicts(dict_a[key], dict_b[key])
            elif isinstance(dict_a[key], list) and isinstance(dict_b[key], list):
                dict_a[key].extent(dict_b[key])
            elif isinstance(dict_a[key], dict) and isinstance(dict_b[key], list):
                dict_a[key].update({value: '' for value in dict_b[key]})
    result = {}
    for d in dicts:
        merge_two_dicts(result, d)
    return result

def get_model_info_list():
    encodings = get_encoding(MODEL_CFG_PATH)
    if encodings is not None:
        with open_state(MODEL_CFG_PATH, 'r', encoding=encodings) as f:
            model_info_list = json.load(f)
    else:
        model_info_list = []
    return model_info_list

def get_one_model_config(model_id):
    model_info_list = get_model_info_list()
    model_config = None
    for cfg in model_info_list:
        if cfg['model_id'] == model_id:
            model_config = cfg
            break
    return model_config

def _flatten_with_rules(obj, parent_key='', sep='.', current_path=()):
    """
    递归展平字典，遵循以下规则：
    1. 只处理最底层的 key（叶子节点）
    2. 遇到 list 时，取第 0 个元素继续递归（如果 list 非空）
    3. 相同 key 路径时，后面的值会覆盖前面的（自然满足"取最后一个"）
    """
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f'{parent_key}{sep}{k}' if parent_key else k
            new_path = current_path + (k,)
            if isinstance(v, dict):
                nested_items = _flatten_with_rules(v, new_key, sep, new_path)
                items.update(nested_items)
            elif isinstance(v, list):
                if v:
                    first_element = v[0]
                    if isinstance(first_element, dict):
                        nested_items = _flatten_with_rules(first_element, new_key, sep, new_path)
                        items.update(nested_items)
                    else:
                        items[new_key] = first_element
                else:
                    items[new_key] = ''
            else:
                items[new_key] = v
    else:
        pass
    return items

def jsonl_to_csv(jsonl_path, csv_path):
    """
    将 JSONL 文件转换为 CSV 文件。

    核心原则：
    1. 最底层的key，都算作csv的某一列；
    2. 如果存在list，取第0个元素向下递归；
    3. 如果遇到key值相同，取最外层的，如果层级相同，取最后一个；
    4. 支持中文和阿拉伯语等多语言文本。

    参数:
        jsonl_path (str): 输入的 .jsonl 文件路径
        csv_path (str): 输出的 .csv 文件路径
    """
    all_records = []
    all_fields = set()
    with open_state(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    print(f'警告: 第 {line_num} 行不是 JSON 对象，已跳过: {line[:50]}...')
                    continue
                flat_record = _flatten_with_rules(data)
                all_records.append(flat_record)
                all_fields.update(flat_record.keys())
            except json.JSONDecodeError as e:
                print(f'错误: 第 {line_num} 行 JSON 解析失败，已跳过。错误: {e}')
                continue
    if not all_records:
        print('没有有效记录，未生成 CSV。')
        return
    sorted_fields = sorted(all_fields)
    with open_state(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=sorted_fields, restval='', extrasaction='ignore')
        writer.writeheader()
        for record in all_records:
            row = {field: record.get(field, '') for field in sorted_fields}
            writer.writerow(row)
    print(f'   共 {len(all_records)} 行，{len(sorted_fields)} 列')

def write_log(log_path, log_info):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with open_state(os.path.join(log_path, 'eval_log.log'), 'a', encoding='utf-8') as log_file:
        log_file.write(f'{timestamp}: {log_info}\n')

def txt_to_excel(txt_path, excel_base_path, chunk_size=9999):
    try:
        if not state_exists(txt_path):
            print(f'错误: 文件 {txt_path} 不存在')
            return ([], [])
        if not excel_base_path.lower().endswith(('.xlsx', '.xls')):
            print(f'警告: 文件路径 {excel_base_path} 缺少扩展名，已添加 .xlsx')
            excel_base_path += '.xlsx'
        with open_state(txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        non_empty_lines = [line.rstrip('\n\r') for line in lines if line.strip()]
        if not non_empty_lines:
            return ([], [])
        serial_numbers = list(range(1, len(non_empty_lines) + 1))
        output_dir = os.path.dirname(excel_base_path)
        if output_dir and (not state_exists(output_dir)):
            os.makedirs(output_dir)
        total_lines = len(non_empty_lines)
        total_files = (total_lines + chunk_size - 1) // chunk_size
        excel_path_list = []
        all_chunk_lines = []
        for i in range(total_files):
            start_idx = i * chunk_size
            end_idx = min((i + 1) * chunk_size, total_lines)
            chunk_lines = non_empty_lines[start_idx:end_idx]
            chunk_serial_numbers = serial_numbers[start_idx:end_idx]
            df = pd.DataFrame({'序号': chunk_serial_numbers, '文本': chunk_lines})
            df.to_excel(excel_base_path, index=False, sheet_name='Sheet1')
            excel_path_list.append(excel_base_path)
            all_chunk_lines.append(chunk_lines)
        return (excel_path_list, all_chunk_lines)
    except Exception as e:
        print(f'处理过程出错: {str(e)}')
        return ([], [])

def base64_to_audio(base64_str, output_path):
    """
    将 Base64 编码的音频数据还原为音频文件
    :param base64_str: Base64 编码的字符串（可以是带 data URI 前缀的，也可以是纯 Base64）
    :param output_path: 输出文件路径，如 "output.wav" 或 "output.pcm"
    """
    if base64_str.startswith('data:'):
        base64_str = base64_str.split(',', 1)[1]
    audio_data = base64.b64decode(base64_str)
    with open_state(output_path, 'wb') as f:
        f.write(audio_data)

def _decode_zip_filename(raw_filename):
    """
    修复ZIP文件中包含中文的文件名乱码问题。

    Python 3 的 zipfile 模块在读取文件名时，若字节不是有效的 UTF-8，
    会默认用 CP437 解码。对于简体中文 Windows 环境创建的 ZIP，
    实际编码是 GBK/GB18030，导致文件名乱码。

    修复策略：
    1. 先将已被 CP437 解码为乱码的 str 编码回 bytes（用 cp437）
    2. 然后用正确的编码（GBK/GB18030）重新解码
    3. 只有在前两步产生可读字符串时才替换，否则保留原值
    """
    if isinstance(raw_filename, bytes):
        for enc in ('utf-8', 'gbk', 'gb18030'):
            try:
                return raw_filename.decode(enc)
            except UnicodeDecodeError:
                continue
        print(f'警告：无法解码文件名: {raw_filename!r}')
        return raw_filename.decode('utf-8', errors='replace')
    if any((ord(c) > 127 for c in raw_filename)):
        try:
            raw_bytes = raw_filename.encode('cp437')
            decoded = raw_bytes.decode('gbk')
            if decoded.isprintable() or any(('一' <= c <= '鿿' for c in decoded)):
                return decoded
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        try:
            raw_bytes = raw_filename.encode('cp437')
            decoded = raw_bytes.decode('gb18030')
            if decoded.isprintable() or any(('一' <= c <= '鿿' for c in decoded)):
                return decoded
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return raw_filename

def unzip_if_needed(zip_path, target_dir):
    """
    更新ZIP文件中的内容到目标目录：
      - 更新缺失或过期的ZIP文件
      - 保留目录中原有的非ZIP文件
      - 不删除ZIP文件中已移除的旧文件

    :param zip_path: ZIP文件路径
    :param target_dir: 目标目录路径
    """
    if not state_exists(zip_path):
        raise FileNotFoundError(f'ZIP文件 {zip_path} 不存在')
    os.makedirs(target_dir, exist_ok=True)
    zip_files = {}
    raw_by_fixed = {}
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                if not info.is_dir():
                    raw_filename = info.filename
                    rel_path = _decode_zip_filename(raw_filename).replace('\\', '/')
                    zip_time = time.mktime(info.date_time + (0, 0, -1))
                    zip_files[rel_path] = zip_time
                    raw_by_fixed[rel_path] = raw_filename
    except Exception as e:
        raise RuntimeError(f'解析ZIP文件失败: {str(e)}') from e
    files_to_update = []
    for rel_path, zip_time in zip_files.items():
        abs_path = os.path.join(target_dir, rel_path)
        if not state_exists(abs_path) or os.path.getmtime(abs_path) < zip_time:
            files_to_update.append(rel_path)
    if not files_to_update:
        print(f'所有文件已最新，无需更新: {target_dir}')
        return
    temp_dir = tempfile.mkdtemp(prefix='unzip_update_')
    try:
        print(f'解压需要更新的文件: {len(files_to_update)} 个')
        with zipfile.ZipFile(zip_path) as zf:
            for rel_path in files_to_update:
                raw_name = raw_by_fixed[rel_path]
                fixed_name = _decode_zip_filename(raw_name)
                zf.extract(raw_name, temp_dir)
                src_raw = os.path.join(temp_dir, raw_name)
                src_fixed = os.path.join(temp_dir, fixed_name)
                if fixed_name != raw_name:
                    if state_exists(src_raw):
                        os.makedirs(os.path.dirname(src_fixed), exist_ok=True)
                        os.rename(src_raw, src_fixed)
                src = src_fixed if state_exists(src_fixed) else src_raw
                dst = os.path.join(target_dir, rel_path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
    finally:
        shutil.rmtree(temp_dir)
    print(f'更新完成: {target_dir}')

def add_row_to_table(table):
    """为 python-pptx Table 动态添加一行（复制最后一行结构）"""
    tbl = table._tbl
    tr_list = tbl.xpath('a:tr')
    if not tr_list:
        raise ValueError('表格无行，无法添加')
    last_tr = tr_list[-1]
    new_tr = deepcopy(last_tr)
    new_tr.set('h', str(int(last_tr.get('h', '360000'))))
    for tc in new_tr.xpath('a:tc'):
        txBody = tc.get_or_add_txBody()
        txBody.clear_content()
    tbl.append(new_tr)
    table._rows._rgt = len(tr_list) + 1

def set_cell_text_centered(cell, text: str):
    """设置单元格文字内容并水平+垂直居中"""
    tf = cell.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.text = text
    for run in p.runs:
        run.font.size = Pt(14)
    p.alignment = PP_ALIGN.CENTER
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    return p

def set_shape_text(shapes, key_word, new_text: str, font_size=12, is_bold=False):
    sum_shape = None
    for shape in shapes:
        print(shape.name)
        if shape.name == key_word:
            sum_shape = shape
            break
    if sum_shape:
        if not sum_shape.has_text_frame:
            raise ValueError('该shape不含文本框')
        tf = sum_shape.text_frame
        if isinstance(new_text, str):
            lines = [line.strip() for line in new_text.split('\n') if line.strip()]
        else:
            lines = [str(line).strip() for line in new_text if str(line).strip()]
        tf.clear()
        if len(lines) < 2:
            p = tf.paragraphs[0]
            p.text = new_text
            for run in p.runs:
                run.font.size = Pt(font_size)
                run.font.bold = is_bold
        else:
            for i, line_text in enumerate(lines):
                prefix = '•  '
                if i == 0 and len(tf.paragraphs) > i:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.line_spacing = 1.5
                run = p.add_run()
                run.text = prefix
                content_run = p.add_run()
                content_run.text = line_text
                for run in p.runs:
                    run.font.size = Pt(font_size)
                    run.font.bold = is_bold

def table_to_json(table_data):
    headers = table_data[0]
    rows = table_data[1:]
    result = []
    for row in rows:
        entry = {headers[i]: row[i] for i in range(len(headers))}
        result.append(entry)
    json_result = json.dumps(result, ensure_ascii=False, indent=4)
    return json_result

def dict_to_json(data):
    json_result = json.dumps(data, ensure_ascii=False, indent=4)
    return json_result

def replace_placeholder_keep_format(shape, placeholder: str, replacement: str):
    """
    替换 shape 中的占位符，支持跨 run 的情况
    保留原始格式（使用第一个 run 的格式作为新文本的格式）
    """
    if not shape.has_text_frame:
        return
    for paragraph in shape.text_frame.paragraphs:
        while True:
            runs = paragraph.runs
            if len(runs) == 0:
                break
            full_text = ''.join((run.text for run in runs))
            start_idx = full_text.find(placeholder)
            if start_idx == -1:
                break
            end_idx = start_idx + len(placeholder)
            char_idx = 0
            start_run_idx = -1
            end_run_idx = -1
            run_char_ranges = []
            for i, run in enumerate(runs):
                run_start = char_idx
                run_end = char_idx + len(run.text)
                run_char_ranges.append((run_start, run_end))
                if start_run_idx == -1 and run_end > start_idx:
                    start_run_idx = i
                if end_run_idx == -1 and run_end >= end_idx:
                    end_run_idx = i
                    break
                char_idx = run_end
            if start_run_idx == -1 or end_run_idx == -1:
                break
            first_run = runs[start_run_idx]
            font = first_run.font
            start_run_start, start_run_end = run_char_ranges[start_run_idx]
            end_run_start, end_run_end = run_char_ranges[end_run_idx]
            prefix = runs[start_run_idx].text[:start_idx - start_run_start]
            suffix = runs[end_run_idx].text[end_idx - end_run_start:]
            new_text = prefix + replacement + suffix
            runs[start_run_idx].text = new_text
            runs[start_run_idx].font.bold = font.bold
            runs[start_run_idx].font.italic = font.italic
            runs[start_run_idx].font.underline = font.underline
            runs[start_run_idx].font.size = font.size
            runs[start_run_idx].font.name = font.name
            for i in range(end_run_idx, start_run_idx, -1):
                p = runs[i]._r.getparent()
                p.remove(runs[i]._r)

def fill_model_placeholder(prs, slide_index, placeholder: str, model_name: str):
    """将所有页中 name='title' 的文本框内的 {{model}} 替换为 model_name"""
    if slide_index == -1:
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.name == 'title' and shape.has_text_frame:
                    replace_placeholder_keep_format(shape, placeholder, model_name)
    elif slide_index < len(prs.slides):
        for shape in prs.slides[slide_index].shapes:
            if shape.name == 'date' and shape.has_text_frame:
                replace_placeholder_keep_format(shape, placeholder, model_name)
    else:
        print(f'slide index {slide_index} invalid')

def replace_image_by_name(shapes, name: str, image_path: str, width=None, height=None, scale_with_aspect_ratio=True):
    """
    替换指定名称的图片 shape 为新图片

    Args:
        shapes: pptx Slide shapes
        name: shape.name（如 "logo", "product_img"）
        image_path: 本地图片路径（支持 .png/.jpg/.jpeg/.bmp）
        width: 目标宽度（Inches/Cm/Pt/Emu），如 Inches(2)
        height: 目标高度
        scale_with_aspect_ratio:
            True → 按比例缩放（优先满足 width，height 自适应）
            False → 强制拉伸到指定宽高

    Returns:
        新图片 shape
    """
    if os.path.isabs(image_path):
        new_image_path = image_path
    else:
        new_image_path = os.path.join('..', '.cache', 'download', image_path)
    if not state_exists(new_image_path):
        print(f'图片不存在: {new_image_path}')
        return
    dest_shape = None
    for shape in shapes:
        if shape.name == name:
            dest_shape = shape
            break
    if not dest_shape:
        raise ValueError(f"未找到名为 '{name}' 的 shape")
    if not (dest_shape.shape_type == MSO_SHAPE_TYPE.PICTURE or (dest_shape.placeholder_format and dest_shape.placeholder_format.type == 18)):
        raise ValueError(f"Shape '{name}' 不是图片类型")
    left = dest_shape.left
    top = dest_shape.top
    parent = dest_shape._element.getparent()
    idx = list(parent).index(dest_shape._element)
    shapes._spTree.remove(dest_shape._element)
    try:
        pic = shapes.add_picture(new_image_path, left=left, top=top)
    except Exception as e:
        raise RuntimeError(f'插入图片失败: {e}')
    if width is None and height is None:
        pass
    elif width is not None and height is not None:
        if scale_with_aspect_ratio:
            img_width, img_height = (pic.width, pic.height)
            scale_w = width / img_width
            scale_h = height / img_height
            scale = min(scale_w, scale_h)
            pic.width = int(img_width * scale)
            pic.height = int(img_height * scale)
            if pic.width < width:
                pic.left = left + (width - pic.width) // 2
            if pic.height < height:
                pic.top = top + (height - pic.height) // 2
        else:
            pic.width = width
            pic.height = height
    elif width is not None:
        scale = width / pic.width
        pic.width = width
        pic.height = int(pic.height * scale)
    elif height is not None:
        print(f'original: {pic.height}, {pic.width}')
        scale = height / pic.height
        pic.height = height
        pic.width = int(pic.width * scale)
        print(f'change: {pic.height}, {pic.width}')
    parent.insert(idx, pic._element)
    return pic

def get_report_score_ruler2(score_ruler2, compare_models, model_name, compare_type):
    with open_state(LLM_RULER_2_RESULT, 'r', encoding='utf-8') as file:
        chart2 = json.load(file)
    models_to_process = [model_name]
    for model in compare_models:
        if model not in models_to_process:
            models_to_process.append(model)
    for model in models_to_process:
        get_score_ru2(chart2, model, score_ruler2, compare_type)

def get_score_ru2(chart2, model_name, score_ruler2, compare_type):
    score_ruler2.setdefault(SCORE_DICT_PPT_FILL_KEY, {})[model_name] = {}
    score_ruler2.setdefault(SCORE_DICT_LLM_SUMMARY_KEY, {})[model_name] = {}
    ppt_scores = score_ruler2[SCORE_DICT_PPT_FILL_KEY][model_name]
    llm_scores = score_ruler2[SCORE_DICT_LLM_SUMMARY_KEY][model_name]
    dataset_mapping = {3: 'aisf_llm_gaixie', 9: 'aisf_llm_yitu', 10: None}
    ruler2_dataset_name = dataset_mapping.get(compare_type, 'aisf_llm_gaixie')
    if compare_type == 3:
        base_datasets = PPT_AISF_GAIXIE
    elif compare_type == 9:
        base_datasets = PPT_AISF_YITU
    elif compare_type == 10:
        base_datasets = PPT_AISF_MEMORY
    else:
        base_datasets = PPT_AISF_GAIXIE
    for ds in base_datasets:
        ppt_scores[ds] = -1
        if ds in DATASET_EN_TO_CN:
            llm_scores[DATASET_EN_TO_CN.get(ds)] = -1
        else:
            llm_scores[ds] = -1
    ppt_scores['average'] = -1
    llm_scores[DATASET_EN_TO_CN.get('average', 'average')] = -1
    if model_name not in chart2:
        return
    if compare_type == 10:
        memory_datasets = ['aisf_memory_cuiqu', 'aisf_memory_zhaohui']
        found_any = False
        total_average_sum = 0.0
        total_average_count = 0
        for dataset_name in memory_datasets:
            for item in chart2[model_name]:
                if item.get('dataset_name') == dataset_name and item.get('metrics'):
                    metrics = item['metrics'][0]
                    if metrics.get('categories'):
                        subsets = metrics['categories'][0].get('subsets', [])
                        for subset in subsets:
                            subset_name = subset['name']
                            if subset_name in base_datasets:
                                ppt_scores[subset_name] = round(subset['score'], 3)
                                llm_key = DATASET_EN_TO_CN.get(subset_name, subset_name)
                                llm_scores[llm_key] = round(subset['score'], 3)
                        found_any = True
                        total_average_sum += item['score']
                        total_average_count += 1
                    break
        if found_any and total_average_count > 0:
            avg = round(total_average_sum / total_average_count, 3)
            ppt_scores['average'] = avg
            llm_scores[DATASET_EN_TO_CN.get('average')] = avg
    else:
        for item in chart2[model_name]:
            if item.get('dataset_name') == ruler2_dataset_name and item.get('metrics'):
                metrics = item['metrics'][0]
                if metrics.get('categories'):
                    subsets = metrics['categories'][0].get('subsets', [])
                    for subset in subsets:
                        subset_name = subset['name']
                        if subset_name in base_datasets:
                            ppt_scores[subset_name] = round(subset['score'], 3)
                            llm_key = DATASET_EN_TO_CN.get(subset_name, subset_name)
                            llm_scores[llm_key] = round(subset['score'], 3)
                    ppt_scores['average'] = round(item['score'], 3)
                    llm_scores[DATASET_EN_TO_CN.get('average')] = round(item['score'], 3)
                    break
SCORE_DICT_PPT_FILL_KEY = 'ppt'
SCORE_DICT_LLM_SUMMARY_KEY = 'llm'
SCORE_DICT_MLLM_SUMMARY_KEY = 'mllm'
AIME_DATASETS = {'aime24', 'aime25'}
MATH_SUBJECT = '数学'

def get_score_ru1(chart1, model_name, score_data_ruler1):
    score_data_ruler1.setdefault(SCORE_DICT_PPT_FILL_KEY, {})[model_name] = {}
    score_data_ruler1.setdefault(SCORE_DICT_LLM_SUMMARY_KEY, {})[model_name] = {}
    ppt_scores = score_data_ruler1[SCORE_DICT_PPT_FILL_KEY][model_name]
    llm_scores = score_data_ruler1[SCORE_DICT_LLM_SUMMARY_KEY][model_name]
    for ds in PPT_GENERATE_RULER1:
        ppt_scores[ds] = -1
    llm_scores[MATH_SUBJECT] = 0
    for ds in PPT_GENERATE_RULER1:
        if ds in DATASET_EN_TO_CN:
            llm_scores[DATASET_EN_TO_CN[ds]] = -1
    if model_name not in chart1:
        return
    cur_math_score = 0
    t_count = 0
    for item in chart1[model_name]:
        dataset_name = item['dataset_name']
        score = item['score']
        ppt_scores[dataset_name] = round(score, 3)
        if any((dataset in dataset_name for dataset in AIME_DATASETS)):
            cur_math_score += score
            t_count += 1
        elif dataset_name in DATASET_EN_TO_CN:
            llm_scores[DATASET_EN_TO_CN[dataset_name]] = round(score, 3)
    cur_math_score = round(cur_math_score / t_count, 3) if t_count > 0 else 0
    llm_scores[MATH_SUBJECT] = cur_math_score

def get_report_score_ruler1(compare_models, model_name, score_data_ruler1):
    try:
        with open_state(LLM_RULER_1_RESULT, 'r', encoding='utf-8') as file:
            chart1 = json.load(file)
    except FileNotFoundError:
        print(f'文件 {LLM_RULER_1_RESULT} 未找到')
        raise FileNotFoundError(f'文件 {LLM_RULER_1_RESULT} 未找到')
    except json.JSONDecodeError:
        print(f'文件 {LLM_RULER_1_RESULT} 解析失败')
        raise Exception(f'文件 {LLM_RULER_1_RESULT} 解析失败')
    models_to_process = [model_name]
    for model in compare_models:
        if model not in models_to_process:
            models_to_process.append(model)
    for model in models_to_process:
        get_score_ru1(chart1, model, score_data_ruler1)

def get_report_score_data(model_name, compare_models, compare_type):
    score_data_ruler1 = {}
    print(f'path: {os.getcwd()}')
    get_report_score_ruler1(compare_models, model_name, score_data_ruler1)
    score_data_ruler2 = {}
    get_report_score_ruler2(score_data_ruler2, compare_models, model_name, compare_type)
    return (score_data_ruler1, score_data_ruler2)

def delete_slide(prs, index):
    """删除指定索引的幻灯片"""
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    if index < 0 or index >= len(slides):
        raise ValueError('指定删除的幻灯片索引超出范围')
    xml_slides.remove(slides[index])

def ensure_table_fill_data(table, data):
    while len(table.rows) < len(data):
        add_row_to_table(table)
    while len(table.columns) < len(data[0]):
        table.add_column()

def fill_ppt_score(shapes, score_data, summary_content, model_names=None):
    """
    填充数据页的 scores 到 PPT 表格中。
    使用当前 type 对应的 model_names 替换该页所有 shape 中的 {{modelN}} 占位符。

    Args:
        shapes: pptx Slide shapes
        score_data: dict, {model_name: {sub_key: score, ...}}
        summary_content: str, 总结文本
        model_names: list[str] or None, 当前 type 的模型名列表。
                     不为 None 时，替换该页所有 shape 中的 {{modelN}} 占位符。
    """
    if model_names is not None:
        for shape in shapes:
            for idx, name in enumerate(model_names):
                replace_placeholder_keep_format(shape, f'{{{{model{idx}}}}}', name)
    table = None
    for shape in shapes:
        if shape.has_table:
            table = shape.table
            break
    if not table:
        raise ValueError(f'未找到表格！')
    GUI_DATASETS = set(MLLM_TYPE_TO_DATASETS.get('7', [])) | set(MLLM_TYPE_TO_DATASETS.get('8', []))
    YITU_DATASETS = set(PPT_AISF_YITU)
    TEST_CATEGORIES = {'gui': (GUI_DATASETS, AISF_GUI_NUMS), 'yitu': (YITU_DATASETS, AISF_YITU_NUMS)}
    PERCENTAGE_DATASETS = set(PPT_AISF_MEMORY)
    model_totals = {}
    for model_name, model_data in score_data.items():
        total = 0
        for sub_key, sub_value in model_data.items():
            if sub_key == 'top' or sub_value == -1:
                continue
            for cat_name, (cat_datasets, cat_nums) in TEST_CATEGORIES.items():
                if sub_key in cat_datasets:
                    case_count = cat_nums.get(sub_key, 0)
                    total += round(sub_value * case_count)
                    break
        model_totals[model_name] = total
    if model_totals:
        max_total = max(model_totals.values())
        for model_name, total in model_totals.items():
            if total == max_total and total > 0:
                score_data[model_name].setdefault('top', []).append('__total__')
    avg_scores = {}
    for model_name, model_data in score_data.items():
        avg_val = model_data.get('average', -1)
        if avg_val != -1:
            avg_scores[model_name] = avg_val
    if avg_scores:
        max_avg = max(avg_scores.values())
        for model_name, avg_val in avg_scores.items():
            if avg_val == max_avg:
                score_data[model_name].setdefault('top', []).append('average')
    for row in table.rows:
        for cell in row.cells:
            paragraph = cell.text_frame.paragraphs[0]
            runs = paragraph.runs
            full_text = ''.join((run.text for run in runs if run.text))
            replaced = False
            for i, (model_name, model_data) in enumerate(score_data.items()):
                model_placeholder = f'{{{{model{i}}}}}'
                if model_placeholder in full_text and (not replaced):
                    new_text = full_text.replace(model_placeholder, str(model_name))
                    for run in runs:
                        run.text = ''
                    if runs:
                        runs[0].text = new_text
                    else:
                        paragraph.add_run().text = new_text
                    replaced = True
                    break
                if not replaced:
                    for sub_key, sub_value in model_data.items():
                        sub_placeholder = f'{{{{{sub_key}_{i}}}}}'
                        if sub_placeholder in full_text:
                            if sub_value == -1:
                                display_value = '/'
                            else:
                                display_value = sub_value
                                for cat_name, (cat_datasets, cat_nums) in TEST_CATEGORIES.items():
                                    if sub_key in cat_datasets:
                                        case_count = cat_nums.get(sub_key, 0)
                                        display_value = round(sub_value * case_count)
                                        break
                                else:
                                    if sub_value <= 1:
                                        display_value = sub_value * 100
                                if isinstance(display_value, float):
                                    display_value = f'{display_value:.2f}'
                                else:
                                    display_value = str(int(display_value))
                                if sub_key in PERCENTAGE_DATASETS:
                                    display_value += '%'
                            new_text = full_text.replace(sub_placeholder, display_value)
                            for run in runs:
                                run.text = ''
                            if runs:
                                runs[0].text = new_text
                            else:
                                paragraph.add_run().text = new_text
                            if sub_value != -1:
                                tops = model_data.get('top', [])
                                if sub_key in tops:
                                    runs[0].font.bold = True
                                    runs[0].font.color.rgb = RGBColor(255, 0, 0)
                            replaced = True
                            break
                    if replaced:
                        break
                total_placeholder = f'{{{{total_{i}}}}}'
                if total_placeholder in full_text and (not replaced):
                    total_correct = 0
                    for sub_key, sub_value in model_data.items():
                        if sub_key == 'top' or sub_value == -1:
                            continue
                        for cat_name, (cat_datasets, cat_nums) in TEST_CATEGORIES.items():
                            if sub_key in cat_datasets:
                                case_count = cat_nums.get(sub_key, 0)
                                total_correct += round(sub_value * case_count)
                                break
                    new_text = full_text.replace(total_placeholder, str(total_correct))
                    for run in runs:
                        run.text = ''
                    if runs:
                        runs[0].text = new_text
                    else:
                        paragraph.add_run().text = new_text
                    tops = model_data.get('top', [])
                    if '__total__' in tops:
                        runs[0].font.bold = True
                        runs[0].font.color.rgb = RGBColor(255, 0, 0)
                    replaced = True
                    break
    for row in table.rows:
        for cell in row.cells:
            paragraph = cell.text_frame.paragraphs[0]
            runs = paragraph.runs
            full_text = ''.join((run.text for run in runs if run.text))
            if re.search('\\{\\{.*?\\}\\}', full_text):
                new_text = re.sub('\\{\\{.*?\\}\\}', '/', full_text)
                for run in runs:
                    run.text = ''
                if runs:
                    runs[0].text = new_text
                else:
                    paragraph.add_run().text = new_text
    set_shape_text(shapes, 'summary', summary_content, 8, True)

def extract_image_path(url):
    last_slash_index = url.rfind('/')
    second_last_slash_index = url.rfind('/', 0, last_slash_index)
    result = url[second_last_slash_index + 1:]
    return result

def _download_image(url, save_dir):
    """
    从 URL 下载图片到本地缓存目录。
    返回下载后的本地路径，若失败则返回 None。
    """
    filename = os.path.basename(url.split('?')[0])
    if not filename:
        filename = f'img_{hash(url) % 100000}.png'
    os.makedirs(save_dir, exist_ok=True)
    local_path = os.path.join(save_dir, filename)
    if state_exists(local_path):
        return local_path
    try:
        import urllib.request
        print(f'[INFO] 下载图片: {url}')
        urllib.request.urlretrieve(url, local_path)
        return local_path
    except Exception as e:
        print(f'[WARN] 图片下载失败: {url}, 错误: {e}')
        return None

def set_to_ppt_data(model_name, model_id):
    to_ppt_data = {'model_name': model_name, 'date': datetime.now().strftime('%Y-%m-%d'), 'model_title_1': '暂无', 'model_intro_1': '暂无', 'model_title_2': '暂无', 'model_intro_2': '暂无', 'model_title_3': '暂无', 'model_intro_3': '暂无', 'model_title_4': '暂无', 'model_intro_4': '暂无', 'images_1': [], 'images_2': [], 'images_3': [], 'images_4': []}
    model_config = get_one_model_config(model_id)
    model_doc = model_config['info']['model_doc']
    if not model_doc:
        return to_ppt_data
    soup = BeautifulSoup(model_doc, 'html.parser')
    title_list = [p.get_text(strip=True) for p in soup.find_all('p') if p.strong]
    if len(title_list) >= 4:
        to_ppt_data['model_title_1'] = title_list[0]
        to_ppt_data['model_title_2'] = title_list[1]
        to_ppt_data['model_title_3'] = title_list[2]
        to_ppt_data['model_title_4'] = title_list[3]
    else:
        raise Exception('请按格式输入模型介绍标题（如Qwen3-32B）')

    def _convert_table_to_text(table_node):
        """将HTML表格转换为制表符分隔的文本"""
        rows = []
        for tr in table_node.find_all('tr'):
            cells = []
            for cell in tr.find_all(['th', 'td']):
                cell_text = cell.get_text(strip=True).replace('\n', ' ').replace('\t', ' ')
                cells.append(cell_text)
            if cells:
                rows.append('\t'.join(cells))
        return '\n'.join(rows)
    img_cache_dir = os.path.join('.cache', 'ppt_images')
    img_counter = [0, 0, 0, 0]

    def _process_img_tag(img_tag, section_idx):
        """处理 <img> 标签：下载图片，返回占位标记"""
        src = img_tag.get('src', '')
        if not src:
            return None
        local_path = _download_image(src, img_cache_dir)
        if local_path:
            idx = img_counter[section_idx]
            img_counter[section_idx] += 1
            section_key = f'images_{section_idx + 1}'
            to_ppt_data.setdefault(section_key, []).append(local_path)
            return f'[IMAGE_{idx + 1}]'
        return None

    def _content_between(start_anchor, end_anchor, section_idx=0):
        parts = []
        if not start_anchor or not end_anchor:
            return parts
        node = start_anchor.find_next_sibling()
        while node and node != end_anchor:
            if node.name == 'table':
                parts.append(_convert_table_to_text(node))
            elif node.name == 'ul':
                parts.append('\n'.join((li.get_text(strip=True) for li in node.find_all('li') if li.get_text(strip=True))))
            elif node.name == 'img':
                marker = _process_img_tag(node, section_idx)
                if marker:
                    parts.append(marker)
            elif node.name in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span'):
                img_inline = node.find('img')
                if img_inline:
                    marker = _process_img_tag(img_inline, section_idx)
                    if marker:
                        text = node.get_text(strip=True)
                        if text:
                            parts.append(text)
                        parts.append(marker)
                else:
                    text = node.get_text(strip=True)
                    if text:
                        parts.append(text)
            node = node.find_next_sibling()
        return parts

    def _content_from(anchor, section_idx=3):
        parts = []
        if not anchor:
            return parts
        node = anchor.find_next_sibling()
        while node:
            if node.name == 'table':
                parts.append(_convert_table_to_text(node))
            elif node.name == 'ul':
                parts.append('\n'.join((li.get_text(strip=True) for li in node.find_all('li') if li.get_text(strip=True))))
            elif node.name == 'img':
                marker = _process_img_tag(node, section_idx)
                if marker:
                    parts.append(marker)
            elif node.name in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span'):
                img_inline = node.find('img')
                if img_inline:
                    marker = _process_img_tag(img_inline, section_idx)
                    if marker:
                        text = node.get_text(strip=True)
                        if text:
                            parts.append(text)
                        parts.append(marker)
                else:
                    text = node.get_text(strip=True)
                    if text:
                        parts.append(text)
            node = node.find_next_sibling()
        return parts
    anchor_names = ['模型介绍', '技术亮点', '官方评测', '三方评测']
    anchors = {}
    for name in anchor_names:
        anchor = soup.find(lambda tag, n=name: tag.name == 'p' and tag.strong and (tag.strong.get_text(strip=True) == n))
        anchors[name] = anchor
    parts_1 = _content_between(anchors['模型介绍'], anchors['技术亮点'], section_idx=0)
    to_ppt_data['model_intro_1'] = '\n'.join(parts_1) if parts_1 else '暂无'
    parts_2 = _content_between(anchors['技术亮点'], anchors['官方评测'], section_idx=1)
    to_ppt_data['model_intro_2'] = '\n'.join(parts_2) if parts_2 else '暂无'
    parts_3 = _content_between(anchors['官方评测'], anchors['三方评测'], section_idx=2)
    to_ppt_data['model_intro_3'] = '\n'.join(parts_3) if parts_3 else '暂无'
    parts_4 = _content_from(anchors['三方评测'], section_idx=3)
    to_ppt_data['model_intro_4'] = '\n'.join(parts_4) if parts_4 else '暂无'
    return to_ppt_data

def set_to_ppt_data_v2(model_name, model_id):
    """
    新版 set_to_ppt_data（简化版）：
    - 仅填充 model_name、date、model_intro_1 三个字段
    - model_intro_1 从 model_config['info']['model_desc'] 获取
    - 填充完成后，将 model_intro_1 插入 PPT 第2页（index 1）的 shape 中
    - 其余三页模型介绍页后续将从模板中移除，因此不再填充
    """
    model_config = get_one_model_config(model_id)
    if model_config is None:
        model_desc = ''
    else:
        model_desc = model_config.get('info', {}).get('model_desc', '')
    to_ppt_data = {'model_name': model_name, 'date': datetime.now().strftime('%Y-%m-%d'), 'model_intro_1': model_desc if model_desc else '暂无'}
    return to_ppt_data

def fill_ppt_other_v2(prs, info_data, base_slide_offset=0, max_base_slides=164, all_model_names=None):
    """
    填充封面和模型介绍页（支持多基准模型偏移）。
    对于单基准模型（base_slide_offset=0）：
      - 替换所有幻灯片中的 {{model}} 和 {{date}}
      - 填充 slide[1] 的模型介绍
    对于多基准模型分组：
      - 仅填充本组范围内的幻灯片
      - 封面: slide[0]，仅替换 {{model}} 和 {{date}}
      - 介绍: slide[base_slide_offset]

    Args:
        all_model_names: list[str] or None, 所有基准模型名列表。不为 None 时，封面页 {{model}}
                         替换为所有模型逗号连接；本组内仍用 info_data['model_name']。
    """
    if all_model_names:
        for slide in prs.slides:
            for shape in slide.shapes:
                for index, name in enumerate(all_model_names):
                    replace_placeholder_keep_format(shape, f'{{{{basemodel{index}}}}}', name)
    group_start = base_slide_offset
    group_end = min(base_slide_offset + 55, max_base_slides)
    cover_model_str = '&'.join(all_model_names) if all_model_names else info_data['model_name']
    slide = prs.slides[0]
    for shape in slide.shapes:
        replace_placeholder_keep_format(shape, '{{model}}', cover_model_str)
    fill_model_placeholder(prs, 0, '{{date}}', info_data['date'])

def fill_ppt_other(prs, info_data, model_names=None):
    if model_names is None:
        model_names = [info_data['model_name']]
    print(f'model_names: {model_names}')
    for slide in prs.slides:
        for shape in slide.shapes:
            for idx, name in enumerate(model_names):
                replace_placeholder_keep_format(shape, '{{model}}', info_data['model_name'])
                replace_placeholder_keep_format(shape, f'{{{{model{idx}}}}}', name)
    fill_model_placeholder(prs, 0, '{{date}}', info_data['date'])
    shapes = prs.slides[1].shapes
    set_shape_text(shapes, 'title1', info_data['model_title_1'], 16, True)
    set_shape_text(shapes, 'introduction1', info_data['model_intro_1'])
    _fill_slide_images(shapes, info_data.get('images_1', []))
    shapes = prs.slides[2].shapes
    set_shape_text(shapes, 'title1', info_data['model_title_2'], 16, True)
    set_shape_text(shapes, 'introduction1', info_data['model_intro_2'])
    _fill_slide_images(shapes, info_data.get('images_2', []))
    shapes = prs.slides[3].shapes
    set_shape_text(shapes, 'title1', info_data['model_title_3'], 16, True)
    set_shape_text(shapes, 'introduction1', info_data['model_intro_3'])
    _fill_slide_images(shapes, info_data.get('images_3', []))
    shapes = prs.slides[4].shapes
    set_shape_text(shapes, 'title1', info_data['model_title_4'], 16, True)
    set_shape_text(shapes, 'introduction1', info_data['model_intro_4'])
    _fill_slide_images(shapes, info_data.get('images_4', []))

def _fill_slide_images(shapes, image_paths):
    """
    将图片列表依次替换到 slide 中的图片占位 shape（image1, image2, ...）。
    如果找不到对应的占位 shape，则静默跳过。
    """
    for i, img_path in enumerate(image_paths):
        placeholder_name = f'image{i + 1}'
        try:
            replace_image_by_name(shapes, placeholder_name, img_path)
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            print(f"[WARN] 替换图片占位符 '{placeholder_name}' 失败: {e}")

def generate_ppt_report(prs, model_id, report_name=None):
    curr_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join(EVAL_REPORT_OUTPUT_PATH, model_id, curr_time)
    os.makedirs(output_dir, exist_ok=True)
    if report_name:
        base_name = report_name
    else:
        base_name = f'{model_id}_eval_report_{curr_time}'
    output_path = os.path.join(output_dir, f'{base_name}.pptx')
    if state_exists(output_path):
        counter = 1
        while True:
            new_path = os.path.join(output_dir, f'{base_name}({counter}).pptx')
            if not state_exists(new_path):
                output_path = new_path
                break
            counter += 1
    prs.save(output_path)
    return output_path

def handle_score_data(score_data, type=0):
    """
    1. 对每个维度（ruler1、ruler2、tool）分别找出所有模型中的最高分
    2. 检查每个模型，在这个维度上的得分是否等于最高分
    3. 如果等于最高分，就将该维度添加到该模型的top字段中
    4. 最终每个模型的top字段包含所有它在该维度上达到最高分的维度名称
    为每个模型添加'top'字段，包含该模型在各子维度中达到最高分的维度

    参数:
        score_data: 字典，结构为 {'模型名': {'ruler1': 分数, 'ruler2': 分数, 'tool': 分数}}

    返回:
        处理后的字典，每个模型新增'top'字段
    """
    for model in score_data:
        score_data[model]['top'] = []
    if not score_data:
        return score_data
    if type == 0:
        dimensions = PPT_GENERATE_RULER1
    elif type == 1:
        dimensions = PPT_MULTI_RULER1_VISION
    elif type == 2:
        dimensions = PPT_MULTI_RULER1_VIDEO
    elif type == 3:
        dimensions = PPT_AISF_GAIXIE
    elif type == 6:
        dimensions = PPT_MULTI_STUDY
    elif type == 7:
        dimensions = PPT_MULTI_GUI
    elif type == 8:
        dimensions = PPT_MULTI_GUI
    elif type == 9:
        dimensions = PPT_AISF_YITU
    elif type == 10:
        dimensions = PPT_AISF_MEMORY
    else:
        dimensions = list(next(iter(score_data.values())).keys())
    for dim in dimensions:
        valid_scores = [scores[dim] for scores in score_data.values() if scores[dim] != -1]
        if not valid_scores:
            continue
        max_score = max(valid_scores)
        for model, scores in score_data.items():
            if scores[dim] != -1 and scores[dim] == max_score:
                scores['top'].append(dim)
    return score_data

def fill_min_dataset_content_to_ppt(fill_data, score_data, summary, model_names=None):
    template_file = 'min_dataset_template.pptx'
    template_path = EVAL_REPORT_TEMPLATE_PATH_BASE + template_file
    if not state_exists(template_path):
        raise FileNotFoundError(f"未找到 '{template_path}' 的模板文件")
    prs = Presentation(template_path)
    if len(prs.slides) < 4:
        raise Exception('PPT pages count is < 4')
    fill_ppt_other_v2(prs, fill_data)
    score_data = handle_score_data(score_data)
    print(f'handle after score_data, {score_data}')
    fill_ppt_score(prs.slides[5].shapes, score_data, summary, model_names=model_names)
    return prs

def get_report_score_min_dataset(model_name):
    try:
        with open_state(LLM_MIN_DATASET_RESULT, 'r', encoding='utf-8') as file:
            chart = json.load(file)
    except FileNotFoundError:
        print(f'文件 {LLM_MIN_DATASET_RESULT} 未找到')
        raise FileNotFoundError(f'文件 {LLM_MIN_DATASET_RESULT} 未找到')
    except json.JSONDecodeError:
        print(f'文件 {LLM_MIN_DATASET_RESULT} 解析失败')
        raise Exception(f'文件 {LLM_MIN_DATASET_RESULT} 解析失败')
    if model_name not in chart:
        raise Exception(f'榜单中未找到模型 {model_name} ')
    target_model = {model_name: chart[model_name]}
    chart.pop(model_name)
    chart = {**target_model, **chart}
    score_data = {}
    max_compare_model_count = 6
    for index, (key, value) in enumerate(chart.items()):
        if index >= max_compare_model_count:
            print(f'current chart model num > 6, only top 6.')
            break
        score_data.setdefault(SCORE_DICT_PPT_FILL_KEY, {})[key] = {}
        score_data.setdefault(SCORE_DICT_LLM_SUMMARY_KEY, {})[key] = {}
        ppt_scores = score_data[SCORE_DICT_PPT_FILL_KEY][key]
        llm_scores = score_data[SCORE_DICT_LLM_SUMMARY_KEY][key]
        for item in value:
            dataset_name = item['dataset_name']
            score = item['score']
            ppt_scores[dataset_name] = round(score, 1)
            llm_scores[DATASET_EN_TO_CN[dataset_name]] = round(score, 1)
    return score_data

def get_report_score_mllm_dataset(model_name, compare_models, type):
    if type in (1, 2):
        try:
            with open_state(MULTI_RULER_1_RESULT, 'r', encoding='utf-8') as file:
                chart = json.load(file)
        except FileNotFoundError:
            print(f'文件 {MULTI_RULER_1_RESULT} 未找到')
            raise FileNotFoundError(f'文件 {MULTI_RULER_1_RESULT} 未找到')
        except json.JSONDecodeError:
            print(f'文件 {MULTI_RULER_1_RESULT} 解析失败')
            raise Exception(f'文件 {MULTI_RULER_1_RESULT} 解析失败')
    elif type in (6, 7, 8):
        try:
            with open_state(MULTI_RULER_2_RESULT, 'r', encoding='utf-8') as file:
                chart = json.load(file)
        except FileNotFoundError:
            print(f'文件 {MULTI_RULER_2_RESULT} 未找到')
            raise FileNotFoundError(f'文件 {MULTI_RULER_2_RESULT} 未找到')
        except json.JSONDecodeError:
            print(f'文件 {MULTI_RULER_2_RESULT} 解析失败')
            raise Exception(f'文件 {MULTI_RULER_2_RESULT} 解析失败')
    score_data = {}
    max_compare_model_count = 6
    cur_datasets = MLLM_TYPE_TO_DATASETS.get(str(type), [])
    if len(cur_datasets) == 0:
        raise Exception(f'榜单中未找到当前类型的测试集数据 {type}， 应该是1,2,6,7,8其中一种')
    models_to_process = [model_name]
    for compare_model in compare_models:
        if compare_model not in models_to_process:
            models_to_process.append(compare_model)
    for index, key in enumerate(models_to_process):
        if index >= max_compare_model_count:
            print(f'current chart model num > 6, only top 6.')
            break
        score_data.setdefault(SCORE_DICT_PPT_FILL_KEY, {})[key] = {}
        score_data.setdefault(SCORE_DICT_MLLM_SUMMARY_KEY, {})[key] = {}
        ppt_scores = score_data[SCORE_DICT_PPT_FILL_KEY][key]
        llm_scores = score_data[SCORE_DICT_MLLM_SUMMARY_KEY][key]
        for ds in cur_datasets:
            ppt_scores[ds] = -1
            llm_scores[ds] = -1
        if key not in chart:
            continue
        value = chart[key]
        if type in (1, 2):
            for item in value:
                dataset_name = item['dataset_name']
                if dataset_name not in cur_datasets:
                    continue
                score = item['score']
                ppt_scores[dataset_name] = round(score, 3)
                llm_scores[dataset_name] = round(score, 3)
        elif type == 6:
            for item in value:
                if item.get('dataset_name') == 'aisf_banxue' and item.get('metrics'):
                    metrics = item['metrics'][0]
                    if metrics.get('categories'):
                        subsets = metrics['categories'][0].get('subsets', [])
                        for subset in subsets:
                            subset_name = subset['name']
                            if subset_name in cur_datasets:
                                ppt_scores[subset_name] = round(subset['score'], 3)
                                llm_scores[subset_name] = round(subset['score'], 3)
                        ppt_scores['average'] = round(item['score'], 3)
                        llm_scores[DATASET_EN_TO_CN.get('average')] = round(item['score'], 3)
        elif type in (7, 8):
            gui_dataset_name = 'aisf_gui_plan' if type == 7 else 'aisf_gui_vla'
            for item in value:
                if item.get('dataset_name') == gui_dataset_name and item.get('metrics'):
                    metrics = item['metrics'][0]
                    if metrics.get('categories'):
                        subsets = metrics['categories'][0].get('subsets', [])
                        for subset in subsets:
                            subset_name = subset['name']
                            if subset_name in cur_datasets:
                                ppt_scores[subset_name] = round(subset['score'], 3)
                                llm_scores[subset_name] = round(subset['score'], 3)
                        ppt_scores['average'] = round(item['score'], 3)
                        llm_scores[DATASET_EN_TO_CN.get('average')] = round(item['score'], 3)
    return score_data

def fill_multi_base_unified_content_to_ppt(all_ppt_data_list, all_llm_ppt_score_list, all_mllm_ppt_score_list, all_llm_summary_list, all_mllm_summary_list, llm_type_list, mllm_type_list, all_model_count_dict_list, all_model_names_dict_list, all_base_model_names=None):
    """
    多基准模型 LLM + 多模态 PPT 报告填充。

    template_all.pptx layout (164 slides, 0~163):
      0: 封面页
      1~54:   基准模型0的报告页（1: 模型介绍, 2~54: 数据页）
      55~108: 基准模型1的报告页（55: 模型介绍, 56~108: 数据页）
      109~162: 基准模型2的报告页（109: 模型介绍, 110~162: 数据页）
      163: 结束页

      9种类型按 rank 固定排列，每种 6 页：
        rank 0: 大语言 (type=0)     rank 1: 视觉 (type=1)
        rank 2: 音频 (type=2)       rank 3: 意图 (type=9)
        rank 4: 改写 (type=3)       rank 5: 记忆 (type=10)
        rank 6: 伴学 (type=6)       rank 7: GUI规划 (type=7)
        rank 8: GUI执行 (type=8)

      每基准模型数据页 formula: slide_idx = intro_slide + rank * 6 + group
        intro_slide = 1, 55, 109
        group = count - 1 (0~5, 对应1~6个模型)
    """
    template_path = os.path.join(EVAL_REPORT_TEMPLATE_PATH_BASE, 'template_all.pptx')
    if not state_exists(template_path):
        raise FileNotFoundError(f"未找到 '{template_path}' 的模板文件")
    try:
        prs = Presentation(template_path)
    except Exception as e:
        print(f'加载PPT模板失败: {e}')
        raise
    REQUIRED_SLIDES = 164
    if len(prs.slides) < REQUIRED_SLIDES:
        raise Exception(f'PPT模板页数不足{REQUIRED_SLIDES}页，template_all.pptx 需要至少{REQUIRED_SLIDES}页')
    base_count = len(all_ppt_data_list)
    if base_count < 1 or base_count > 3:
        raise ValueError(f'基准模型数量 {base_count} 超出支持范围（1~3）')
    ALL_TYPE_TO_RANK = {0: 0, 1: 1, 2: 2, 9: 3, 3: 4, 10: 5, 6: 6, 7: 7, 8: 8}
    PAGES_PER_TYPE = 6
    PAGES_PER_BASE = 54
    BASE_INTRO = [1, 55, 109]
    target_slide_indices = []
    for base_idx in range(base_count):
        intro_slide = BASE_INTRO[base_idx]
        fill_ppt_other_v2(prs, all_ppt_data_list[base_idx], base_slide_offset=intro_slide, max_base_slides=REQUIRED_SLIDES, all_model_names=all_base_model_names)
        llm_list = all_llm_ppt_score_list[base_idx]
        mllm_list = all_mllm_ppt_score_list[base_idx]
        llm_sum = all_llm_summary_list[base_idx]
        mllm_sum = all_mllm_summary_list[base_idx]
        model_count_dict = all_model_count_dict_list[base_idx]
        model_names_dict = all_model_names_dict_list[base_idx]
        all_type_list = llm_type_list + mllm_type_list
        all_score_list = llm_list + mllm_list
        all_sum_list = llm_sum + mllm_sum
        for i, ct in enumerate(all_type_list):
            scores = all_score_list[i]
            if scores is None:
                continue
            rank = ALL_TYPE_TO_RANK.get(ct)
            if rank is None:
                raise ValueError(f'不支持的 compare_type: {ct}')
            count = model_count_dict.get(ct, 1)
            group = count - 1
            if group < 0 or group > 5:
                raise ValueError(f'type={ct} 模型数量 {count} 超出支持范围（1~6）')
            slide_idx = intro_slide + rank * PAGES_PER_TYPE + group
            base_end = BASE_INTRO[base_idx] + PAGES_PER_BASE
            if slide_idx > base_end:
                raise ValueError(f'type={ct} 模型数量 {count} 导致 slide_idx={slide_idx} 超出本组范围 ({BASE_INTRO[base_idx] + 1}~{base_end})')
            target_slide_indices.append(slide_idx)
            names = model_names_dict.get(ct, list(scores.keys())) if model_names_dict else None
            fill_ppt_score(prs.slides[slide_idx].shapes, scores, all_sum_list[i], model_names=names)
    print(f'target_slide_indices: {sorted(target_slide_indices)}')
    pages_to_keep = set(target_slide_indices)
    pages_to_keep.add(REQUIRED_SLIDES - 1)
    for idx in range(REQUIRED_SLIDES - 2, 0, -1):
        if idx not in pages_to_keep:
            delete_slide(prs, idx)
    return prs
