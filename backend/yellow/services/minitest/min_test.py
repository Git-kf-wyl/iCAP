# Private iCAP Yellow business implementation. Do not publish.
import ast
import json
import os
import re
import threading
import time
from datetime import datetime
import httpx
import requests
import pandas as pd
from openai import OpenAI
from services import logger
from utils.consts import LLM_MIN_DATASET_PATH
RULER1_PROMPT = '\nPlease put your final answer within \\boxed{}.'
NOTHINK_FLAG = '/nothink'
JUDGE_MODEL_API_URL = 'http://127.0.0.1:1/unconfigured'
JUDGE_MODEL_NAME = 'Qwen3-32B'
JUDGE_MODEL_API_KEY = ''

def read_from_excel(filename, sheetname, limit):
    test_cases = []
    df = pd.read_excel(filename, sheet_name=sheetname)
    limit_index = limit - 1 if limit > 0 else len(df) - 1
    for index, row in df.iterrows():
        if index > limit_index:
            break
        case_id = row['序号']
        input_data = row['问题']
        expected_ans = row['答案']
        if '</think>' in str(expected_ans):
            expected_ans = str(expected_ans).split('</think>')[1].strip()
            if 'usage' in str(expected_ans):
                expected_ans = str(expected_ans).split('usage')[0].strip()[:-2]
        question_type = row['类型']
        question_source = row['来源']
        if '系统prompt' in row:
            system_prompt = row['系统prompt']
        else:
            system_prompt = ''
        test_cases.append({'id': case_id, 'input': input_data, 'gold_answer': expected_ans, 'system_prompt': '这是一项非常冗长的任务，建议您充分利用完整的输出上下文来处理。整体输入和输出 tokens 控制在 64k tokens，充分利用上下文窗口长度将任务彻底完成，避免耗尽 tokens。', 'question_type': question_type, 'question_source': question_source})
    return test_cases

def call_model(model_input, url, model):
    headers = {'Content-Type': 'application/json'}
    body = {'model': model, 'messages': model_input, 'temperature': 0}
    start_time = time.time()
    response = requests.post(url, json=body, headers=headers)
    end_time = time.time()
    elapsed_time = end_time - start_time
    return (response.text, elapsed_time)

def extract_clean_text(text):
    """去除 HTML 标签并清理空白字符"""
    text = re.sub('<[^>]+>', '', text)
    text = re.sub('\\s+', ' ', text).strip()
    if 'boxed' in text:
        match = re.search('boxed\\{([^}]*)\\}', text)
        text = match.group(1) if match else 'no match'
    return text

def parse_think_response_clean(message_body):
    """
    解析消息体，分割出 think 内容和回答内容（纯文本）
    返回: (think_content, answer_content)
          如果没有 </think>，则 think_content=None
    """
    parts = message_body.split('</think>', 1)
    if len(parts) == 2:
        answer_content = extract_clean_text(parts[1])
    else:
        answer_content = extract_clean_text(message_body)
    return answer_content

def is_successful(expected, actual):
    if actual and (actual in expected or expected in actual):
        return (True, '')
    return (False, '内容不一致')

def is_successful_json(answer, extracted):
    try:
        answer_dict = ast.literal_eval(answer)
        if not isinstance(answer_dict, dict):
            return (False, '非json')
        extracted_dict = ast.literal_eval(extracted)
        if not isinstance(extracted_dict, dict):
            return (False, '非json')
    except Exception as e:
        return (False, str(e))
    for k, v in answer_dict.items():
        if k not in extracted_dict:
            return (False, f'模型提取 {k} 参数错误')
        if extracted_dict[k] != v:
            return (False, f'模型提取 {k} 参数值错误')
    if len(answer_dict) != len(extracted_dict):
        return (False, '模型提取非指定参数')
    return (True, 'success')

def is_successful_json_slow(answer, extracted):
    try:
        answer_dict = ast.literal_eval(answer)
        if not isinstance(answer_dict, dict):
            return (False, '非json')
        extracted_dict = ast.literal_eval(extracted)
        if not isinstance(extracted_dict, dict):
            return (False, '非json')
        extracted_dict = extracted_dict.get('arguments', None)
        if not extracted_dict:
            return (False, '没有arguments')
    except Exception as e:
        return (False, str(e))
    for k, v in answer_dict.items():
        if k not in extracted_dict:
            return (False, f'模型提取 {k} 参数错误')
        if extracted_dict[k] != v:
            return (False, f'模型提取 {k} 参数值错误')
    if len(answer_dict) != len(extracted_dict):
        return (False, '模型提取非指定参数')
    return (True, 'success')

