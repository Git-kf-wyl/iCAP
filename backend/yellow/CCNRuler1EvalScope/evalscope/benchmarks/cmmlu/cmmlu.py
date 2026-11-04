# Private iCAP Yellow implementation. Do not publish.
import datasets
import os
import pandas as pd
_CITATION = '@misc{li2023cmmlu,\n      title={CMMLU: Measuring massive multitask language understanding in Chinese},\n      author={Haonan Li and Yixuan Zhang and Fajri Koto and Yifei Yang and Hai Zhao and Yeyun Gong and Nan Duan and Timothy Baldwin},\n      year={2023},\n      eprint={2306.09212},\n      archivePrefix={arXiv},\n      primaryClass={cs.CL}\n}\n'
_DESCRIPTION = 'CMMLU is a comprehensive Chinese assessment suite specifically designed to evaluate the advanced knowledge and reasoning abilities of LLMs within the Chinese language and cultural context.\n'
_HOMEPAGE = 'https://modelscope.cn/datasets/modelscope/cmmlu/summary'
_URL = 'https://modelscope.cn/api/v1/datasets/modelscope/cmmlu/repo?Revision=master&FilePath=cmmlu_v1_0_1.zip'
task_list = ['agronomy', 'anatomy', 'ancient_chinese', 'arts', 'astronomy', 'business_ethics', 'chinese_civil_service_exam', 'chinese_driving_rule', 'chinese_food_culture', 'chinese_foreign_policy', 'chinese_history', 'chinese_literature', 'chinese_teacher_qualification', 'clinical_knowledge', 'college_actuarial_science', 'college_education', 'college_engineering_hydrology', 'college_law', 'college_mathematics', 'college_medical_statistics', 'college_medicine', 'computer_science', 'computer_security', 'conceptual_physics', 'construction_project_management', 'economics', 'education', 'electrical_engineering', 'elementary_chinese', 'elementary_commonsense', 'elementary_information_and_technology', 'elementary_mathematics', 'ethnology', 'food_science', 'genetics', 'global_facts', 'high_school_biology', 'high_school_chemistry', 'high_school_geography', 'high_school_mathematics', 'high_school_physics', 'high_school_politics', 'human_sexuality', 'international_law', 'journalism', 'jurisprudence', 'legal_and_moral_basis', 'logical', 'machine_learning', 'management', 'marketing', 'marxist_theory', 'modern_chinese', 'nutrition', 'philosophy', 'professional_accounting', 'professional_law', 'professional_medicine', 'professional_psychology', 'public_relations', 'security_study', 'sociology', 'sports_science', 'traditional_chinese_medicine', 'virology', 'world_history', 'world_religions']

class CMMLUConfig(datasets.BuilderConfig):

    def __init__(self, **kwargs):
        super().__init__(version=datasets.Version('1.0.1'), **kwargs)

class CMMLU(datasets.GeneratorBasedBuilder):
    BUILDER_CONFIGS = [CMMLUConfig(name=task_name) for task_name in task_list]

    def _info(self):
        features = datasets.Features({'Question': datasets.Value('string'), 'A': datasets.Value('string'), 'B': datasets.Value('string'), 'C': datasets.Value('string'), 'D': datasets.Value('string'), 'Answer': datasets.Value('string')})
        return datasets.DatasetInfo(description=_DESCRIPTION, features=features, homepage=_HOMEPAGE, citation=_CITATION)

    def _split_generators(self, dl_manager):
        data_dir = dl_manager.download_and_extract(_URL)
        task_name = self.config.name
        return [datasets.SplitGenerator(name=datasets.Split.TEST, gen_kwargs={'filepath': os.path.join(data_dir, f'test/{task_name}.csv')}), datasets.SplitGenerator(name=datasets.Split('dev'), gen_kwargs={'filepath': os.path.join(data_dir, f'dev/{task_name}.csv')})]

    def _generate_examples(self, filepath):
        df = pd.read_csv(filepath, header=0, index_col=0, encoding='utf-8')
        for i, instance in enumerate(df.to_dict(orient='records')):
            yield (i, instance)
