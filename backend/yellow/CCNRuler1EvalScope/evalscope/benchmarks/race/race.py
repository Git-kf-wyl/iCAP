# Private iCAP Yellow implementation. Do not publish.
import datasets
import os
import pandas as pd
_CITATION = '@inproceedings{lai-etal-2017-race,\n    title = "{RACE}: Large-scale {R}e{A}ding Comprehension Dataset From Examinations",\n    author = "Lai, Guokun  and\n      Xie, Qizhe  and\n      Liu, Hanxiao  and\n      Yang, Yiming  and\n      Hovy, Eduard",\n    booktitle = "Proceedings of the 2017 Conference on Empirical Methods in Natural Language Processing",\n    month = sep,\n    year = "2017",\n    address = "Copenhagen, Denmark",\n    publisher = "Association for Computational Linguistics",\n    url = "https://aclanthology.org/D17-1082",\n    doi = "10.18653/v1/D17-1082",\n    pages = "785--794",\n}\n'
_DESCRIPTION = 'RACE is a large-scale reading comprehension dataset with more than 28,000 passages and nearly 100,000 questions.\n'
_HOMEPAGE = 'https://modelscope.cn/datasets/modelscope/race/summary'
_URL = 'https://modelscope.cn/api/v1/datasets/modelscope/race/repo?Revision=master&FilePath=race.zip'
task_list = ['high', 'middle']

class RACEConfig(datasets.BuilderConfig):

    def __init__(self, **kwargs):
        super().__init__(version=datasets.Version('1.0.0'), **kwargs)

class RACE(datasets.GeneratorBasedBuilder):
    BUILDER_CONFIGS = [RACEConfig(name=task_name) for task_name in task_list]

    def _info(self):
        features = datasets.Features({'example_id': datasets.Value('string'), 'article': datasets.Value('string'), 'answer': datasets.Value('string'), 'question': datasets.Value('string'), 'options': [datasets.Value('string')]})
        return datasets.DatasetInfo(description=_DESCRIPTION, features=features, homepage=_HOMEPAGE, citation=_CITATION)

    def _split_generators(self, dl_manager):
        data_dir = dl_manager.download_and_extract(_URL)
        task_name = self.config.name
        return [datasets.SplitGenerator(name=datasets.Split.TEST, gen_kwargs={'filepath': os.path.join(data_dir, f'race/test/{task_name}-00000-of-00001.parquet')}), datasets.SplitGenerator(name=datasets.Split.VALIDATION, gen_kwargs={'filepath': os.path.join(data_dir, f'race/val/{task_name}-00000-of-00001.parquet')}), datasets.SplitGenerator(name=datasets.Split.TRAIN, gen_kwargs={'filepath': os.path.join(data_dir, f'race/train/{task_name}-00000-of-00001.parquet')})]

    def _generate_examples(self, filepath):
        df = pd.read_parquet(filepath)
        df.columns = ['example_id', 'article', 'answer', 'question', 'options']
        for i, instance in enumerate(df.to_dict(orient='records')):
            yield (i, instance)
