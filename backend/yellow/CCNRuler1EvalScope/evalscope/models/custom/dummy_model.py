# Private iCAP Yellow implementation. Do not publish.
import os
import time
from evalscope.models.custom import CustomModel
from evalscope.run import run_task
from evalscope.utils.io_utils import yaml_to_dict
from evalscope.utils.logger import get_logger
logger = get_logger()
'\nThis script is used to rewrite the evaluation results without re-running the model predictions.\n'

class DummyCustomModel(CustomModel):

    def __init__(self, config: dict, **kwargs):
        super(DummyCustomModel, self).__init__(config=config, **kwargs)

    def predict(self, prompts: str, **kwargs):
        response = 'The answer is C. NOTE: ONLY FOR TEST'
        res_d: dict = {'choices': [{'index': 0, 'message': {'content': response, 'role': 'assistant'}}], 'created': time.time(), 'model': self.config.get('model_id'), 'object': 'chat.completion', 'usage': {'completion_tokens': 0, 'prompt_tokens': 0, 'total_tokens': 0}}
        return [res_d for _ in prompts]
if __name__ == '__main__':
    swift_model = DummyCustomModel(config={'model_id': 'swift-model-dummy'})
    task_cfg_file = '/path/to/eval_your_model_results/configs/task_output_config.yaml'
    task_cfg_d = yaml_to_dict(task_cfg_file)
    task_cfg_d.update({'model': swift_model})
    eval_results: dict = run_task(task_cfg=task_cfg_d)
    print('** Evaluation results finished !\n')
