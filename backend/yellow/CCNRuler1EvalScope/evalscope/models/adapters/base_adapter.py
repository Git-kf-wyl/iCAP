# Private iCAP Yellow API-model adapter. Do not publish.
from abc import ABC, abstractmethod
class BaseModelAdapter(ABC):
    def __init__(self,model=None,**kwargs):
        self.model_cfg=kwargs.get('model_cfg')
    @abstractmethod
    def predict(self,*args,**kwargs):raise NotImplementedError

def initialize_model_adapter(task_cfg,benchmark,base_model=None):
    from .server_adapter import ServerModelAdapter
    from ..model_pool import ModelPool
    if benchmark.model_adapter=='bfcl_server':
        from .bfcl_adapter import BFCLAdapter
        ServerModelAdapter=BFCLAdapter
    if not task_cfg.models:raise ValueError('iCAP 仅启用已注册的 API 模型')
    adapters=[ServerModelAdapter(api_url=model['api_url'],model_id=model['model'],api_key=model['api_key'],
                non_openai_format=False,seed=task_cfg.seed,timeout=task_cfg.timeout,stream=task_cfg.stream)
              for model in task_cfg.models]
    return ModelPool(adapters,task_cfg.eval_batch_size)
