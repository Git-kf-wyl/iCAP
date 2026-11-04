# Private iCAP Yellow implementation. Do not publish.
import pandas as pd
import os
import re
import json
import logging
import requests
import time
import traceback
from openai import OpenAI
import httpx
from eval.utils.logger import get_logger
logger = get_logger()

def ls_all_excel(input_dir):
    """
    列出指定文件夹及其子文件夹下的所有Excel文件，并返回文件名和路径的字典
    """
    result = {}
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.xlsx') or file.endswith('.xls'):
                file_path = os.path.join(root, file)
                result[file] = file_path
    return result

def read_from_excel(filename):
    """
    从Excel文件中读取测试用例
    """
    test_cases = []
    df = pd.read_excel(filename, sheet_name='评测集', header=[0, 1])
    for index, row in df.iterrows():
        test_cases.append(row)
    return test_cases

def read_from_mml_excel(filename):
    """
    从最新的mml测试集 Excel文件中读取测试用例
    """
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append(row)
    return test_cases

def read_from_alarm_excel(filename):
    """
    从最新的告警测试集 Excel文件中读取测试用例
    """
    sheet_names = ['Plan', 'Step', 'StepRevise', 'Summarize']
    test_cases = []
    for sheet in sheet_names:
        df = pd.read_excel(filename, sheet_name=sheet)
        for index, row in df.iterrows():
            test_cases.append(row)
    return test_cases

def excel_key(excel_data, key_word):
    for key in excel_data[0].keys():
        if isinstance(key_word, tuple) and key == key_word:
            return key
        if isinstance(key_word, str) and (key[0] == key_word or key[1] == key_word):
            return key
    raise Exception(f'not found {key_word} in excel_data columns')

def split_data_by_key(excel_data, key):
    """
    根据指定的参数将测试用例数据进行拆分
    """
    result = {}
    for case in excel_data:
        if case[key] not in result:
            result[case[key]] = []
        result[case[key]].append(case)
    return result

def repack_src_data(c_columns, excel_data):
    """
    根据指定的参数将测试用例数据进行重新封装，只提取后续训练需要的数据
    """
    c_no = excel_key(excel_data, c_columns[0])
    c_question = excel_key(excel_data, c_columns[1])
    c_predict = excel_key(excel_data, c_columns[2])
    c_judge = excel_key(excel_data, c_columns[3])
    return [{'No': x[c_no], 'Question': x[c_question], 'Answer': x[c_predict], 'Judge': x[c_judge]} for x in excel_data]

def repack_src_data_single_head(c_columns, excel_data):
    """
    默认单行表头直接提取
    """
    return [{'No': x[c_columns[0]], 'Question': x[c_columns[1]], 'Answer': x[c_columns[2]], 'Judge': x[c_columns[3]]} for x in excel_data]

