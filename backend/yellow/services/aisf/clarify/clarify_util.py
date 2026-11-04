# Private iCAP Yellow business implementation. Do not publish.
import os
import pandas as pd

def merge_summary(output_path, input_path):
    all_items = os.listdir(input_path)
    directories = [item for item in all_items if os.path.isdir(os.path.join(input_path, item))]
    merged_df = pd.DataFrame()
    for path in directories:
        excel_files = [f for f in os.listdir(os.path.join(input_path, path)) if f.endswith('Summary.xlsx')]
        for file in excel_files:
            df = pd.read_excel(os.path.join(input_path, path, file))
            merged_df = pd.concat([merged_df, df], ignore_index=True)
            merged_df = merged_df.drop_duplicates()
    with pd.ExcelWriter(output_path + '/merged_summary.xlsx') as writer:
        merged_df.to_excel(writer, index=False)
