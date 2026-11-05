"""Platform-wide evaluation data, with administrator-only mutation."""
from fastapi import HTTPException

EVALUATION_READS = {
    'get_current_full_res','get_current_multi_full_res','lmarena/leaderboard','get_min_test_chart',
    'get_evaluation_result','get_run_test_progress_list','get_one_test_task','get_file_path',
    'get_result','logs','get_eld_statistics','download_aisf_release_result',
    'get_all_report_tasks','get_report_tasks_by_name','query_report_status','get_latest_report',
    'download/report','preview/report','preview/report/pdf','get_all_published_tasks',
    'get_eval_report','get_eval_model_list',
}
EVALUATION_WRITES = {
    'run_testcase_ruler1','run_testcase_ruler2','run_testcase_dev','run_vlm_ruler1',
    'run_aisf_release','run_simultaneous_interpretation','run_testcase_mcp_atlas',
    'delete_test_progress','pause_test_task','resume_test_task','update_top_chart',
    'update_score','async_score','upload_test_result','upload_local_result','upload_mos_file',
    'write_evaluation_result','delete_single_result','generate_report','delete_report_task',
    'publish_report_from_task','direct_publish_report','delete_published_task','update_published_report',
    'modify_eval_report','modify_eval_model_list',
}

def require_evaluator(actor):
    if actor.get('role') != 'admin':
        raise HTTPException(403,'只有管理员可以执行评测或发布、修改评测结果')

def evaluation_actor(actor):
    # Reuse the original administrator workspace, preserving its files and scores.
    # This identity selects storage only; permission checks use the actual caller.
    return {**actor,'id':'admin','role':'admin'}

def evaluation_route(path, query):
    if path in EVALUATION_READS | EVALUATION_WRITES or path.startswith('check_run_test_progress/'):
        return True
    if path in {'download/file','download/dataset_zip','get_excel_file'}:
        values=[value.replace('\\','/') for key,value in query if key in {'filepath','filepaths[]','file_path','path'}]
        return bool(values) and all(value.startswith(('outputs/','backend/report/output/')) for value in values)
    return False
