# Private iCAP Yellow implementation. Do not publish.
import copy
import json
import os
from argparse import Namespace
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
from eval.constants import DEFAULT_DATASET_CACHE_DIR, DEFAULT_WORK_DIR, EvalBackend, EvalStage, EvalType, HubType, JudgeStrategy, OutputType
from eval.utils import gen_hash
from eval.utils.io_utils import dict_to_yaml, json_to_dict
from eval.utils.logger import get_logger
logger = get_logger()
cur_path = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_ARGS = {'revision': 'master', 'precision': 'torch.float16'}
DEFAULT_GENERATION_CONFIG = {'max_length': 2048, 'max_new_tokens': 512, 'do_sample': False, 'top_k': 50, 'top_p': 1.0, 'temperature': 1.0}

@dataclass
class TaskConfig:
    model: Union[str, None] = None
    models: Union[List[dict], None] = None
    model_id: Optional[str] = None
    model_args: Optional[Dict] = field(default_factory=lambda: DEFAULT_MODEL_ARGS | {})
    template_type: Optional[str] = None
    chat_template: Optional[str] = None
    datasets: List[str] = field(default_factory=list)
    dataset_args: Dict = field(default_factory=dict)
    dataset_dir: str = DEFAULT_DATASET_CACHE_DIR
    dataset_hub: str = HubType.MODELSCOPE
    generation_config: Optional[Dict] = field(default_factory=lambda: DEFAULT_GENERATION_CONFIG | {})
    eval_type: str = EvalType.CHECKPOINT
    eval_backend: str = EvalBackend.NATIVE
    eval_config: Union[str, Dict, None] = None
    stage: str = EvalStage.ALL
    limit: Optional[int] = None
    eval_batch_size: Optional[int] = None
    mem_cache: bool = False
    use_cache: Optional[str] = None
    work_dir: str = DEFAULT_WORK_DIR
    outputs: Optional[str] = None
    debug: bool = False
    dry_run: bool = False
    seed: Optional[int] = 42
    api_url: Optional[str] = None
    api_key: Optional[str] = 'EMPTY'
    timeout: Optional[float] = None
    stream: bool = False
    judge_strategy: str = JudgeStrategy.AUTO
    judge_worker_num: int = 1
    judge_model_args: Optional[List] = field(default_factory=list)
    task_dir: str = None
    request_retry: bool = False
    retry_content_none: bool = True
    task_id: str = '123'
    system_prompt: str = None

    def __post_init__(self):
        if not self.model_id and self.model:
            self.model_id = os.path.basename(self.model).rstrip(os.sep)
            self.model_id = self.model_id.replace(':', '-')
        if self.eval_batch_size is None:
            self.eval_batch_size = 8 if self.eval_type == EvalType.SERVICE else 1

    def to_dict(self):
        result = self.__dict__.copy()
        return result

    def __str__(self):
        return json.dumps(self.to_dict(), indent=4, default=str, ensure_ascii=False)

    def update(self, other: Union['TaskConfig', dict]):
        if isinstance(other, TaskConfig):
            other = other.to_dict()
        self.__dict__.update(other)

    def dump_yaml(self, output_dir: str):
        """Dump the task configuration to a YAML file."""
        task_cfg_file = os.path.join(output_dir, f'task_config_{gen_hash(str(self), bits=6)}.yaml')
        try:
            logger.info(f'Dump task config to {task_cfg_file}')
            dict_to_yaml(self.to_dict(), task_cfg_file)
        except Exception as e:
            logger.warning(f'Failed to dump overall task config: {e}')

    @staticmethod
    def from_dict(d: dict):
        return TaskConfig(**d)

    @staticmethod
    def from_json(json_file: str):
        return TaskConfig.from_dict(json_to_dict(json_file))

    @staticmethod
    def from_args(args: Namespace):
        args_dict = {k: v for k, v in vars(args).items() if v is not None}
        if 'func' in args_dict:
            del args_dict['func']
        return TaskConfig.from_dict(args_dict)

def parse_task_config(task_cfg) -> TaskConfig:
    """Parse task configuration from various formats into a TaskConfig object."""
    if isinstance(task_cfg, TaskConfig):
        logger.info('Args: Task config is provided with TaskConfig type.')
    elif isinstance(task_cfg, dict):
        logger.info('Args: Task config is provided with dictionary type.')
        task_cfg = TaskConfig.from_dict(task_cfg)
    elif isinstance(task_cfg, Namespace):
        logger.info('Args: Task config is provided with CommandLine type.')
        task_cfg = TaskConfig.from_args(task_cfg)
    elif isinstance(task_cfg, str):
        extension = os.path.splitext(task_cfg)[-1]
        logger.info(f'Args: Task config is provided with {extension} file type.')
    else:
        raise ValueError('Args: Please provide a valid task config.')
    return task_cfg
