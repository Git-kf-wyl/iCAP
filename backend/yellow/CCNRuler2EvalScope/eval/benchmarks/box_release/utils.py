# Private iCAP Yellow implementation. Do not publish.
import jsonlines as jsonl
import logging
import re
import json
import pandas as pd

def jsonl_to_list(jsonl_file):
    """
    Read jsonl file to list.

    Args:
        jsonl_file: jsonl file path.

    Returns:
        list: list of lines. Each line is a dict.
    """
    res_list = []
    with jsonl.open(jsonl_file, mode='r') as reader:
        for line in reader.iter(type=dict, allow_none=True, skip_invalid=False):
            res_list.append(line)
    return res_list

def extract_clean_text(text):
    """去除 HTML 标签并清理空白字符"""
    text = re.sub('<[^>]+>', '', text)
    text = re.sub('\\s+', ' ', text).strip()
    return text

def parse_think_response_clean(message_body):
    """
    解析消息体，分割出 think 内容和回答内容（纯文本）
    返回: (think_content, answer_content)
          如果没有 </think>，则 think_content=None
    """
    text = message_body['contents']
    parts = text.split('</think>', 1)
    if len(parts) == 2:
        think_content = extract_clean_text(parts[0])
        answer_content = extract_clean_text(parts[1])
    else:
        think_content = None
        answer_content = extract_clean_text(text)
    return answer_content

def get_json_structure(input, need_json_fix=False):
    """
    提取字符串中的json结构，去掉```json和```并取中间部分，若没有干扰的字符，直接取整个字符串转化为json
    """

    def get_json_data(loc_str, need_json_fix):
        try:
            json_data = json.loads(loc_str)
        except Exception as ex:
            if need_json_fix:
                loc_str = fix_json(loc_str)
            sub_json_str, sub_json_result = get_last_json_object(loc_str)
            replace_str = loc_str.replace(sub_json_str, '')
            sec_sub_json_str, sec_sub_json_result = get_last_json_object(replace_str)
            found_all_key = True
            for key_str in sub_json_result:
                if key_str not in sec_sub_json_result:
                    found_all_key = False
                    break
            if found_all_key:
                return {}
            return sub_json_result
        return json_data
    loc_str = input
    try:
        loc_str = erase_comment(loc_str)
        loc_str = loc_str.replace('\xa0', ' ')
        if '```json' in loc_str:
            json_str = loc_str.split('```json', 1)[-1].split('```', 1)[0]
            json_data = json.loads(json_str)
        elif '```' in loc_str:
            json_str = loc_str.split('```', 1)[-1].split('```', 1)[0]
            json_data = json.loads(json_str)
        else:
            return get_json_data(loc_str, need_json_fix)
    except Exception as ex:
        logging.error('get json error:' + loc_str)
        json_data = get_json_data(loc_str, need_json_fix)
    return json_data

def fix_json(self, json_str):
    json_str = json_str.strip()
    is_windows = '\r\n' in json_str
    enter_key = '\r\n' if is_windows else '\n'
    json_str_list = json_str.split('\r\n"') if is_windows else json_str.split('\n"')
    for i in range(len(json_str_list)):
        curr_kv = json_str_list[i]
        if not curr_kv.endswith('{') and (not curr_kv.endswith('}')):
            if not curr_kv.endswith('",'):
                if curr_kv.endswith('"'):
                    json_str_list[i] = curr_kv + ','
                else:
                    json_str_list[i] = curr_kv + '",'
    json_str = '\n"'.join(json_str_list)
    if json_str.endswith('".' + enter_key + '}'):
        json_str = re.sub('"\\.' + enter_key + '}$', '"' + enter_key + '}', json_str)
    json_str_list = json_str.split('": "')
    for i in range(len(json_str_list)):
        curr_str = json_str_list[i]
        second_split_str = '",\r\n"' if is_windows else '",\n"'
        if second_split_str in curr_str:
            sub_str_list = curr_str.split(second_split_str)
            for j in range(len(sub_str_list)):
                sub_str_list[j] = re.sub('(?<!\\\\)"', '', sub_str_list[j])
                sub_str_list[j] = re.sub(':\\\\ +\\\\"', ': \\"\\"', sub_str_list[j])
            curr_str = second_split_str.join(sub_str_list)
        json_str_list[i] = curr_str
    json_str = '": "'.join(json_str_list)
    return json_str

def get_last_json_object(loc_str):
    end_pos = loc_str.rfind('}')
    left_brackets_indexs = find_all_index_of_char(loc_str, '{')
    find_json = False
    for i in left_brackets_indexs[::-1]:
        if i < end_pos:
            json_str = loc_str[i:end_pos + 1]
            try:
                json_result = json.loads(json_str)
                find_json = True
            except Exception as ex:
                json_result = {}
            if find_json:
                return (json_str, json_result)
    return ('{}', {})

def find_all_index_of_char(str, char):
    result = []
    for i in range(len(str)):
        if str[i] == char:
            result.append(i)
    return result

def erase_comment(erase_predict):
    lines = erase_predict.split('\n')
    new_lines = []
    for line in lines:
        if '//' in line:
            comma = line.find(',')
            pos = line.rfind('//')
            s_quotation = line.rfind("'")
            d_quotation = line.rfind('"')
            colon = line.find('\\:')
            rcolon = line.rfind('\\:')
            if (s_quotation < pos and d_quotation < pos or (comma > 0 and comma < pos and (colon == rcolon))) and colon < pos:
                line = line[:pos]
        new_lines.append(line)
    new_str = '\n'.join(new_lines)
    return new_str
