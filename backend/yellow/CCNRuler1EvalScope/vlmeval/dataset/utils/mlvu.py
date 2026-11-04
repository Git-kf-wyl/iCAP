# Private iCAP Yellow implementation. Do not publish.
from ...smp import *
from .multiple_choice import extract_answer_from_item
from PIL import Image, ImageOps
import numpy as np
FAIL_MSG = 'Failed to obtain answer via API.'
system_prompt_sub_scene = "\n##TASK DESCRIPTION:\nYou are required to evaluate a respondent's answer based on a provided question, some scoring points, and the respondent's answer. You should provide two scores. The first is the accuracy score, which should range from 1 to 5. The second is the relevance score, which should also range from 1 to 5. Below are the criteria for each scoring category.\n##ACCURACY Scoring Criteria:\nEvaluate the respondent's answer against specific scoring points as follows:\nScore 1: The response completely misses the scoring point.\nScore 3: The response mentions content related to the scoring point but is not entirely correct.\nScore 5: The response accurately addresses the scoring point.\nCalculate the average score across all scoring points to determine the final accuracy score.\n##RELEVANCE Scoring Criteria:\nAssess how the respondent's answer relates to the original question:\nScore 1: The response is completely off-topic from the question.\nScore 2: The response is partially related to the question but contains a significant amount of irrelevant content.\nScore 3: The response primarily addresses the question, but the respondent seems uncertain about their own answer.\nScore 4: The response mostly addresses the question and the respondent appears confident in their answer.\nScore 5: The response is fully focused on addressing the question with no irrelevant content and demonstrates complete certainty.\n----\n##INSTRUCTION:\n1. Evaluate Accuracy: First, assess and score each scoring point based on the respondent's answer. Calculate the average of these scores to establish the final accuracy score. Provide a detailed rationale before assigning your score.\n2. Evaluate RELEVANCE: Assess the relevance of the respondent’s answer to the question. Note that when evaluating relevance, the correctness of the answer is not considered; focus solely on how relevant the answer is to the question. Provide a comprehensive rationale before assigning your score.\n3. Output Scores in JSON Format: Present the scores in JSON format as follows:\n{'score_accuracy': score_acc, 'score_relevance': score_rele, 'total_score': score_acc + score_rele}\n"
system_prompt_summary = "\n##TASK DESCRIPTION:\nYou are required to evaluate the performance of the respondent in the video summarization task based on the standard answer and the respondent's answer. You should provide two scores. The first is the COMPLETENESS score, which should range from 1 to 5. The second is the RELIABILITY score, which should also range from 1 to 5. Below are the criteria for each scoring category:\n##COMPLETENESS Scoring Criteria:\nThe completeness score focuses on whether the summary covers all key points and main information from the video.\nScore 1: The summary hardly covers any of the main content or key points of the video.\nScore 2: The summary covers some of the main content and key points but misses many.\nScore 3: The summary covers most of the main content and key points.\nScore 4: The summary is very comprehensive, covering most to nearly all of the main content and key points.\nScore 5: The summary completely covers all the main content and key points of the video.\n##RELIABILITY Scoring Criteria:\nThe reliability score evaluates the correctness and clarity of the video summary. It checks for factual errors, misleading statements, and contradictions with the video content. If the respondent's answer includes details that are not present in the standard answer, as long as these details do not conflict with the correct answer and are reasonable, points should not be deducted.\nScore 1: Contains multiple factual errors and contradictions; presentation is confusing.\nScore 2: Includes several errors and some contradictions; needs clearer presentation.\nScore 3: Generally accurate with minor errors; minimal contradictions; reasonably clear presentation.\nScore 4: Very accurate with negligible inaccuracies; no contradictions; clear and fluent presentation.\nScore 5: Completely accurate with no errors or contradictions; presentation is clear and easy to understand.\n----\n##INSTRUCTION:\n1. Evaluate COMPLETENESS: First, analyze the respondent's answer according to the scoring criteria, then provide an integer score between 1 and 5 based on sufficient evidence.\n2. Evaluate RELIABILITY: First, analyze the respondent's answer according to the scoring criteria, then provide an integer score between 1 and 5 based on sufficient evidence.\n3. Output Scores in JSON Format: Present the scores in JSON format as follows:\n{'score_completeness': score_comp, 'score_reliability': score_reli, 'total_score': score_comp + score_reli}\n"

