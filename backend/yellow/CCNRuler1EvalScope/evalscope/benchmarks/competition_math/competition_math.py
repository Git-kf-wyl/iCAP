# Private iCAP Yellow implementation. Do not publish.
"""Mathematics Aptitude Test of Heuristics (MATH) dataset."""
import datasets
import json
import os
_CITATION = '@article{hendrycksmath2021,\n  title={Measuring Mathematical Problem Solving With the MATH Dataset},\n  author={Dan Hendrycks\n    and Collin Burns\n    and Saurav Kadavath\n    and Akul Arora\n    and Steven Basart\n    and Eric Tang\n    and Dawn Song\n    and Jacob Steinhardt},\n  journal={arXiv preprint arXiv:2103.03874},\n  year={2021}\n}\n'
_DESCRIPTION = 'The Mathematics Aptitude Test of Heuristics (MATH) dataset consists of problems\nfrom mathematics competitions, including the AMC 10, AMC 12, AIME, and more.\nEach problem in MATH has a full step-by-step solution, which can be used to teach\nmodels to generate answer derivations and explanations.\n'
_HOMEPAGE = 'https://github.com/hendrycks/math'
_LICENSE = 'https://github.com/hendrycks/math/blob/main/LICENSE'
_URL = 'https://sail-moe.oss-cn-hangzhou.aliyuncs.com/open_data/math/MATH.zip'

class CompetitionMathDataset(datasets.GeneratorBasedBuilder):
    """Mathematics Aptitude Test of Heuristics (MATH) dataset."""
    VERSION = datasets.Version('1.0.0')

    def _info(self):
        features = datasets.Features({'problem': datasets.Value('string'), 'level': datasets.Value('string'), 'type': datasets.Value('string'), 'solution': datasets.Value('string')})
        return datasets.DatasetInfo(description=_DESCRIPTION, features=features, supervised_keys=None, homepage=_HOMEPAGE, license=_LICENSE, citation=_CITATION)

    def _split_generators(self, dl_manager):
        """Returns SplitGenerators."""
        download_dir = dl_manager.download_and_extract(_URL)
        return [datasets.SplitGenerator(name=datasets.Split.TRAIN, gen_kwargs={'data_dir': dl_manager.iter_files(os.path.join(download_dir, 'MATH', 'train'))}), datasets.SplitGenerator(name=datasets.Split.TEST, gen_kwargs={'data_dir': dl_manager.iter_files(os.path.join(download_dir, 'MATH', 'test'))})]

    def _generate_examples(self, data_dir):
        """Yields examples as (key, example) tuples."""
        for id_, filepath in enumerate(data_dir):
            with open(filepath, 'rb') as fin:
                example = json.load(fin)
                yield (id_, example)
