# Private iCAP Yellow implementation. Do not publish.
import os
import re
from evalscope.benchmarks import Benchmark, DataAdapter
from evalscope.metrics import metric_registry
from evalscope.utils.logger import get_logger
from evalscope.metrics.llm_judge import LLMJudge
from typing import Any, List, Optional, Union
logger = get_logger()
SYSTEM_EXACT_ANSWER = 'Your response should be in the following format:\nExplanation: {your explanation for your final answer}\nExact Answer: {your succinct, final answer}\nConfidence: {your confidence score between 0% and 100% for your answer}'
SYSTEM_MC = 'Your response should be in the following format:\nExplanation: {your explanation for your answer choice}\nAnswer: {your chosen answer}\nConfidence: {your confidence score between 0% and 100% for your answer}'

@Benchmark.register(name='hle', pretty_name="Humanity's Last Exam", dataset_id='cais/hle', subset_list=['default'], metric_list=['Pass@1'], few_shot_num=0, train_split=None, eval_split='test', prompt_template='{query}')
class HLEAdapter(DataAdapter):
    """
    A placeholder for humaneval adapter, see HumanevalEvaluator for implementation.
    """

    def __init__(self, **kwargs):
        JUDGE_PROMPT = "Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.\n\n[question]: {question}\n\n[response]: {pred}\n\n[correct_answer]: {gold}\n\nYour judgment must focus only on if there are meaningful differences between [correct_answer] and the [response]. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match. Explain why the [response] is correct or incorrect based on [correct_answer] in one or two sentences. Finally, write your answer in the format 'GRADE: C' for correct answer or 'GRADE: I' for incorrect answer."
        os.environ['JUDGE_PROMPT_TEMPLATE'] = JUDGE_PROMPT
        super().__init__(llm_as_a_judge=True, **kwargs)

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate prompt for the model.

        Args:
            input_d (dict): The raw input. A single data format of the Humaneval:
            {'task_id': '', 'prompt': '', 'entry_point': '', 'canonical_solution': '', 'test': ''}
        """
        if input_d['image'] or input_d['rationale_image']:
            return None
        query = input_d['question']
        full_prompt = self.prompt_template.format(query=query)
        if input_d['answer_type'] == 'exactMatch':
            self.system_prompt = SYSTEM_EXACT_ANSWER
        else:
            self.system_prompt = SYSTEM_MC
        return self.gen_prompt_data(prompt=full_prompt, system_prompt=self.system_prompt)

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        return result

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['answer']

    def match(self, gold: str, pred: str) -> float:
        return gold == pred

    def compute_metric(self, review_res_list: Union[dict, list], **kwargs) -> List[dict]:
        import math
        if len(self.metric_list) == 0:
            raise ValueError('No metric list found for the benchmark.')
        res_list = []
        for metric_str in self.metric_list:
            metric = metric_registry.get(metric_str)
            metric_name = metric.name
            metric_func = metric.object
            if isinstance(review_res_list, dict):
                review_res = review_res_list.get(metric_name, [])
            else:
                review_res = review_res_list
            res_list.append({'metric_name': metric_name, 'score': metric_func(review_res), 'num': len(review_res), 'time': kwargs.get('time_difference')})
        return res_list

    @classmethod
    def _postprocess(cls, text: str) -> float:
        if text is None:
            return 0
        match = re.search('GRADE:\\s*([CI])', text, re.IGNORECASE)
        try:
            if match:
                return 1.0 if match.group(1) == 'C' else 0.0
            else:
                return 0
        except Exception as e:
            logger.error(f'{e}')
            return 0

    def llm_match(self, gold: Any, pred: Any, judge: [Optional[LLMJudge]]=None, **kwargs):
        """
        Use LLM as a judge to evaluate the predicted answer against the gold answer.

        Args:
            gold (Any): The golden answer.
            pred (Any): The predicted answer.

        Returns:
            The match result as a float score between 0 and 1.
        """
        if judge is None:
            logger.warning('No judge LLM provided, please specify a judge LLM in the config.')
            return 0
        raw_input = kwargs.get('raw_input', {})
        question_keys = ['question', 'prompt', 'query', 'problem']
        question = next((raw_input.get(key) for key in question_keys if raw_input.get(key)), None)
        score = 0
        for jd in judge:
            prompt = jd.build_prompt(pred, gold, question)
            s = jd(prompt)
            score += self._postprocess(s)
        return score / len(judge)
