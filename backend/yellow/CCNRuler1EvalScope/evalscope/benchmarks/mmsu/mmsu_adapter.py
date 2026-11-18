"""MMSU 语音理解基准适配器（iCAP Yellow / CCNRuler1EvalScope）。

上游：`ddwang2000/MMSU`（ICLR 2026，MIT），5000 题 / 47 个 task_name，
每条记录是一段音频 + 四选一（A–D），`answer_gt` 存的是**选项文本**而不是字母。

口径对齐官方两个脚本：
- `MMSU-main/mmsu_inference.py`：提示词模板、指令文案、选项拼法（逐字符一致）；
- `MMSU-main/mmsu_evaluation.py`：解析规则、判分规则、**分母规则**。

三处曾与官方不一致的地方，现已同步：
1. 分母：官方对格式错误的回复 `continue`（不计入分母），对空回复/字面量 `None`
   计入分母但不得分。这里用哨兵 `DROP` 区分两者，`match` 对 DROP 返回 None，
   由 `compute_metric` 剔除，分母与官方完全一致。
2. 音频：官方读 HF `Audio` 特征解码后的 16kHz 单声道数组。这里用 `soundfile`
   解码 + `soxr` 重采样到 16kHz 再编码成 WAV(PCM16)，内容与官方一致；
   剩余差异只有 float32→PCM16 量化（约 -90dB，可忽略）。
3. 报表粒度：官方按 (category, sub-category) 分组输出。这里的 `load()` 支持
   通过 subset_list 传入 `"Perception|Linguistics"` 这类分组键来拆分；
   拆开后整体分数仍按样本加权（micro），与官方总体准确率相等。
"""
from __future__ import annotations

import base64
import glob
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyarrow.parquet as pq

from evalscope.benchmarks import Benchmark, DataAdapter
from evalscope.constants import OutputType

LETTERS = ('A', 'B', 'C', 'D')

# 官方 mmsu_inference.py 的指令文案，含结尾句号与空行结构
INSTRUCTION = ('Choose the most suitable answer from options A, B, C, and D. '
               'You must respond with only A, B, C, or D.')

# 「格式错误、官方不计入分母」的哨兵值。空字符串表示「计入分母但不得分」。
DROP = '__mmsu_format_error__'

TARGET_SAMPLE_RATE = 16000


def sniff_audio_format(data: bytes) -> str:
    """按文件头判断容器格式（上游扩展名不可信）。"""
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return 'wav'
    if len(data) >= 4 and data[:4] == b'fLaC':
        return 'flac'
    if len(data) >= 4 and data[:4] == b'OggS':
        return 'ogg'
    if len(data) >= 3 and data[:3] == b'ID3':
        return 'mp3'
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return 'mp3'
    return 'wav'


def to_official_wav(data: bytes) -> bytes:
    """复刻官方音频口径：解码 → 单声道 → 16kHz → WAV(PCM16)。

    失败时抛异常，由调用方决定回退策略。
    """
    import numpy as np
    import soundfile as sf
    import soxr

    array, sample_rate = sf.read(io.BytesIO(data), dtype='float32', always_2d=True)
    mono = array.mean(axis=1) if array.shape[1] > 1 else array[:, 0]
    if sample_rate != TARGET_SAMPLE_RATE:
        mono = soxr.resample(mono, sample_rate, TARGET_SAMPLE_RATE, quality='HQ')
    mono = np.clip(mono, -1.0, 1.0)
    buffer = io.BytesIO()
    sf.write(buffer, mono, TARGET_SAMPLE_RATE, subtype='PCM_16', format='WAV')
    return buffer.getvalue()


