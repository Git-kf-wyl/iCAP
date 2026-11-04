# Private iCAP Yellow implementation. Do not publish.
import datasets
import json
import os
import pandas as pd
_CITATION = '@article{2017arXivtriviaqa,\n       author = {{Joshi}, Mandar and {Choi}, Eunsol and {Weld},\n                 Daniel and {Zettlemoyer}, Luke},\n        title = "{triviaqa: A Large Scale Distantly Supervised Challenge Dataset for Reading Comprehension}",\n      journal = {arXiv e-prints},\n         year = 2017,\n          eid = {arXiv:1705.03551},\n        pages = {arXiv:1705.03551},\narchivePrefix = {arXiv},\n       eprint = {1705.03551},\n}\n'
_DESCRIPTION = 'TriviaqQA is a reading comprehension dataset containing over 650K question-answer-evidence triples.\n'
_HOMEPAGE = 'https://modelscope.cn/datasets/modelscope/trivia_qa/summary'
_URL = 'https://modelscope.cn/api/v1/datasets/modelscope/trivia_qa/repo?Revision=master&FilePath=trivia_qa.zip'
task_list = ['default']

class TriviaQAConfig(datasets.BuilderConfig):

    def __init__(self, **kwargs):
        super().__init__(version=datasets.Version('1.0.0'), **kwargs)

class TriviaQA(datasets.GeneratorBasedBuilder):
    BUILDER_CONFIGS = [TriviaQAConfig(name=task_name) for task_name in task_list]

    def _info(self):
        features = datasets.Features({'input': [{'role': datasets.features.Value('string'), 'content': datasets.features.Value('string')}], 'ideal': [datasets.Value('string')]})
        return datasets.DatasetInfo(description=_DESCRIPTION, features=features, homepage=_HOMEPAGE, citation=_CITATION)

    def _split_generators(self, dl_manager):
        data_dir = dl_manager.download_and_extract(_URL)
        return [datasets.SplitGenerator(name=datasets.Split.TEST, gen_kwargs={'filepath': os.path.join(data_dir, 'trivia_qa/test.jsonl')}), datasets.SplitGenerator(name=datasets.Split('dev'), gen_kwargs={'filepath': os.path.join(data_dir, 'trivia_qa/dev.jsonl')})]

    def _generate_examples(self, filepath):
        with open(filepath, encoding='utf-8') as f:
            contents = [json.loads(line) for line in f.readlines()]
            for i, instance in enumerate(contents):
                yield (i, instance)
