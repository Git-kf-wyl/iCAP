# Private iCAP Yellow implementation. Do not publish.
import re
import unicodedata
from pylatexenc.latex2text import LatexNodes2Text
from bs4 import BeautifulSoup
import subprocess
import shutil
import uuid
import html
import os

def remove_markdown_fences(content):
    content = re.sub('^```markdown\\n?', '', content, flags=re.MULTILINE)
    content = re.sub('```\\n?$', '', content, flags=re.MULTILINE)
    return content

def replace_repeated_chars(input_str):
    input_str = re.sub('_{4,}', '____', input_str)
    input_str = re.sub(' {4,}', '    ', input_str)
    return re.sub('([^a-zA-Z0-9])\\1{10,}', '\\1\\1\\1\\1', input_str)

def fullwidth_to_halfwidth(s):
    result = []
    for char in s:
        code = ord(char)
        if code == 12288:
            code = 32
        elif 65281 <= code <= 65374:
            code -= 65248
        result.append(chr(code))
    return ''.join(result)

def find_special_unicode(s):
    special_chars = {}
    for char in s:
        if ord(char) > 127:
            unicode_name = unicodedata.category(char)
            special_chars[char] = f'U+{ord(char):04X} ({unicode_name})'
    return special_chars
inline_reg = re.compile('\\$(.*?)\\$|\\\\\\((.*?)\\\\\\)')

def textblock2unicode(text):
    inline_matches = inline_reg.finditer(text)
    removal_positions = []
    for match in inline_matches:
        position = [match.start(), match.end()]
        content = match.group(1) if match.group(1) is not None else match.group(2)
        clean_content = re.sub('\\\\([\\\\_&%^])', '', content)
        try:
            if any((char in clean_content for char in '\\^_')):
                if clean_content.endswith('\\'):
                    clean_content += ' '
                unicode_content = LatexNodes2Text().latex_to_text(clean_content)
                removal_positions.append((position[0], position[1], unicode_content))
        except:
            continue
    for start, end, unicode_content in sorted(removal_positions, reverse=True):
        text = text[:start] + unicode_content.strip() + text[end:]
    return text

def normalized_formula(text):
    filter_list = ['\\mathbf', '\\mathrm', '\\mathnormal', '\\mathit', '\\mathbb', '\\mathcal', '\\mathscr', '\\mathfrak', '\\mathsf', '\\mathtt', '\\textbf', '\\text', '\\boldmath', '\\boldsymbol', '\\operatorname', '\\bm', '\\symbfit', '\\mathbfcal', '\\symbf', '\\scriptscriptstyle', '\\notag', '\\setlength', '\\coloneqq', '\\space', '\\thickspace', '\\thinspace', '\\medspace', '\\nobreakspace', '\\negmedspace', '\\quad', '\\qquad', '\\enspace', '\\substackw', ' ']
    pattern = re.compile('\\\\\\[(.+?)(?<!\\\\)\\\\\\]')
    match = pattern.search(text)
    if match:
        text = match.group(1).strip()
    tag_pattern = re.compile('\\\\tag\\{.*?\\}')
    text = tag_pattern.sub('', text)
    hspace_pattern = re.compile('\\\\hspace\\{.*?\\}')
    text = hspace_pattern.sub('', text)
    begin_pattern = re.compile('\\\\begin\\{.*?\\}')
    text = begin_pattern.sub('', text)
    end_pattern = re.compile('\\\\end\\{.*?\\}')
    text = end_pattern.sub('', text)
    col_sep = re.compile('\\\\arraycolsep.*?\\}')
    text = col_sep.sub('', text)
    text = text.strip('.')
    for filter_text in filter_list:
        text = text.replace(filter_text, '')
    text = text.lower()
    return text

