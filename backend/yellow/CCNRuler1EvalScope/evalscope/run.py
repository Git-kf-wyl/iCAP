# Private iCAP Yellow implementation. Do not publish.
"""
Run evaluation for LLMs.
"""
import os
import shutil
from argparse import Namespace
from datetime import datetime
from typing import TYPE_CHECKING, List, Union
import threading
from evalscope.config import TaskConfig, parse_task_config
from evalscope.constants import DataCollection, EvalBackend
from evalscope.utils import seed_everything
from evalscope.utils.io_utils import OutputsStructure
from evalscope.utils.logger import configure_logging, get_logger
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
    if task_cfg.seed is not None:
        seed_everything(task_cfg.seed)
    outputs = setup_work_directory(task_cfg, run_time)
    configure_logging(task_cfg.debug, os.path.join(outputs.logs_dir, 'eval_log.log'))
    logger.info('configure_logging !!')
    if task_cfg.eval_backend != EvalBackend.NATIVE:
        result = run_non_native_backend(task_cfg, outputs)
    else:
        result = evaluate_model(task_cfg, outputs)
    return result
'\n    备份文件夹，每次备份只备份新增文件，已经存在的文件不覆盖\n    \n    Args:\n        src: 源目录\n        det：目标目录\n    \n    Author: 60034501\n    Date: 2025-05\n'

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
            logger.info(f'复制文件: {dst_item}')

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
    elif task_cfg.eval_backend != EvalBackend.NATIVE:
        print(task_cfg.work_dir)
        print(task_cfg.task_id)
        print('_'.join(task_cfg.eval_config['model_name'].split('/')))
        task_cfg.work_dir = os.path.join(task_cfg.work_dir, '_'.join(task_cfg.eval_config['model_name'].split('/')), task_cfg.task_id)
    else:
        task_cfg.work_dir = os.path.join(task_cfg.work_dir, task_cfg.model, task_cfg.task_id)
    outputs = OutputsStructure(outputs_dir=task_cfg.work_dir)
    if task_cfg.eval_backend == EvalBackend.OPEN_COMPASS:
        task_cfg.eval_config['time_str'] = run_time
    elif task_cfg.eval_backend == EvalBackend.VLM_EVAL_KIT:
        task_cfg.eval_config['work_dir'] = task_cfg.work_dir
    elif task_cfg.eval_backend == EvalBackend.RAG_EVAL:
        from evalscope.backend.rag_eval import Tools
        if task_cfg.eval_config['tool'].lower() == Tools.MTEB:
            task_cfg.eval_config['eval']['output_folder'] = task_cfg.work_dir
        elif task_cfg.eval_config['tool'].lower() == Tools.CLIP_BENCHMARK:
            task_cfg.eval_config['eval']['output_dir'] = task_cfg.work_dir
    elif task_cfg.eval_backend == EvalBackend.THIRD_PARTY:
        task_cfg.eval_config['outputs'] = task_cfg.work_dir
    return outputs

def run_non_native_backend(task_cfg: TaskConfig, outputs: OutputsStructure) -> dict:
    """Run evaluation using a non-native backend."""
    eval_backend = task_cfg.eval_backend
    eval_config = task_cfg.eval_config
    if eval_config is None:
        logger.warning(f'Got eval_backend {eval_backend}, but eval_config is not provided.')
    backend_manager_class = get_backend_manager_class(eval_backend)
    backend_manager = backend_manager_class(config=eval_config)
    task_cfg.dump_yaml(outputs.configs_dir)
    logger.info(task_cfg)
    backend_manager.run()
    return dict()

def get_backend_manager_class(eval_backend: EvalBackend):
    """Get the backend manager class based on the evaluation backend."""
    if eval_backend == EvalBackend.OPEN_COMPASS:
        from evalscope.backend.opencompass import OpenCompassBackendManager
        return OpenCompassBackendManager
    elif eval_backend == EvalBackend.VLM_EVAL_KIT:
        from evalscope.backend.vlm_eval_kit import VLMEvalKitBackendManager
        return VLMEvalKitBackendManager
    elif eval_backend == EvalBackend.RAG_EVAL:
        from evalscope.backend.rag_eval import RAGEvalBackendManager
        return RAGEvalBackendManager
    raise NotImplementedError(f'Not implemented for evaluation backend {eval_backend}')

def evaluate_model(task_cfg: TaskConfig, outputs: OutputsStructure) -> dict:
    """Evaluate the model based on the provided task configuration."""

    logger.info('enter evaluate')
    eval_results = {}
    base_model = None
    evaluators = []
    try:
        for dataset_name in task_cfg.datasets:
            evaluator = create_evaluator(task_cfg, dataset_name, outputs, base_model)
            evaluators.append(evaluator)
    except Exception as e:
        logger.info(e)
    task_cfg.dump_yaml(outputs.configs_dir)
    logger.info(task_cfg)
    for evaluator in evaluators:
        try:
            res_dict = evaluator.eval()
            eval_results[evaluator.dataset_name] = res_dict
        except Exception as e:
            logger.error(f'此测评集执行失败：{e}')
    if base_model is not None:
        import gc
        import torch
        del base_model
        del evaluators
        torch.cuda.empty_cache()
        gc.collect()
    return eval_results

def create_evaluator(task_cfg: TaskConfig, dataset_name: str, outputs: OutputsStructure, base_model: 'LocalModel'):
    """Create an evaluator object for the specified dataset."""
    from evalscope.benchmarks import Benchmark, BenchmarkMeta
    from evalscope.evaluator import Evaluator
    from evalscope.models import initialize_model_adapter
    benchmark: BenchmarkMeta = Benchmark.get(dataset_name)
    if dataset_name == DataCollection.NAME:
        from evalscope.collections import EvaluatorCollection
        data_adapter = benchmark.get_data_adapter(config=task_cfg.dataset_args.get(dataset_name, {}))
        return EvaluatorCollection(task_cfg, data_adapter, outputs, base_model)
    model_pool = initialize_model_adapter(task_cfg, benchmark, base_model)
    data_adapter = benchmark.get_data_adapter(config=task_cfg.dataset_args.get(dataset_name, {}))
    task_cfg.dataset_args[dataset_name] = benchmark.to_string_dict()
    return Evaluator(data_adapter=data_adapter, model_pool=model_pool, outputs=outputs, task_cfg=task_cfg)

def main():
    from evalscope.arguments import parse_args
    args = parse_args()
    run_task(args)
if __name__ == '__main__':
    main()
