# Private iCAP Yellow business implementation. Do not publish.
from utils.consts import *
from utils.utils import get_model_info_list

def load_model_info(model_id):
    """加载模型配置信息"""
    model_cfg = get_model_info_list()
    for cfg in model_cfg:
        if cfg['model_id'] == model_id:
            return cfg
    print(f"⚠️ 警告: Model '{model_id}' not found in configuration.")
    return None

def get_score(task, model_name, testcase):
    """从任务结果中获取指定数据集的分数"""
    for res in task['result'][model_name]:
        if res['dataset_name'] == testcase:
            return (res['score'], res['create_time'])
    raise ValueError(f'Dataset {testcase} not found for model {model_name}.')

def create_new_config(model_info, testcase, score, metric, create_time):
    """创建新的测试配置"""
    return {'dataset_name': testcase, 'score': score, 'history': {create_time: score}, 'metrics': metric, 'publisher': model_info['info']['vendor'], 'type': ','.join(model_info['info']['category']), 'test_time': create_time}

def add_new_item(old_res, model_id, testcase, task, model_name):
    """添加新的测试结果到旧的结果中"""
    model_info = load_model_info(model_id)
    old_res[model_id] = []
    average_score = 0
    count = 0
    create_time = task['createTime']
    for case in testcase:
        score, create_time = get_score(task, model_name, case)
        count += 1
        average_score += score
        new_cfg = create_new_config(model_info, case, score, [], create_time)
        old_res[model_id].append(new_cfg)
    average_score = round(average_score / count, 4) if count != 0 else 0
    new_cfg = create_new_config(model_info, 'average', average_score, [], create_time)
    old_res[model_id].append(new_cfg)

def add_new_eld(old_res, model_id, testcase, task, model_name):
    """添加新的测试结果到旧的结果中（儿童伴读：合并所有业务类别到一个 entry）"""
    old_res[model_id] = []
    create_time = task['createTime']
    subsets = task['taskConfig']['dataset_args'][0]['subset_list']
    subsets_result = task['result'][model_name][0]['metrics'][0]['categories'][0]['subsets']
    subsets_score = []
    total_score = 0.0
    for case in testcase:
        for item in subsets_result:
            item_name = item.get('name', '')
            if case in item_name or item_name in case:
                subsets_score.append(item)
                total_score += item.get('score', 0.0)
                break
    avg_score = round(total_score / len(testcase), 4) if testcase else 0.0
    new_cfg = {'dataset_name': 'aisf_banxue', 'metrics': [{'categories': [{'subsets': subsets_score}]}], 'score': avg_score, 'test_time': create_time}
    print(f'add_new_eld new_cfg:{new_cfg}')
    old_res[model_id].append(new_cfg)

def modify_test_eld(old_res, model_id, testcase, task, model_name):
    """修改已存在的测试结果（儿童伴读：更新/添加指定业务类别的子集数据）"""
    create_time = task['createTime']
    subsets_result = task['result'][model_name][0]['metrics'][0]['categories'][0]['subsets']
    idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == 'aisf_banxue'), -1)
    if idx == -1:
        print('modify_test_eld: aisf_banxue entry not found, creating new one.')
        add_new_eld(old_res, model_id, testcase, task, model_name)
        return
    existing_subsets = old_res[model_id][idx]['metrics'][0]['categories'][0]['subsets']
    existing_names = {s.get('name') for s in existing_subsets}
    for case in testcase:
        matched_item = None
        for item in subsets_result:
            item_name = item.get('name', '')
            if case in item_name or item_name in case:
                matched_item = item
                break
        if matched_item is None:
            print(f"modify_test_eld: case '{case}' not found in task result, skipping.")
            continue
        item_name = matched_item.get('name', case)
        if item_name in existing_names:
            for existing in existing_subsets:
                if existing.get('name') == item_name:
                    existing['score'] = matched_item.get('score', 0.0)
                    existing['subsets'] = matched_item.get('subsets', [])
                    break
        else:
            existing_subsets.append(matched_item)
            existing_names.add(item_name)
    total_score = 0.0
    count = 0
    for s in existing_subsets:
        total_score += s.get('score', 0.0)
        count += 1
    avg_score = round(total_score / count, 4) if count > 0 else 0.0
    if 'history' not in old_res[model_id][idx]:
        old_res[model_id][idx]['history'] = {old_res[model_id][idx].get('test_time', ''): old_res[model_id][idx].get('score', 0.0)}
    else:
        old_res[model_id][idx]['history'].update({old_res[model_id][idx].get('test_time', ''): old_res[model_id][idx].get('score', 0.0)})
    old_res[model_id][idx]['score'] = avg_score
    old_res[model_id][idx]['test_time'] = create_time
    print(f"modify_test_eld updated: score={avg_score}, subsets={[s.get('name') for s in existing_subsets]}")

