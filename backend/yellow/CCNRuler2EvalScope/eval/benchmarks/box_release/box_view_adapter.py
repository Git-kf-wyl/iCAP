# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
import jsonlines as jsonl
import json
import os
from typing import List, Any
from eval.benchmarks.box_release.utils import get_json_structure

@Benchmark.register(name='box_view', pretty_name='BOX', dataset_id='box_view', subset_list=['default'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class BoxToolUseViewAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        subset_list = kwargs['subset_list']
        for item in kwargs['subset_list']:
            res_dict[item] = []
        json_files = [f for f in os.listdir(input_file_path) if f.endswith('.jsonl')]
        for json_file in json_files:
            file_path = os.path.join(input_file_path, json_file)
            with open(file_path, 'r', encoding='utf-8') as f:
                if 'view' in json_file:
                    for line in f:
                        data = json.loads(line.strip())
                        res_dict['default'].append(data)
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = input_d['Question']
        full_prompt = self.prompt_template.format(query=problem)
        system_prompt = input_d['system_prompt'] if 'system_prompt' in input_d else self.system_prompt
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['Answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        pred = get_json_structure(result)
        return pred

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        """
        比较两个 JSON 字符串是否内容相等，不考虑字典键和列表元素的顺序。

        参数:
            pred (str): 预测的 JSON 字符串
            gold (str): 标准答案的 JSON 字符串

        返回:
            bool: 如果内容相同（忽略顺序），返回 True；否则返回 False
        """
        import json
        pred = json.dumps(pred, ensure_ascii=False)
        pred = pred.replace('<think>\n\n</think>\n\n', '').replace('<think>', '').replace('</think>', '').replace('</tool_call>', '').replace('<tool_call>', '').replace('\n', '').replace('```json', '').replace('```}', '').replace('```', '').replace('True', 'true').replace("'", '"').replace('[', '').replace(']', '')
        gold = gold.replace('<think>\n\n</think>\n\n', '').replace('<think>', '').replace('</think>', '').replace('</tool_call>', '').replace('<tool_call>', '').replace('\n', '').replace('```json', '').replace('```}', '').replace('```', '').replace('True', 'true').replace("'", '"')

        def remove_empty_values(data):
            """
            递归删除字典中值为空的字段（包括 "", None, [], {}），
            同时忽略 "call_state" 和 "callCategory" 字段。
            """
            if isinstance(data, dict):
                cleaned = {}
                for key, value in data.items():
                    if key in ['call_state', 'callCategory']:
                        continue
                    cleaned_value = remove_empty_values(value)
                    if cleaned_value not in [None, '', [], {}]:
                        cleaned[key] = cleaned_value
                return cleaned
            elif isinstance(data, list):
                cleaned = [remove_empty_values(item) for item in data]
                return [item for item in cleaned if item not in (None, '', [], {})]
            else:
                return data

        def process_callway(data):
            """
            如果是 INTENT_AVCALL_DIAL，且 callWay 不存在或为空，则设为 'facetime'
            """
            if isinstance(data, dict):
                name = data.get('name')
                args = data.get('args', {})
                if name == 'INTENT_AVCALL_DIAL':
                    if not isinstance(args, dict):
                        args = {}
                    if not args.get('callWay'):
                        args['callWay'] = 'facetime'
                    data['args'] = args
                return data
            return data

        def process_number_field(data):
            """
            如果是 INTENT_AVCALL_ADD_CONTACT，并且 number 的值不是数字格式（如 '123' 或 123），
            则从 args 中移除 number 字段。
            """
            if isinstance(data, dict):
                name = data.get('name')
                args = data.get('args', {})
                if name == 'INTENT_AVCALL_ADD_CONTACT' and isinstance(args, dict):
                    number = args.get('number')
                    if isinstance(number, int) or (isinstance(number, str) and number.isdigit()):
                        pass
                    else:
                        args.pop('number', None)
                    data['args'] = args
                return data
            return data

        def parse_if_needed(x):
            if isinstance(x, str):
                try:
                    return json.loads(x)
                except json.JSONDecodeError:
                    return None
            elif isinstance(x, dict):
                return x
            else:
                return None
        a_parsed = parse_if_needed(gold)
        b_parsed = parse_if_needed(pred)
        if a_parsed is None or b_parsed is None:
            return False
        a_parsed = process_callway(a_parsed)
        b_parsed = process_callway(b_parsed)
        a_parsed = process_number_field(a_parsed)
        b_parsed = process_number_field(b_parsed)
        a_clean = remove_empty_values(a_parsed)
        b_clean = remove_empty_values(b_parsed)
        return a_clean == b_clean

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
