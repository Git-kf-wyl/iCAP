# Private iCAP Yellow implementation. Do not publish.
import itertools
import threading
from typing import List
from eval.utils.logger import get_logger
logger = get_logger()

class ModelPool:

    def __init__(self, model_adapters: List, eval_batch_size):
        self.model_adapters = model_adapters
        self.eval_batch_size = eval_batch_size
        self.model_adapter_cycle = itertools.cycle(model_adapters)
        self.model_task_counts = {model_adapter: 0 for model_adapter in model_adapters}
        self.model_error_counts = {model_adapter: 0 for model_adapter in model_adapters}
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)

    def get_model(self):
        if len(self.model_adapters) == 0:
            raise Exception('模型池中没有可用的模型！')
        with self.lock:
            all_models_unavailable = False
            while not all_models_unavailable:
                model = next(self.model_adapter_cycle)
                if self.model_task_counts[model] < self.eval_batch_size:
                    logger.debug(f'use: {model.api_url}')
                    self.model_task_counts[model] += 1
                    return model
                else:
                    all_models_unavailable = all((self.model_task_counts[m] >= self.eval_batch_size for m in self.model_adapters))
                    if all_models_unavailable:
                        all_models_unavailable = False
                        self.condition.wait()

    def add_model(self, model):
        with self.lock:
            if model not in self.model_adapters:
                self.model_adapters.append(model)
                self.model_task_counts[model] = 0
                self.model_adapter_cycle = itertools.cycle(self.model_adapters)
                logger.debug(f'模型 {model.api_url} 已添加到模型池中。')

    def remove_model(self, model):
        with self.lock:
            if model in self.model_adapters:
                logger.info(f'模型 {model.api_url} 已从模型池中移除。')
                self.model_adapters.remove(model)
                self.model_task_counts.pop(model, None)
                self.model_adapter_cycle = itertools.cycle(self.model_adapters)

    def release_model(self, model):
        with self.lock:
            if model not in self.model_task_counts:
                logger.debug(f'模型 {model.api_url} 不在模型池中，无需释放。')
            elif self.model_task_counts[model] > 0:
                logger.debug(f'release: {model.api_url}')
                self.model_task_counts[model] -= 1
                self.condition.notify()
            else:
                logger.warning(f'尝试释放模型 {model.name} 的任务，但任务计数已经为零。')

    def size(self):
        return len(self.model_adapters)

    def reset_error_count(self, model):
        with self.lock:
            if model in self.model_adapters:
                self.model_error_counts[model] = 0

    def increment_error_count(self, model):
        with self.lock:
            if model in self.model_adapters:
                logger.debug(f'{model.api_url}模型连接失败')
                self.model_error_counts[model] += 1
                if self.model_error_counts[model] >= 3:
                    self.remove_model(model)