def add_new_item_ruler2_yitu(old_res, model_id, testcase, task, model_name):
    """添加新的意图测试结果到榜单中（aisf_llm_yitu）"""
    if model_id not in old_res.keys():
        old_res[model_id] = []
    create_time = task['createTime']
    subsets_result = task['result'][model_name][0]['metrics'][0]['categories'][0]['subsets']
    chart_subsets = []
    total_score = 0
    if len(subsets_result) == 1 and subsets_result[0].get('name') == 'default':
        default_score = subsets_result[0].get('score', 0.0)
        chart_subsets = [{'name': '单意图', 'score': default_score}, {'name': '两意图', 'score': default_score}, {'name': '三意图', 'score': default_score}]
        total_score = default_score
    else:
        for subset in subsets_result:
            sname = subset.get('name', '')
            sscore = subset.get('score', 0.0)
            chart_subsets.append({'name': sname, 'score': sscore})
            total_score += sscore
        total_score = round(total_score / len(chart_subsets), 4) if chart_subsets else 0.0
    model_info = load_model_info(model_id)
    new_cfg = {'dataset_name': 'aisf_llm_yitu', 'metrics': [{'categories': [{'subsets': chart_subsets}]}], 'score': total_score, 'test_time': create_time}
    if model_info:
        new_cfg['publisher'] = model_info['info']['vendor']
        new_cfg['type'] = ','.join(model_info['info']['category'])
    old_res[model_id].append(new_cfg)

def modify_test_res_ruler2_yitu(old_res, model_id, testcase, task, model_name):
    """修改已存在的意图测试结果（aisf_llm_yitu）"""
    create_time = task['createTime']
    idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == 'aisf_llm_yitu'), -1)
    if idx == -1:
        add_new_item_ruler2_yitu(old_res, model_id, testcase, task, model_name)
        return
    subsets_result = task['result'][model_name][0]['metrics'][0]['categories'][0]['subsets']
    existing_subsets = old_res[model_id][idx]['metrics'][0]['categories'][0]['subsets']
    existing_names = {s.get('name') for s in existing_subsets}
    if len(subsets_result) == 1 and subsets_result[0].get('name') == 'default':
        default_score = subsets_result[0].get('score', 0.0)
        for name in ['单意图', '两意图', '三意图']:
            found = False
            for es in existing_subsets:
                if es['name'] == name:
                    es['score'] = default_score
                    found = True
                    break
            if not found:
                existing_subsets.append({'name': name, 'score': default_score})
    else:
        for subset in subsets_result:
            sname = subset.get('name', '')
            sscore = subset.get('score', 0.0)
            if sname in existing_names:
                for es in existing_subsets:
                    if es['name'] == sname:
                        es['score'] = sscore
                        break
            else:
                existing_subsets.append({'name': sname, 'score': sscore})
                existing_names.add(sname)
    average_score = 0
    count = 0
    for subset in existing_subsets:
        count += 1
        average_score += subset['score']
    average_score = round(average_score / count, 4) if count != 0 else 0
    if 'history' not in old_res[model_id][idx]:
        old_res[model_id][idx]['history'] = {old_res[model_id][idx]['test_time']: average_score}
    else:
        old_res[model_id][idx]['history'].update({old_res[model_id][idx]['test_time']: average_score})
    old_res[model_id][idx]['score'] = average_score
    old_res[model_id][idx]['test_time'] = create_time

