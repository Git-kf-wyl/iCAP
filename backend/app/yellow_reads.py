"""FastAPI read models; browsing never needs to launch the Flask evaluator."""
from datetime import datetime
from state_storage import read_document,state_exists
from .evaluation_policy import EVALUATION_READS, evaluation_actor

FAST_READS={'get_current_full_res','get_current_multi_full_res','get_all_published_tasks',
            'get_all_report_tasks','get_testcase_info','dataset/counts','get_run_test_progress_list',
            'get_eval_report','get_eval_model','get_evaluation_result','lmarena/leaderboard'}

def read_business(runtime,actor,path,query,*,prepared_root=None):
    if path in EVALUATION_READS:actor=evaluation_actor(actor)
    root=prepared_root or runtime.initialize(actor)
    if prepared_root is None:
        with runtime.lock:runtime.sync_resources(root,actor)
    def read(name,default=None):
        file=root/'backend/config'/name
        return read_document(file) if state_exists(file) else ({} if default is None else default)
    if path=='get_testcase_info':
        kind={'2':'field','3':'dev'}.get(str(query.get('is_field','1')),'common')
        return {key:row for key,row in read(kind+'_testcase_cfg.json').items() if row.get('status')==1}
    if path=='dataset/counts':return read('dataset_download_view_count.json')
    if path=='get_evaluation_result':return read('evaluationResult.json')
    if path=='lmarena/leaderboard':
        from .historical_rankings import arena_rows
        return arena_rows(read('lmarena_leaderboard.json', []))
    if path in {'get_all_report_tasks','get_all_published_tasks'}:
        rows=read('publishedReportTasks.json' if path=='get_all_published_tasks' else 'reportTasks.json')
        result=[{**row,'id':key} for key,row in rows.items()]
        return sorted(result,key=lambda row:row.get('publish_time' if path=='get_all_published_tasks' else 'create_time',''),reverse=True)
    if path=='get_run_test_progress_list':
        rows=list(read('tasks.json').values())
        # Active evaluators still compute live progress from their run artifacts.
        if any(row.get('status') in {'running','queued','paused'} for row in rows):return None
        return list(reversed(rows))
    if path in {'get_eval_report','get_eval_model'}:
        file=root/'backend/report'/('eval_report_list.json' if path=='get_eval_report' else 'eval_model_list.json')
        return read_document(file) if state_exists(file) else {}
    multi=path=='get_current_multi_full_res'
    result={}
    for ruler in ('ruler1','ruler2'):
        records=read(ruler+'_cheat'+('_multi' if multi else '')+'.json')
        result[ruler]={}
        for model,rows in records.items():
            dates=[]
            for row in rows:
                try:dates.append(datetime.strptime(row['test_time'],'%Y-%m-%d %H:%M:%S'))
                except (KeyError,TypeError,ValueError):pass
            name=model.lower()
            provider='DeepSeek' if 'deepseek' in name or 'ds' in name else 'Alibaba' if 'qwen' in name or name.startswith('qwq') else 'Huawei' if 'pangu' in name else 'Meta' if 'llama' in name else 'Others'
            result[ruler][model]={'is_new':False,'result':rows,'publisher':provider,
                                  'creation_date':'xxxx-xx-xx','update_date':max(dates).strftime('%Y-%m-%d') if dates else 'xxxx-xx-xx'}
    return result
