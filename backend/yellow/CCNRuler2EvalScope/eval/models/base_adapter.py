# Private iCAP Yellow implementation. Do not publish.
try:
    from torch import no_grad
except ImportError:
    def no_grad(): return lambda function:function
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, List, Optional, Union
from eval.constants import EvalType, OutputType
from eval.utils.logger import get_logger
from .model_pool import ModelPool
logger = get_logger()
if TYPE_CHECKING:
    from eval.benchmarks import BenchmarkMeta
    from eval.config import TaskConfig

class BaseModelAdapter(ABC):

    def __init__(self, model: Optional[Union[None]], **kwargs):
        if model is None:
            self.model_cfg = kwargs.get('model_cfg', None)
        else:
            raise ValueError(f'Unsupported model type: {type(model)}')

    @abstractmethod
    @no_grad()
    def predict(self, *args, **kwargs) -> Any:
        raise NotImplementedError

def initialize_model_adapter(task_cfg: 'TaskConfig', benchmark: 'BenchmarkMeta'):
    """Initialize the model adapter based on the task configuration."""
    if task_cfg.eval_type == EvalType.SERVICE or task_cfg.models:
        from .register import get_model_adapter
        if benchmark.model_adapter in [OutputType.CONTINUOUS, OutputType.MULTIPLE_CHOICE]:
            logger.warning('Output type is set to logits. This is not supported for service evaluation. Setting output type to generation by default.')
            benchmark.model_adapter = OutputType.GENERATION
        model_adapter_cls_str = benchmark.model_adapter
        if 'server' not in model_adapter_cls_str:
            model_adapter_cls_str = 'server'
        model_adapter_cls = get_model_adapter(model_adapter_cls_str)
        model_adapters = []
        for model in task_cfg.models:
            model_adapters.append(model_adapter_cls(api_url=model['api_url'], model_id=model['model'], api_key=model['api_key'], non_openai_format=model.get('non_openai_format', False), generate_config=task_cfg.generation_config, seed=task_cfg.seed, timeout=task_cfg.timeout, stream=task_cfg.stream))
        return ModelPool(model_adapters, task_cfg.eval_batch_size)
    else:
        raise ValueError(f'Please set model type: task_cfg.eval_type or task_cfg.models')
