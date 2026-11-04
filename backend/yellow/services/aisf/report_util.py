# Private iCAP Yellow business implementation. Do not publish.
import json
import os

def gen_report_json(model_name, dataset, report_path, suc_count, total_count):
    acc = suc_count / total_count if total_count != 0 else 0
    report_map = {'name': f'{model_name}_{dataset}', 'dataset_name': dataset, 'model_name': model_name, 'score': acc, 'metrics': [{'categories': [{'macro_score': acc, 'name': ['default'], 'num': total_count, 'score': acc, 'subsets': [{'name': 'default', 'num': total_count, 'score': acc}]}], 'macro_score': acc, 'name': 'AverageAccuracy', 'num': total_count, 'score': acc}]}
    report_path_file: str = os.path.join(report_path, f'{dataset}.json')
    os.makedirs(os.path.dirname(report_path_file), exist_ok=True)
    with open(report_path_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report_map, ensure_ascii=False, indent=4))
