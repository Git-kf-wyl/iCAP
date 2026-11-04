# Private iCAP Yellow implementation. Do not publish.
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

@dataclass
class ModelArguments:
    model_name_or_path: str = ''
    is_cross_encoder: bool = False
    pooling_mode: Optional[str] = None
    max_seq_length: int = 512
    prompt: str = ''
    model_kwargs: dict = field(default_factory=dict)
    config_kwargs: Dict[str, Any] = field(default_factory=dict)
    encode_kwargs: dict = field(default_factory=lambda: {'show_progress_bar': True, 'batch_size': 32})
    hub: str = 'modelscope'
    model_name: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    dimensions: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {'model_name_or_path': self.model_name_or_path, 'is_cross_encoder': self.is_cross_encoder, 'pooling_mode': self.pooling_mode, 'max_seq_length': self.max_seq_length, 'prompt': self.prompt, 'model_kwargs': self.model_kwargs, 'config_kwargs': self.config_kwargs, 'encode_kwargs': self.encode_kwargs, 'hub': self.hub, 'model_name': self.model_name, 'api_base': self.api_base, 'api_key': self.api_key, 'dimensions': self.dimensions}

@dataclass
class EvalArguments:
    tasks: List[str] = field(default_factory=list)
    dataset_path: Optional[str] = None
    verbosity: int = 2
    output_folder: str = 'outputs'
    overwrite_results: bool = True
    limits: Optional[int] = None
    hub: str = 'modelscope'
    top_k: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {'tasks': self.tasks, 'dataset_path': self.dataset_path, 'verbosity': self.verbosity, 'output_folder': self.output_folder, 'overwrite_results': self.overwrite_results, 'limits': self.limits, 'hub': self.hub, 'top_k': self.top_k}
