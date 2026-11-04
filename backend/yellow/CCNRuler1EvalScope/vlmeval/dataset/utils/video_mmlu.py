# Private iCAP Yellow implementation. Do not publish.
from ...smp import *
import numpy as np
import pandas as pd
FAIL_MSG = 'Failed to obtain answer via API.'
SYSTEM_CAL_SCORE_PROMPT_CAP = "\n    You are an intelligent chatbot designed for evaluating the correctness of generative outputs for question-answer pairs.\n    Your task is to compare the predicted answer with the correct answer and determine if they match meaningfully. The evaluation criteria differ based on the type of question:\n    ------\n    ## INSTRUCTIONS:\n    1. For **OCR-related questions**:\n       - Perform a strict letter-by-letter comparison.\n       - Any difference in characters (including case, punctuation, or letter substitution) must result in 'no'.\n       - Minor spelling errors or missing characters should not be accepted.\n    2. For **non-OCR-related questions**:\n       - Focus on the meaningful match between the predicted answer and the correct answer.\n       - Synonyms or paraphrases can be considered valid matches.\n       - Minor spelling differences or alternative expressions should not be penalized.\n"
SYSTEM_CAL_SCORE_PROMPT_QA = "\n    You are an intelligent chatbot designed for evaluating the correctness of generative outputs for reasoning-based question-answer pairs.\n    Your task is to compare the predicted answer with the correct answer based on the following rules:\n    ------\n    ## INSTRUCTIONS:\n    1. **Evaluate Reasoning Tasks Strictly:**\n       - The predicted answer must capture all critical concepts and details mentioned in the correct answer.\n       - If the correct answer mentions specific concepts or examples (e.g., 'odd numbers accumulate to form perfect squares'), the predicted answer must include these concepts or examples.\n       - Even if the phrasing differs, the key meaning and concepts must be preserved. However, omitting or altering key concepts or examples is **not acceptable**.\n       - **Example 1:** If the correct answer is 'The construction method shows how odd numbers accumulate to form perfect squares,' the predicted answer must include 'odd numbers' and 'perfect squares'.\n       - **Example 2:** If the correct answer is 'To eliminate HBr and form an alkene,' the predicted answer must address the elimination of HBr as well.\n       - Minor differences in phrasing are acceptable as long as the key information is retained.\n       - **Critical Detail:** If any essential element (e.g., key terms, concepts, or examples) is missing from the predicted answer, the answer is considered incorrect.\n       - Do **not** introduce new, unrelated information in the predicted answer.\n"
SYSTEM_GENER_PRED_PROMPT = "You are an intelligent chatbot designed for providing accurate answers to questions related to the content based on a detailed description of a video or image.\nHere's how you can accomplish the task:\n------\n##INSTRUCTIONS:\n- Read the detailed description carefully.\n- Answer the question only based on the detailed description.\n- The answer should be a short sentence or phrase.\n"
USER_GENER_PRED_PROMPT = 'Please provide accurate answers to questions related to the content based on a detailed description of a video or image:\n\ndetailed description: {pred_cap}\nquestion: {q}\n\nDO NOT PROVIDE ANY OTHER OUTPUT TEXT OR EXPLANATION. Only provide short but accurate answer.'
VIDEO_MMLU_DIMENSIONS = {'math': ['math'], 'physics': ['physics'], 'chemistry': ['chemistry'], 'overall': []}
L3_DIMS = []
for k, v in VIDEO_MMLU_DIMENSIONS.items():
    if k != 'overall':
        L3_DIMS.extend(v)
        VIDEO_MMLU_DIMENSIONS['overall'].extend(v)

def get_dimension_rating(data_path):
    data = load(data_path)
    coarse_rating = {k: [] for k in VIDEO_MMLU_DIMENSIONS}
    coarse_acc = {k: [] for k in VIDEO_MMLU_DIMENSIONS}

    def parse_score_dict(score_dict):
        """Helper function to parse score dictionary string"""
        if isinstance(score_dict, dict):
            return score_dict
        if isinstance(score_dict, str):
            try:
                return json.loads(score_dict)
            except json.JSONDecodeError:
                try:
                    return eval(score_dict)
                except:
                    print(f'Failed to parse score_dict: {score_dict}')
                    return None
        return None
    for i in range(len(data)):
        discipline = data.iloc[i]['discipline'].lower()
        score_dict = parse_score_dict(data.iloc[i]['score'])
        if score_dict and isinstance(score_dict, dict) and ('pred' in score_dict) and ('score' in score_dict):
            score = score_dict['score']
            is_correct = 1 if score_dict['pred'].lower() == 'yes' else 0
        else:
            score = -1
            is_correct = -1
        if discipline in ['math', 'physics', 'chemistry']:
            coarse_rating[discipline].append(score)
            coarse_rating['overall'].append(score)
            if is_correct != -1:
                coarse_acc[discipline].append(is_correct)
                coarse_acc['overall'].append(is_correct)
    coarse_valid = {k: f'{np.mean([x for x in v if x >= 0]):.2f}' for k, v in coarse_rating.items()}
    coarse_accuracy = {k: f'{np.mean(v):.2f}' if v else '0.00' for k, v in coarse_acc.items()}
    return dict(coarse_valid=coarse_valid, coarse_accuracy=coarse_accuracy)

def prepare_response_prompt(item):
    """
    Prepare messages for response generation

    Args:
        item: DataFrame row containing pred_cap and question

    Returns:
        list: List of message dictionaries for the model
    """
    return USER_GENER_PRED_PROMPT.format(pred_cap=item['prediction'], q=item['question'])

def prepare_score_prompt(item):
    """
    Prepare messages for score evaluation

    Args:
        item: DataFrame row containing question, answer, and prediction

    Returns:
        list: List of message dictionaries for the model
    """
    if isinstance(item, pd.Series):
        item = item.to_dict()
    prompt = f"Please evaluate the following video-based question-answer pair:\n\n\n            Question: {item['question']}\n\n            Correct Answer: {item['answer']}\n\n            Predicted Answer: {item['pred_response']}\n\n\n            Provide your evaluation only as a yes/no and score where the score is an integer value between 0 and 5, with 5 indicating the highest meaningful match.\n            Please generate the response in the form of a Python dictionary string with keys 'pred' and 'score', where value of 'pred' is  a string of 'yes' or 'no' and value of 'score' is in INTEGER, not STRING.\n            DO NOT PROVIDE ANY OTHER OUTPUT TEXT OR EXPLANATION. Only provide the Python dictionary string.\n                For example, your response should look like this: {{'pred': 'yes', 'score': 4.8}}."
    return prompt

def prepare_score_prompt_qa(item):
    """
    Prepare messages for score evaluation

    Args:
        item: DataFrame row containing question, answer, and prediction

    Returns:
        list: List of message dictionaries for the model
    """
    if isinstance(item, pd.Series):
        item = item.to_dict()
    prompt = f"Please evaluate the following video-based question-answer pair:\n\n\n            Question: {item['question']}\n\n            Correct Answer: {item['answer']}\n\n            Predicted Answer: {item['prediction']}\n\n\n            Provide your evaluation only as a yes/no and score where the score is an integer value between 0 and 5, with 5 indicating the highest meaningful match.\n            Please generate the response in the form of a Python dictionary string with keys 'pred' and 'score', where value of 'pred' is  a string of 'yes' or 'no' and value of 'score' is in INTEGER, not STRING.\n            DO NOT PROVIDE ANY OTHER OUTPUT TEXT OR EXPLANATION. Only provide the Python dictionary string.\n                For example, your response should look like this: {{'pred': 'yes', 'score': 4.8}}."
    return prompt
