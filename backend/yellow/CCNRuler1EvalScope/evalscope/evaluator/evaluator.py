# Private iCAP Yellow implementation. Do not publish.
import io
import json
import os
import sys
import time
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from tqdm import tqdm
from typing import Any, Dict, List, Optional, Union
from tabulate import tabulate
from datetime import datetime
from evalscope.benchmarks import DataAdapter
from evalscope.config import TaskConfig
from evalscope.constants import AnswerKeys, DumpMode, EvalStage, EvalType, JudgeStrategy, ReviewKeys
from evalscope.models import ModelPool
from evalscope.report import Report, gen_table, Subset, Category
from evalscope.utils import dict_torch_dtype_to_str, gen_hash
from evalscope.utils.io_utils import OutputsStructure, dump_jsonl_data, jsonl_to_list, del_jsonl_line
from evalscope.utils.logger import get_logger
from datetime import timedelta
logger = get_logger()

class Evaluator(object):
    """
    The evaluator for model on datasets.

    Args:
        dataset_name_or_path: str, the dataset name or path.
                if the dataset is a local path, e.g. /path/to/your_dataset_name,
                then the task name will be the basename of the path, which is `your_dataset_name`.
        data_adapter: DataAdapter, the data adapter for the dataset.
        model_adapter: BaseModelAdapter, the model adapter for the model.
        outputs: OutputsStructure, the outputs dir. Default: None
        task_cfg: TaskConfig, the overall task config. Default: None
        **kwargs: kwargs.
    """

    def __init__(self, data_adapter: DataAdapter, model_pool: ModelPool, outputs: OutputsStructure=None, task_cfg: TaskConfig=None, **kwargs):
        self.dataset_name = data_adapter.name
        self.dataset_name_or_path = os.path.expanduser(data_adapter.dataset_id)
        self.model_name = task_cfg.model_id
        self.custom_task_name = f'{self.model_name}_{self.dataset_name}'
        self.data_adapter = data_adapter
        self.model_pool = model_pool
        self.eval_type = task_cfg.eval_type
        self.dataset_hub = task_cfg.dataset_hub
        self.stage = task_cfg.stage
        self.use_cache = task_cfg.use_cache
        self.task_cfg = task_cfg
        self.outputs_structure = outputs
        self.kwargs = kwargs
        self._init_judge()

    def _init_judge(self):
        if self.task_cfg.judge_strategy == JudgeStrategy.RULE:
            self.judge = None
        else:
            self.judge = []
            from evalscope.metrics.llm_judge import LLMJudge
            if self.task_cfg.judge_model_args:
                for judge_model_args in self.task_cfg.judge_model_args:
                    self.judge.append(LLMJudge(**judge_model_args))

    def load_dataset(self):
        dataset = self.data_adapter.load(work_dir=os.path.expanduser(self.task_cfg.dataset_dir), datasets_hub=self.dataset_hub, **self.kwargs)
        prompts = self.data_adapter.gen_prompts(data_dict=dataset)
        limited_prompts = defaultdict(list)
        for subset_name, prompts_list in prompts.items():
            limit = self.task_cfg.limit or len(prompts_list)
            for index, prompt in enumerate(prompts_list[:limit]):
                prompt[AnswerKeys.INDEX] = index
                limited_prompts[subset_name].append(prompt)
        return limited_prompts

    def _generate_answer_id(self, model_cfg, input_d, infer_cfg):
        model_cfg_str = json.dumps(OrderedDict(sorted(dict_torch_dtype_to_str(model_cfg).items())), ensure_ascii=False)
        input_prompt_str = json.dumps(OrderedDict(sorted(dict_torch_dtype_to_str(input_d).items())), ensure_ascii=False)
        infer_cfg_str = json.dumps(OrderedDict(sorted(dict_torch_dtype_to_str(infer_cfg).items())), ensure_ascii=False)
        return 'answer-' + gen_hash(model_cfg_str + input_prompt_str + infer_cfg_str)

    def _process_answer(self, answer_d, input_d, subset_name, answer_id, model):
        answer_d[AnswerKeys.MODEL_SPEC] = model.model_cfg
        answer_d[AnswerKeys.ANSWER_ID] = answer_id
        answer_d[AnswerKeys.SUBSET_NAME] = subset_name
        answer_d[AnswerKeys.RAW_INPUT] = input_d[AnswerKeys.RAW_INPUT]
        answer_d[AnswerKeys.INDEX] = input_d[AnswerKeys.INDEX]
        return answer_d

    def _get_answer(self, input_prompts, subset_name, infer_cfg, **kwargs) -> List[dict]:
        answers_list = []
        model = self.model_pool.get_model()
        kwargs['model_pool'] = self.model_pool
        kwargs['model'] = model
        try:
            answer_ds: List[dict] = model.predict(inputs=input_prompts, infer_cfg=infer_cfg, **kwargs)
            for answer_d, input_prompt in zip(answer_ds, input_prompts):
                answer_id = self._generate_answer_id(model.model_cfg, input_prompt, infer_cfg)
                processed_answer = self._process_answer(answer_d, input_prompt, subset_name, answer_id, model)
                answers_list.append(processed_answer)
            return answers_list
        finally:
            self.model_pool.release_model(model)

    @staticmethod
    def filter_answer(use_cache, prompts_list, pred_file_path, retry_content_none, request_nums):
        answers_list = []
        need_reties = []
        if not use_cache or not os.path.exists(pred_file_path):
            return (answers_list, prompts_list, need_reties)

        def get_answered_indices(answers_list: List[Dict]) -> List[int]:
            indices = [answer.get(AnswerKeys.INDEX) for answer in answers_list]
            if all((index is None for index in indices)):
                return list(range(len(answers_list)))
            return [index for index in indices if index is not None]
        answers_list = jsonl_to_list(pred_file_path)
        if retry_content_none:
            i = 0
            index_list = []
            while i < len(answers_list):
                if len(answers_list[i]['choices']) < request_nums:
                    need_reties.append(answers_list[i])
                    index_list.append(answers_list[i]['index'])
                    del answers_list[i]
                    continue
                for choice in answers_list[i]['choices']:
                    if choice['message']['content'] == '' or choice['message']['content'] is None:
                        need_reties.append(answers_list[i])
                        index_list.append(answers_list[i]['index'])
                        del answers_list[i]
                        i -= 1
                        break
                i += 1
            del_jsonl_line(pred_file_path, index_list)
        answered_indices = set(get_answered_indices(answers_list))
        logger.info(f'Reusing predictions from {pred_file_path}, got {len(answered_indices)} answers.')
        prompts = [prompt for i, prompt in enumerate(prompts_list) if i not in answered_indices]
        return (answers_list, prompts, need_reties)

    def get_answers(self, subset_name: str, prompts_list: List[dict], infer_cfg: dict=None, **kwargs) -> list:
        """
        Get answers from model inference.
        It is required to rewrite this method to support your own evaluator.

        Args:
            subset_name: subset name for benchmark.
            prompts_list: prompts list.
            infer_cfg: model inference config.
                Attributes:
                    do_sample: bool, whether to use sampling.
                    top_k: int, the number of highest probability vocabulary tokens to keep for top-k-filtering.
                    top_p: float, if set to float < 1, only the most probable tokens with probabilities to add.
                    temperature: float, the value used to module the next token probabilities.
                    num_beams: int, number of beams for beam search. 1 means no beam search.
                    max_length: int, the max length of the sequence to be generated.
                    max_new_tokens: int, the max number of new tokens to be generated.
                    repetition_penalty: float, the parameter for repetition penalty. 1.0 means no penalty.
            **kwargs: kwargs.

        Returns: The list of answers.
        """
        assert self.data_adapter is not None, 'data_adapter must be provided when calling func get_answers() !'
        assert len(prompts_list) > 0, 'prompts_list must not be empty when calling func get_answers() !'
        pred_file_name = self.dataset_name + '_' + subset_name + '.jsonl'
        pred_file_path = os.path.join(self.outputs_structure.predictions_dir, self.model_name, pred_file_name)
        os.makedirs(os.path.dirname(pred_file_path), exist_ok=True)
        request_nums = self.task_cfg.generation_config['request_nums'] if 'request_nums' in self.task_cfg.generation_config else 1
        answers_list, prompts_list, need_reties = Evaluator.filter_answer(self.use_cache, prompts_list, pred_file_path, self.task_cfg.retry_content_none, request_nums)
        answers = []
        eval_batch_size = self.task_cfg.eval_batch_size
        logger.info(f'Predicting({subset_name}):   0%|          | 0/{len(prompts_list)} [00:00<?, ?it/s]')
        if self.task_cfg.eval_type == EvalType.SERVICE:
            with tqdm(total=len(prompts_list), desc=f'Predicting({subset_name}): ', mininterval=20.0, maxinterval=50.0) as pbar:
                with ThreadPoolExecutor(max_workers=eval_batch_size * self.model_pool.size()) as executor:
                    futures = []
                    for input_prompt in prompts_list:
                        futures.append(executor.submit(self._get_answer, [input_prompt], subset_name, infer_cfg, **kwargs))
                    for future in as_completed(futures):
                        try:
                            answer_ds: List[dict] = future.result()
                            answers.extend(answer_ds)
                            dump_jsonl_data(answer_ds, pred_file_path, dump_mode=DumpMode.APPEND)
                            pbar.update(1)
                            logger.info(pbar)
                        except Exception as e:
                            logger.error(f'此题请求失败，即将请求下一题：{e}')
        else:
            batch_prompts_list = [prompts_list[i:i + eval_batch_size * self.model_pool.size()] for i in range(0, len(prompts_list), eval_batch_size * self.model_pool.size())]
            with tqdm(total=len(prompts_list), desc=f'Predicting else ({subset_name}): ', maxinterval=20.0) as pbar:
                for batch_prompts in batch_prompts_list:
                    try:
                        answer_ds: List[dict] = self._get_answer(input_prompts=batch_prompts, subset_name=subset_name, infer_cfg=infer_cfg)
                        answers.extend(answer_ds)
                        dump_jsonl_data(answer_ds, pred_file_path, dump_mode=DumpMode.APPEND)
                        pbar.update(1)
                        logger.info(pbar)
                    except Exception as e:
                        logger.error(f'此题请求失败，即将请求下一题：{e}')
        new_answers = self.merge_answer(answers, need_reties, request_nums)
        answers_list.extend(new_answers)
        if need_reties:
            dump_jsonl_data(answers_list, pred_file_path, dump_mode=DumpMode.OVERWRITE)
        logger.info(f'Dump predictions to {pred_file_path}.')
        return answers_list

    def _get_review(self, answer_d: dict, review_id: str=None, reviewer_spec: dict=None) -> dict:
        if reviewer_spec is None:
            reviewer_spec = {}
        review_res = deepcopy(answer_d)
        choices = review_res[AnswerKeys.CHOICES]
        if len(choices) == 0:
            review_res[ReviewKeys.REVIEWED] = False
            review_res[ReviewKeys.REVIEW_ID] = None
            review_res[ReviewKeys.REVIEWER_SPEC] = reviewer_spec
            review_res[ReviewKeys.REVIEW_TIME] = time.time()
            return review_res
        rev_choices = []
        for choice in choices:
            raw_input_d: dict = review_res[AnswerKeys.RAW_INPUT]
            answer_content = choice[ReviewKeys.MESSAGE][ReviewKeys.CONTENT]
            if isinstance(answer_content, str):
                think_index = answer_content.find('</think>')
                answer_content = answer_content.split('</think>', 1)[1].strip() if think_index != -1 else answer_content
            gold_content = self.data_adapter.get_gold_answer(raw_input_d)
            use_llm = self.task_cfg.judge_strategy == JudgeStrategy.LLM or (self.task_cfg.judge_strategy == JudgeStrategy.AUTO and self.data_adapter.llm_as_a_judge)
            if use_llm:
                assert self.judge is not None, f'Judge model is required for LLM judging {self.data_adapter.name}'
                review_result = self.data_adapter.llm_match(gold_content, answer_content, self.judge, raw_input=raw_input_d)
                pred = answer_content
            else:
                pred_content = self.data_adapter.parse_pred_result(result=answer_content, raw_input_d=raw_input_d, eval_type=self.eval_type)
                review_result = self.data_adapter.match(gold_content, pred_content)
                if self.task_cfg.judge_strategy == JudgeStrategy.LLM_RECALL and isinstance(review_result, (bool, int, float)) and (not bool(review_result)):
                    assert self.judge is not None, f'Judge model is required for LLM_RECALL strategy {self.data_adapter.name}'
                    review_result = self.data_adapter.llm_match(gold_content, answer_content, self.judge, raw_input=raw_input_d)
                    pred = answer_content
                else:
                    pred = pred_content
            choice[ReviewKeys.REVIEW] = {ReviewKeys.GOLD: gold_content if gold_content != raw_input_d else '*Same as Input*', ReviewKeys.PRED: pred, ReviewKeys.RESULT: review_result}
            rev_choices.append(choice)
        review_res[AnswerKeys.CHOICES] = rev_choices
        review_res[ReviewKeys.REVIEWED] = True
        review_res[ReviewKeys.REVIEW_ID] = review_id
        review_res[ReviewKeys.REVIEWER_SPEC] = reviewer_spec
        review_res[ReviewKeys.REVIEW_TIME] = time.time()
        return review_res

    def _generate_review_id(self, answer_d):
        answer_id = answer_d[AnswerKeys.ANSWER_ID]
        reviewer_spec = {'metric': self.data_adapter.metric_list, 'reviewer': ['Evaluator'], 'revision': ['default']}
        reviewer_spec_str = json.dumps(OrderedDict(sorted(dict_torch_dtype_to_str(reviewer_spec).items())), ensure_ascii=False)
        review_id = 'review-' + gen_hash(answer_id + reviewer_spec_str)
        return (review_id, reviewer_spec)

    def get_reviews(self, subset_name: str, answers_list: List[dict], **kwargs) -> list:
        """
        Get reviews from answers.
        It is required to rewrite this method to support your own evaluator.

        Args:
            subset_name: subset name of benchmark
            answers_list: inference results list.
            **kwargs: kwargs.

        Returns: reviews list.
        """
        reviews_list = []
        review_file_name = self.dataset_name + '_' + subset_name + '.jsonl'
        review_file_path = os.path.join(self.outputs_structure.reviews_dir, self.model_name, review_file_name)
        os.makedirs(os.path.dirname(review_file_path), exist_ok=True)
        if self.use_cache and os.path.exists(review_file_path):
            logger.info(f'Updating the review file: {review_file_path} ...')
            os.remove(review_file_path)

        def process_single_review(answer_d):
            review_id, reviewer_spec = self._generate_review_id(answer_d)
            review_d = self._get_review(answer_d=answer_d, review_id=review_id, reviewer_spec=reviewer_spec)
            return review_d
        with ThreadPoolExecutor(max_workers=self.task_cfg.judge_worker_num) as executor:
            futures = [executor.submit(process_single_review, answer_d) for answer_d in answers_list]
            futures_len = len(futures)
            logger.info(f'Reviewing({subset_name}):   0%|          | 0/{futures_len} [00:00<?, ?it/s]')
            try:
                with tqdm(total=futures_len, desc=f'Reviewing({subset_name}): ', mininterval=20.0, maxinterval=50.0) as pbar:
                    logger_step = max(futures_len // 10, 1)
                    completed_count = 0
                    for future in as_completed(futures):
                        review_d = future.result()
                        reviews_list.append(review_d)
                        dump_jsonl_data(review_d, review_file_path, dump_mode=DumpMode.APPEND)
                        pbar.update(1)
                        completed_count += 1
                        if completed_count % logger_step == 0:
                            logger.info(str(pbar))
            except Exception as e:
                logger.error(f'Reviewing error: {e}')
            logger.info('Reviewing end')
        return reviews_list

    def compute_metrics(self, reviews_list: List[dict], **kwargs) -> List[dict]:
        """
        To compute metrics from reviews_list for each subset.
        It is required to rewrite this method to support your own evaluator.

        Args:
            reviews_list: reviews list.

        Returns:
            The metric result. Depends on the metric function in data_adapter.
        """
        logger.info('compute_metrics start')
        choices_lengths = [len(review_d[AnswerKeys.CHOICES]) for review_d in reviews_list if review_d.get(ReviewKeys.REVIEWED)]
        if choices_lengths:
            max_choices = max(choices_lengths)
        else:
            max_choices = 0
        review_res_list = []
        metric_score = []
        for review_d in reviews_list:
            if not review_d[ReviewKeys.REVIEWED]:
                logger.warning(f'Review not finished for answer_id: {review_d[AnswerKeys.ANSWER_ID]}')
                continue
            if len(review_d[AnswerKeys.CHOICES]) == 0:
                logger.warning(f'No choices found for answer_id: {review_d[AnswerKeys.ANSWER_ID]}')
                continue
            elif len(review_d[AnswerKeys.CHOICES]) == 1 and max_choices == 1:
                review_res = review_d[AnswerKeys.CHOICES][0][ReviewKeys.REVIEW][ReviewKeys.RESULT]
            else:
                review_res = [choice[ReviewKeys.REVIEW][ReviewKeys.RESULT] for choice in review_d[AnswerKeys.CHOICES]]
                if len(review_d[AnswerKeys.CHOICES]) < max_choices:
                    logger.warning(f'Less choices found for answer_id: {review_d[AnswerKeys.ANSWER_ID]}, max_choices is {max_choices}, but only {len(review_d[AnswerKeys.CHOICES])} choices found')
            review_res_list.append(review_res)
        logger.info('compute_metrics enter')
        metric_score: List[dict] = self.data_adapter.compute_metric(review_res_list=review_res_list, reviews_list=reviews_list, time_difference=kwargs.get('time_difference'))
        return metric_score

    def dump_report(self, reviews_score_all: List[dict], use_table: bool=True):
        """
        Get report for total reviews of specific dataset.
        It is required to rewrite this method to support your own evaluator.

        Args:
            reviews_score_all: reviews score list. Generated by func self.data_adapter.compute_metric().
            use_table: whether to generate table for reports. Default to True.

        Returns: None
        """
        report_map: Report = self.data_adapter.gen_report(subset_score_map=reviews_score_all, report_name=self.custom_task_name, model_name=self.model_name, dataset_name=self.dataset_name)
        report_path: str = os.path.join(self.outputs_structure.reports_dir, self.model_name, self.dataset_name + '.json')
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        all_time = '00:00:00'
        for report in report_map.metrics:
            is_all_score = False
            for category in report.categories:
                if len(category.subsets) > 1 or len(report.categories) > 1:
                    is_all_score = True
                    for subset in category.subsets:
                        all_time = self.sum_time(subset.time, all_time)
            if is_all_score:
                if len(report.categories) == 1:
                    name = report.categories[0].name[0]
                else:
                    name = '-'
                report.categories.append(Category(name=(name,), score=report.score, num=report.num, macro_score=report.macro_score, subsets=[Subset(name='OVERALL', score=report.score, num=report.num, time=all_time)]))
        with open(report_path, 'w') as f:
            f.write(json.dumps(report_map.to_dict(), ensure_ascii=False, indent=4))
        logger.info(f'Dump report: {report_path} \n')
        if use_table:
            try:
                report_table: str = gen_table([self.outputs_structure.reports_dir])
                logger.info(f'Report table: \n{report_table} \n')
            except Exception:
                logger.error('Failed to generate report table.')
        return report_map

    def get_unfinished(self, pred_file_path, subset_name):
        """
        查询模型输出的content内容为空的数据

        Args:
            pred_file_path: 输出的结果文件路径
            subset_name: 子测评集名称

        Returns:
            [模型名称，数据集名称，子集名称，content为空的索引值，所有content为空的数量]

        Author: w60034501
        Date: 2025-05
        """
        answers_list = jsonl_to_list(pred_file_path)
        i = 0
        unfinished_count = 0
        index_list = []
        while i < len(answers_list):
            unfinished_sub_count = 0
            for choice in answers_list[i]['choices']:
                if choice['message']['content'] == '' or choice['message']['content'] is None:
                    unfinished_sub_count += 1
                    unfinished_count += 1
            if unfinished_sub_count > 0:
                index_list.append(str(answers_list[i]['index']))
            i += 1
        unfinished = [self.model_name, self.dataset_name, subset_name, ','.join(index_list), unfinished_count]
        return unfinished

    def dump_unfinished(self):
        """
        输出content为空的数据

        Author: w60034501
        Date: 2025-05
        """
        unf_file_name = self.model_name + '_unfinished.jsonl'
        unf_file_path = os.path.join(self.outputs_structure.predictions_dir, unf_file_name)
        unf_list = jsonl_to_list(unf_file_path)
        output = tabulate([v for ls in unf_list for k, v in ls.items()], headers=('Model', 'Dataset', 'Subset', 'Fail_Ids', 'Num'), maxcolwidths=[None, None, None, None, None], tablefmt='grid')
        logger.info(f'Unfinished table: \n{output} \n')

    def save_unfinished(self, unfinished_dict):
        """
        保存content内容为空的数据到文件

        Args:
            unfinished_dict: [模型名称，数据集名称，子集名称，content为空的索引值，所有content为空的数量]

        Author: w60034501
        Date: 2025-05
        """
        unf_file_name = self.model_name + '_unfinished.jsonl'
        unf_file_path = os.path.join(self.outputs_structure.predictions_dir, unf_file_name)
        os.makedirs(os.path.dirname(unf_file_path), exist_ok=True)
        if os.path.exists(unf_file_path):
            unf_list = jsonl_to_list(unf_file_path)
            temp = {**unfinished_dict}
            for unf in unf_list:
                for k, v in temp.items():
                    if k in unf:
                        unf[k] = v
                        unfinished_dict.pop(k)
            if unfinished_dict:
                unf_list.append(unfinished_dict)
            os.remove(unf_file_path)
            dump_jsonl_data(unf_list, unf_file_path, dump_mode=DumpMode.APPEND)
        else:
            dump_jsonl_data(unfinished_dict, unf_file_path, dump_mode=DumpMode.APPEND)

    def merge_answer(self, new_answer_list, answer_list, request_nums):
        """
        合并断点续测时重新跑的新数据和老数据

        Args:
            new_answer_list: 新跑的数据
            answer_list: 需要重跑的数据
            request_nums: 请求并发数

        Author: w60034501
        Date: 2025-05
        """
        for answer in new_answer_list:
            need_tmp = []
            for new_answer in answer_list:
                if answer['index'] == new_answer['index']:
                    answer['choices'].extend(new_answer['choices'])
            i = 0
            while i < len(answer['choices']):
                if i >= request_nums:
                    del answer['choices'][i]
                elif answer['choices'][i]['message']['content'] is None or answer['choices'][i]['message']['content'] == '':
                    need_tmp.append(answer['choices'][i])
                    del answer['choices'][i]
                else:
                    i += 1
            if len(answer['choices']) < request_nums:
                answer['choices'].extend(need_tmp[:request_nums - len(answer['choices'])])
        return new_answer_list

    def format_time(self, seconds):
        """
        将秒数格式化为 HH:MM:SS 的形式
        Args:
             seconds: 总秒数
        Returns:
            格式化后的时间字符串

        Author: w60034501
        Date: 2025-05
        """
        hours = seconds // 3600
        minutes = seconds % 3600 // 60
        seconds = seconds % 60
        return f'{int(hours):02}:{int(minutes):02}:{int(seconds):02}'

    def sum_time(self, time1, time2):
        """
        两个时间相加

        Returns：
            time1 + time2

        Author: w60034501
        Date: 2025-05
        """
        h1, m1, s1 = map(int, time1.split(':'))
        h2, m2, s2 = map(int, time2.split(':'))
        total_seconds = h1 * 3600 + m1 * 60 + s1 + (h2 * 3600 + m2 * 60 + s2)
        return self.format_time(total_seconds)

    def eval(self, **kwargs) -> dict:
        """
        Evaluate the model on the specific benchmark. Streaming & parallel mode is supported.
        It is required to rewrite this method to support your own evaluator.

        The evaluation process is as follows:
            1. Get the input samples from the dataset (benchmarks on the ModelScope or HuggingFace).
            2. Get the input prompts from dataset with specific data adapter.
            3. Get answers with model inference.
            4. Get reviews with metric function (or reviewers).
            5. Generate report from review results.

        Args:
            infer_cfg: The config for model inference.

        Returns:
            Dict of results. Depends on the stage of evaluation.

            stage == 'all': return the report_map
            stage == 'infer': return the answers_map
            stage == 'review': return the reviews_map
        """
        logger.info(f'**** Start evaluating on dataset {self.dataset_name_or_path} ****')
        reviews_score_all = {}
        stage_answers_dict = {}
        stage_reviews_dict = {}
        unfinished_dict = {}
        prompts = self.load_dataset()
        for subset_name, prompts_list in prompts.items():
            start_time = time.time()
            kwargs['data_adapter'] = self.data_adapter
            kwargs['task_config'] = self.task_cfg
            answers_list: list = self.get_answers(subset_name=subset_name, prompts_list=prompts_list, infer_cfg=self.task_cfg.generation_config, **kwargs)
            if self.stage == EvalStage.INFER:
                stage_answers_dict[subset_name] = answers_list
                continue
            reviews_list: list = self.get_reviews(subset_name=subset_name, answers_list=answers_list, **kwargs)
            end_time = time.time()
            try:
                metric_res = self.compute_metrics(reviews_list=reviews_list, time_difference=self.format_time(end_time - start_time))
            except Exception as e:
                logger.error(f'Compute metrics error: {e}')
            reviews_score_all[subset_name] = metric_res
            stage_reviews_dict[subset_name] = reviews_list
            pred_file_name = self.dataset_name + '_' + subset_name + '.jsonl'
            pred_file_path = os.path.join(self.outputs_structure.predictions_dir, self.model_name, pred_file_name)
            sub_pred = self.get_unfinished(pred_file_path, subset_name)
            unfinished_dict[self.dataset_name + '_' + subset_name] = sub_pred
        self.save_unfinished(unfinished_dict)
        if self.stage == EvalStage.INFER:
            return stage_answers_dict
        if self.stage == EvalStage.REVIEW:
            return stage_reviews_dict
        logger.info('start dump_report')
        report_map = self.dump_report(reviews_score_all)
        logger.info(f'**** Evaluation finished on {self.dataset_name_or_path} ****\n')
        return report_map