def add_new_item_ruler2_memory(old_res, model_id, testcase, task, model_name):
    """添加新的记忆测试结果到榜单中（aisf_memory_cuiqu 和 aisf_memory_zhaohui）"""
    if model_id not in old_res.keys():
        old_res[model_id] = []
    create_time = task['createTime']
    model_info = load_model_info(model_id)
    subsets_result = task['result'][model_name][0]['metrics'][0]['categories'][0]['subsets']
    chart_groups = {}
    for subset in subsets_result:
        sname = subset.get('name', '')
        if sname in MEMORY_TASK_SUBSET_MAP:
            chart_dataset_name, chart_subset_name = MEMORY_TASK_SUBSET_MAP[sname]
            if chart_dataset_name not in chart_groups:
                chart_groups[chart_dataset_name] = []
            chart_groups[chart_dataset_name].append({'name': chart_subset_name, 'score': subset.get('score', 0.0)})
    for chart_dataset_name, chart_subsets in chart_groups.items():
        avg_score = round(sum((s['score'] for s in chart_subsets)) / len(chart_subsets), 4) if chart_subsets else 0.0
        new_cfg = {'dataset_name': chart_dataset_name, 'metrics': [{'categories': [{'subsets': chart_subsets}]}], 'score': avg_score, 'test_time': create_time}
        if model_info:
            new_cfg['publisher'] = model_info['info']['vendor']
            new_cfg['type'] = ','.join(model_info['info']['category'])
        old_res[model_id].append(new_cfg)
        print(f'add_new_item_ruler2_memory: added {chart_dataset_name}, score={avg_score}, subsets={chart_subsets}')

def modify_test_res_ruler2_memory(old_res, model_id, testcase, task, model_name):
    """修改已存在的记忆测试结果（aisf_memory_cuiqu 和 aisf_memory_zhaohui）"""
    create_time = task['createTime']
    subsets_result = task['result'][model_name][0]['metrics'][0]['categories'][0]['subsets']
    chart_groups = {}
    for subset in subsets_result:
        sname = subset.get('name', '')
        if sname in MEMORY_TASK_SUBSET_MAP:
            chart_dataset_name, chart_subset_name = MEMORY_TASK_SUBSET_MAP[sname]
            if chart_dataset_name not in chart_groups:
                chart_groups[chart_dataset_name] = []
            chart_groups[chart_dataset_name].append({'name': chart_subset_name, 'score': subset.get('score', 0.0)})
    for chart_dataset_name, new_subsets in chart_groups.items():
        idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == chart_dataset_name), -1)
        if idx == -1:
            print(f'modify_test_res_ruler2_memory: {chart_dataset_name} not found, creating new.')
            existing_chart_dataset_names = {g['dataset_name'] for g in old_res[model_id] if 'dataset_name' in g}
            model_info = load_model_info(model_id)
            avg_score = round(sum((s['score'] for s in new_subsets)) / len(new_subsets), 4) if new_subsets else 0.0
            new_cfg = {'dataset_name': chart_dataset_name, 'metrics': [{'categories': [{'subsets': new_subsets}]}], 'score': avg_score, 'test_time': create_time}
            if model_info:
                new_cfg['publisher'] = model_info['info']['vendor']
                new_cfg['type'] = ','.join(model_info['info']['category'])
            old_res[model_id].append(new_cfg)
            continue
        existing_subsets = old_res[model_id][idx]['metrics'][0]['categories'][0]['subsets']
        existing_names = {s.get('name') for s in existing_subsets}
        for new_subset in new_subsets:
            nsname = new_subset['name']
            if nsname in existing_names:
                for es in existing_subsets:
                    if es['name'] == nsname:
                        es['score'] = new_subset['score']
                        break
            else:
                existing_subsets.append(new_subset)
                existing_names.add(nsname)
        avg_score = 0
        count = 0
        for s in existing_subsets:
            count += 1
            avg_score += s['score']
        avg_score = round(avg_score / count, 4) if count != 0 else 0
        if 'history' not in old_res[model_id][idx]:
            old_res[model_id][idx]['history'] = {old_res[model_id][idx].get('test_time', ''): avg_score}
        else:
            old_res[model_id][idx]['history'].update({old_res[model_id][idx].get('test_time', ''): avg_score})
        old_res[model_id][idx]['score'] = avg_score
        old_res[model_id][idx]['test_time'] = create_time
        print(f"modify_test_res_ruler2_memory: updated {chart_dataset_name}, score={avg_score}, subsets={[s.get('name') for s in existing_subsets]}")

