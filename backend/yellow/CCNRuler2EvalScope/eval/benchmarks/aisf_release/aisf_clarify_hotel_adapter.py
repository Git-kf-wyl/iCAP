# Private iCAP Yellow implementation. Do not publish.
import csv
from datetime import datetime
from typing import List, Any
import json
import os
from pathlib import Path
import re
import pandas as pd
from eval.benchmarks import Benchmark, DataAdapter
import eval.benchmarks.aisf_release.utils as aisf_release_utils
from typing import Any, Optional
from eval.benchmarks.aisf_release.prompt import HotelPrompt
from eval.metrics.llm_judge import LLMJudge
from eval.benchmarks.aisf_release.judge_step_sys_prompt import Travel_Reply_Prompt_Para_Check, Travel_Reply_Prompt_Must_Clarify, Travel_Reply_Prompt_Modify_User_Input, Travel_Reply_Prompt_Not_Use_His_Preference, Travel_Reply_Prompt_Use_His_Preference
from eval.benchmarks.aisf_release.judge_step_sys_prompt_2 import Clarify_Travel_Prompt_Hotel
from eval.utils.logger import get_logger
logger = get_logger()

@Benchmark.register(name='aisf_clarify_hotel', pretty_name='AISF Clarify Test', dataset_id='aisf_clarify_hotel', subset_list=['参数校验', '必须澄清', '修改用户输入', '不使用历史偏好', '使用历史偏好'], metric_list=['AverageAccuracy'], model_adapter='aisf_clarify_server', few_shot_num=0, system_prompt=None, prompt_template='{query}', llm_as_a_judge=True, extra_params={'need_step_judge': True})
class AISFClarifyHotelDataAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        extra_params = kwargs.get('extra_params', {})
        self.need_step_judge = extra_params.get('need_step_judge', False)
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls'))]
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            if '参数校验01' in excel_file:
                res_dict['参数校验'] = aisf_release_utils.read_from_excel_1(file_path)
            elif '必须要澄清的参数02' in excel_file:
                res_dict['必须澄清'] = aisf_release_utils.read_from_excel_2(file_path)
            elif '用户原始诉求03' in excel_file:
                res_dict['修改用户输入'] = aisf_release_utils.read_from_excel_3(file_path)
            elif '不使用历史偏好04' in excel_file:
                res_dict['不使用历史偏好'] = aisf_release_utils.read_from_excel_4(file_path)
            elif '使用历史偏好05' in excel_file:
                res_dict['使用历史偏好'] = aisf_release_utils.read_from_excel_5(file_path)
        return res_dict
    '\n    input_d = res_dict[subset_name]\n    '

    def gen_prompt(self, input_d: dict, subset_name: str, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        input_d['turns'] = []
        input_d['need_step_judge'] = True if self.need_step_judge else False
        input_d['step_system_prompt'] = ''
        input_d['step_system_prompt_2'] = ''
        d = datetime.now()
        messages = []
        messages.append({'role': 'system', 'content': HotelPrompt})
        input = ''
        if subset_name in ['参数校验']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{input_d.get('Current date', '{}')}\n\n"
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Para_Check
        elif subset_name in ['必须澄清']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Must_Clarify
            input_d['step_system_prompt_2'] = Clarify_Travel_Prompt_Hotel.replace('{1}', str(['入住日期', '酒店离店日期', '目的地']))
        elif subset_name in ['修改用户输入']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Modify_User_Input
        elif subset_name in ['不使用历史偏好']:
            input += f"## 历史偏好\n{input_d.get('User prefer', '{}')}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            system_prompt = Travel_Reply_Prompt_Not_Use_His_Preference.replace('{1}', input_d['Query content'])
            system_prompt = system_prompt.replace('{2}', input_d['Must answer'])
            input_d['step_system_prompt'] = system_prompt
        elif subset_name in ['使用历史偏好']:
            input += f"## 历史偏好\n{input_d.get('User prefer', '{}')}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Use_His_Preference
        input += f"## 用户输入 {input_d['Input']}"
        messages.append({'role': 'user', 'content': f'{input}\n\n/nothink'})
        input_d['turns'].append(messages)
        return self.gen_prompt_data(prompt='', index=0, messages=input_d)

    def get_gold_answer(self, input_d: dict) -> str:
        if 'Test answer' in input_d:
            return input_d['Test answer']
        else:
            return None

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        return result

    def match(self, gold: str, pred: str, question: str, subset_name) -> float:
        if subset_name != '必须澄清':
            result = aisf_release_utils.is_successful_hotel(gold, pred)
        elif str(pred) == '1':
            result = True
        else:
            result = False
        print(result)
        return result
    '\n    pred : [\n        [ans_str_turn0],\n        [ans_str_ans_str_turn1],\n    ]\n    kwargs={\n        raw_input: res_dict[subset_name]\n        subset_name: str\n    }\n    '

    def llm_match(self, gold: Any, pred: Any, judge: Optional[LLMJudge]=None, **kwargs):
        subset_name = kwargs.get('subset_name')
        if not subset_name:
            logger.error('subset_name is None')
            return False
        if subset_name == '必须澄清':
            return str(pred) == '1'
        if not judge:
            logger.error('LLMJudge is None')
            return False
        sys_prompt = 'You are a helpful assistant'
        usr_prompt_format = '请对输入的如下A和B两个句子进行语义对比，给出语义相似度评分（0~1之间），其中1表示完全相同，0表示完全不同，不需要其他的输出。\\n====A：{}\\nB：{}'
        try:
            test_answer = gold.replace("'", '"')
            llm_answer = pred.replace("'", '"')
            test_answer = json.loads(test_answer)
            llm_answer = json.loads(llm_answer)
        except Exception as e:
            logger.error('llm_match字符串转化为JSON错误' + str(e))
            print('llm_match字符串转化为JSON错误' + str(e))
            return False
        date_keys = ['dDate1', 'checkOutDate']
        for key in test_answer:
            if key not in llm_answer:
                return False
            if key not in date_keys:
                outputs = judge[0](usr_prompt_format.format(test_answer[key], llm_answer[key]), sys_prompt)
                return float(outputs) >= 0.5
        return False
