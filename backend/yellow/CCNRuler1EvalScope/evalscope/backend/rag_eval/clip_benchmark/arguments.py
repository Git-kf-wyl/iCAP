# Private iCAP Yellow implementation. Do not publish.
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class Arguments:
    """
    A dataclass to store and manage the arguments for the model configuration and data processing.
    """
    '\n    For CLIP model support, you can use the following fields:\n        model_name: str\n        revision: str = "master"\n        hub: str = "modelscope"\n\n    For API VLM model support, you can use the following fields, (image caption only):\n        model_name="gpt-4o-mini"\n        api_base: str = "",\n        api_key: Optional[str] = None\n        prompt: str = None\n    '
    models: List[Dict] = field(default_factory=dict)
    dataset_name: List[str] = field(default_factory=list)
    data_dir: str = None
    split: str = 'test'
    task: str = None
    batch_size: int = 128
    num_workers: int = 1
    verbose: bool = True
    output_dir: str = 'outputs'
    cache_dir: str = 'cache'
    skip_existing: bool = False
    limit: int = None
