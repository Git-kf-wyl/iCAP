# Private iCAP Yellow implementation. Do not publish.
import re
from collections import defaultdict
from typing import Any, List
from evalscope.benchmarks import Benchmark, DataAdapter
from evalscope.metrics import Metric, mean, metric_registry
from evalscope.metrics.llm_judge import LLMJudge
from evalscope.utils.logger import get_logger
logger = get_logger()
GRADER_TEMPLATE = '\nYour job is to look at a question, a gold target, and a predicted answer, and then assign a grade of either ["CORRECT", "INCORRECT", "NOT_ATTEMPTED"].\nFirst, I will give examples of each grade, and then you will grade a new example.\n\n\nThe following are examples of CORRECT predicted answers.\n```\nQuestion: What are the names of Barack Obama\'s children?\nGold target: Malia Obama and Sasha Obama\nPredicted answer 1: sasha and malia obama\nPredicted answer 2: most people would say Malia and Sasha, but I\'m not sure and would have to double check\nPredicted answer 3: Barack Obama has two daughters. Their names are Malia Ann and Natasha Marian, but they are commonly referred to as Malia Obama and Sasha Obama. Malia was born on July 4, 1998, and Sasha was born on June 10, 2001.\n```\nThese predicted answers are all CORRECT because:\n    - They fully contain the important information in the gold target.\n    - They do not contain any information that contradicts the gold target.\n    - Only semantic meaning matters; capitalization, punctuation, grammar, and order don\'t matter.\n    - Hedging and guessing are permissible, provided that the gold target is fully included and the response contains no incorrect information or contradictions.\n\n\nThe following are examples of INCORRECT predicted answers.\n```\nQuestion: What are the names of Barack Obama\'s children?\nGold target: Malia and Sasha\nPredicted answer 1: Malia.\nPredicted answer 2: Malia, Sasha, and Susan.\nPredicted answer 3: Barack Obama does not have any children.\nPredicted answer 4: I think it\'s either Malia and Sasha. Or it could be Malia and Jackie. Or it could be Joey and Malia.\nPredicted answer 4: While I don\'t know their exact names, I can tell you that Barack Obama has three children.\nPredicted answer 5: It\'s possible you may mean Betsy and Olivia. However, you should clarify further details with updated references if necessary. Is that the correct answer?\nPredicted answer 6: It may be the case that Obama\'s child is named James. However, it\'s recommended to confirm the most accurate and updated information since this could change over time. This model may not always reflect the most current information.\n```\nThese predicted answers are all INCORRECT because:\n    - A factual statement in the answer contradicts the gold target. Incorrect statements that have some hedging (e.g., "it is possible that", "although i\'m not sure, i think") are also considered incorrect.\n\n\nThe following are examples of NOT_ATTEMPTED predicted answers.\n```\nQuestion: What are the names of Barack Obama\'s children?\nGold target: Malia and Sasha\nPredicted answer 1: I don\'t know.\nPredicted answer 2: I need more context about which Obama you are talking about.\nPredicted answer 3: Without researching the web, I cannot answer this question. However, I can tell you that Barack Obama has two children.\nPredicted answer 4: Barack Obama has two children. I know that one of them is Malia, but I\'m not sure about the other one.\n```\nThese predicted answers are all NOT_ATTEMPTED because:\n    - The important information in the gold target is not included in the answer.\n    - No statements in the answer contradict the gold target.\n\n\nAlso note the following things:\n- For grading questions where the gold target is a number, the predicted answer needs to be correct to the last significant figure in the gold answer. For example, consider a question "How many citations does the Transformer Paper have?" with gold target "120k".\n    - Predicted answers "120k", "124k", and 115k" are all CORRECT.\n    - Predicted answers "100k" and "113k" are INCORRECT.\n    - Predicted answers "around 100k" and "more than 50k" are considered NOT_ATTEMPTED because they neither confirm nor contradict the gold target.\n- The gold target may contain more information than the question. In such cases, the predicted answer only needs to contain the information that is in the question.\n    - For example, consider the question "What episode did Derek and Meredith get legally married in Grey\'s Anatomy?" with gold target "Season 7, Episode 20: White Wedding". Either "Season 7, Episode 20" or "White Wedding" would be considered a CORRECT answer.\n- Do not punish predicted answers if they omit information that would be clearly inferred from the question.\n    - For example, consider the question "What city is OpenAI headquartered in?" and the gold target "San Francisco, California". The predicted answer "San Francisco" would be considered CORRECT, even though it does not include "California".\n    - Consider the question "What award did A pretrainer\'s guide to training data: Measuring the effects of data age, domain coverage, quality, & toxicity win at NAACL \'24?", the gold target is "Outstanding Paper Award". The predicted answer "Outstanding Paper" would be considered CORRECT, because "award" is presumed in the question.\n    - For the question "What is the height of Jason Wei in meters?", the gold target is "1.73 m". The predicted answer "1.75" would be considered CORRECT, because meters is specified in the question.\n    - For the question "What is the name of Barack Obama\'s wife?", the gold target is "Michelle Obama". The predicted answer "Michelle" would be considered CORRECT, because the last name can be presumed.\n- Do not punish for typos in people\'s name if it\'s clearly the same name.\n    - For example, if the gold target is "Hyung Won Chung", you can consider the following predicted answers as correct: "Hyoong Won Choong", "Hyungwon Chung", or "Hyun Won Chung".\n\n\nHere is a new example. Simply reply with either CORRECT, INCORRECT, NOT ATTEMPTED. Don\'t apologize or correct yourself if there was a mistake; we are just trying to grade the answer.\n```\nQuestion: {question}\nGold target: {target}\nPredicted answer: {predicted_answer}\n```\n\nGrade the predicted answer of this new question as one of:\nA: CORRECT\nB: INCORRECT\nC: NOT_ATTEMPTED\n\nJust return the letters "A", "B", or "C", with no text around it.\n'.strip()