def is_successful_jsonl(expected_answer, llm_answer):
    data = llm_answer.replace('```', '')
    data = data.replace('json', '')
    try:
        data = json.loads(data)
        test_answer = json.loads(expected_answer)
    except Exception as e:
        return (False, '字符串转化为JSON错误')
    if len(test_answer) != len(data):
        return (False, 'Agent数量匹配错误')
    for test_answer_item, data_item in zip(test_answer, data):
        if test_answer_item['agent_name'] != data_item['agent_name']:
            return (False, 'LLM模型返回的agent_name与测试答案不一致')
        if test_answer_item['agent_name'] == 'LifeAssistantAgent' and test_answer_item['APP'] == '':
            continue
        if test_answer_item['APP'] != data_item['APP']:
            return (False, 'LLM模型返回的APP与测试答案不一致')
    return (True, 'success')

def judge_new_mml_equal_result(answer, predict):
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

def judge_equal_result(answer, predict):
    if predict is None:
        return False
    if answer and ':' in answer:
        answer = answer.split(':', 1)[-1]
        if answer.find(predict) != -1:
            return True
    if isinstance(predict, (int, float)):
        predict = str(predict)
    if judge_new_mml_equal_result(answer, predict):
        return True
    return False

def erase_comment(erase_predict):
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

def find_all_index_of_char(str, char):
    result = []
    for i in range(len(str)):
        if str[i] == char:
            result.append(i)
    return result

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

def fix_json(json_str):
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

def auto_judge_semantics(sentence1, sentence2, prompt):
    transport = httpx.HTTPTransport(retries=3, verify=True)
    http_client = httpx.Client(transport=transport, timeout=3600)
    client = OpenAI(api_key=JUDGE_MODEL_API_KEY, base_url=JUDGE_MODEL_API_URL, http_client=http_client)
    response = client.chat.completions.create(model=JUDGE_MODEL_NAME, messages=[{'role': 'system', 'content': 'You are a helpful assistant'}, {'role': 'user', 'content': prompt.format(sentence1, sentence2)}], stream=False)
    return response.choices[0].message.content

def call_and_parse_model(model_name, model_url, prompt_system: str, prompt_user: str):
    llm_answer = ''
    messages = []
    if prompt_system:
        messages.append({'role': 'system', 'content': prompt_system})
    messages.append({'role': 'user', 'content': prompt_user})
    try:
        response_text, elapsed_time_print = call_model(messages, model_url, model_name)
        tokens_print = json.loads(response_text)['usage']
        message_body = json.loads(response_text)['choices'][0]['message']['content']
        llm_answer = parse_think_response_clean(message_body)
    except Exception as e:
        print(f'调用报错: {e}')
    return str(llm_answer)

def parse_pred_result(result: str) -> str:
    """
    获取mml的参数值
    """
    try:
        start = result.find('```json\n')
        start_len = len('```json\n')
        end = result.rfind('\n```')
        mark_result = result[start + start_len:end].strip() if start != -1 and end != -1 else result
        parts = mark_result.split('\\n\\n')
        for part in parts:
            if part.find('extract_mml') != -1:
                mark_result = part.strip()
        param_result = json.loads(mark_result)['arguments']['parameter_value']
    except Exception as e:
        param_result = result
        print(f'Error in json loads err: {e}, pred: {param_result}')
    return param_result