def normalized_html_table(text):

    def process_table_html(md_i):
        """
        pred_md format edit
        """

        def process_table_html(html_content):
            soup = BeautifulSoup(html_content, 'html.parser')
            th_tags = soup.find_all('th')
            for th in th_tags:
                th.name = 'td'
            thead_tags = soup.find_all('thead')
            for thead in thead_tags:
                thead.unwrap()
            math_tags = soup.find_all('math')
            for math_tag in math_tags:
                alttext = math_tag.get('alttext', '')
                alttext = f'${alttext}$'
                if alttext:
                    math_tag.replace_with(alttext)
            span_tags = soup.find_all('span')
            for span in span_tags:
                span.unwrap()
            return str(soup)
        table_res = ''
        table_res_no_space = ''
        if '<table' in md_i.replace(' ', '').replace("'", '"'):
            md_i = process_table_html(md_i)
            table_res = html.unescape(md_i).replace('\n', '')
            table_res = unicodedata.normalize('NFKC', table_res).strip()
            pattern = '<table\\b[^>]*>(.*)</table>'
            tables = re.findall(pattern, table_res, re.DOTALL | re.IGNORECASE)
            table_res = ''.join(tables)
            table_res = re.sub('( style=".*?")', '', table_res)
            table_res = re.sub('( height=".*?")', '', table_res)
            table_res = re.sub('( width=".*?")', '', table_res)
            table_res = re.sub('( align=".*?")', '', table_res)
            table_res = re.sub('( class=".*?")', '', table_res)
            table_res = re.sub('</?tbody>', '', table_res)
            table_res = re.sub('\\s+', ' ', table_res)
            table_res_no_space = '<html><body><table border="1" >' + table_res.replace(' ', '') + '</table></body></html>'
            table_res_no_space = re.sub('colspan="', ' colspan="', table_res_no_space)
            table_res_no_space = re.sub('rowspan="', ' rowspan="', table_res_no_space)
            table_res_no_space = re.sub('border="', ' border="', table_res_no_space)
            table_res = '<html><body><table border="1" >' + table_res + '</table></body></html>'
        return (table_res, table_res_no_space)

    def clean_table(input_str, flag=True):
        if flag:
            input_str = input_str.replace('<sup>', '').replace('</sup>', '')
            input_str = input_str.replace('<sub>', '').replace('</sub>', '')
            input_str = input_str.replace('<span>', '').replace('</span>', '')
            input_str = input_str.replace('<div>', '').replace('</div>', '')
            input_str = input_str.replace('<p>', '').replace('</p>', '')
            input_str = input_str.replace('<spandata-span-identity="">', '')
            input_str = re.sub('<colgroup>.*?</colgroup>', '', input_str)
        return input_str
    norm_text, _ = process_table_html(text)
    norm_text = clean_table(norm_text)
    return norm_text

def normalized_latex_table(text):

    def latex_template(latex_code):
        template = '\n        \\documentclass[border=20pt]{article}\n        \\usepackage{subcaption}\n        \\usepackage{url}\n        \\usepackage{graphicx}\n        \\usepackage{caption}\n        \\usepackage{multirow}\n        \\usepackage{booktabs}\n        \\usepackage{color}\n        \\usepackage{colortbl}\n        \\usepackage{xcolor,soul,framed}\n        \\usepackage{fontspec}\n        \\usepackage{amsmath,amssymb,mathtools,bm,mathrsfs,textcomp}\n        \\setlength{\\parindent}{0pt}' + '\n        \\begin{document}\n        ' + latex_code + '\n        \\end{document}'
        return template

    def process_table_latex(latex_code):
        SPECIAL_STRINGS = [['\\\\vspace\\{.*?\\}', ''], ['\\\\hspace\\{.*?\\}', ''], ['\\\\rule\\{.*?\\}\\{.*?\\}', ''], ['\\\\addlinespace\\[.*?\\]', ''], ['\\\\addlinespace', ''], ['\\\\renewcommand\\{\\\\arraystretch\\}\\{.*?\\}', ''], ['\\\\arraystretch\\{.*?\\}', ''], ['\\\\(row|column)?colors?\\{[^}]*\\}(\\{[^}]*\\}){0,2}', ''], ['\\\\color\\{.*?\\}', ''], ['\\\\textcolor\\{.*?\\}', ''], ['\\\\rowcolor(\\[.*?\\])?\\{.*?\\}', ''], ['\\\\columncolor(\\[.*?\\])?\\{.*?\\}', ''], ['\\\\cellcolor(\\[.*?\\])?\\{.*?\\}', ''], ['\\\\colorbox\\{.*?\\}', ''], ['\\\\(tiny|scriptsize|footnotesize|small|normalsize|large|Large|LARGE|huge|Huge)', ''], ['\\s+', ' '], ['\\\\centering', ''], ['\\\\begin\\{table\\}\\[.*?\\]', '\\\\begin{table}'], ['\t', ''], ['@{}', ''], ['\\\\toprule(\\[.*?\\])?', '\\\\hline'], ['\\\\bottomrule(\\[.*?\\])?', '\\\\hline'], ['\\\\midrule(\\[.*?\\])?', '\\\\hline'], ['p\\{[^}]*\\}', 'l'], ['m\\{[^}]*\\}', 'c'], ['\\\\scalebox\\{[^}]*\\}\\{([^}]*)\\}', '\\1'], ['\\\\textbf\\{([^}]*)\\}', '\\1'], ['\\\\textit\\{([^}]*)\\}', '\\1'], ['\\\\cmidrule(\\[.*?\\])?\\(.*?\\)\\{([0-9]-[0-9])\\}', '\\\\cline{\\2}'], ['\\\\hline', ''], ['\\\\multicolumn\\{1\\}\\{[^}]*\\}\\{((?:[^{}]|(?:\\{[^{}]*\\}))*)\\}', '\\1']]
        pattern = '\\\\begin\\{tabular\\}.*\\\\end\\{tabular\\}'
        matches = re.findall(pattern, latex_code, re.DOTALL)
        latex_code = ' '.join(matches)
        for special_str in SPECIAL_STRINGS:
            latex_code = re.sub(f'{special_str[0]}', f'{special_str[1]}', latex_code)
        return latex_code

    def convert_latex_to_html(latex_content, cache_dir='./temp'):
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        uuid_str = str(uuid.uuid1())
        with open(f'{cache_dir}/{uuid_str}.tex', 'w') as f:
            f.write(latex_template(latex_content))
        cmd = ['latexmlc', '--quiet', '--nocomments', f'--log={cache_dir}/{uuid_str}.log', f'{cache_dir}/{uuid_str}.tex', f'--dest={cache_dir}/{uuid_str}.html']
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open(f'{cache_dir}/{uuid_str}.html', 'r') as f:
                html_content = f.read()
            pattern = '<table\\b[^>]*>(.*)</table>'
            tables = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            tables = [f'<table>{table}</table>' for table in tables]
            html_content = '\n'.join(tables)
        except Exception as e:
            html_content = ''
        shutil.rmtree(cache_dir)
        return html_content
    html_text = convert_latex_to_html(text)
    normlized_tables = normalized_html_table(html_text)
    return normlized_tables