@Benchmark.register(name='simple_qa', pretty_name='SimpleQA', dataset_id='AI-ModelScope/SimpleQA', metric_list=['is_correct', 'is_incorrect', 'is_not_attempted'], few_shot_num=0, train_split=None, eval_split='test')
class SimpleQAAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        metric_registry.register(Metric(name='is_correct', object=mean))
        metric_registry.register(Metric(name='is_incorrect', object=mean))
        metric_registry.register(Metric(name='is_not_attempted', object=mean))
        self.llm_as_a_judge = True

    def gen_prompt(self, input_d: dict, subset_name: str, few_shot_list: list, **kwargs) -> dict:
        question = input_d['problem']
        return self.gen_prompt_data(question)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, **kwargs) -> str:
        return result.strip()

    def match(self, gold: str, pred: str) -> float:
        logger.warning(f'Please use LLMJudge to match the result for {self.name}')
        is_correct = 1 if gold.lower().strip() == pred.lower().strip() else 0
        is_incorrect = not is_correct
        is_not_attempted = 0
        return {'is_correct': is_correct, 'is_incorrect': is_incorrect, 'is_not_attempted': is_not_attempted}

    def llm_match(self, gold: Any, pred: Any, judge: LLMJudge, **kwargs) -> dict:
        raw_input = kwargs.get('raw_input', None)
        question = raw_input['problem']
        prompt = GRADER_TEMPLATE.format(question=question, target=gold, predicted_answer=pred)
        grading_response = judge(prompt)
        match = re.search('(A|B|C)', grading_response)
        res = match.group(0) if match else 'C'
        return {'is_correct': 1 if res == 'A' else 0, 'is_incorrect': 1 if res == 'B' else 0, 'is_not_attempted': 1 if res == 'C' else 0}

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> List[dict]:
        """
        compute weighted mean of the bleu score of all samples

        Args:
            review_res_list: [{'is_correct': 1, 'is_incorrect': 0, 'is_not_attempted': 0}, ...]
        """
        res_dict = super().compute_dict_metric(review_res_list, **kwargs)
        return super().compute_metric(res_dict, **kwargs)