class HardCodedCheck:

    def __init__(self):
        self.cnt = 0

    def judge_answer_subjective(self, answer='', pattern='', predict=''):
        try:
            if pattern in ['judge_start_end_result']:
                res = self.judge_start_end_result(answer, predict)
            elif pattern in ['judge_equal_result']:
                res = self.judge_equal_result(answer, predict)
            elif pattern in ['judge_json_result']:
                res = self.judge_json_result(answer, predict)
            elif pattern in ['judge_json_list_value_strict_result']:
                res = self.judge_json_list_value_strict_result(answer, predict)
            elif pattern in ['judge_json_list_value_result']:
                res = self.judge_json_list_value_result(answer, predict)
            elif pattern in ['judge_mermaid_result']:
                res = self.judge_mermaid_result(answer, predict)
            elif pattern in ['judge_tree_result']:
                res = self.judge_tree_result(answer, predict)
            elif pattern in ['judge_kpi_result']:
                res = self.judge_kpi_result(answer, predict)
            elif pattern in ['judge_common_key_similar_result']:
                res = self.judge_common_key_similar_result(answer, predict)
            elif pattern in ['judge_alarm_plan_result']:
                res = self.judge_alarm_plan_result(answer, predict)
            elif pattern in ['judge_alarm_step_result']:
                res = self.judge_alarm_step_result(answer, predict)
            elif pattern in ['judge_alarm_step_revise_result']:
                res = self.judge_alarm_step_revise_result(answer, predict)
            elif pattern in ['judge_alarm_summarize_result']:
                res = self.judge_alarm_summarize_result(answer, predict)
            elif answer == predict:
                res = 'T'
            else:
                res = 'F'
            if res == 'T':
                return 1
            elif res == 'F':
                return 0
            else:
                print('error question!')
                return 0
        except Exception as ex:
            traceback.print_exc()
            print('error question!')
            return 0

    def judge_start_end_result(self, answer, predict):
        answer = self.erase_middle_space(answer)
        predict = self.erase_middle_space(predict)
        try:
            label_answer, length = self.handle_mml(answer.split('START\n', 1)[-1].split('\nEND', 1)[0])
        except Exception as err:
            print('judge_start_end_result error1')
        predict_response = ''
        try:
            predict_response, length = self.handle_mml(predict.split('START\n', 1)[-1].split('\nEND', 1)[0])
        except Exception as err:
            print('judge_start_end_result error2')
        if len(label_answer) == len(predict_response):
            for i, label_item in enumerate(label_answer):
                if self.erase_space(label_item) != self.erase_space(predict_response[i]):
                    return 'F'
            return 'T'
        return 'F'

    def judge_new_mml_equal_result(self, answer, predict):
        max_uint32 = (1 << 32) - 1
        if answer == predict:
            return True
        if answer == str(max_uint32) and predict == '/':
            return True
        if not answer and predict == '/':
            return True
        if answer.lower() == 'none' and predict == '/':
            return True
        return False

    def judge_equal_result(self, answer, predict):
        predict_effect_result = predict
        logger.info(f'answer {answer}, predict {predict}')
        if answer and ':' in answer:
            answer = answer.split(':', 1)[-1]
            if answer.find(predict) != -1:
                return 'T'
        if isinstance(predict, (int, float)):
            predict = str(predict)
        if self.judge_new_mml_equal_result(answer, predict):
            return 'T'
        return 'F'

    def judge_json_result(self, answer, predict):
        """
        判断两个json结构体是否一致，适用于单个层级逐个字段比较，去除```json和 ```
        """
        if answer == predict:
            return 'T'
        if not self.is_json_head_similarity(answer, predict):
            return 'F'
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        result = self.is_json_level_same(answer_json, predict_json, '0')
        return result

    def judge_json_list_value_strict_result(self, answer, predict):
        """
        判断两个json结构体是否一致，适用于单个层级逐个字段比较，去除```json和 ```
        对list类型的值做特殊比对，两者忽略顺序必须完全一致，严格模式
        """
        if answer == predict:
            return 'T'
        if not self.is_json_head_similarity(answer, predict):
            return 'F'
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        result = self.is_json_level_same(answer_json, predict_json, '0', list_value_model=1)
        return result

    def judge_json_list_value_result(self, answer, predict):
        """
        判断两个json结构体是否一致，适用于单个层级逐个字段比较，去除```json和 ```
        对list类型的值做特殊比对，两者忽略顺序，predict完全包含在answer中，两者语义一致即可
        """
        if answer == predict:
            return 'T'
        if not self.is_json_head_similarity(answer, predict):
            return 'F'
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        result = self.is_json_level_same(answer_json, predict_json, '1', list_value_model=2)
        return result

    def judge_mermaid_result(self, answer, predict):
        """
        判断两个mermaid流程图是否一致，适用于单个层级逐个字段比较，去除
        """
        if answer == predict:
            return 'T'
        answer_mermaid = self.get_mermaid_structure(answer)
        predict_mermaid = self.get_mermaid_structure(predict)
        result = self.is_mermaid_level_same(answer_mermaid, predict_mermaid)
        return result

    def judge_tree_result(self, answer, predict):
        """
        判断两个树结构是否一致，用模型来判断相似度
        """
        if answer == predict:
            return 'T'
        answer_tree = self.get_tree_structure(answer)
        predict_tree = self.get_tree_structure(predict)
        reply = self.auto_judge_semantics(answer_tree, predict_tree, '下面这两个树是否一致, 请以json形式输出相似，例如：{{"相似度": 0.9}}\\n# 树A:\\n{}\\n# 树B:\\n{}')
        reply_json = self.get_json_structure(reply)
        if '相似度' in reply_json and float(reply_json['相似度']) >= 0.8:
            return 'T'
        return 'F'

    def judge_kpi_result(self, answer, predict):
        """
        判断两个kpi是否一致，适用于单个层级逐个字段比较，去除
        """
        if answer == predict:
            return 'T'
        answer_kpi = self.get_kpi_structure(answer)
        predict_kpi = self.get_kpi_structure(predict)
        if not answer_kpi or not predict_kpi or len(answer_kpi) != len(predict_kpi):
            return 'F'
        if not set(answer_kpi.keys()) == set(predict_kpi.keys()):
            return 'F'
        for common_fault in set(answer_kpi.keys()):
            if '故障对象' not in answer_kpi[common_fault] or '故障对象' not in predict_kpi[common_fault]:
                return 'F'
            if '分析依据' not in answer_kpi[common_fault] or '分析依据' not in predict_kpi[common_fault]:
                return 'F'
            if not self.is_llm_judge_fault_same(answer_kpi[common_fault]['故障对象'], predict_kpi[common_fault]['故障对象'], '故障对象'):
                return 'F'
        return 'T'

    def get_kpi_structure(self, content):
        content = self.get_json_structure(content)
        result = {}
        if isinstance(content, list):
            for obj in content:
                result[obj['故障根因类型']] = {'故障对象': obj['故障对象'], '分析依据': obj['分析依据']}
        return result

    def judge_common_key_similar_result(self, answer, predict):
        """
        判断两个kpi是否一致，适用于单个层级逐个字段比较，去除
        """
        if answer == predict:
            return 'T'
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        if not answer_json or not predict_json:
            return 'F'
        common_keys = set(answer_json.keys()) & set(predict_json.keys())
        for common_key in common_keys:
            if not self.is_llm_judge_fault_same(answer_json[common_key], predict_json[common_key], common_key):
                return 'F'
        return 'T'

    def judge_alarm_plan_result(self, answer, predict):
        """
        Plan通过语义判断吧，或者裁判模型
        """
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        if not answer_json or not predict_json:
            return 'F'
        if not predict_json['plan']:
            return 'T'
        common_keys = set(answer_json.keys()) & set(predict_json.keys())
        if 'plan' in common_keys and self.is_llm_judge_fault_same(answer_json['plan'], predict_json['plan'], 'plan'):
            return 'T'
        return 'F'

    def judge_alarm_step_result(self, answer, predict):
        """
        Step判valid和api两个字段是否一致，和next_step字段的语义
        """
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        if not answer_json or not predict_json:
            return 'F'
        common_keys = set(answer_json.keys()) & set(predict_json.keys())
        valid_res = True if 'valid' in common_keys and answer_json['valid'] == predict_json['valid'] else False
        if not valid_res:
            return 'F'
        api_res = True if 'api' in common_keys and answer_json['api'] == predict_json['api'] else False
        if not api_res:
            return 'F'
        next_step_res = True if 'next_step' in common_keys and self.is_llm_judge_fault_same(answer_json['next_step'], predict_json['next_step'], 'next_step') else False
        if next_step_res:
            return 'T'
        return 'F'

    def judge_alarm_step_revise_result(self, answer, predict):
        """
        StepRevise判valid字段是否一致就好
        """
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        if not answer_json or not predict_json:
            return 'F'
        common_keys = set(answer_json.keys()) & set(predict_json.keys())
        if 'valid' in common_keys and answer_json['valid'] == predict_json['valid']:
            return 'T'
        return 'F'

    def judge_alarm_summarize_result(self, answer, predict):
        """
        Summarize判Can_a_conclusion_be_drawn字段是否一致，和Conclusion字段的语义
        """
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        if not answer_json or not predict_json:
            return 'F'
        common_keys = set(answer_json.keys()) & set(predict_json.keys())
        can_conclusion_res = True if 'Can_a_conclusion_be_drawn' in common_keys and str(answer_json['Can_a_conclusion_be_drawn']).lower() == str(predict_json['Can_a_conclusion_be_drawn']).lower() else False
        if not can_conclusion_res:
            return 'F'
        if not predict_json['Conclusion']:
            return 'T'
        conclusion_res = True if 'Conclusion' in common_keys and self.is_llm_judge_fault_same(answer_json['Conclusion'], predict_json['Conclusion'], 'Conclusion') else False
        if conclusion_res:
            return 'T'
        return 'F'

    def is_llm_judge_fault_same(self, answer, predict, key, similarity=0.5):
        """
        KPI故障，告警故障等诊断类的，模型输出结果不会完全一致，语义一致即可
        """
        prompt = f'你是一个通信领域故障诊断专家。请分析以下两条故障诊断的"{key}"是否表达相同的含义（如果是列表，可以忽略顺序），并给出语义相似度评分（0~1之间），其中1表示完全相同，0表示完全不同。\n\n        1: {{}}\n        2: {{}}\n\n        请以如下JSON格式返回结果：\n        {{{{\n          "相似度": <float>,\n          "是否匹配": <true/false>,\n          "原因": "<简要说明判断依据>"\n        }}}}'
        reply = self.auto_judge_semantics(answer, predict, prompt)
        reply_json = self.get_json_structure(reply)
        if '是否匹配' in reply_json and reply_json['是否匹配'] is True:
            return True
        elif '相似度' in reply_json and float(reply_json['相似度']) >= similarity:
            return True
        return False

    def get_tree_structure(self, content):
        start = content.find('```')
        if start == -1:
            return content
        end = content.find('```', start + len('```'))
        if end == -1:
            return content[start + len('```'):]
        return content[start + len('```'):end].strip()

    def get_mermaid_structure(self, content):
        """
        提取字符串中的mermaid图结构，去掉```mermaid和```并取中间部分
        """
        start = content.find('```mermaid')
        if start == -1:
            return ''
        end = content.find('```', start + len('```mermaid'))
        if end == -1:
            return ''
        return content[start + len('```mermaid'):end].strip()

    def is_mermaid_level_same(self, answer_mermaid, predict_mermaid, similarity_level=None):
        """
        similarity_level相似模式，严格相同
        """
        result = 'F'
        if answer_mermaid == predict_mermaid:
            result = 'T'

        def parse_sequence_mermaid(mermaid_str):
            lines = mermaid_str.strip().split('\n')
            participants = []
            messages = []
            notes = []
            for line in lines:
                line = line.strip()
                if line.startswith('participant'):
                    participant = line.split(' ', 1)[1].strip()
                    participants.append(participant)
                elif '->>' in line or '-->' in line:
                    parts = re.split('\\s*->>\\s*|\\s*-->\\s*', line)
                    if len(parts) < 2:
                        continue
                    source = parts[0].strip()
                    target_content = parts[1].split(':', 1)
                    target = target_content[0].strip()
                    content = target_content[1].strip() if len(target_content) > 1 else ''
                    messages.append((source, target, content))
                elif line.startswith('Note'):
                    note_parts = line.split(':', 1)
                    position = note_parts[0].split('of')[0].strip()
                    content = note_parts[1].strip() if len(note_parts) > 1 else ''
                    notes.append((position, content))
            return {'participants': participants, 'messages': messages, 'notes': notes}

        def compare_sequence_structures(expected, actual):
            if expected['participants'] != actual['participants']:
                return False
            if expected['messages'] != actual['messages']:
                return False
            if expected['notes'] != actual['notes']:
                return False
            return True

        def compare_mermaid_sequence_diagrams(expected, actual):
            expected_parsed = parse_sequence_mermaid(expected)
            actual_parsed = parse_sequence_mermaid(actual)
            return compare_sequence_structures(expected_parsed, actual_parsed)

        def parse_class_diagram(mermaid_str):
            lines = mermaid_str.strip().split('\n')
            classes = {}
            relations = []
            for line in lines:
                line = line.strip()
                if not line or line == 'classDiagram':
                    continue
                if line.startswith('class'):
                    class_name = re.search('class\\s+([^\\s{]+)', line).group(1)
                    class_name = class_name.strip()
                    classes[class_name] = []
                    if '{' in line:
                        attributes = line.split('{', 1)[1].split('}')[0].strip().split('\n')
                        for attr in attributes:
                            attr = attr.strip()
                            if attr:
                                classes[class_name].append(attr)
                elif '--' in line:
                    parts = line.split('--')
                    if len(parts) != 2:
                        continue
                    left = parts[0].strip()
                    right = parts[1].split(':', 1)[0].strip()
                    relation_type = 'ASSOCIATION'
                    if line.startswith('*--'):
                        relation_type = 'AGGREGATION'
                    relations.append((left, right, relation_type))
            return {'classes': classes, 'relations': relations}

        def compare_class_diagrams(expected, actual):
            if expected['classes'] != actual['classes']:
                return False
            if expected['relations'] != actual['relations']:
                return False
            return True

        def compare_mermaid_class_diagrams(expected_str, actual_str):
            expected = parse_class_diagram(expected_str)
            actual = parse_class_diagram(actual_str)
            return compare_class_diagrams(expected, actual)

        def judge_mermaid_by_llm(sentence1, sentence2, expect_score=0.5):
            """
            用模型评估相似度，两个图相似度大于80%，认为ok
            """
            reply = self.auto_judge_semantics(sentence1, sentence2, '请问下面两个mermaid图的功能等价性和表现形式相似性有多少？\\n以json形式展示结果：{{"功能等价性": 0.52, "表现形式相似性": 0.32}}\\n# 图A:\\n{}\\n# 图B:\\n{}')
            reply_json = self.get_json_structure(reply)
            return '功能等价性' in reply_json and float(reply_json['功能等价性']) >= expect_score
        if 'classDiagram' in predict_mermaid and 'classDiagram' in answer_mermaid:
            if compare_mermaid_class_diagrams(predict_mermaid, answer_mermaid) or judge_mermaid_by_llm(predict_mermaid, answer_mermaid):
                result = 'T'
        elif 'sequenceDiagram' in predict_mermaid and 'sequenceDiagram' in answer_mermaid:
            if compare_mermaid_sequence_diagrams(predict_mermaid, answer_mermaid) or judge_mermaid_by_llm(predict_mermaid, answer_mermaid):
                result = 'T'
        return result

    def erase_middle_space(self, outer_str):
        start_end_pos = outer_str.find('START') + len('START')
        newline_pos = outer_str.find('\n', start_end_pos)
        if newline_pos == -1:
            span_str = outer_str[start_end_pos:]
        else:
            span_str = outer_str[start_end_pos:newline_pos]
        cleaned_span_str = span_str.strip()
        if cleaned_span_str != span_str:
            if newline_pos == -1:
                result_str = outer_str[:start_end_pos] + cleaned_span_str
            else:
                result_str = outer_str[:start_end_pos] + cleaned_span_str + outer_str[newline_pos:]
        else:
            result_str = outer_str
        return result_str

    def handle_mml(self, script):
        mml_list = []
        for mml in script.split('\n'):
            if not mml:
                continue
            mml = mml.strip().strip(';')
            cmd, param = mml.split(':', 1)
            mml_list.append(cmd.strip() + ':' + ','.join((p.strip() for p in sorted(param.split(','), key=lambda p: p.strip()))) + ';')
        return (mml_list, len(mml_list))

    def erase_space(self, outer_str):
        str = outer_str
        str = str.strip()
        str = str.replace(' ', '')
        return str

    def is_json_level_same(self, answer_json, predict_json, similarity_level, list_value_model=0):
        result = 'F'
        if answer_json == predict_json:
            return 'T'
        if len(answer_json) == len(predict_json) and len(answer_json) > 0:
            for key in answer_json.keys():
                label_param_value = answer_json[key]
                if key not in predict_json:
                    return 'F'
                predict_param_value = predict_json[key]
                if label_param_value == predict_param_value or str(label_param_value) == str(predict_param_value) or str(label_param_value).replace(' ', '') == str(predict_param_value).replace(' ', '') or self.special_compare(key, label_param_value, predict_param_value):
                    result = 'T'
                elif similarity_level == '1' and self.auto_judge_semantics_same(label_param_value, predict_param_value) == '是':
                    result = 'T'
                elif similarity_level == '2' and self.auto_judge_similarity(label_param_value, predict_param_value) == '是':
                    result = 'T'
                elif type(label_param_value) == dict:
                    result = self.is_json_level_same(label_param_value, predict_param_value, similarity_level)
                    if result == 'F':
                        break
                elif self.are_both_list_str(label_param_value, predict_param_value):
                    if list_value_model == 1:
                        if sorted(label_param_value) == sorted(predict_param_value):
                            result = 'T'
                    elif list_value_model == 2:
                        if len(label_param_value) >= len(predict_param_value):
                            result = 'T'
                            for predict_item in predict_param_value:
                                flag = False
                                for label_item in label_param_value:
                                    if self.auto_judge_semantics_same(predict_item, label_item) == '是':
                                        flag = True
                                        break
                                if not flag:
                                    result = 'F'
                                    break
                else:
                    result = 'F'
                    break
        return result

    def are_both_list_str(self, list1, list2):
        if type(list1) == list and type(list2) == list:
            flag1 = all((isinstance(item, str) for item in list1))
            flag2 = all((isinstance(item, str) for item in list2))
            return flag1 and flag2
        return False

    def special_compare(self, key, label_param_value, predict_param_value):
        if key == 'neName':
            if label_param_value.replace('网元', '') == predict_param_value.replace('网元', '') or label_param_value.replace('NE', '') == predict_param_value.replace('NE', ''):
                return True
        return False

    def is_json_head_similarity(self, answer, predict):
        if predict.startswith('```\n') and predict.endswith('\n```'):
            length = len(predict)
            predict = predict[len('```\n'):length - len('\n```')]
        if answer.startswith('START\n'):
            answer_head = answer[len('START\n'):answer.index('{')].replace(':', '').replace('：', '')
            predict_head = predict[len('START\n'):predict.index('{')].replace(':', '').replace('：', '')
            if self.auto_judge_semantics_same(answer_head, predict_head) != '是':
                return False
            bad_example = {'物理网卡': '某个设备'}
            for bad_key, bad_val in bad_example.items():
                if bad_key in answer_head and bad_val in predict_head:
                    return False
        return True

    def get_json_structure(self, input, need_json_fix=False):
        """
        提取字符串中的json结构，去掉```json和```并取中间部分，若没有干扰的字符，直接取整个字符串转化为json
        """

        def get_json_data(inner_loc_str, inner_need_json_fix):
            try:
                start = inner_loc_str.find('Thought')
                end = inner_loc_str.rfind('Can_a_conclusion_be_drawn')
                if inner_loc_str.find('\n') != -1:
                    inner_loc_str = inner_loc_str.replace('\n', '\\n')
                if start != -1 and end != -1:
                    new_str = inner_loc_str[0:start - 1] + inner_loc_str[end - 1:len(inner_loc_str)]
                    js_data = json.loads(new_str)
                else:
                    js_data = json.loads(inner_loc_str)
            except Exception as e:
                if inner_need_json_fix:
                    inner_loc_str = self.fix_json(inner_loc_str)
                logger.error(f'get_json_data error, str:{inner_loc_str}')
                try:
                    new_str = inner_loc_str.replace('\n', '').strip()
                    js_data = json.loads(new_str)
                    return js_data
                except:
                    logger.error(f'get_json_data error after replace')
                sub_json_str, sub_json_result = self.get_last_json_object(inner_loc_str)
                replace_str = inner_loc_str.replace(sub_json_str, '')
                sec_sub_json_str, sec_sub_json_result = self.get_last_json_object(replace_str)
                found_all_key = True
                for key_str in sub_json_result:
                    if key_str not in sec_sub_json_result:
                        found_all_key = False
                        break
                if found_all_key:
                    return {}
                return sub_json_result
            return js_data
        loc_str = input
        try:
            loc_str = self.erase_comment(loc_str)
            if '</think>' in loc_str:
                loc_str = loc_str.split('</think>', 1)[-1]
            loc_str = loc_str.replace('\xa0', ' ').replace('\\n', '\n').replace("'", '\\"')
            if '```json' in loc_str:
                loc_str = loc_str.split('```json', 1)[-1].split('```', 1)[0]
            elif '```' in loc_str:
                loc_str = loc_str.split('```', 1)[-1].split('```', 1)[0]
            json_data = json.loads(loc_str)
        except Exception as ex:
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

    def get_last_json_object(self, loc_str):
        end_pos = loc_str.rfind('}')
        left_brackets_indexs = self.find_all_index_of_char(loc_str, '{')
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

    def find_all_index_of_char(self, str, char):
        result = []
        for i in range(len(str)):
            if str[i] == char:
                result.append(i)
        return result

    def erase_comment(self, erase_predict):
        lines = erase_predict.split('\n')
        new_lines = []
        for line in lines:
            if '//' in line:
                comma = line.find(',')
                pos = line.rfind('//')
                s_quotation = line.rfind("'")
                d_quotation = line.rfind('"')
                colon = line.find(':')
                rcolon = line.rfind(':')
                if (s_quotation < pos and d_quotation < pos or (comma > 0 and comma < pos and (colon == rcolon))) and colon < pos:
                    line = line[:pos]
            new_lines.append(line)
        new_str = '\n'.join(new_lines)
        return new_str

    def auto_judge_semantics_same(self, sentence1, sentence2):
        return self.auto_judge_semantics(sentence1, sentence2, '请对输入的如下A和B两个句子进行语义对比，如果语义一致，则回答“是”，如果语义不一致则回答“否”，只需要回答“是”和“否”，不需要其他的输出。\\n====A：{}\\nB：{}')

    def auto_judge_similarity(self, sentence1, sentence2):
        return self.auto_judge_semantics(sentence1, sentence2, '请对输入的如下A和B两个句子进行语义对比，如果语义一致或B句子的语义包含A句子表达的意思，则回答“是”，如果语义不一致则回答“否”，只需要回答“是”和“否”，不需要其他的输出。\\n====A：{}\\nB：{}')

    def auto_judge_semantics2(self, sentence1, sentence2, prompt):
        APP_Token = '62ac2501-caaf-4f54-b725-daa18514bdff'
        qwen_model = 'qwen2.5-72B-int4'
        Roma_URL = 'http://127.0.0.1:1/unconfigured'
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer NAIE_' + qwen_model, 'csb-token': APP_Token}
        submit_body = {'model': 'qwen2.5-72B-int4', 'messages': [{'role': 'user', 'content': prompt.format(sentence1, sentence2)}]}
        label_answer = requests.post(url=Roma_URL + '&path=/v1/chat/completions', json=submit_body, headers=headers, verify=True, timeout=1200)
        time.sleep(0.1)
        return json.loads(label_answer.text)['choices'][0]['message']['content']

    def auto_judge_semantics(self, sentence1, sentence2, prompt):
        transport = httpx.HTTPTransport(retries=3, verify=True)
        http_client = httpx.Client(transport=transport, timeout=3000)
        client = OpenAI(api_key='EMPTY', base_url='http://127.0.0.1:1/unconfigured', http_client=http_client)
        response = client.chat.completions.create(model='Qwen3-32B', messages=[{'role': 'system', 'content': 'You are a helpful assistant'}, {'role': 'user', 'content': prompt.format(sentence1, sentence2)}], stream=False)
        return response.choices[0].message.content
