# Private iCAP Yellow implementation. Do not publish.
from evalscope.benchmarks import Benchmark, DataAdapter
from evalscope.constants import OutputType
from evalscope.metrics.math_parser import extract_answer, math_equal, strip_answer_string
from evalscope.utils.logger import get_logger
import os
from evalscope.utils.io_utils import jsonl_to_list
logger = get_logger()

@Benchmark.register(name='aime25', pretty_name='AIME-2025', dataset_id='opencompass/AIME2025', subset_list=['AIME2025-I', 'AIME2025-II'], metric_list=['AveragePass@1'], few_shot_num=0, train_split=None, eval_split='test', prompt_template='{query}\nPlease reason step by step, and put your final answer within \\boxed{{}}.')
class AIME25Adapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load_from_disk(self, dataset_name_or_path, subset_list, work_dir, **kwargs) -> dict:
        data_dict = {}
        for subset in subset_list:
            data_dict[subset] = {}
            file_path = os.path.join(dataset_name_or_path, subset + '.jsonl')
            data_dict[subset][self.eval_split] = jsonl_to_list(file_path)
        return data_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = input_d['question']
        full_prompt = self.prompt_template.format(query=problem)
        return self.gen_prompt_data(full_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return strip_answer_string(input_d['answer'])

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        result = strip_answer_string(extract_answer(result))
        return result

    def match(self, gold: str, pred: str) -> float:
        return math_equal(pred, gold)