def add_new_item_ruler2(old_res, model_id, testcase, task, model_name):
    if model_id not in old_res.keys():
        old_res[model_id] = []
    if len(testcase) < 1:
        return
    new_metrics = [{'categories': [{'subsets': []}]}]
    average_score = 0
    count = 0
    create_time = task['createTime']
    for case in testcase:
        score, _ = get_score(task, model_name, case)
        if case in TASK_2_CHART_DATASET.keys():
            count += 1
            average_score += score
            new_metrics[0]['categories'][0]['subsets'].append({'name': TASK_2_CHART_DATASET.get(case)[1], 'score': score})
    average_score = round(average_score / count, 4) if count != 0 else 0
    model_info = load_model_info(model_id)
    new_cfg = create_new_config(model_info, TASK_2_CHART_DATASET[testcase[0]][0], average_score, new_metrics, create_time)
    old_res[model_id].append(new_cfg)

def modify_test_res(old_res, model_id, testcase, task, model_name):
    """修改现有的测试结果或添加新的测试结果"""
    model_info = load_model_info(model_id)
    for case in testcase:
        score, create_time = get_score(task, model_name, case)
        idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == case), -1)
        if idx != -1:
            if 'history' not in old_res[model_id][idx]:
                old_res[model_id][idx]['history'] = {old_res[model_id][idx]['test_time']: score}
            else:
                old_res[model_id][idx]['history'].update({old_res[model_id][idx]['test_time']: score})
            old_res[model_id][idx]['score'] = score
            old_res[model_id][idx]['test_time'] = create_time
        else:
            new_cfg = create_new_config(model_info, case, score, [], create_time)
            old_res[model_id].append(new_cfg)
    average_score = 0
    count = 0
    for test_info in old_res[model_id]:
        if 'average' in test_info['dataset_name']:
            continue
        score = test_info['score']
        count += 1
        average_score += score
    average_score = round(average_score / count, 4) if count != 0 else 0
    create_time = task['createTime']
    for test_info in old_res[model_id]:
        if 'average' in test_info['dataset_name']:
            test_info['score'] = average_score
            test_info['test_time'] = create_time

def _extract_gaixie_subsets(task, model_name, testcase):
    """从改写任务结果中提取榜单 subsets（aisf_llm_gaixie）。

    兼容两种产物：
      - 本地上传（虚拟任务）：report 走统一结构 metrics[0]['categories'][0]['subsets']，
        即「外挂fewshot库」「不外挂fewshot库」两个子业务的 subsets；
      - 在线：result[model_name] 为按 testcase 拆分的多个 entry，
        metric_name 形如「外挂fewshot库」/「不外挂fewshot库」。
    返回 (chart_subsets, score)。
    """
    try:
        subsets = task['result'][model_name][0]['metrics'][0]['categories'][0]['subsets']
        if subsets:
            chart_subsets = [{'name': s.get('name', ''), 'score': s.get('score', 0.0)} for s in subsets]
            avg_score = round(sum((s['score'] for s in chart_subsets)) / len(chart_subsets), 4) if chart_subsets else 0.0
            return (chart_subsets, avg_score)
    except Exception:
        pass
    result_entries = task['result'].get(model_name, [])
    chart_subsets = []
    for case in testcase:
        entry = next((e for e in result_entries if e.get('metrics')[0]['name'] == case), None)
        if entry is None:
            continue
        metrics = entry.get('metrics', [])
        for metric in metrics:
            metric_name = metric.get('name', '')
            metric_score = metric.get('score', 0.0)
            if metric_name:
                if not any((s['name'] == metric_name for s in chart_subsets)):
                    chart_subsets.append({'name': metric_name, 'score': metric_score})
    avg_score = round(sum((s['score'] for s in chart_subsets)) / len(chart_subsets), 4) if chart_subsets else 0.0
    return (chart_subsets, avg_score)

def add_new_item_ruler2_gaixie(old_res, model_id, testcase, task, model_name):
    """添加新的改写测试结果到榜单中（aisf_llm_gaixie）"""
    if model_id not in old_res.keys():
        old_res[model_id] = []
    create_time = task['createTime']
    model_info = load_model_info(model_id)
    chart_subsets, avg_score = _extract_gaixie_subsets(task, model_name, testcase)
    new_cfg = {'dataset_name': 'aisf_llm_gaixie', 'metrics': [{'categories': [{'subsets': chart_subsets}]}], 'score': avg_score, 'test_time': create_time}
    if model_info:
        new_cfg['publisher'] = model_info['info']['vendor']
        new_cfg['type'] = ','.join(model_info['info']['category'])
    print(f'add_new_item_ruler2_gaixie: score={avg_score}, subsets={chart_subsets}')
    old_res[model_id].append(new_cfg)

