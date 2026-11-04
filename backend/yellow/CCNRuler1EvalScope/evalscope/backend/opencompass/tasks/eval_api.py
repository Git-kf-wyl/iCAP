# Private iCAP Yellow implementation. Do not publish.
from mmengine.config import read_base
from opencompass.partitioners import NaivePartitioner
from opencompass.runners import LocalRunner
from opencompass.tasks import OpenICLInferTask
with read_base():
    from evalscope.backend.opencompass.tasks.eval_datasets import datasets
for _dataset in datasets:
    if _dataset['path'] == 'openai_humaneval':
        from opencompass.datasets.humaneval import humaneval_gpt_postprocess
        _dataset['eval_cfg']['pred_postprocessor']['type'] = humaneval_gpt_postprocess
models = []
infer = dict(partitioner=dict(type=NaivePartitioner), runner=dict(type=LocalRunner, max_num_workers=4, task=dict(type=OpenICLInferTask)))
