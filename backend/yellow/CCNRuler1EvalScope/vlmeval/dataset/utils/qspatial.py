# Private iCAP Yellow implementation. Do not publish.
from ...smp import *
from ...utils import can_infer
FAIL_MSG = 'Failed to obtain answer via API.'

def get_gpt4_ICE_for_qspatial():
    example_1 = '\nHint: Please answer the question requiring in a tuple format. The tuple should contain a numeric value and a unit,\ne.g., (1, m), (2.2, cm), (3.12, meter), at the end.\n\nModel response: **Object Identification**\n\n* The object in question is a chair.\n* The chair is not visible in the image.\n\n**Conclusion**\n\nThe height of the chair cannot be determined from the provided image.\n\nExtracted answer: (0, cm)\n'
    example_2 = '\nHint: Please answer the question requiring in a tuple format. The tuple should contain a numeric value and a unit,\ne.g., (1, inch), (1.2, cm), (3.0, feet), at the end.\n\nModel response: **Step 1: Identify the stapler and the recycle bin in the image.**\n\nThe stapler is located on the wooden table, and the recycle bin is located on the floor.\n\n**Step 2: Determine the distance between the stapler and the recycle bin.**\n\nThe stapler is 0.5 meters from the edge of the table, and the recycle bin is 1.5 meters from the edge of the table.\nTherefore, the minimum distance between the stapler and the recycle bin is 1.5 - 0.5 = 1 meter.\n\n**Answer:** 1 m\n\nExtracted answer: (1, m)\n'
    example_3 = '\nHint: Please answer the question requiring in a tuple format. The tuple should contain a numeric value and a unit,\ne.g., (1, foot), (2, cm), (4.3, meter), at the end.\n\nModel response: The mirror in the image is approximately 5 feet 4 inches tall.\n\nExtracted answer: (64, inch)\n'
    example_4 = '\nHint: Please answer the question requiring in a tuple format. The tuple should contain a numeric value and a unit,\ne.g., (0.1, cm), (2.9, cm), (0.3, meter), at the end.\n\nModel response: The minimum distance between the wooden chair and the chair near the camera in the image is 1.7 feet.\n\nExtracted answer: (1.7, feet)\n'
    example_5 = "\nHint: Please answer the question requiring in a tuple format. The tuple should contain a numeric value and a unit,\ne.g., (5.1, cm), (0.9, cm), (55, mm), at the end.\n\nModel response: The height of the painting's bottom edge from the floor is approximately 4.5 feet.\n\nExtracted answer: (4.5, feet)\n"
    return [example_1, example_2, example_3, example_4, example_5]

def list_to_dict(lst):
    return {chr(65 + i): val for i, val in enumerate(lst)}

def post_check(line, prefetch=False):
    res = None
    ans = line['answer']
    response = line['prediction'] if prefetch else line['res']
    try:
        if line['question_type'] == 'multi_choice':
            ans = line['answer_option']
            choices = list_to_dict(eval(line['choices']))
            res = can_infer(response, choices)
            if prefetch:
                return res
        elif line['answer_type'] == 'integer':
            res = int(response)
            ans = int(line['answer'])
        elif line['answer_type'] == 'float':
            res = float(response)
            ans = float(line['answer'])
        else:
            res = str(res)
            ans = str(ans)
    except ValueError:
        pass
    if res == ans:
        return res if prefetch else True
    else:
        return False

def build_qspatial_gpt4_prompt(line):
    task_description = '\nPlease read the following example.\nThen extract the answer from the model response and type it at the end of the prompt.\n\n'
    prediction = str(line['prediction'])
    prompt = task_description
    examples = get_gpt4_ICE_for_qspatial()
    for example in examples:
        prompt += example + '\n'
    prompt += 'Model respone: ' + prediction
    prompt += '\nExtracted answer:'
    return prompt

def QSpatial_auxeval(model, line):
    prompt = build_qspatial_gpt4_prompt(line)
    log = ''
    retry = 5
    for i in range(retry):
        prediction = line['prediction']
        res = model.generate(prompt, temperature=i * 0.5)
        if FAIL_MSG in res:
            log += f'Try {i}: output is {prediction}, failed to parse.\n'
        else:
            log += 'Succeed'
            return dict(log=log, res=res)
    log += 'All 5 retries failed.\n'
    return dict(log=log, res='')
