# Private iCAP Yellow business implementation. Do not publish.
import os
import zipfile

def zip_directory(folder_path, output_path, only_error=False):
    """
    将指定目录压缩为Zip文件。

    :param folder_path: 需要压缩的目录路径
    :param output_path: 输出的Zip文件路径
    """
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(folder_path):
            for filename in filenames:
                if filename.endswith('.zip'):
                    continue
                if only_error:
                    if filename.endswith('.log'):
                        continue
                    elif 'bad_case' not in filename.lower() and 'summary' not in filename.lower() and ('result.xlsx' not in filename.lower()):
                        continue
                file_path = os.path.join(foldername, filename)
                zipf.write(file_path, os.path.relpath(file_path, folder_path))
