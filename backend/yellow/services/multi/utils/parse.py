# Private iCAP Yellow business implementation. Do not publish.
import json
import subprocess
import pandas as pd

def convert_parquet_to_json(parquet_file_name, json_file_name):
    df = pd.read_parquet(parquet_file_name, engine='fastparquet')
    meta_data = []
    for index, row in df.iterrows():
        meta_data.append({'text': row['text'], 'speaker_id': row['speaker_id'], 'chapter_id': row['chapter_id'], 'id': row['id'], 'path': f"audio/clean/{row['audio.path']}"})
    with open(json_file_name, 'w', encoding='utf-8') as json_file:
        json.dump(meta_data, json_file, ensure_ascii=False, indent=4)

def convert_to_wav(file_path, output_wav_path):
    """
    将 MP4 转换为 WAV 格式
    """
    command = ['ffmpeg', '-y', '-i', file_path, '-acodec', 'pcm_s16le', '-ar', '44100', output_wav_path]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print('转换成功!')
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print('转换失败, 错误信息:', e.stderr)
