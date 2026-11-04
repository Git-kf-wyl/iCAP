# Private iCAP Yellow implementation. Do not publish.
"""AI2 ARC (Abstraction and Reasoning Corpus) for General Artificial Intelligence Benchmark."""
'AUTO GENERATED, DO NOT EDIT'
import datasets
import json
import os
_CITATION = '@article{allenai:arc,\n      author    = {Peter Clark  and Isaac Cowhey and Oren Etzioni and Tushar Khot and\n                    Ashish Sabharwal and Carissa Schoenick and Oyvind Tafjord},\n      title     = {Think you have Solved Question Answering? Try ARC, the AI2 Reasoning Challenge},\n      journal   = {arXiv:1803.05457v1},\n      year      = {2018},\n}\n'
_DESCRIPTION = 'A new dataset of 7,787 genuine grade-school level, multiple-choice science questions, assembled to encourage research in\n advanced question-answering. The dataset is partitioned into a Challenge Set and an Easy Set, where the former contains\n only questions answered incorrectly by both a retrieval-based algorithm and a word co-occurrence algorithm. We are also\n including a corpus of over 14 million science sentences relevant to the task,\n and an implementation of three neural baseline models for this dataset. We pose ARC as a challenge to the community.\n\nARC-Easy:\n    train: 2251\n    test: 2376\n    validation: 570\n\nARC-Challenge:\n    train: 1119\n    test: 1172\n    validation: 299\n'
_URL = 'https://modelscope.oss-cn-beijing.aliyuncs.com/open_data/arc/ARC-V1-Feb2018.zip'

class Ai2ArcConfig(datasets.BuilderConfig):
    """BuilderConfig for Ai2ARC."""

    def __init__(self, **kwargs):
        """BuilderConfig for Ai2Arc.

        Args:
          **kwargs: keyword arguments forwarded to super.
        """
        super(Ai2ArcConfig, self).__init__(version=datasets.Version('1.0.0', ''), **kwargs)

class Ai2Arc(datasets.GeneratorBasedBuilder):
    """
    The AI2 Reasoning Challenge (ARC) dataset.
    Subset: ARC-Easy, ARC-Challenge.
    """
    VERSION = datasets.Version('1.0.0')
    BUILDER_CONFIGS = [Ai2ArcConfig(name='ARC-Challenge', description='          Challenge Set of 2590 “hard” questions (those that both a retrieval and a co-occurrence method fail to answer correctly)\n          '), Ai2ArcConfig(name='ARC-Easy', description='          Easy Set of 5197 questions\n          ')]

    def _info(self):
        return datasets.DatasetInfo(description=_DESCRIPTION, features=datasets.Features({'id': datasets.Value('string'), 'question': datasets.Value('string'), 'choices': datasets.features.Sequence({'text': datasets.Value('string'), 'label': datasets.Value('string')}), 'answerKey': datasets.Value('string')}), supervised_keys=None, homepage='https://allenai.org/data/arc', citation=_CITATION)

    def _split_generators(self, dl_manager):
        """Returns SplitGenerators."""
        dl_dir = dl_manager.download_and_extract(_URL)
        data_dir = os.path.join(dl_dir, 'ARC-V1-Feb2018-2')
        return [datasets.SplitGenerator(name=datasets.Split.TRAIN, gen_kwargs={'filepath': os.path.join(data_dir, self.config.name, self.config.name + '-Train.jsonl')}), datasets.SplitGenerator(name=datasets.Split.TEST, gen_kwargs={'filepath': os.path.join(data_dir, self.config.name, self.config.name + '-Test.jsonl')}), datasets.SplitGenerator(name=datasets.Split.VALIDATION, gen_kwargs={'filepath': os.path.join(data_dir, self.config.name, self.config.name + '-Dev.jsonl')})]

    def _generate_examples(self, filepath):
        """Yields examples."""
        with open(filepath, encoding='utf-8') as f:
            for row in f:
                data = json.loads(row)
                answerkey = data['answerKey']
                id_ = data['id']
                question = data['question']['stem']
                choices = data['question']['choices']
                text_choices = [choice['text'] for choice in choices]
                label_choices = [choice['label'] for choice in choices]
                yield (id_, {'id': id_, 'answerKey': answerkey, 'question': question, 'choices': {'text': text_choices, 'label': label_choices}})