class _AudioStore:
    """按需读取 parquet 内嵌音频，避免一次性把 1.6GB 载入内存。

    只缓存最近一个 row group（约 100 条），切换分片时释放旧缓存。
    """

    def __init__(self, paths: List[Path]):
        self._files = [pq.ParquetFile(str(p)) for p in paths]
        self._cache: Dict[tuple, Any] = {}

    def get(self, shard: int, group: int, index: int) -> bytes:
        key = (shard, group)
        table = self._cache.get(key)
        if table is None:
            if len(self._cache) > 1:
                self._cache.clear()
            table = self._files[shard].read_row_group(group, columns=['audio'])
            self._cache[key] = table
        audio = table.column('audio')[index].as_py() or {}
        return audio.get('bytes') or b''


@Benchmark.register(
    name='mmsu',
    pretty_name='MMSU',
    dataset_id='ddwang2000/MMSU',
    subset_list=['default'],
    metric_list=['AverageAccuracy'],
    few_shot_num=0,
    train_split=None,
    eval_split='train',
    output_types=[OutputType.GENERATION],
    tags=['audio', 'speech', 'multimodal'],
)
class MMSUAdapter(DataAdapter):
    """MMSU 四选一语音题。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.train_split = None
        self.eval_split = 'train'
        extra = kwargs.get('extra_params') or {}
        # include_audio=False 时退化为纯文本，仅用于无音频模型时打通链路
        self.include_audio = bool(extra.get('include_audio', True))
        # audio_profile:
        #   official（默认）= 解码 + 16kHz 重采样 + WAV PCM16，与官方输入分布一致
        #   raw            = 直接下发 parquet 原始字节（省 CPU，但采样率可能不是 16k）
        self.audio_profile = str(extra.get('audio_profile', 'official')).lower()
        self._store: Optional[_AudioStore] = None
        self._paths: List[Path] = []

    # ------------------------------------------------------------------ 数据加载
    def load(self, dataset_name_or_path: str = None, subset_list: list = None,
             work_dir: Optional[str] = None, **kwargs) -> dict:
        """覆写父类实现。

        父类的 load_from_disk 在循环里对同一 subset/split 反复赋值，多个 parquet
        分片只有最后一个会生效（5000 条只剩 1666 条）。这里显式合并全部分片。

        subset_list 语义：
          - 缺省 / ['default']：全部 5000 条一个子集；
          - 形如 'Perception|Linguistics' 的分组键：按 (category, sub-category) 过滤。
        """
        root = os.path.expanduser(dataset_name_or_path or self.dataset_id)
        if not os.path.isdir(root):
            raise FileNotFoundError(f'MMSU 数据集目录不存在：{root}')
        paths = sorted(Path(p) for p in glob.glob(os.path.join(root, '*.parquet')))
        if not paths:
            raise FileNotFoundError(f'MMSU 目录下没有 parquet：{root}')

        self._paths = paths
        self._store = _AudioStore(paths)

        rows: List[dict] = []
        for shard, path in enumerate(paths):
            pf = pq.ParquetFile(str(path))
            for group in range(pf.metadata.num_row_groups):
                table = pf.read_row_group(group, columns=[
                    'id', 'task_name', 'question', 'choice_a', 'choice_b', 'choice_c', 'choice_d',
                    'answer_gt', 'category', 'sub-category'])
                for index, row in enumerate(table.to_pylist()):
                    row['_shard'] = shard
                    row['_group'] = group
                    row['_index'] = index
                    rows.append(row)

        if not rows:
            raise ValueError(f'MMSU 数据集为空：{root}')

        requested = subset_list or self.subset_list or ['default']
        if requested == ['default']:
            return {'default': {'train': rows}}

        grouped: Dict[str, List[dict]] = {}
        for row in rows:
            grouped.setdefault(self.group_key(row), []).append(row)
        data = {key: {'train': grouped[key]} for key in requested if key in grouped}
        if not data:
            raise ValueError(f'MMSU 没有匹配的子集：{requested}；可用键见 group_key()')
        return data

    # ------------------------------------------------------------------ 分组
    @staticmethod
    def group_key(row: Dict) -> str:
        """与官方 mmsu_evaluation.py 的分组口径一致：category / sub-category。"""
        return f"{row.get('category') or ''}|{row.get('sub-category') or ''}"

    # ------------------------------------------------------------------ 提示词
    @staticmethod
    def _choices_text(input_d: Dict) -> List[str]:
        return [input_d.get('choice_a') or '', input_d.get('choice_b') or '',
                input_d.get('choice_c') or '', input_d.get('choice_d') or '']

    def _audio_payload(self, input_d: Dict) -> Optional[Dict[str, str]]:
        audio = self._store.get(input_d['_shard'], input_d['_group'], input_d['_index']) \
            if self._store else b''
        if not audio:
            return None
        if self.audio_profile == 'raw':
            return {'data': base64.b64encode(audio).decode('ascii'),
                    'format': sniff_audio_format(audio)}
        try:
            wav = to_official_wav(audio)
        except Exception as exc:  # noqa: BLE001 - 解码失败不应中断整轮评测
            print(f'[mmsu] 音频转 16kHz 失败，回退原始字节：{type(exc).__name__}: {exc}')
            return {'data': base64.b64encode(audio).decode('ascii'),
                    'format': sniff_audio_format(audio)}
        return {'data': base64.b64encode(wav).decode('ascii'), 'format': 'wav'}

    def gen_prompt(self, input_d: dict, subset_name: str = 'default',
                   few_shot_list: list = None, **kwargs) -> dict:
        choices = self._choices_text(input_d)
        # 官方拼法：A. xxx\nB. xxx\nC. xxx\nD. xxx（choice_c/d 为空时该行仍保留）
        choice_block = '\n'.join(f'{LETTERS[i]}. {choices[i]}' for i in range(4))
        prompt = f'{INSTRUCTION}\n\nQuestion: {input_d.get("question", "")}\n\n{choice_block}'

        if not self.include_audio:
            return self.gen_prompt_data(prompt, id=input_d.get('id'))

        audio = self._audio_payload(input_d)
        if not audio:
            return self.gen_prompt_data(prompt, id=input_d.get('id'))

        messages = [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'input_audio', 'input_audio': audio},
            ],
        }]
        return self.gen_prompt_data(prompt, messages=messages, id=input_d.get('id'))

    # ------------------------------------------------------------------ 判分
    @staticmethod
    def _extract_letter(result: str) -> str:
        """复刻官方解析规则；返回字母、''（空/None，计错）或 DROP（格式错误，丢分母）。"""
        if result is None:
            return ''
        predict = str(result).strip().replace('\n', '')
        if not predict or predict == 'None':
            return ''
        if predict[0] in LETTERS:
            return predict[0]
        if len(predict) > 1 and predict[-2] in LETTERS:
            return predict[-2]
        return DROP

    def get_gold_answer(self, input_d: dict) -> str:
        """官方按「选项文本」判分，因此 gold 取 answer_gt 原文。"""
        return input_d.get('answer_gt') or ''

    def parse_pred_result(self, result: str, raw_input_d: dict = None,
                          eval_type: str = 'checkpoint') -> str:
        """解析为「模型所选字母对应的选项文本」；DROP 原样传递以便下游剔除。"""
        letter = self._extract_letter(result)
        if letter == DROP:
            return DROP
        if not letter or not raw_input_d:
            return ''
        return self._choices_text(raw_input_d)[LETTERS.index(letter)]

    def match(self, gold: str, pred: str) -> Optional[float]:
        """与官方 `choices[model_predict] == answer_gt` 等价。

        对 DROP 返回 None，表示「官方不计入分母」，由 compute_metric 剔除。
        """
        if pred == DROP:
            return None
        return 1.0 if pred and gold and pred == gold else 0.0

    def compute_metric(self, review_res_list, **kwargs) -> List[dict]:
        """剔除被丢弃的样本，使分母与官方 mmsu_evaluation.py 完全一致。"""
        if isinstance(review_res_list, list):
            review_res_list = [item for item in review_res_list if item is not None]
        return super().compute_metric(review_res_list, **kwargs)
