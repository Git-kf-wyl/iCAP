# Private iCAP Yellow implementation. Do not publish.
import re
from evalscope.benchmarks import Benchmark, DataAdapter
from evalscope.utils.logger import get_logger
logger = get_logger()

@Benchmark.register(name='humaneval', pretty_name='HumanEval', dataset_id='modelscope/humaneval', subset_list=['openai_humaneval'], metric_list=['Pass@1'], few_shot_num=0, train_split=None, eval_split='test', prompt_template='Complete the following python code:\n{query}', extra_params={'num_workers': 4, 'timeout': 120})
class HumanevalAdapter(DataAdapter):
    """
    A placeholder for humaneval adapter, see HumanevalEvaluator for implementation.
    """

    def __init__(self, **kwargs):
        try:
            from human_eval.data import stream_jsonl, write_jsonl
            from human_eval.evaluation import check_correctness
        except ImportError:
            raise ImportError('Please install human_eval:https://github.com/openai/human-eval/tree/master#installation , Note that you need to enable the execution code in the human_eval/execution.py first.')
        super().__init__(**kwargs)
        extra_params = kwargs.get('extra_params', {})
        self.k = [1]
        self.num_workers = extra_params.get('num_workers', 4)
        self.timeout = extra_params.get('timeout', 120)
        self.read_problems_func = stream_jsonl
        self.write_jsonl_func = write_jsonl
        self.eval_func = check_correctness

    def load_from_disk(self, dataset_name_or_path, subset_list, work_dir, **kwargs) -> dict:
        data_dict = {}
        import os, glob
        for subset_name in subset_list:
            data_dict[subset_name] = {}
            files = glob.glob(os.path.join(dataset_name_or_path, '*'))
            data_dict[subset_name][self.eval_split] = [task for task in self.read_problems_func(files[0])]
        return data_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate prompt for the model.

        Args:
            input_d (dict): The raw input. A single data format of the Humaneval:
            {'task_id': '', 'prompt': '', 'entry_point': '', 'canonical_solution': '', 'test': ''}
        """
        query = input_d['prompt']
        full_prompt = self.prompt_template.format(query=query)
        return self.gen_prompt_data(full_prompt)

    @classmethod
    def _postprocess(cls, text: str) -> str:
        if '```' in text:
            blocks = re.findall('```(.*?)```', text, re.DOTALL)
            for block in blocks:
                text = block
                if not text.startswith('\n'):
                    text = text[max(text.find('\n') + 1, 0):]
                if text.strip().startswith('from') or text.strip().startswith('import'):
                    def_idx = text.find('def')
                    if def_idx != -1:
                        text = text[max(text.find('\n', def_idx) + 1, 0):]
                elif text.find('def') == -1:
                    continue
                if '"""' in text:
                    text = text.split('"""')[-1].strip('\n')
                text = text.split('\n\n\n')[0]
                if text.strip().startswith('def'):
                    text = '\n'.join(text.split('\n')[1:])
                if not text.startswith('    '):
                    if text.startswith(' '):
                        text = '    ' + text.lstrip()
                    else:
                        text = '\n'.join(['    ' + line for line in text.split('\n')])
                return text
        else:
            return ''

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        return self._postprocess(result)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d

    def match(self, gold: str, pred: str) -> float:
        if not pred:
            return float(False)
        res = self.eval_func(gold, pred, self.timeout)
        return float(res['passed'])
