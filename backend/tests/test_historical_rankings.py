import json
from pathlib import Path
import pytest
from app.historical_rankings import import_rankings, archive, arena_rows, RANKING_FILES
from state_storage import register_state_root, close_state_root, read_document, write_document, state_location, database

SEED=Path(__file__).resolve().parents[1]/'yellow/seed/rankings'


@pytest.fixture
def workspace(tmp_path):
    register_state_root(tmp_path)
    root=tmp_path/'users'/'account'
    (root/'backend/config').mkdir(parents=True)
    yield root
    close_state_root(tmp_path)


@pytest.mark.parametrize('legacy_file',[False,True])
def test_history_import_preserves_new_scores_and_does_not_resurrect_deletions(workspace,legacy_file):
    historical=archive(SEED)
    model,rows=next(iter(historical['ruler1_cheat.json'].items()))
    current={model:[{**rows[0],'score':999}], 'private-model':[{'dataset_name':'private','score':5}]}
    file=workspace/'backend/config/ruler1_cheat.json'
    if legacy_file:file.write_text(json.dumps(current),encoding='utf-8')
    else:write_document(file,current)
    import_rankings(workspace,SEED)
    saved=read_document(file)
    assert saved[model][0]['score']==999
    assert saved['private-model']==current['private-model']
    for filename in RANKING_FILES[1:]:
        assert read_document(workspace/'backend/config'/filename)==historical[filename]
    assert len(read_document(workspace/'backend/config/lmarena_leaderboard.json'))==154
    assert historical['ruler1_cheat.json'][model][0]['score']!=999,'shared seed must stay immutable'
    write_document(file,{})
    import_rankings(workspace,SEED)
    assert read_document(file)=={},'deleted rows must not return on another request'


def test_history_import_is_atomic(workspace,monkeypatch):
    db_path,_=state_location(workspace/'backend/config/ruler1_cheat.json')
    db=database(db_path);original=db.write
    def fail(name,value,conn=None):
        if name.endswith('ruler2_cheat.json'):raise RuntimeError('interrupted import')
        return original(name,value,conn)
    monkeypatch.setattr(db,'write',fail)
    with pytest.raises(RuntimeError):import_rankings(workspace,SEED)
    assert not db.names(), 'partial import and marker must roll back together'


def test_arena_view_matches_original_variant_rules():
    rows=[{'model_name':'model-think','elo':100,'rank':2},
          {'model_name':'model-high','elo':110,'rank':1},
          {'model_name':'other-think','elo':80,'rank':4},
          {'model_name':'other-high','elo':120,'rank':3}]
    assert [r['rank'] for r in arena_rows(rows)]==[1,3,4]
    actual=arena_rows(archive(SEED)['lmarena_leaderboard.json'])
    assert actual and all(isinstance(r['elo'],(int,float)) for r in actual)
