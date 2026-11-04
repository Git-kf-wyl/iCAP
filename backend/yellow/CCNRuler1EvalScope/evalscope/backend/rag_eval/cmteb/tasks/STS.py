# Private iCAP Yellow implementation. Do not publish.
from mteb.abstasks.AbsTaskSTS import AbsTaskSTS
from mteb.abstasks.TaskMetadata import TaskMetadata

class ATEC(AbsTaskSTS):
    metadata = TaskMetadata(name='ATEC', dataset={'path': 'C-MTEB/ATEC', 'revision': '0f319b1142f28d00e055a6770f3f726ae9b7d865'}, description='A Chinese dataset for textual relatedness', reference='https://aclanthology.org/2021.emnlp-main.357', type='STS', category='s2s', modalities=['text'], eval_splits=['validation', 'test'], eval_langs=['cmn-Hans'], main_score='cosine_spearman', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@inproceedings{raghu-etal-2021-end,\n    title = "End-to-End Learning of Flowchart Grounded Task-Oriented Dialogs",\n    author = "Raghu, Dinesh  and\n      Agarwal, Shantanu  and\n      Joshi, Sachindra  and\n      {Mausam}",\n    editor = "Moens, Marie-Francine  and\n      Huang, Xuanjing  and\n      Specia, Lucia  and\n      Yih, Scott Wen-tau",\n    booktitle = "Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing",\n    month = nov,\n    year = "2021",\n    address = "Online and Punta Cana, Dominican Republic",\n    publisher = "Association for Computational Linguistics",\n    url = "https://aclanthology.org/2021.emnlp-main.357",\n    doi = "10.18653/v1/2021.emnlp-main.357",\n    pages = "4348--4366",\n    abstract = "We propose a novel problem within end-to-end learning of task oriented dialogs (TOD), in which the dialog system mimics a troubleshooting agent who helps a user by diagnosing their problem (e.g., car not starting). Such dialogs are grounded in domain-specific flowcharts, which the agent is supposed to follow during the conversation. Our task exposes novel technical challenges for neural TOD, such as grounding an utterance to the flowchart without explicit annotation, referring to additional manual pages when user asks a clarification question, and ability to follow unseen flowcharts at test time. We release a dataset (FLODIAL) consisting of 2,738 dialogs grounded on 12 different troubleshooting flowcharts. We also design a neural model, FLONET, which uses a retrieval-augmented generation architecture to train the dialog agent. Our experiments find that FLONET can do zero-shot transfer to unseen flowcharts, and sets a strong baseline for future research.",\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['min_score'] = 0
        metadata_dict['max_score'] = 1
        return metadata_dict

class BQ(AbsTaskSTS):
    metadata = TaskMetadata(name='BQ', dataset={'path': 'C-MTEB/BQ', 'revision': 'e3dda5e115e487b39ec7e618c0c6a29137052a55'}, description='A Chinese dataset for textual relatedness', reference='https://aclanthology.org/2021.emnlp-main.357', type='STS', category='s2s', modalities=['text'], eval_splits=['validation', 'test'], eval_langs=['cmn-Hans'], main_score='cosine_spearman', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@misc{xiao2024cpackpackagedresourcesadvance,\n      title={C-Pack: Packaged Resources To Advance General Chinese Embedding},\n      author={Shitao Xiao and Zheng Liu and Peitian Zhang and Niklas Muennighoff and Defu Lian and Jian-Yun Nie},\n      year={2024},\n      eprint={2309.07597},\n      archivePrefix={arXiv},\n      primaryClass={cs.CL},\n      url={https://arxiv.org/abs/2309.07597},\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['min_score'] = 0
        metadata_dict['max_score'] = 1
        return metadata_dict

class LCQMC(AbsTaskSTS):
    metadata = TaskMetadata(name='LCQMC', dataset={'path': 'C-MTEB/LCQMC', 'revision': '17f9b096f80380fce5ed12a9be8be7784b337daf'}, description='A Chinese dataset for textual relatedness', reference='https://aclanthology.org/2021.emnlp-main.357', type='STS', category='s2s', modalities=['text'], eval_splits=['test'], eval_langs=['cmn-Hans'], main_score='cosine_spearman', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@misc{xiao2024cpackpackagedresourcesadvance,\n      title={C-Pack: Packaged Resources To Advance General Chinese Embedding},\n      author={Shitao Xiao and Zheng Liu and Peitian Zhang and Niklas Muennighoff and Defu Lian and Jian-Yun Nie},\n      year={2024},\n      eprint={2309.07597},\n      archivePrefix={arXiv},\n      primaryClass={cs.CL},\n      url={https://arxiv.org/abs/2309.07597},\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['min_score'] = 0
        metadata_dict['max_score'] = 1
        return metadata_dict

class PAWSX(AbsTaskSTS):
    metadata = TaskMetadata(name='PAWSX', dataset={'path': 'C-MTEB/PAWSX', 'revision': '9c6a90e430ac22b5779fb019a23e820b11a8b5e1'}, description='A Chinese dataset for textual relatedness', reference='https://aclanthology.org/2021.emnlp-main.357', type='STS', category='s2s', modalities=['text'], eval_splits=['test'], eval_langs=['cmn-Hans'], main_score='cosine_spearman', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@misc{xiao2024cpackpackagedresourcesadvance,\n      title={C-Pack: Packaged Resources To Advance General Chinese Embedding},\n      author={Shitao Xiao and Zheng Liu and Peitian Zhang and Niklas Muennighoff and Defu Lian and Jian-Yun Nie},\n      year={2024},\n      eprint={2309.07597},\n      archivePrefix={arXiv},\n      primaryClass={cs.CL},\n      url={https://arxiv.org/abs/2309.07597},\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['min_score'] = 0
        metadata_dict['max_score'] = 1
        return metadata_dict

class STSB(AbsTaskSTS):
    metadata = TaskMetadata(name='STSB', dataset={'path': 'C-MTEB/STSB', 'revision': '0cde68302b3541bb8b3c340dc0644b0b745b3dc0'}, description='A Chinese dataset for textual relatedness', reference='https://aclanthology.org/2021.emnlp-main.357', type='STS', category='s2s', modalities=['text'], eval_splits=['validation', 'test'], eval_langs=['cmn-Hans'], main_score='cosine_spearman', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@misc{xiao2024cpackpackagedresourcesadvance,\n      title={C-Pack: Packaged Resources To Advance General Chinese Embedding},\n      author={Shitao Xiao and Zheng Liu and Peitian Zhang and Niklas Muennighoff and Defu Lian and Jian-Yun Nie},\n      year={2024},\n      eprint={2309.07597},\n      archivePrefix={arXiv},\n      primaryClass={cs.CL},\n      url={https://arxiv.org/abs/2309.07597},\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['min_score'] = 0
        metadata_dict['max_score'] = 5
        return metadata_dict

class AFQMC(AbsTaskSTS):
    metadata = TaskMetadata(name='AFQMC', dataset={'path': 'C-MTEB/AFQMC', 'revision': 'b44c3b011063adb25877c13823db83bb193913c4'}, description='A Chinese dataset for textual relatedness', reference='https://aclanthology.org/2021.emnlp-main.357', type='STS', category='s2s', modalities=['text'], eval_splits=['validation'], eval_langs=['cmn-Hans'], main_score='cosine_spearman', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@inproceedings{raghu-etal-2021-end,\n    title = "End-to-End Learning of Flowchart Grounded Task-Oriented Dialogs",\n    author = "Raghu, Dinesh  and\n      Agarwal, Shantanu  and\n      Joshi, Sachindra  and\n      {Mausam}",\n    editor = "Moens, Marie-Francine  and\n      Huang, Xuanjing  and\n      Specia, Lucia  and\n      Yih, Scott Wen-tau",\n    booktitle = "Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing",\n    month = nov,\n    year = "2021",\n    address = "Online and Punta Cana, Dominican Republic",\n    publisher = "Association for Computational Linguistics",\n    url = "https://aclanthology.org/2021.emnlp-main.357",\n    doi = "10.18653/v1/2021.emnlp-main.357",\n    pages = "4348--4366",\n    abstract = "We propose a novel problem within end-to-end learning of task oriented dialogs (TOD), in which the dialog system mimics a troubleshooting agent who helps a user by diagnosing their problem (e.g., car not starting). Such dialogs are grounded in domain-specific flowcharts, which the agent is supposed to follow during the conversation. Our task exposes novel technical challenges for neural TOD, such as grounding an utterance to the flowchart without explicit annotation, referring to additional manual pages when user asks a clarification question, and ability to follow unseen flowcharts at test time. We release a dataset (FLODIAL) consisting of 2,738 dialogs grounded on 12 different troubleshooting flowcharts. We also design a neural model, FLONET, which uses a retrieval-augmented generation architecture to train the dialog agent. Our experiments find that FLONET can do zero-shot transfer to unseen flowcharts, and sets a strong baseline for future research.",\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['min_score'] = 0
        metadata_dict['max_score'] = 1
        return metadata_dict

class QBQTC(AbsTaskSTS):
    metadata = TaskMetadata(name='QBQTC', dataset={'path': 'C-MTEB/QBQTC', 'revision': '790b0510dc52b1553e8c49f3d2afb48c0e5c48b7'}, description='', reference='https://github.com/CLUEbenchmark/QBQTC/tree/main/dataset', type='STS', category='s2s', modalities=['text'], eval_splits=['test'], eval_langs=['cmn-Hans'], main_score='cosine_spearman', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation=None, descriptive_stats={'n_samples': None, 'avg_character_length': None})