class MinDatasetEvaluator:

    def __init__(self, model_config, output_path, limit, debug: bool=False):
        self.model_config = model_config
        self.output_path = output_path
        self.limit = 1000 if limit is None or limit == 0 else limit
        self.debug = debug
        self.log_min_dataset = logger.Logger('eval_log', console_log=debug)
        self.log_min_dataset.update_log_dir(f'{output_path}/logs')
        self.input_path = 'input' if os.name == 'nt' else LLM_MIN_DATASET_PATH
        self.api_url = model_config.get('api_url', '').rstrip('/').rsplit('/chat/completions', 1)[0]
        self.api_key = model_config.get('api_key', '')
        self.model_name = model_config.get('model', '')
        self.temp_num = 1
        self.max_tokens_num = 65536
        self.stream = False
        param_list = model_config.get('model_params', [])
        for param in param_list:
            if param['key'] == 'max_tokens':
                self.max_tokens_num = param['value']
            elif param['key'] == 'temperature':
                self.temp_num = param['value']
        self.log_min_dataset.info(f'cur model:{self.model_name}, {self.api_url}')
        self.client = OpenAI(base_url=self.api_url, api_key=self.api_key, http_client=httpx.Client(verify=True))
        models = self.client.models.list()
        self.log_min_dataset.info(f'model data: {models.data}')
        self.failed_count = 0

    def call_in_openai(self, sheetname, index, mml_input, prompt_system: str='', prompt_user: str=''):
        llm_answer = ''
        if mml_input:
            messages = mml_input
        else:
            messages = []
            if prompt_system:
                messages.append({'role': 'system', 'content': prompt_system})
            messages.append({'role': 'user', 'content': prompt_user})
        message_body = 'error'
        retry_count = 3
        for attempt in range(retry_count):
            try:
                self.log_min_dataset.info(f'start call_in_openai {sheetname} {index}, 尝试次数: {attempt + 1}')
                start_time = time.time()
                response = self.client.chat.completions.create(model=self.model_name, messages=messages, timeout=3600, temperature=self.temp_num, max_tokens=self.max_tokens_num, stream=self.stream)
                if self.stream:
                    collected_chunks = []
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content_chunk = chunk.choices[0].delta.content
                            collected_chunks.append(content_chunk)
                    message_body = ''.join(collected_chunks)
                    self.log_min_dataset.info(f'llm_answer:{message_body}')
                else:
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    tokens_print = response.usage
                    message_body = response.choices[0].message.content
                    self.log_min_dataset.info(f'end call_in_openai, origin_llm_answer: {message_body}')
                    llm_answer = parse_think_response_clean(message_body)
                    self.log_min_dataset.info(f'llm_answer: {llm_answer}, elapsed_time: {elapsed_time}, total_tokens: {tokens_print.total_tokens}')
                break
            except Exception as e:
                self.log_min_dataset.info(f'{sheetname} {index} openai调用报错: {e}')
                if attempt < retry_count - 1:
                    self.log_min_dataset.info(f'尝试重试，{60}秒后重试第 {attempt + 2} 次')
                    time.sleep(60)
                else:
                    self.failed_count += 1
        return (message_body, str(llm_answer))

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
                    inner_loc_str = fix_json(inner_loc_str)
                self.log_min_dataset.info(f'get_json_data error, str:{inner_loc_str}')
                try:
                    new_str = inner_loc_str.replace('\n', '').strip()
                    js_data = json.loads(new_str)
                    return js_data
                except:
                    self.log_min_dataset.info(f'get_json_data error after replace')
                sub_json_str, sub_json_result = get_last_json_object(inner_loc_str)
                replace_str = inner_loc_str.replace(sub_json_str, '')
                sec_sub_json_str, sec_sub_json_result = get_last_json_object(replace_str)
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
            loc_str = erase_comment(loc_str)
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

    def is_llm_judge_fault_same(self, answer, predict, key, similarity=0.5):
        """
        KPI故障，告警故障等诊断类的，模型输出结果不会完全一致，语义一致即可
        """
        prompt = f'你是一个通信领域故障诊断专家。请分析以下两条故障诊断的"{key}"是否表达相同的含义（如果是列表，可以忽略顺序），并给出语义相似度评分（0~1之间），其中1表示完全相同，0表示完全不同。\n\n1: {{}}\n2: {{}}\n\n请以如下JSON格式返回结果：\n{{{{\n  "相似度": <float>,\n  "是否匹配": <true/false>,\n  "原因": "<简要说明判断依据>"\n}}}}'
        reply = auto_judge_semantics(answer, predict, prompt)
        reply_json = self.get_json_structure(reply)
        if '是否匹配' in reply_json and reply_json['是否匹配'] is True:
            return True
        elif '相似度' in reply_json and float(reply_json['相似度']) >= similarity:
            return True
        return False

    def judge_alarm_step_result(self, answer, predict):
        """
        Step判valid和api两个字段是否一致，和next_step字段的语义
        """
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        if not answer_json or not predict_json:
            return False
        common_keys = set(answer_json.keys()) & set(predict_json.keys())
        valid_res = True if 'valid' in common_keys and answer_json['valid'] == predict_json['valid'] else False
        if not valid_res:
            return False
        api_res = True if 'api' in common_keys and answer_json['api'] == predict_json['api'] else False
        if not api_res:
            return False
        next_step_res = True if 'next_step' in common_keys and self.is_llm_judge_fault_same(answer_json['next_step'], predict_json['next_step'], 'next_step') else False
        if next_step_res:
            return True
        return False

    def judge_alarm_step_revise_result(self, answer, predict):
        """
        StepRevise判valid字段是否一致就好
        """
        answer_json = self.get_json_structure(answer)
        predict_json = self.get_json_structure(predict)
        if not answer_json or not predict_json:
            return False
        common_keys = set(answer_json.keys()) & set(predict_json.keys())
        if 'valid' in common_keys and answer_json['valid'] == predict_json['valid']:
            return True
        return False

    def is_successful_alarm_mml(self, pattern='', answer='', predict=''):
        if pattern == 'judge_equal_result':
            answer = parse_pred_result(answer.split("}}'")[0] + '}}' if len(answer.split("}}'")) > 1 else answer)
            print(f'answer: {answer}')
            predict = parse_pred_result(predict)
            print(f'predict: {predict}')
            res = judge_equal_result(answer, predict)
        elif pattern == 'judge_alarm_step_result':
            res = self.judge_alarm_step_result(answer, predict)
        elif pattern == 'judge_alarm_step_revise_result':
            res = self.judge_alarm_step_revise_result(answer, predict)
        else:
            res = True
        return (res, '')

    def run_eval(self, file_path, sheetname, model_config, limit):
        input_data_read = read_from_excel(file_path, sheetname, limit)
        test_res = []
        for index, line in enumerate(input_data_read):
            user_input = str(line['input'])
            if sheetname != '运维智能' and sheetname != 'AISF':
                user_input += RULER1_PROMPT
            sys_input = str(line['system_prompt'])
            q_type = str(line['question_type'])
            gold = str(line['gold_answer'])
            if sheetname == '运维智能' and q_type == 'mml生成':
                try:
                    full_prompt = user_input.split("'messages': ", 1)[1] if user_input.startswith("{'") else user_input.split('"messages": ', 1)[1]
                    full_prompt = full_prompt[:-1] if full_prompt[-1] == '}' else full_prompt[:-2]
                    messages = ast.literal_eval(full_prompt)
                    for msg in messages:
                        if msg.get('role') == 'tool':
                            msg['role'] = 'user'
                            msg.pop('name', None)
                            msg.pop('tool_call_id', None)
                    user_input = messages
                    origin_ans, llm_answer = self.call_in_openai(sheetname, index, mml_input=user_input)
                except Exception as e:
                    user_input = []
                    origin_ans, llm_answer = ('{}', '{}')
                    self.log_min_dataset.info(f'Error in json load: {e}')
            else:
                origin_ans, llm_answer = self.call_in_openai(sheetname, index, mml_input='', prompt_system=sys_input, prompt_user=user_input)
            question_source = str(line['question_source'])
            if question_source in ['judge_alarm_step_result', 'judge_alarm_step_revise_result', 'judge_equal_result']:
                compare_res, fail_reason = self.is_successful_alarm_mml(question_source, gold, llm_answer)
            elif question_source == 'json':
                compare_res, fail_reason = is_successful_json(gold, llm_answer)
            elif question_source == 'json_slow':
                compare_res, fail_reason = is_successful_json_slow(gold, llm_answer)
            elif question_source == 'jsonl':
                compare_res, fail_reason = is_successful_jsonl(gold, llm_answer)
            else:
                compare_res, fail_reason = is_successful(gold, llm_answer)
            data = {'问题': user_input, '标准答案': gold, '模型答案': llm_answer, '原始答案': origin_ans, 'result': 'Y' if compare_res else 'N'}
            test_res.append(data)
            self.log_min_dataset.info(f"******{sheetname}******模型回答: {llm_answer}, 答案: {line['gold_answer']}, 判题结果: {str(compare_res)}")
            time.sleep(600)
            self.log_min_dataset.info('60s ok')
        model_id_basename = os.path.basename(self.model_config.get('model_id', '')).rstrip(os.sep)
        review_path = f'{self.output_path}/reviews/{model_id_basename}'
        output_file_name = os.path.join(review_path, f'output_{self.model_name}_LLM最小集.xlsx')
        os.makedirs(os.path.dirname(output_file_name), exist_ok=True)
        self.write_to_excel(output_file_name, sheetname, test_res)

    def write_to_excel(self, filename, sheetname, out_data):
        df1 = pd.DataFrame(out_data)
        mode = 'w' if not os.path.exists(filename) else 'a'
        if_sheet_exists_option = 'replace' if mode == 'a' else None
        try:
            with pd.ExcelWriter(filename, engine='openpyxl', mode=mode, if_sheet_exists=if_sheet_exists_option) as writer:
                df1.to_excel(writer, sheet_name=sheetname, index=False)
            self.log_min_dataset.info(f'数据成功写入 {filename} 的 {sheetname} 工作表')
        except Exception as e:
            self.log_min_dataset.info(f'写入Excel文件时出错: {str(e)}')

    def run_min_test_eval(self):
        for file in os.listdir(self.input_path):
            if file.endswith(('.xlsx', '.xls')):
                file_path = os.path.join(self.input_path, file)
                sheets = ['知识百科', '数学', '逻辑推理', '指令遵从', '工具选择', '运维智能', 'AISF']
                for sheet in sheets:
                    if self.failed_count > 10:
                        self.log_min_dataset.error('******失败用例过多，退出测评，请检查网络******')
                        break
                    self.run_eval(file_path, sheet, self.model_config, self.limit)
                self.log_min_dataset.info('******所有测试用例执行完毕******')
