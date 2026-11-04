# Private iCAP Yellow implementation. Do not publish.
from mteb.abstasks.AbsTaskClassification import AbsTaskClassification
from mteb.abstasks.TaskMetadata import TaskMetadata

class TNews(AbsTaskClassification):
    metadata = TaskMetadata(name='TNews', description='Short Text Classification for News', reference='https://www.cluebenchmarks.com/introduce.html', dataset={'path': 'C-MTEB/TNews-classification', 'revision': '317f262bf1e6126357bbe89e875451e4b0938fe4'}, type='Classification', category='s2s', modalities=['text'], eval_splits=['validation'], eval_langs=['cmn-Hans'], main_score='accuracy', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@inproceedings {xu-etal-2020-clue,\n title = "{CLUE}: A {C}hinese Language Understanding Evaluation Benchmark",\n author = "Xu, Liang  and\n    Hu, Hai and\n    Zhang, Xuanwei and\n    Li, Lu and\n    Cao, Chenjie and\n    Li, Yudong and\n    Xu, Yechen and\n    Sun, Kai and\n    Yu, Dian and\n    Yu, Cong and\n    Tian, Yin and\n    Dong, Qianqian and\n    Liu, Weitang and\n    Shi, Bo and\n    Cui, Yiming and\n    Li, Junyi and\n    Zeng, Jun and\n    Wang, Rongzhao and\n    Xie, Weijian and\n    Li, Yanting and\n    Patterson, Yina and\n    Tian, Zuoyu and\n    Zhang, Yiwen and\n    Zhou, He and\n    Liu, Shaoweihua and\n    Zhao, Zhe and\n    Zhao, Qipeng and\n    Yue, Cong and\n    Zhang, Xinrui and\n    Yang, Zhengliang and\n    Richardson, Kyle and\n    Lan, Zhenzhong ",\n booktitle = "Proceedings of the 28th International Conference on Computational Linguistics",\n month = dec,\n year = "2020",\n address = "Barcelona, Spain (Online)",\n publisher = "International Committee on Computational Linguistics",\n url = "https://aclanthology.org/2020.coling-main.419",\n doi = "10.18653/v1/2020.coling-main.419",\n pages = "4762--4772",\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['samples_per_label'] = 32
        return metadata_dict

class IFlyTek(AbsTaskClassification):
    metadata = TaskMetadata(name='IFlyTek', description='Long Text classification for the description of Apps', reference='https://www.cluebenchmarks.com/introduce.html', dataset={'path': 'C-MTEB/IFlyTek-classification', 'revision': '421605374b29664c5fc098418fe20ada9bd55f8a'}, type='Classification', category='s2s', modalities=['text'], eval_splits=['validation'], eval_langs=['cmn-Hans'], main_score='accuracy', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@inproceedings {xu-etal-2020-clue,\n title = "{CLUE}: A {C}hinese Language Understanding Evaluation Benchmark",\n author = "Xu, Liang  and\n    Hu, Hai and\n    Zhang, Xuanwei and\n    Li, Lu and\n    Cao, Chenjie and\n    Li, Yudong and\n    Xu, Yechen and\n    Sun, Kai and\n    Yu, Dian and\n    Yu, Cong and\n    Tian, Yin and\n    Dong, Qianqian and\n    Liu, Weitang and\n    Shi, Bo and\n    Cui, Yiming and\n    Li, Junyi and\n    Zeng, Jun and\n    Wang, Rongzhao and\n    Xie, Weijian and\n    Li, Yanting and\n    Patterson, Yina and\n    Tian, Zuoyu and\n    Zhang, Yiwen and\n    Zhou, He and\n    Liu, Shaoweihua and\n    Zhao, Zhe and\n    Zhao, Qipeng and\n    Yue, Cong and\n    Zhang, Xinrui and\n    Yang, Zhengliang and\n    Richardson, Kyle and\n    Lan, Zhenzhong ",\n booktitle = "Proceedings of the 28th International Conference on Computational Linguistics",\n month = dec,\n year = "2020",\n address = "Barcelona, Spain (Online)",\n publisher = "International Committee on Computational Linguistics",\n url = "https://aclanthology.org/2020.coling-main.419",\n doi = "10.18653/v1/2020.coling-main.419",\n pages = "4762--4772",\n abstract = "The advent of natural language understanding (NLU) benchmarks for English, such as GLUE and SuperGLUE allows new NLU models to be evaluated across a diverse set of tasks. These comprehensive benchmarks have facilitated a broad range of research and applications in natural language processing (NLP). The problem, however, is that most such benchmarks are limited to English, which has made it difficult to replicate many of the successes in English NLU for other languages. To help remedy this issue, we introduce the first large-scale Chinese Language Understanding Evaluation (CLUE) benchmark. CLUE is an open-ended, community-driven project that brings together 9 tasks spanning several well-established single-sentence/sentence-pair classification tasks, as well as machine reading comprehension, all on original Chinese text. To establish results on these tasks, we report scores using an exhaustive set of current state-of-the-art pre-trained Chinese models (9 in total). We also introduce a number of supplementary datasets and additional tools to help facilitate further progress on Chinese NLU. Our benchmark is released at https://www.cluebenchmarks.com",\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['samples_per_label'] = 32
        metadata_dict['n_experiments'] = 5
        return metadata_dict

class MultilingualSentiment(AbsTaskClassification):
    metadata = TaskMetadata(name='MultilingualSentiment', description='A collection of multilingual sentiments datasets grouped into 3 classes -- positive, neutral, negative', reference='https://github.com/tyqiangz/multilingual-sentiment-datasets', dataset={'path': 'C-MTEB/MultilingualSentiment-classification', 'revision': '46958b007a63fdbf239b7672c25d0bea67b5ea1a'}, type='Classification', category='s2s', modalities=['text'], eval_splits=['validation', 'test'], eval_langs=['cmn-Hans'], main_score='accuracy', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation=None, descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['samples_per_label'] = 32
        return metadata_dict

class JDReview(AbsTaskClassification):
    metadata = TaskMetadata(name='JDReview', description='review for iphone', reference='https://aclanthology.org/2023.nodalida-1.20/', dataset={'path': 'C-MTEB/JDReview-classification', 'revision': 'b7c64bd89eb87f8ded463478346f76731f07bf8b'}, type='Classification', category='s2s', modalities=['text'], eval_splits=['test'], eval_langs=['cmn-Hans'], main_score='accuracy', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@article{xiao2023c,\n  title={C-pack: Packaged resources to advance general chinese embedding},\n  author={Xiao, Shitao and Liu, Zheng and Zhang, Peitian and Muennighof, Niklas},\n  journal={arXiv preprint arXiv:2309.07597},\n  year={2023}\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['samples_per_label'] = 32
        return metadata_dict

class OnlineShopping(AbsTaskClassification):
    metadata = TaskMetadata(name='OnlineShopping', description='Sentiment Analysis of User Reviews on Online Shopping Websites', reference='https://aclanthology.org/2023.nodalida-1.20/', dataset={'path': 'C-MTEB/OnlineShopping-classification', 'revision': 'e610f2ebd179a8fda30ae534c3878750a96db120'}, type='Classification', category='s2s', modalities=['text'], eval_splits=['test'], eval_langs=['cmn-Hans'], main_score='accuracy', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@article{xiao2023c,\n  title={C-pack: Packaged resources to advance general chinese embedding},\n  author={Xiao, Shitao and Liu, Zheng and Zhang, Peitian and Muennighof, Niklas},\n  journal={arXiv preprint arXiv:2309.07597},\n  year={2023}\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['samples_per_label'] = 32
        return metadata_dict

class Waimai(AbsTaskClassification):
    metadata = TaskMetadata(name='Waimai', description='Sentiment Analysis of user reviews on takeaway platforms', reference='https://aclanthology.org/2023.nodalida-1.20/', dataset={'path': 'C-MTEB/waimai-classification', 'revision': '339287def212450dcaa9df8c22bf93e9980c7023'}, type='Classification', category='s2s', modalities=['text'], eval_splits=['test'], eval_langs=['cmn-Hans'], main_score='accuracy', date=None, domains=None, task_subtypes=None, license=None, annotations_creators=None, dialect=None, sample_creation=None, bibtex_citation='@article{xiao2023c,\n  title={C-pack: Packaged resources to advance general chinese embedding},\n  author={Xiao, Shitao and Liu, Zheng and Zhang, Peitian and Muennighof, Niklas},\n  journal={arXiv preprint arXiv:2309.07597},\n  year={2023}\n}', descriptive_stats={'n_samples': None, 'avg_character_length': None})

    @property
    def metadata_dict(self) -> dict[str, str]:
        metadata_dict = super().metadata_dict
        metadata_dict['samples_per_label'] = 32
        return metadata_dict
