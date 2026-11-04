# Private iCAP Yellow implementation. Do not publish.
import json
import ast
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import eval.benchmarks.om_release.utils as om_util
from eval.utils.logger import get_logger
logger = get_logger()

@Benchmark.register(name='om_mml_generate', pretty_name='OM', dataset_id='om_mml_generate', subset_list=['default'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class OMTaskConfGenerateAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        res_temp = []
        subset_list = kwargs['subset_list']
        excel_dict = om_util.ls_all_excel(input_file_path)
        for e_name, e_path in excel_dict.items():
            excel_data = om_util.read_from_mml_excel(e_path)
            if e_name == 'mml_generate_0918.xlsx':
                c_columns = ('序号', '模型输入', '正确答案', '判题规则')
                res_dict['default'] = om_util.repack_src_data_single_head(c_columns, excel_data)
        logger.info(f'load {len(res_dict)} subsets from {input_file_path}')
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        try:
            full_prompt = input_d['Question'].split("'messages': ", 1)[1] if input_d['Question'].startswith("{'") else input_d['Question'].split('"messages": ', 1)[1]
            full_prompt = full_prompt[:-1] if full_prompt[-1] == '}' else full_prompt[:-2]
            full_messages = ast.literal_eval(full_prompt)
            for msg in full_messages:
                if msg.get('role') == 'tool':
                    msg['role'] = 'user'
                    msg.pop('name', None)
                    msg.pop('tool_call_id', None)
        except Exception as e:
            full_messages = []
            logger.error(f'Error in json load: {e}')
        return self.gen_prompt_data('', messages=full_messages, system_prompt=None)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['Answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        try:
            start = result.find('```json\n')
            start_len = len('```json\n')
            end = result.rfind('\n```')
            mark_result = result[start + start_len:end].strip() if start != -1 and end != -1 else result
            parts = mark_result.split('\n\n')
            for part in parts:
                if part.find('extract_mml') != -1:
                    mark_result = part.strip()
            param_result = json.loads(mark_result)['arguments']['parameter_value']
        except Exception as e:
            param_result = result
            logger.error(f'Error in json loads err: {e}, pred: {param_result}')
        return param_result

    def match(self, gold: str, pred: str, raw_input_d: dict, subset_name: str) -> float:
        return om_util.HardCodedCheck().judge_answer_subjective(answer=pred, predict=gold, pattern=raw_input_d['Judge'])

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
