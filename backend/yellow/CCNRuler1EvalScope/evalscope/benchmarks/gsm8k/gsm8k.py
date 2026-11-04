# Private iCAP Yellow implementation. Do not publish.
"""Grade School Math 8k dataset."""
import datasets
import json
import textwrap
_CITATION = '@misc{cobbe2021training,\n      title={Training Verifiers to Solve Math Word Problems},\n      author={Karl Cobbe and Vineet Kosaraju and Mohammad Bavarian and Jacob Hilton and Reiichiro Nakano and Christopher Hesse and John Schulman},\n      year={2021},\n      eprint={2110.14168},\n      archivePrefix={arXiv},\n      primaryClass={cs.LG}\n}\n'
_DESCRIPTION = 'GSM8K (Grade School Math 8K) is a dataset of 8.5K high quality\nlinguistically diverse grade school math word problems. The\ndataset was created to support the task of question answering\non basic mathematical problems that require multi-step reasoning.\n'
_HOMEPAGE = 'https://openai.com/blog/grade-school-math'
_MODELSCOPE_PAGE = 'https://modelscope.cn/datasets/modelscope/gsm8k/summary'
_LICENSE = 'MIT'
TRAIN_URL = 'https://sail-moe.oss-cn-hangzhou.aliyuncs.com/open_data/gsm8k/train.jsonl'
TEST_URL = 'https://sail-moe.oss-cn-hangzhou.aliyuncs.com/open_data/gsm8k/test.jsonl'

class Gsm8kConfig(datasets.BuilderConfig):
    """BuilderConfig for GSM8K."""

    def __init__(self, urls, **kwargs):
        """BuilderConfig for GSM8K.
        Args:
        urls: *dict[string]*, the urls for each split of the GSM8k set.
        """
        super().__init__(version=datasets.Version('1.1.0'), **kwargs)
        self.urls = urls

class Gsm8k(datasets.GeneratorBasedBuilder):
    """Grade School Math 8k (GSM8K)"""
    BUILDER_CONFIGS = [Gsm8kConfig(name='main', description=textwrap.dedent('\n                It is segmented into 7.5K training problems and 1K test problems.\n                These problems take between 2 and 8 steps to solve, and solutions\n                primarily involve performing a sequence of elementary calculations\n                using basic arithmetic operations (+ - / *) to reach the final\n                answer. A bright middle school student should be able to solve\n                every problem.\n                '), urls={'train': TRAIN_URL, 'test': TEST_URL})]

    def _info(self):
        features = datasets.Features({'question': datasets.Value('string'), 'answer': datasets.Value('string')})
        return datasets.DatasetInfo(description=_DESCRIPTION, features=features, homepage=_HOMEPAGE, license=_LICENSE, citation=_CITATION)

    def _split_generators(self, dl_manager):
        data_dir = dl_manager.download_and_extract(self.config.urls)
        return [datasets.SplitGenerator(name=datasets.Split.TRAIN, gen_kwargs={'filepath': data_dir['train']}), datasets.SplitGenerator(name=datasets.Split.TEST, gen_kwargs={'filepath': data_dir['test']})]

    def _generate_examples(self, filepath):
        with open(filepath, encoding='utf-8') as f:
            for key, row in enumerate(f):
                data = json.loads(row)
                yield (key, {'question': data['question'], 'answer': data['answer']})
