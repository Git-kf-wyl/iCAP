# Private iCAP Yellow implementation. Do not publish.
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import re
import pandas as pd
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.service_release.utils import process_results
from typing import Any, Optional
from eval.metrics.llm_judge import LLMJudge

@Benchmark.register(name='aisf_clarify_dev', pretty_name='AISF Clarify Test', dataset_id='aisf_clarify_dev', subset_list=['shopping', 'foodie', 'taxi-simple', 'trip', 'airplane', 'hotel'], metric_list=['AverageAccuracy'], model_adapter='aisf_clarify_server', few_shot_num=0, system_prompt=None, prompt_template='{query}', llm_as_a_judge=True, extra_params={'need_step_judge': False})
class AISFClarifyDataAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        extra_params = kwargs.get('extra_params', {})
        self.need_step_judge = extra_params.get('need_step_judge', False)
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        """
        Args:
            input_file_path: The path is the storage location for the dataset.
            pred_file_path: None.
            kwargs: subset_list is included here.
        Return: 
            {
                "subset_name": [
                    {
                        "name": "subset_name2",
                        "system_prompt": "",
                        "judge_prompt": "",
                        "instructions": [{"instruction":"user_input_1", "context":"{...}"}, {"instruction":"user_input_2", "context":"{...}"}, ...],
                        "preference": "",
                    }
                ],
                "subset_name2": [
                    {
                        "name": "subset_name2",
                        "system_prompt": "",
                        "judge_prompt": "",
                        "instructions": [{"instruction":"user_input_1", "context":"{...}"}, {"instruction":"user_input_2", "context":"{...}"}, ...],
                        "preference": "",
                    }
                ]
            }
        """
        res_dict = {}
        for subset_name in kwargs.get('subset_list', []):
            data = []
            with open(os.path.join(input_file_path, f'{subset_name}.csv'), 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                for row in reader:
                    data.append(row)
            dataset = pd.DataFrame(data)
            systemPrompt = Path(os.path.join(input_file_path, f'{subset_name}.md')).read_text('utf-8')
            judgePrompt = Path(os.path.join(input_file_path, f'{subset_name}_judge.md')).read_text('utf-8')
            res_dict[subset_name] = [{'name': subset_name, 'system_prompt': systemPrompt, 'judge_prompt': judgePrompt, 'preference': row[1], 'instructions': [{'instruction': x, 'context': y if y and len(y) > 0 else '{}'} for x, y in zip(row[2::2], row[3::2]) if pd.notna(x) and len(x) > 0], 'task_index': row[0]} for row in dataset.itertuples()]
        return res_dict
    '\n    input_d = res_dict[subset_name]\n    '

    def gen_prompt(self, input_d: dict, subset_name: str, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        input_d['turns'] = []
        input_d['need_step_judge'] = True if self.need_step_judge else False
        d = datetime.now()
        for index, step in enumerate(input_d.get('instructions', [])):
            messages = []
            if index == 0:
                messages.append({'role': 'system', 'content': input_d.get('system_prompt', '')})
                input = ''
                if subset_name in ['trip', 'hotel', 'airplane']:
                    input += f"## 历史偏好\n{input_d.get('preferennce', '{}')}\n\n"
                    input += f"## 当前日期\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
                    if subset_name != 'hotel':
                        input += '## 当前城市\n广东省深圳市\n\n'
                elif subset_name in ['shopping', 'foodie']:
                    input += f"## 历史偏好\n{input_d.get('preferennce', '{}')}\n\n"
                elif subset_name == 'taxi':
                    input += f"## 历史偏好\n{input_d.get('preferennce', '{}')}\n\n"
                    input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]} {d.strftime('%H:%M')}\n\n"
                input += f"## 用户输入\n{step.get('instruction')}\n\n## 相关上下文\n{step.get('context')}\n\n"
                messages.append({'role': 'user', 'content': f'{input}/nothink'})
            else:
                input = f"## 用户输入\n{step.get('instruction')}\n\n## 相关上下文\n{step.get('context')}\n\n"
                messages.append({'role': 'user', 'content': f'{input}/nothink'})
            input_d['turns'].append(messages)
        return self.gen_prompt_data(prompt='', index=0, messages=input_d)

    def get_gold_answer(self, input_d: dict) -> str:
        return ''

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        return result

    def match(self, gold: str, pred: str, raw_input, subset_name) -> float:
        return 0
    '\n    pred : [\n        [ans_str_turn0],\n        [ans_str_ans_str_turn1],\n    ]\n    kwargs={\n        raw_input: res_dict[subset_name]\n        subset_name: str\n    }\n    '

    def llm_match(self, gold: Any, pred: Any, judge: Optional[LLMJudge]=None, **kwargs):
        input_d = kwargs.get('raw_input')
        subset_name = kwargs.get('subset_name')
        if not input_d:
            return False
        if not judge:
            return False
        pattern = re.compile('^(?:(?:<think>)?(?P<think>.*)</think>)?[^\\{]*(?P<result>\\{.*\\})[^\\}]*$', flags=re.DOTALL)
        d = datetime.now()
        for jg in judge:
            history = ''
            context = ''
            for idx, (request, response) in enumerate(zip(input_d.get('instructions', []), pred)):
                history += f"User: {request.get('instruction')}\n"
                context += f"{request.get('context', '{}')}\n"
                match = pattern.match(response[0])
                if not match or not match.groupdict():
                    return False
                else:
                    content = json.loads(match.groupdict().get('result', '{}'))
                    if content.get('澄清状态', '') == '完成' or content.get('Type', '') == 'result':
                        break
                    if content.get('澄清问题') is not None:
                        history += f"System: {content['澄清问题']}\n"
                    elif content.get('Desc') is not None:
                        history += f"System: {content['Desc']}\n"
                    else:
                        return False
            input = ''
            if subset_name in ['trip', 'hotel', 'airplane']:
                input += f"<历史偏好>\n{input_d.get('preferennce', '{}')}\n\n"
                input += f"<当前日期>\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
                if subset_name != 'hotel':
                    input += '<当前城市>\n广东省深圳市\n\n'
            elif subset_name in ['shopping', 'foodie']:
                input += f"<历史偏好>\n{input_d.get('preferennce', '{}')}\n\n"
            elif subset_name == 'taxi':
                input += f"<历史偏好>\n{input_d.get('preferennce', '{}')}\n\n"
                input += f"<当前时间>\n{d.date()} 星期{'一二三四五六日'[d.weekday()]} {d.strftime('%H:%M')}\n\n"
            input += f'<历史对话>\n{history}\n\n'
            input += f'<相关上下文>\n{context}\n\n'
            input += f'<提取结果>\n{pred[-1][0]}'
            outputs = jg(input, input_d.get('judge_prompt', ''))
            raw_input = kwargs.get('raw_input', {})
            raw_input['judge_output'] = outputs
            if 'Pass' in outputs:
                return True
            else:
                return False
