# Private iCAP Yellow implementation. Do not publish.
"""
Run evaluation for LLMs.
"""
import os
import shutil
from argparse import Namespace
from datetime import datetime
from typing import TYPE_CHECKING, List, Union
from eval.config import TaskConfig, parse_task_config
from eval.utils.io_utils import OutputsStructure
from eval.utils.logger import configure_logging, get_logger
if TYPE_CHECKING:
    pass
logger = get_logger()

def run_task(task_cfg: Union[str, dict, TaskConfig, List[TaskConfig], Namespace]) -> Union[dict, List[dict]]:
    """Run evaluation task(s) based on the provided configuration."""
    run_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    if isinstance(task_cfg, list):
        return [run_single_task(parse_task_config(cfg), run_time) for cfg in task_cfg]
    task_cfg = parse_task_config(task_cfg)
    return run_single_task(task_cfg, run_time)

def run_single_task(task_cfg: TaskConfig, run_time: str) -> dict:
    """Run a single evaluation task."""
    outputs = setup_work_directory(task_cfg, run_time)
    configure_logging(task_cfg.debug, os.path.join(outputs.logs_dir, 'eval_log.log'))
    result = evaluate_model(task_cfg, outputs)
    return result

def copy_folder(src, dst):
    if not os.path.exists(src):
        return
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        src_item = os.path.join(src, item)
        dst_item = os.path.join(dst, item)
        if os.path.isdir(src_item):
            copy_folder(src_item, dst_item)
        elif os.path.exists(dst_item):
            continue
        else:
            shutil.copy2(src_item, dst_item)
            print(f'复制文件: {dst_item}')

def setup_work_directory(task_cfg: TaskConfig, run_time: str):
    """Set the working directory for the task."""
    if task_cfg.use_cache:
        if not os.path.exists(os.path.join(task_cfg.use_cache, 'logs')):
            raise FileExistsError(f'从{task_cfg.use_cache}下读取数据，请确保路径下有logs目录.')
        logger.info(f'数据目录为{task_cfg.use_cache},将从此目录执行未完成的任务，先对目录进行备份...')
        if os.path.exists(task_cfg.use_cache + '_bak'):
            copy_folder(task_cfg.use_cache, task_cfg.use_cache + '_bak')
        else:
            shutil.copytree(task_cfg.use_cache, task_cfg.use_cache + '_bak')
        task_cfg.work_dir = task_cfg.use_cache
        logger.info(f'Set resume from {task_cfg.work_dir}')
    else:
        task_cfg.work_dir = os.path.join(task_cfg.work_dir, task_cfg.model, task_cfg.task_id)
    outputs = OutputsStructure(outputs_dir=task_cfg.work_dir)
    return outputs

def evaluate_model(task_cfg: TaskConfig, outputs: OutputsStructure) -> dict:
    """Evaluate the model based on the provided task configuration."""
    eval_results = {}
    evaluators = []
    for dataset_name in task_cfg.datasets:
        evaluator = create_evaluator(task_cfg, dataset_name, outputs)
        evaluators.append(evaluator)
    task_cfg.dump_yaml(outputs.configs_dir)
    logger.info(task_cfg)
    for evaluator in evaluators:
        try:
            res_dict = evaluator.eval()
            eval_results[evaluator.dataset_name] = res_dict
        except Exception as e:
            logger.error(f'此测评集执行失败：{e}')
    return eval_results

def create_evaluator(task_cfg: TaskConfig, dataset_name: str, outputs: OutputsStructure):
    """Create an evaluator object for the specified dataset."""
    from eval.benchmarks import Benchmark, BenchmarkMeta
    from eval.evaluator import Evaluator
    from eval.models import initialize_model_adapter
    benchmark: BenchmarkMeta = Benchmark.get(dataset_name)
    logger.error('initialize_model_adapter')
    model_pool = initialize_model_adapter(task_cfg, benchmark)
    logger.error('get_data_adapter')
    data_adapter = benchmark.get_data_adapter(config=task_cfg.dataset_args.get(dataset_name, {}))
    logger.error('dataset_args')
    task_cfg.dataset_args[dataset_name] = benchmark.to_string_dict()
    logger.error('return Evaluator')
    return Evaluator(data_adapter=data_adapter, model_pool=model_pool, outputs=outputs, task_cfg=task_cfg)
