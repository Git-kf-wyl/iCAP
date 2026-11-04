# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import eval.benchmarks.om_release.utils as om_util

@Benchmark.register(name='om_new_scene', pretty_name='OM', dataset_id='om_new_scene', subset_list=['default'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class OMTaskNewSceneAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        res_temp = []
        subset_list = kwargs['subset_list']
        excel_dict = om_util.ls_all_excel(input_file_path)
        for e_name, e_path in excel_dict.items():
            excel_data = om_util.read_from_excel(e_path)
            if e_name == '摸高评测-V0.9_输出结果优化.xlsx':
                c_columns = ('编号', 'Updated Question', 'Updated Answer', 'Judge_answer_subjective')
                res_dict['default'] = om_util.repack_src_data(c_columns, excel_data)
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        full_prompt = input_d['Question']
        return self.gen_prompt_data(full_prompt, system_prompt=None)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['Answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: dict, subset_name: str) -> float:
        return om_util.HardCodedCheck().judge_answer_subjective(answer=pred, predict=gold, pattern=raw_input_d['Judge'])

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
