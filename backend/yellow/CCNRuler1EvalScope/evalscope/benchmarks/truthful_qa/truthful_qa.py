# Private iCAP Yellow implementation. Do not publish.
"""TruthfulQA dataset."""
import csv
import datasets
import json
_CITATION = '@misc{lin2021truthfulqa,\n    title={TruthfulQA: Measuring How Models Mimic Human Falsehoods},\n    author={Stephanie Lin and Jacob Hilton and Owain Evans},\n    year={2021},\n    eprint={2109.07958},\n    archivePrefix={arXiv},\n    primaryClass={cs.CL}\n}\n'
_DESCRIPTION = 'TruthfulQA is a benchmark to measure whether a language model is truthful in\ngenerating answers to questions. The benchmark comprises 817 questions that\nspan 38 categories, including health, law, finance and politics. Questions are\ncrafted so that some humans would answer falsely due to a false belief or\nmisconception. To perform well, models must avoid generating false answers\nlearned from imitating human texts.\n'
_HOMEPAGE = 'https://github.com/sylinrl/TruthfulQA'
_LICENSE = 'Apache License 2.0'

class TruthfulQaConfig(datasets.BuilderConfig):
    """BuilderConfig for TruthfulQA."""

    def __init__(self, url, features, **kwargs):
        """BuilderConfig for TruthfulQA.
        Args:
          url: *string*, the url to the configuration's data.
          features: *list[string]*, list of features that'll appear in the feature dict.
          **kwargs: keyword arguments forwarded to super.
        """
        super().__init__(version=datasets.Version('1.1.0'), **kwargs)
        self.url = url
        self.features = features

class TruthfulQa(datasets.GeneratorBasedBuilder):
    """TruthfulQA is a benchmark to measure whether a language model is truthful in generating answers to questions."""
    BUILDER_CONFIGS = [TruthfulQaConfig(name='generation', url='https://modelscope.oss-cn-beijing.aliyuncs.com/open_data/truthful_qa/TruthfulQA.csv', features=datasets.Features({'type': datasets.Value('string'), 'category': datasets.Value('string'), 'question': datasets.Value('string'), 'best_answer': datasets.Value('string'), 'correct_answers': datasets.features.Sequence(datasets.Value('string')), 'incorrect_answers': datasets.features.Sequence(datasets.Value('string')), 'source': datasets.Value('string')}), description="The Generation TruthfulQA (main) task tests a model's ability to generate 1-2 sentence answers for a given question truthfully."), TruthfulQaConfig(name='multiple_choice', url='https://modelscope.oss-cn-beijing.aliyuncs.com/open_data/truthful_qa/mc_task.json', features=datasets.Features({'question': datasets.Value('string'), 'mc1_targets': {'choices': datasets.features.Sequence(datasets.Value('string')), 'labels': datasets.features.Sequence(datasets.Value('int32'))}, 'mc2_targets': {'choices': datasets.features.Sequence(datasets.Value('string')), 'labels': datasets.features.Sequence(datasets.Value('int32'))}}), description="The Multiple-Choice TruthfulQA task provides a multiple-choice option to test a model's ability to identify true statements.")]

    def _info(self):
        return datasets.DatasetInfo(description=_DESCRIPTION, features=self.config.features, homepage=_HOMEPAGE, license=_LICENSE, citation=_CITATION)

    def _split_generators(self, dl_manager):
        data_dir = dl_manager.download(self.config.url)
        return [datasets.SplitGenerator(name=datasets.Split.VALIDATION, gen_kwargs={'filepath': data_dir})]

    def _split_csv_list(self, csv_list: str, delimiter: str=';') -> str:
        """
        Splits a csv list field, delimited by `delimiter` (';'), into a list
        of strings.
        """
        csv_list = csv_list.strip().split(delimiter)
        return [item.strip() for item in csv_list]

    def _generate_examples(self, filepath):
        if self.config.name == 'multiple_choice':
            with open(filepath, encoding='utf-8') as f:
                contents = json.load(f)
                for key, row in enumerate(contents):
                    yield (key, {'question': row['question'], 'mc1_targets': {'choices': list(row['mc1_targets'].keys()), 'labels': list(row['mc1_targets'].values())}, 'mc2_targets': {'choices': list(row['mc2_targets'].keys()), 'labels': list(row['mc2_targets'].values())}})
        else:
            with open(filepath, newline='', encoding='utf-8-sig') as f:
                contents = csv.DictReader(f)
                for key, row in enumerate(contents):
                    if not row['Correct Answers'] or not row['Incorrect Answers']:
                        continue
                    yield (key, {'type': row['Type'], 'category': row['Category'], 'question': row['Question'], 'best_answer': row['Best Answer'], 'correct_answers': self._split_csv_list(row['Correct Answers']), 'incorrect_answers': self._split_csv_list(row['Incorrect Answers']), 'source': row['Source']})
