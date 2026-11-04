"""Transactional, row-based SQLite business storage with legacy JSON migration."""
from __future__ import annotations

import copy
import json
import os
import threading
from contextlib import closing
from pathlib import Path
from typing import Callable, TypeVar
from state_storage import database,close_state_root

T = TypeVar("T")


def seed() -> dict:
    return {
        "models": [],
        "datasets": [
            dict(id="ds-1", name="通用能力样例集", category="通用", version="v1.0", size=240,
                 description="MMLU、数学与代码题目示例", files=[]),
            dict(id="ds-2", name="AISF 通信领域验证集", category="通信", version="v1.1", size=180,
                 description="意图、功能调用与规划示例", files=[]),
            dict(id="ds-3", name="多模态理解样例集", category="多模态", version="v0.9", size=120,
                 description="视觉理解与语音任务示例", files=[]),
        ],
        "evaluations": [], "reports": [], "deployments": [], "school_jobs": [], "annotations": [], "skill_jobs": [],
        "papers": [
            dict(id="paper-1", title="Efficient Long-Context Reasoning for Language Models", category="模型架构", year=2026,
                 abstract="长上下文推理效率研究。此条为演示记录，尚未连接 arXiv。", source="示例数据"),
            dict(id="paper-2", title="Agent Evaluation with Verifiable Tasks", category="Agent", year=2026,
                 abstract="可验证任务驱动的智能体测评。此条为演示记录，尚未连接 arXiv。", source="示例数据"),
            dict(id="paper-3", title="Multimodal Benchmarks for Practical Systems", category="多模态", year=2025,
                 abstract="面向真实应用的多模态评测。此条为演示记录，尚未连接 arXiv。", source="示例数据"),
        ],
    }


class Store:
    def __init__(self, base: Path):
        self.base = base.resolve()
        self.base.mkdir(parents=True, exist_ok=True)
        self.uploads = self.base / "uploads"
        self.uploads.mkdir(exist_ok=True)
        self.path = self.base / "platform.sqlite3"
        self.lock = threading.RLock()
        self.database = database(self.path)
        if not self.database.exists('_platform_initialized'):
            previous=self.base/'platform.json'
            initial=json.loads(previous.read_text('utf-8-sig')) if previous.is_file() else seed()
            with self.database.transaction() as db:
                if not db.execute('SELECT 1 FROM documents WHERE name=?',('_platform_initialized',)).fetchone():
                    for key,value in initial.items():self.database.write(key,value,db)
                    self.database.write('_platform_initialized',{'version':1},db)
        if not self.database.exists('models'):
            self._save(seed())
        else:
            existing = self._read()
            missing = False
            for key, value in seed().items():
                if key not in existing:
                    existing[key] = [] if isinstance(value, list) else value
                    missing = True
            old_samples = {f"model-{i}" for i in range(1, 6)}
            kept_models = [m for m in existing.get("models", [])
                           if not (m.get("id") in old_samples and
                                   m.get("description") == "演示模型：能力分为示例数据")]
            if len(kept_models) != len(existing.get("models", [])):
                existing["models"] = kept_models
                missing = True
            if missing:
                self._save(existing)

    def _read(self) -> dict:
        return self.snapshot()

    def _save(self, data: dict) -> None:
        with self.database.transaction() as db:
            for key,value in data.items():self.database.write(key,value,db)

    def snapshot(self, collections=None) -> dict:
        with closing(self.database.connect()) as db, db:
            names=collections if collections is not None else [row[0] for row in db.execute("SELECT name FROM documents WHERE name NOT LIKE '\\_%' ESCAPE '\\'")]
            return {key:self.database.read(key,db) for key in names}

    def get_record(self,collection,identifier):
        with closing(self.database.connect()) as db:
            row=db.execute('SELECT payload FROM records WHERE document=? AND record_key=?',(collection,'#'+str(identifier))).fetchone()
            return json.loads(row[0]) if row else None

    def close(self):
        close_state_root(self.path)

    def update(self, transform: Callable[[dict], T], collections=None) -> T:
        with self.database.transaction() as db:
            names=collections if collections is not None else [row[0] for row in db.execute("SELECT name FROM documents WHERE name NOT LIKE '\\_%' ESCAPE '\\'")]
            data={key:self.database.read(key,db) for key in names}
            result = transform(data)
            for key in set(names)-data.keys():db.execute('DELETE FROM documents WHERE name=?',(key,))
            for key,value in data.items():self.database.write(key,value,db)
            return copy.deepcopy(result)
