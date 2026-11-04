# Private iCAP Yellow business implementation. Do not publish.
import os.path
import pandas as pd
import numpy as np
from result_evaluation import calculate_accuracy_with_styles
from result_statistics import processExcel, processReferenceDoubao
from analyze_statistics import analyze_cost_time, analyze_stability, write_to_excel, merge_excel_files
from preprocess_evaluation import preprocess_excel
import time
import argparse
EXCEL_FILE_list = ['E:\\skill-jingjing\\tongji\\source\\20260529_test_模型侧.xlsx']
time_delay_file = ['D:\\AI_Visualization\\CCNModelEvalService\\outputs\\Qwen3.6-27B\\20260602_115709_0001\\reviews\\Qwen3.6-27B\\3329_0601报告_20260602_115709_0001.xlsx']
stability_xlsx = ['E:\\skill-jingjing\\tongji\\source\\20260529_test_产品侧_第一次.xlsx', 'E:\\skill-jingjing\\tongji\\source\\20260529_test_产品侧_第二次.xlsx', 'E:\\skill-jingjing\\tongji\\source\\20260529_test_产品侧_第三次.xlsx']
stability_data = analyze_stability(stability_xlsx)
output_stability_file = stability_xlsx[0].replace('.xlsx', '_out.xlsx')
merge_excel_files(stability_xlsx, output_stability_file)
write_to_excel(output_stability_file, stability_data=stability_data)