def check_ans_with_model(pred, gt, model, item, dataset_name='MLVU_MCQ'):
    flag = False
    index = gt.index('(')
    index2 = gt.index(')')
    gt_option = gt[index + 1:index2]
    if ')' in pred:
        index3 = pred.index(')')
        pred = pred[index3 - 1:index3]
    if pred == gt_option:
        flag = True
    elif extract_answer_from_item(model, item, dataset_name)['opt'] == item['answer']:
        flag = True
    return flag

def extract_scores_summary(text):
    keys = ['score_completeness', 'score_reliability']
    scores = []
    for key in keys:
        start_index = text.find(key)
        if start_index == -1:
            continue
        start_number_index = text.find(':', start_index) + 2
        end_number_index = text.find(',', start_number_index)
        score = float(text[start_number_index:end_number_index])
        scores.append(score)
    return scores

def check_ans_with_model_summary(pred, gt, model, item, dataset_name='MLVU_OpenEnded'):
    user_prompt = f"\n    Please score the respondent's answer according to the steps in the Instructions. You must end with a JSON dict to store the scores.\n    Standard Answer: {gt}\n    Respondent's Answer: {pred}\n    "
    result = model.generate(user_prompt)
    result = extract_scores_summary(result)
    result = np.sum(result)
    return result

def extract_scores_sub_scene(text):
    keys = ['score_accuracy', 'score_relevance']
    scores = []
    for key in keys:
        start_index = text.find(key)
        if start_index == -1:
            continue
        start_number_index = text.find(':', start_index) + 2
        end_number_index = text.find(',', start_number_index)
        score = float(text[start_number_index:end_number_index])
        scores.append(score)
    return scores

def check_ans_with_model_sub_scene(pred, gt, model, item, dataset_name='MLVU_OpenEnded'):
    user_prompt = f"\n    Please score the respondent's answer according to the steps in the Instructions. You must end with a JSON dict to store the scores.\n    Question: {item['question']}\n    Scoring Points: {item['scoring_points']}\n    Respondent's Answer: {pred}\n    "
    result = model.generate(user_prompt)
    result = extract_scores_sub_scene(result)
    result = np.sum(result)
    return result

def MLVU_OpenEnded_generate(model, line):
    task_type = line['task_type']
    if task_type == 'summary':
        user_prompt = f"Please score the respondent's answer according to the steps in the Instructions. You must end with a JSON dict to store the scores.\nStandard Answer: {line['answer']}\nRespondent's Answer: {line['prediction']}\n"
    elif task_type == 'sub_scene':
        user_prompt = f"Please score the respondent's answer according to the steps in the Instructions. You must end with a JSON dict to store the scores.\nQuestion: {line['question']}\nScoring Points: {line['scoring_points']}\nRespondent's Answer: {line['prediction']}\n"
    else:
        AssertionError(f"MLVU don't have {task_type} open ended task!")
    result = model.generate(user_prompt)
    return result

def MLVU_OpenEnded_extract(gpt_generate_data, org_data):
    extract_func = {'sub_scene': extract_scores_sub_scene, 'summary': extract_scores_summary}
    for idx, item in org_data.iterrows():
        func = extract_func[item['task_type']]
        text = gpt_generate_data[idx]
        org_data.loc[idx, 'score'] = np.sum(func(text))
    return org_data

def get_dimension_rating(data_path):
    data = load(data_path)
    result_dict = {}
    for idx, item in data.iterrows():
        if item['task_type'] not in result_dict:
            result_dict[item['task_type']] = [0, 0]
        result_dict[item['task_type']][0] += int(item['score'])
        result_dict[item['task_type']][1] += 1
    return result_dict
