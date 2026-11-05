"""Import the supplied ranking archive once, without replacing account results."""
import copy
import json
import re
from functools import lru_cache
from state_storage import database, state_location


RANKING_FILES = ('ruler1_cheat.json', 'ruler2_cheat.json', 'ruler1_cheat_multi.json',
                 'ruler2_cheat_multi.json', 'min_cheat.json')
VERSION = 1


@lru_cache(maxsize=4)
def archive(seed):
    return {name:json.loads((seed/name).read_text('utf-8'))
            for name in (*RANKING_FILES, 'lmarena_leaderboard.json')}


def import_rankings(root, seed):
    """The marker and every imported document commit in one SQLite transaction.

    Existing scores win per model/dataset. The marker prevents deleted historical
    rows from reappearing on the next request, including after a process restart.
    """
    marker = root/'backend/config/historical_rankings_import.json'
    db_path, marker_name = state_location(marker)
    db = database(db_path)
    with db.transaction() as conn:
        if conn.execute('SELECT 1 FROM documents WHERE name=?', (marker_name,)).fetchone():
            if db.read(marker_name, conn).get('version') == VERSION:
                return
        for filename, historical in archive(seed).items():
            name = 'backend/config/'+filename
            present = conn.execute('SELECT 1 FROM documents WHERE name=?', (name,)).fetchone()
            legacy = root/name
            current = (db.read(name, conn) if present else json.loads(legacy.read_text('utf-8-sig'))
                       if legacy.is_file() else ([] if isinstance(historical,list) else {}))
            if filename in RANKING_FILES:
                for model, rows in historical.items():
                    existing = current.setdefault(model, [])
                    datasets = {row.get('dataset_name') for row in existing}
                    existing.extend(copy.deepcopy(row) for row in rows if row.get('dataset_name') not in datasets)
            elif not current:
                current = copy.deepcopy(historical)
            db.write(name, current, conn)
        db.write(marker_name, {'version':VERSION,'source':'icap_yellow/backend/config'}, conn)


def arena_rows(rows):
    """Match the original leaderboard's variant grouping without loading pandas."""
    suffix = re.compile(r'[-_.\s]?(think|thinking|high|instant|\d+|latest)$', re.I)
    groups = {}
    ordered = sorted(rows, key=lambda row:float(row.get('rank') or 0))
    for index, row in enumerate(ordered):
        name = str(row.get('model_name') or row.get('model') or '').strip()
        for _ in range(2):
            name = suffix.sub('', name).strip()
        key = re.sub(r'[.\- ]', '', name).lower()
        groups.setdefault(key, []).append((index, float(row.get('elo') or 0)))
    keep = set()
    for members in groups.values():
        highest = max(score for _,score in members)
        lowest = min(score for _,score in members)
        keep.update(index for index,score in members if highest-lowest>=20 or abs(score-highest)<1e-9)
    return [row for index,row in enumerate(ordered) if index in keep]
