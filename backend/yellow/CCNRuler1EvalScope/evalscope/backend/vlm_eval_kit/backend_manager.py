# Private iCAP Yellow implementation. Do not publish.
import copy
import os
import subprocess
from functools import partial
from typing import Optional, Union
from evalscope.backend.base import BackendManager
from evalscope.utils import get_valid_list, is_module_installed
from evalscope.utils.logger import get_logger
logger = get_logger()

class ExecutionMode:
    CMD = 'cmd'
    FUNCTION = 'function'

class VLMEvalKitBackendManager(BackendManager):

    def __init__(self, config: Union[str, dict], **kwargs):
        """BackendManager for VLM Evaluation Kit

        Args:
            config (Union[str, dict]): the configuration yaml-file or the configuration dictionary
        """
        self._check_env()
        super().__init__(config, **kwargs)
        from vlmeval.utils.arguments import Arguments as VLMEvalArguments
        self.args = VLMEvalArguments(**self.config_d)
        self.valid_models = self.list_supported_models()
        self.valid_model_names = list(self.valid_models.keys())
        self.valid_datasets = self.list_supported_datasets()
        self._check_valid()

    def _check_valid(self):
        if not self.args.data or not self.args.model:
            raise ValueError('** Args: Please provide model and datasets. **')
        valid_datasets, invalid_datasets = get_valid_list(self.args.data, self.valid_datasets)
        if len(invalid_datasets) != 0:
            logger.warning(f'Using custom dataset: {invalid_datasets}, ')
        if isinstance(self.args.model[0], dict):
            new_model_names = []
            index = 0
            for model_cfg in self.args.model:
                model_name = model_cfg['name']
                model_class = self.valid_models[model_name]
                if model_name == 'CustomAPIModel':
                    model_type = model_cfg['type']
                    remain_cfg = copy.deepcopy(model_cfg)
                    del remain_cfg['name']
                    del remain_cfg['type']
                    norm_model_type = os.path.basename(model_type).replace(':', '-').replace('.', '_') + f'_{index}'
                    self.valid_models.update({norm_model_type: partial(model_class, model=model_type, **remain_cfg)})
                    new_model_names.append(norm_model_type)
                else:
                    remain_cfg = copy.deepcopy(model_cfg)
                    del remain_cfg['name']
                    self.valid_models[model_name] = partial(model_class, **remain_cfg)
                    new_model_names.append(model_name)
                index += 1
            self.args.model = new_model_names
        elif isinstance(self.args.model[0], str):
            valid_model_names, invalid_model_names = get_valid_list(self.args.model, self.valid_model_names)
            if len(invalid_datasets) != 0:
                logger.warning(f'Using custom dataset: {invalid_datasets}, ')

    @property
    def cmd(self):
        return self.get_cmd()

    @staticmethod
    def list_supported_models():
        from vlmeval.config import supported_VLM
        return supported_VLM

    @staticmethod
    def list_supported_datasets():
        from vlmeval.dataset import SUPPORTED_DATASETS
        return SUPPORTED_DATASETS

    @staticmethod
    def _check_env():
        if is_module_installed('vlmeval'):
            logger.info('Check VLM Evaluation Kit: Installed')

    @staticmethod
    def get_restore_arg(arg_name: str, arg_val: bool):
        if arg_val:
            return f'--{arg_name}'
        else:
            return ''

    @staticmethod
    def get_arg_with_default(arg_name: str, arg_val: Optional[str]=None):
        if arg_val:
            return f'--{arg_name} {arg_val}'
        else:
            return ''

    def get_cmd(self):
        assert self.args.data, 'The datasets are required.'
        assert self.args.model, 'The models are required.'
        cmd_str = f"python -m vlmeval --model {' '.join(self.args.model)} --data {' '.join(self.args.data)} {self.get_restore_arg('verbose', self.args.verbose)} {self.get_restore_arg('ignore', self.args.ignore)} {self.get_restore_arg('reuse', self.args.reuse)} {self.get_arg_with_default('work-dir', self.args.work_dir)} {self.get_arg_with_default('limit', self.args.limit)} {self.get_arg_with_default('mode', self.args.mode)} {self.get_arg_with_default('nproc', self.args.nproc)} {self.get_arg_with_default('judge', self.args.judge)} {self.get_arg_with_default('retry', self.args.retry)} "
        return cmd_str

    def run(self, run_mode: str=ExecutionMode.FUNCTION):
        if run_mode == ExecutionMode.CMD:
            logger.info(f'** Run command: {self.cmd}')
            try:
                subprocess.run(self.cmd, check=True, ext=True, shell=True)
            except subprocess.CalledProcessError as e:
                logger.error(f'** Run command failed: {e.stderr}')
                raise
        elif run_mode == ExecutionMode.FUNCTION:
            from vlmeval.run import run_task
            logger.info(f'*** Run task with config: {self.args} \n')
            run_task(self.args)
        else:
            raise NotImplementedError