def modify_test_res_ruler2_gaixie(old_res, model_id, testcase, task, model_name):
    """修改已存在的改写测试结果（aisf_llm_gaixie）"""
    create_time = task['createTime']
    idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == 'aisf_llm_gaixie'), -1)
    if idx == -1:
        add_new_item_ruler2_gaixie(old_res, model_id, testcase, task, model_name)
        return
    chart_subsets, _ = _extract_gaixie_subsets(task, model_name, testcase)
    existing_subsets = old_res[model_id][idx]['metrics'][0]['categories'][0]['subsets']
    existing_names = {s.get('name') for s in existing_subsets}
    for subset in chart_subsets:
        sname = subset['name']
        sscore = subset['score']
        if sname in existing_names:
            for es in existing_subsets:
                if es['name'] == sname:
                    es['score'] = sscore
                    break
        else:
            existing_subsets.append({'name': sname, 'score': sscore})
            existing_names.add(sname)
    avg_score = 0
    count = 0
    for s in existing_subsets:
        count += 1
        avg_score += s['score']
    avg_score = round(avg_score / count, 4) if count != 0 else 0
    if 'history' not in old_res[model_id][idx]:
        old_res[model_id][idx]['history'] = {old_res[model_id][idx].get('test_time', ''): avg_score}
    else:
        old_res[model_id][idx]['history'].update({old_res[model_id][idx].get('test_time', ''): avg_score})
    old_res[model_id][idx]['score'] = avg_score
    old_res[model_id][idx]['test_time'] = create_time
    print(f'modify_test_res_ruler2_gaixie: score={avg_score}, subsets={[s for s in existing_subsets]}')

def _extract_subsets_from_task(task, model_name):
    """从任务结果的 report 中提取榜单 subsets。

    skill提参 / GUI提参 的 report（由壳 _write_report_json 产出，并经 update_eval_res
    反填到 task['result']）为单子集结构。此处做容错：取第一个 entry 的 subsets，
    缺省时退回 task['result'][0]['score']。
    """
    try:
        entries = task['result'][model_name]
        entry = entries[0]
        subsets = entry['metrics'][0]['categories'][0]['subsets']
        if subsets:
            chart_subsets = [{'name': s.get('name', ''), 'score': s.get('score', 0.0)} for s in subsets]
            score = float(chart_subsets[0]['score'] or 0.0)
            return (chart_subsets, score)
        return ([], float(entry['metrics'][0]['score'] or 0.0))
    except Exception:
        try:
            return ([], float(task['result'][model_name][0]['score'] or 0.0))
        except Exception:
            return ([], 0.0)

def _new_chart_entry(model_id, task, model_name, dataset_name, chart_subsets, score):
    """构造一个榜单 entry（与 yitu/gaixie 的 new_cfg 结构一致）。

    模型未配置（load_model_info 返回 None）时跳过 publisher/type，与记忆分支的
    add_new_item_ruler2_memory 行为一致，避免下标错误。
    """
    model_info = load_model_info(model_id)
    entry = {'dataset_name': dataset_name, 'metrics': [{'categories': [{'subsets': chart_subsets}]}], 'score': score, 'test_time': task['createTime']}
    if model_info:
        entry['publisher'] = model_info['info']['vendor']
        entry['type'] = ','.join(model_info['info']['category'])
    return entry

def add_new_item_ruler2_skilltican(old_res, model_id, testcase, task, model_name):
    """添加新的 skill提参 测试结果到榜单中（aisf_llm_skilltican）"""
    if model_id not in old_res.keys():
        old_res[model_id] = []
    chart_subsets, score = _extract_subsets_from_task(task, model_name)
    new_cfg = _new_chart_entry(model_id, task, model_name, 'aisf_llm_skilltican', chart_subsets, score)
    print(f'add_new_item_ruler2_skilltican: dataset=aisf_llm_skilltican, score={score}, subsets={chart_subsets}')
    old_res[model_id].append(new_cfg)

