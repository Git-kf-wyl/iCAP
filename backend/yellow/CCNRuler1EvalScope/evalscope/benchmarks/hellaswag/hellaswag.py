# Private iCAP Yellow implementation. Do not publish.
"""HellaSwag: Can a Machine Really Finish Your Sentence? is a new dataset for commonsense NLI.
    A paper was published at ACL2019.
"""
'DO NOT EDIT.'
import datasets
import json
_CITATION = '@inproceedings{zellers2019hellaswag,\n    title={HellaSwag: Can a Machine Really Finish Your Sentence?},\n    author={Zellers, Rowan and Holtzman, Ari and Bisk, Yonatan and Farhadi, Ali and Choi, Yejin},\n    booktitle ={Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics},\n    year={2019}\n}\n'
_DESCRIPTION = '\nHellaSwag: Can a Machine Really Finish Your Sentence? is a new dataset for commonsense NLI. A paper was published at ACL2019.\n'
_URL = 'https://modelscope.oss-cn-beijing.aliyuncs.com/open_data/hellaswag/'
_URLS = {'train': _URL + 'hellaswag_train.jsonl', 'test': _URL + 'hellaswag_test.jsonl', 'dev': _URL + 'hellaswag_val.jsonl'}

class Hellaswag(datasets.GeneratorBasedBuilder):
    """TODO(hellaswag): Short description of my dataset."""
    VERSION = datasets.Version('0.1.0')

    def _info(self):
        return datasets.DatasetInfo(description=_DESCRIPTION, features=datasets.Features({'ind': datasets.Value('int32'), 'activity_label': datasets.Value('string'), 'ctx_a': datasets.Value('string'), 'ctx_b': datasets.Value('string'), 'ctx': datasets.Value('string'), 'endings': datasets.features.Sequence(datasets.Value('string')), 'source_id': datasets.Value('string'), 'split': datasets.Value('string'), 'split_type': datasets.Value('string'), 'label': datasets.Value('string')}), supervised_keys=None, homepage='https://rowanzellers.com/hellaswag/', citation=_CITATION)

    def _split_generators(self, dl_manager):
        """Returns SplitGenerators."""
        urls_to_download = _URLS
        dl_dir = dl_manager.download_and_extract(urls_to_download)
        return [datasets.SplitGenerator(name=datasets.Split.TRAIN, gen_kwargs={'filepath': dl_dir['train']}), datasets.SplitGenerator(name=datasets.Split.TEST, gen_kwargs={'filepath': dl_dir['test']}), datasets.SplitGenerator(name=datasets.Split.VALIDATION, gen_kwargs={'filepath': dl_dir['dev']})]

    def _generate_examples(self, filepath):
        """Yields examples."""
        with open(filepath, encoding='utf-8') as f:
            for id_, row in enumerate(f):
                data = json.loads(row)
                yield (id_, {'ind': int(data['ind']), 'activity_label': data['activity_label'], 'ctx_a': data.get('ctx_a', ''), 'ctx_b': data.get('ctx_b', ''), 'ctx': data['ctx'], 'endings': data.get('endings', []), 'source_id': data['source_id'], 'split': data['split'], 'split_type': data['split_type'], 'label': str(data.get('label', ''))})
