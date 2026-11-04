# Private iCAP Yellow implementation. Do not publish.
import re
import logging
resp_type = {'Pangu38B-MM': {'num': 4, 'regex': '(\\d+), *(\\d+), *(\\d+), *(\\d+)', 'isMillile': True}, 'UI-TARS-7B-DPO': {'num': 2, 'regex': '<\\|box_start\\|>\\((\\d+), *(\\d+)\\)<\\|box_end\\|>', 'isMillile': True}, 'UI-TARS-7B': {'num': 2, 'regex': '<\\|box_start\\|>\\((\\d+), *(\\d+)\\)<\\|box_end\\|>', 'isMillile': True}, 'UI-TARS-7B-DPO-0301sft': {'num': 2, 'regex': '<\\|box_start\\|>\\((\\d+), *(\\d+)\\)<\\|box_end\\|>', 'isMillile': True}, 'Qwen2-VL-7B-Instruct': {'num': 2, 'regex': '<\\|box_start\\|>\\((\\d+), *(\\d+)\\)<\\|box_end\\|>', 'isMillile': True}, 'Qwen2.5-7B-Instruct': {'num': 4, 'regex': '(\\d+), *(\\d+), *(\\d+), *(\\d+)', 'isMillile': False}, 'Qwen2.5-VL-7B-sft-200': {'num': 2, 'regex': '(\\d+), *(\\d+)', 'isMillile': False}, 'Qwen2.5-VL-7B-sft-330': {'num': 2, 'regex': '(\\d+), *(\\d+)', 'isMillile': False}, 'UI-TARS-72B-DPO': {'num': 2, 'regex': '<\\|box_start\\|>\\((\\d+), *(\\d+)\\)<\\|box_end\\|>', 'isMillile': True}, 'UI-TARS-72B': {'num': 2, 'regex': '(\\d+), *(\\d+)', 'isMillile': True}, 'UI-TARS-7B-sft-330': {'num': 2, 'regex': '(\\d+), *(\\d+)', 'isMillile': True}, 'UI-TARS-7B-sft-100': {'num': 2, 'regex': '(\\d+), *(\\d+)', 'isMillile': True}, 'UI-TARS-7B-SFT': {'num': 2, 'regex': '(\\d+), *(\\d+)', 'isMillile': True}, 'ui-tars': {'num': 2, 'regex': '(\\d+), *(\\d+)', 'isMillile': True}}
DEFAULT_REGEX = resp_type['ui-tars']['regex']

def get_order_type(order):
    try:
        if 'click' in order:
            return 'click'
        if 'swipe_screen' in order or 'scroll' in order:
            return 'scroll'
        if 'set_text' in order or 'type' in order:
            return 'type'
        if 'back' in order:
            return 'back'
        if 'home' in order:
            return 'home'
        if 'wait' in order:
            return 'wait'
        if 'finished' in order:
            return 'finished'
        if 'long_press' in order:
            return 'long_press'
        if 'open_app' in order:
            return 'open_app'
        if 'enter' in order:
            return 'press_enter'
        if 'call_user' in order:
            return 'call_user'
    except:
        logging.error(f'odr is err! {order}')
    return None

def judge_order_type(type, order):
    try:
        if type in order:
            return True
    except:
        logging.error(f'odr is err! {order}')
    return False

def judge_click(order, x, y, width, height, origin_type='Pangu38B-MM'):
    if judge_order_type('click', order) == False:
        return 0
    pangu_bbox_pattern = resp_type[origin_type]['regex']
    click_list = order.split('click')
    for i in click_list:
        result = True
        match = re.findall(pangu_bbox_pattern, i)
        if len(match) > 0:
            try:
                xmin, ymin, xmax, ymax = list(map(int, match[0]))
            except:
                result = False
                continue
        else:
            result = False
            continue
        if result == False:
            return None
        if x >= xmin and x <= xmax and (y >= ymin) and (y <= ymax):
            return 1
    return 0

def fixed_qwen2point5_vl(order, xxmin, yymin, xxmax, yymax, width, height, origin_type='Pangu38B-MM'):
    if get_order_type(order) != 'click':
        return 'F'
    pangu_bbox_pattern = resp_type[origin_type]['regex']
    match = re.findall(pangu_bbox_pattern, order)
    if len(match) > 0:
        try:
            xmin, ymin, xmax, ymax = list(map(int, match[0]))
        except:
            return 0
    else:
        return 0
    xmin = int(xmin / 0.64)
    ymin = int(ymin / 0.64)
    xmax = int(xmax / 0.64)
    ymax = int(ymax / 0.64)
    if xxmin >= xmin and xxmin <= xmax and (yymin >= ymin) and (yymin <= ymax):
        return 1
    if xxmax >= xmin and xxmax <= xmax and (yymin >= ymin) and (yymin <= ymax):
        return 1
    if xxmin >= xmin and xxmin <= xmax and (yymax >= ymin) and (yymax <= ymax):
        return 1
    if xxmax >= xmin and xxmax <= xmax and (yymax >= ymin) and (yymax <= ymax):
        return 1
    return 0