def modify_test_res_ruler2_skilltican(old_res, model_id, testcase, task, model_name):
    """修改已存在的 skill提参 测试结果（aisf_llm_skilltican）"""
    create_time = task['createTime']
    idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == 'aisf_llm_skilltican'), -1)
    if idx == -1:
        add_new_item_ruler2_skilltican(old_res, model_id, testcase, task, model_name)
        return
    chart_subsets, score = _extract_subsets_from_task(task, model_name)
    existing = old_res[model_id][idx]
    existing['metrics'][0]['categories'][0]['subsets'] = chart_subsets or existing['metrics'][0]['categories'][0]['subsets']
    if 'history' not in existing:
        existing['history'] = {existing.get('test_time', ''): score}
    else:
        existing['history'].update({existing.get('test_time', ''): score})
    existing['score'] = score
    existing['test_time'] = create_time
    print(f'modify_test_res_ruler2_skilltican: score={score}, subsets={chart_subsets}')

def add_new_item_ruler2_guican(old_res, model_id, testcase, task, model_name):
    """添加新的 GUI提参 测试结果到榜单中（aisf_llm_guican）"""
    if model_id not in old_res.keys():
        old_res[model_id] = []
    chart_subsets, score = _extract_subsets_from_task(task, model_name)
    new_cfg = _new_chart_entry(model_id, task, model_name, 'aisf_llm_guican', chart_subsets, score)
    print(f'add_new_item_ruler2_guican: dataset=aisf_llm_guican, score={score}, subsets={chart_subsets}')
    old_res[model_id].append(new_cfg)

def modify_test_res_ruler2_guican(old_res, model_id, testcase, task, model_name):
    """修改已存在的 GUI提参 测试结果（aisf_llm_guican）"""
    create_time = task['createTime']
    idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == 'aisf_llm_guican'), -1)
    if idx == -1:
        add_new_item_ruler2_guican(old_res, model_id, testcase, task, model_name)
        return
    chart_subsets, score = _extract_subsets_from_task(task, model_name)
    existing = old_res[model_id][idx]
    existing['metrics'][0]['categories'][0]['subsets'] = chart_subsets or existing['metrics'][0]['categories'][0]['subsets']
    if 'history' not in existing:
        existing['history'] = {existing.get('test_time', ''): score}
    else:
        existing['history'].update({existing.get('test_time', ''): score})
    existing['score'] = score
    existing['test_time'] = create_time
    print(f'modify_test_res_ruler2_guican: score={score}, subsets={chart_subsets}')

def _extract_subsets_from_banxue_task(task, model_name):
    """从伴学提参任务结果中提取榜单 subsets 与总分。

    banxue report 为单 metrics / 单 categories / 多个 subsets（提醒/总结/提参），
    categories.score 即加权总分。与 _extract_subsets_from_task 不同：banxue 需要
    保留所有子集，且总分取 categories 层 score 而非 subsets[0].score。
    """
    try:
        entry = task['result'][model_name][0]
        category = entry['metrics'][0]['categories'][0]
        subsets = category.get('subsets') or []
        chart_subsets = [{'name': s.get('name', ''), 'score': s.get('score', 0.0)} for s in subsets]
        score = float(category.get('score') or entry['metrics'][0].get('score') or entry.get('score') or 0.0)
        return (chart_subsets, score)
    except Exception:
        try:
            return ([], float(task['result'][model_name][0].get('score') or 0.0))
        except Exception:
            return ([], 0.0)

def add_new_item_ruler2_banxue(old_res, model_id, testcase, task, model_name):
    """添加新的伴学提参测试结果到榜单中（aisf_llm_banxue）"""
    if model_id not in old_res.keys():
        old_res[model_id] = []
    chart_subsets, score = _extract_subsets_from_banxue_task(task, model_name)
    new_cfg = _new_chart_entry(model_id, task, model_name, 'aisf_llm_banxue', chart_subsets, score)
    print(f'add_new_item_ruler2_banxue: dataset=aisf_llm_banxue, score={score}, subsets={chart_subsets}')
    old_res[model_id].append(new_cfg)