def normalized_table(text, format='html'):
    if format not in ['html', 'latex']:
        raise ValueError('Invalid format: {}'.format(format))
    else:
        return globals()['normalized_{}_table'.format(format)](text)

def textblock_with_norm_formula(text):
    inline_matches = inline_reg.finditer(text)
    removal_positions = []
    for match in inline_matches:
        position = [match.start(), match.end()]
        content = match.group(1) if match.group(1) is not None else match.group(2)
        norm_content = normalized_formula(content)
        removal_positions.append((position[0], position[1], norm_content))
    for start, end, norm_content in sorted(removal_positions, reverse=True):
        text = text[:start] + norm_content.strip() + text[end:]
    return text

def inline_filter_unicode(text):
    if not isinstance(text, str):
        text = str(text)
    placeholder = '__INLINE_FORMULA_BOUNDARY__'
    text_copy = text.replace('$', placeholder).replace('\\(', placeholder).replace('\\)', placeholder)
    text_copy = LatexNodes2Text().latex_to_text(text_copy)
    text_copy = text_copy.replace(placeholder, '$')
    inline_array = []
    inline_matches = inline_reg.finditer(text_copy)
    removal_positions = []
    for match in inline_matches:
        position = [match.start(), match.end()]
        content = match.group(1) if match.group(1) is not None else match.group(2)
        print('-------- content-------', content)
        clean_content = re.sub('\\\\([\\\\_&%^])', '', content)
        if any((char in clean_content for char in '\\^_')):
            inline_array.append({'category_type': 'equation_inline', 'position': position, 'content': content})
            removal_positions.append((position[0], position[1]))
    for start, end in sorted(removal_positions, reverse=True):
        text = text[:start] + text[end:]
    return (text, inline_array)

def inline_filter(text):
    if not isinstance(text, str):
        text = str(text)
    inline_array = []
    inline_matches = inline_reg.finditer(text)
    for match in inline_matches:
        position = [match.start(), match.end()]
        content = match.group(1) if match.group(1) is not None else match.group(2)
        clean_content = re.sub('\\\\([\\\\_&%^])', '', content)
        if any((char in clean_content for char in '\\^_')):
            inline_array.append({'category_type': 'equation_inline', 'position': position, 'content': match.group(0)})
            text = text.replace(match.group(0), '')
        else:
            text = text.replace(match.group(0), content)
    return (text, inline_array)

def clean_string(input_string):
    input_string = input_string.replace('\\t', '').replace('\\n', '').replace('\t', '').replace('\n', '').replace('/t', '').replace('/n', '')
    cleaned_string = re.sub('[^\\w\\u4e00-\\u9fff]', '', input_string)
    return cleaned_string