def judge_scroll(xxmin, yymin, xxmax, yymax, width, height, order):
    if judge_order_type('swipe_screen', order) == False:
        return 0
    judge_distance = False
    if 'scroll' in order:
        judge_distance = True
    swipe_string = order.split('scroll')[0]
    swipe_bbox_pattern = '(\\d+), *(\\d+), *(\\d+), *(\\d+)'
    match = re.findall(swipe_bbox_pattern, swipe_string)
    if len(match) > 0:
        try:
            xmin, ymin, xmax, ymax = list(map(int, match[0]))
        except:
            return 0
    else:
        return 0
    if judge_distance == True:
        scroll_string = order.split('scroll')[1]
        scroll_bbox_pattern = "start_box=\\'[<\\|box_start\\|>]*\\((\\d+), *(\\d+)\\)[<\\|box_end\\|>]*\\', *end_box=\\'[<\\|box_start\\|>]*\\((\\d+), *(\\d+)\\)"
        match = re.findall(scroll_bbox_pattern, scroll_string)
        if len(match) > 0:
            try:
                xmin1, ymin1, xmax1, ymax1 = list(map(int, match[0]))
            except:
                return 0
        else:
            return 0
    direction_pattern = 'direction=(\\w+)'
    match = re.findall(direction_pattern, order)
    if len(match) > 0:
        try:
            direction = match[0]
        except:
            return 0
    else:
        return 0
    xmin = int(xmin / 999 * width)
    ymin = int(ymin / 999 * height)
    xmax = int(xmax / 999 * width)
    ymax = int(ymax / 999 * height)
    if judge_distance == True:
        xmin1 = int(xmin1 / 999 * width)
        ymin1 = int(ymin1 / 999 * height)
        xmax1 = int(xmax1 / 999 * width)
        ymax1 = int(ymax1 / 999 * height)
    if xmin < xmax:
        x_left, x_right = (xmin, xmax)
    else:
        x_left, x_right = (xmax, xmin)
    if ymin < ymax:
        y_upper, y_lower = (ymin, ymax)
    else:
        y_upper, y_lower = (ymax, ymin)
    scroll_result = 0
    if direction == 'up' and yymin - yymax > 0:
        if judge_distance == True:
            if xxmin >= x_left and xxmin <= x_right and (yymin >= y_upper) and (yymin <= y_lower):
                if abs(abs(yymax - yymin) - abs(ymax1 - ymin1)) < 20:
                    scroll_result = 1
        else:
            scroll_result = 1
    elif direction == 'down' and yymin - yymax < 0:
        if judge_distance == True:
            if xxmin >= x_left and xxmin <= x_right and (yymin >= y_upper) and (yymin <= y_lower):
                if abs(abs(yymax - yymin) - abs(ymax1 - ymin1)) < 20:
                    scroll_result = 1
        else:
            scroll_result = 1
    elif direction == 'left' and xxmin - xxmax > 0:
        if judge_distance == True:
            if xxmin >= x_left and xxmin <= x_right and (yymin >= y_upper) and (yymin <= y_lower):
                if abs(abs(xxmax - xxmin) - abs(xmax1 - xmin1)) < 20:
                    scroll_result = 1
        else:
            scroll_result = 1
    elif direction == 'right' and xxmin - xxmax < 0:
        if judge_distance == True:
            if xxmin >= x_left and xxmin <= x_right and (yymin >= y_upper) and (yymin <= y_lower):
                if abs(abs(xxmax - xxmin) - abs(xmax1 - xmin1)) < 20:
                    scroll_result = 1
        else:
            scroll_result = 1
    else:
        scroll_result = 0
    return scroll_result

def judge_long_press(x, y, width, height, order):
    if judge_order_type('long_press', order) == False:
        return 'F'
    bbox_pattern = '(\\d+), *(\\d+), *(\\d+), *(\\d+)'
    match = re.findall(bbox_pattern, order)
    if len(match) > 0:
        try:
            xmin, ymin, xmax, ymax = list(map(int, match[0]))
        except:
            return 0
    else:
        return 0
    xmin = int(xmin / 999 * width)
    ymin = int(ymin / 999 * height)
    xmax = int(xmax / 999 * width)
    ymax = int(ymax / 999 * height)
    if x >= xmin and x <= xmax and (y >= ymin) and (y <= ymax):
        return 1
    else:
        return 0

def judge_type(text, order):
    if judge_order_type('set_text', order) == False:
        return 0
    pattern_order = 'text=([\\\'"])(.*?)\\1'
    match = re.search(pattern_order, order)
    if match:
        text_order = match.group(2)
    else:
        return 0
    try:
        data = json.loads(text.lstrip('<tool_call>').rstrip('</tool_call>').lstrip('```json').rstrip('```'))
        text_value = data['arguments']['text']
    except:
        print(f'the text is: \n***********\n{text}\n**********')
        text_value = text.split('"text": "')[-1].split('"')[0]
    order_value = text_order.lstrip("='").rstrip("')")
    if text_value == order_value:
        return 1
    return 0

def judge_back(order):
    if judge_order_type('back', order) == False:
        return 0
    return 1

def judge_home(order):
    if judge_order_type('home', order) == False:
        return 0
    return 1

def judge_wait(order):
    if judge_order_type('wait', order) == False:
        return 0
    return 1

def judge_finish(order):
    if judge_order_type('finished', order) == False:
        return 0
    return 1

def judge_open_app(app_name, order):
    if judge_order_type('open_app', order) == False:
        return 0
    return 1

def judge_enter(order):
    if judge_order_type('enter', order) == False:
        return 0
    return 1

def judge_call_user(order, action):
    if judge_order_type('call_user', order) == False:
        return 0
    pattern_action = '"call_user_type"\\s*:\\s*"([^"]+)"'
    pattern_order = 'type="([^"]+)"'
    match_order = re.search(pattern_order, order)
    if match_order:
        order_type = match_order.group(1)
    else:
        return 0
    match_action = re.search(pattern_action, action)
    if match_action:
        call_user_type = match_action.group(1)
    else:
        return 0
    if order_type != call_user_type:
        return 0
    return 1