def modify_test_res_ruler2_banxue(old_res, model_id, testcase, task, model_name):
    """修改已存在的伴学提参测试结果（aisf_llm_banxue）"""
    create_time = task['createTime']
    idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == 'aisf_llm_banxue'), -1)
    if idx == -1:
        add_new_item_ruler2_banxue(old_res, model_id, testcase, task, model_name)
        return
    chart_subsets, score = _extract_subsets_from_banxue_task(task, model_name)
    existing = old_res[model_id][idx]
    existing['metrics'][0]['categories'][0]['subsets'] = chart_subsets or existing['metrics'][0]['categories'][0]['subsets']
    if 'history' not in existing:
        existing['history'] = {existing.get('test_time', ''): score}
    else:
        existing['history'].update({existing.get('test_time', ''): score})
    existing['score'] = score
    existing['test_time'] = create_time
    print(f'modify_test_res_ruler2_banxue: score={score}, subsets={chart_subsets}')

def add_new_item_ruler2_coordinator(old_res, model_id, testcase, task, model_name):
    """添加新的 Coordinate 测试结果到榜单中（aisf_llm_coordinator）"""
    if model_id not in old_res.keys():
        old_res[model_id] = []
    chart_subsets, score = _extract_subsets_from_task(task, model_name)
    new_cfg = _new_chart_entry(model_id, task, model_name, 'aisf_llm_coordinator', chart_subsets, score)
    print(f'add_new_item_ruler2_coordinator: dataset=aisf_llm_coordinator, score={score}, subsets={chart_subsets}')
    old_res[model_id].append(new_cfg)

def modify_test_res_ruler2_coordinator(old_res, model_id, testcase, task, model_name):
    """修改已存在的 Coordinate 测试结果（aisf_llm_coordinator）"""
    create_time = task['createTime']
    idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == 'aisf_llm_coordinator'), -1)
    if idx == -1:
        add_new_item_ruler2_coordinator(old_res, model_id, testcase, task, model_name)
        return
    chart_subsets, score = _extract_subsets_from_task(task, model_name)
    existing = old_res[model_id][idx]
    existing['metrics'][0]['categories'][0]['subsets'] = chart_subsets or existing['metrics'][0]['categories'][0]['subsets']
    if 'history' not in existing:
        existing['history'] = {existing.get('test_time', ''): score}
    else:
        existing['history'].update({existing.get('test_time', ''): score})
    existing['score'] = score
    existing['test_time'] = create_time
    print(f'modify_test_res_ruler2_coordinator: score={score}, subsets={chart_subsets}')

def modify_test_res_ruler2(old_res, model_id, testcase, task, model_name):
    chart_dataset_name = TASK_2_CHART_DATASET[testcase[0]][0]
    for case in testcase:
        if case not in TASK_2_CHART_DATASET.keys():
            print('case not in ruler2 table.')
            return
        if chart_dataset_name != TASK_2_CHART_DATASET[case][0]:
            print('modify_test_res_ruler2 failed.')
            return
    idx = next((i for i, test_info in enumerate(old_res[model_id]) if 'dataset_name' in test_info and test_info['dataset_name'] == chart_dataset_name), -1)
    if idx != -1:
        print(f'ruler2 find case: {chart_dataset_name}, index: {idx}')
        create_time = task['createTime']
        subsets = old_res[model_id][idx]['metrics'][0]['categories'][0]['subsets']
        for case in testcase:
            score, _ = get_score(task, model_name, case)
            target_name = TASK_2_CHART_DATASET[case][1]
            for subset in subsets:
                if subset['name'] == target_name:
                    subset['score'] = score
                    break
                else:
                    subsets.append({'name': target_name, 'score': score})
                    break
        average_score = 0
        count = 0
        for subset in subsets:
            count += 1
            average_score += subset['score']
        average_score = round(average_score / count, 4) if count != 0 else 0
        if 'history' not in old_res[model_id][idx]:
            old_res[model_id][idx]['history'] = {old_res[model_id][idx]['test_time']: average_score}
        else:
            old_res[model_id][idx]['history'].update({old_res[model_id][idx]['test_time']: average_score})
        old_res[model_id][idx]['score'] = average_score
        old_res[model_id][idx]['test_time'] = create_time
    else:
        print(f'ruler2 not find case: {chart_dataset_name}')
        add_new_item_ruler2(old_res, model_id, testcase, task, model_name)
