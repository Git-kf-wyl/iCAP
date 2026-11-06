"""Independent upload-to-job contracts; no external model or paid calls."""
import io
import json
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.skill_evolution.service import SkillService


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("INNOVATION_ADMIN_USER", "admin")
    monkeypatch.setenv("INNOVATION_ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("SKILL_EVOLVE_API_KEY", "local-review-fixture-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    # Inspect the queue without initiating any provider calls.
    monkeypatch.setattr(SkillService, "start", lambda self: None)
    app = create_app(tmp_path, demo=True)
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"username": "admin", "password": "test-password"}).json()["access_token"]
        client.headers["Authorization"] = "Bearer " + token
        yield client, app


def bundle(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return result.getvalue()


def test_upload_501_cases_rubric_reference_limit_and_resume_snapshot(pipeline):
    client, app = pipeline
    original_cases = [{"id": f"memory-{index}", "type": "memory", "sub_type": "identity",
                       "input": [{"type": "json", "data": '[{"role":"user","content":"Remember this"}]'}],
                       "key_steps": [], "output": [{"type": "onlyllm", "data": "userdata/rubric.txt"}],
                       "output_weights": {"onlyllm": 3, "text_output": 0}, "pre_condition": []}
                      for index in range(501)]
    uploaded = client.post("/api/skill-evolution/files/upload", files={"file": (
        "memory.zip", bundle([("userdata/rubric.txt", "Judge {candidate_output} strictly"),
                              ("userdata/cases.json", json.dumps(original_cases))]), "application/zip")})
    assert uploaded.status_code == 201, uploaded.text
    rows = uploaded.json()["items"]
    root = next(row for row in rows if row["kind"] == "directory")
    data = next(row for row in rows if row["name"] == "cases.json")
    rubric = next(row for row in rows if row["name"] == "rubric.txt")
    loaded = client.get(f"/api/skill-evolution/files/{data['id']}/content")
    assert loaded.status_code == 200
    cases = json.loads(loaded.json()["content"])
    payload = {"name": "501 case memory", "preset": "memory_rubric", "skill_content": "Remember user facts.",
               "dataset": cases, "managed_file_ids": [root["id"]], "cases_limit": ""}
    created = client.post("/api/skill-evolution/jobs", json=payload)
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["case_count"] == 501
    stored = app.state.skill_service.get(job["id"])
    cfg = stored["config"]
    assert len(cfg["dataset"]) == 501
    assert cfg["dataset"][0]["output_weights"]["text"] == 0
    assert cfg["dataset"][0]["output_weights"]["onlyllm"] == 3
    assert cfg["dataset"][0]["pre_condition"] == []
    rubric_copy = Path(job["workspace_path"]) / "assets" / cfg["dataset"][0]["output"][0]["data"]
    assert rubric_copy.read_text() == "Judge {candidate_output} strictly"
    assert client.delete(f"/api/skill-evolution/files/{root['id']}").status_code == 200
    assert not Path(rubric["path"]).exists()
    assert client.post(f"/api/skill-evolution/jobs/{job['id']}/cancel").status_code == 200
    assert client.post(f"/api/skill-evolution/jobs/{job['id']}/resume").status_code == 200
    assert rubric_copy.read_text() == "Judge {candidate_output} strictly"
    assert app.state.skill_service.get(job["id"])["resume"] is True
    payload.update(name="small quick check", cases_limit=3, managed_file_ids=[],
                   dataset=[{**case, "output": [{"type": "onlyllm", "data": "rubric.md"}]} for case in cases])
    limited = client.post("/api/skill-evolution/jobs", json=payload)
    assert limited.status_code == 201, limited.text
    assert limited.json()["case_count"] == 3


@pytest.mark.parametrize("reference", [{"path": "/etc/passwd"}, ["/etc/passwd"]])
def test_non_string_rubric_path_returns_validation_error(pipeline, reference):
    client, _ = pipeline
    response = client.post("/api/skill-evolution/jobs", json={
        "name": "invalid path", "skill_content": "test",
        "dataset": [{"id": "case1", "input": [{"type": "text", "data": "hello"}],
                     "output": [{"type": "onlyllm", "data": reference}]}]})
    assert response.status_code == 422


def test_enhanced_hermes_online_rubric_sees_actual_case(tmp_path):
    """Online rubric files can contain plain instructions without placeholders."""
    backend = Path(__file__).resolve().parents[1]
    script = textwrap.dedent("""
        import json, sys
        from pathlib import Path
        from types import SimpleNamespace
        backend, directory = map(Path, sys.argv[1:])
        sys.path.insert(0, str(backend))
        sys.path.insert(0, str(backend / 'vendor/skill_evolution/enhanced'))
        from app.skill_evolution.worker import patch_opt_judge, install_case_policy
        from src.self_evolve.evaluators.components.session_analyzer import SessionAnalyzer
        rubric = directory / 'online.txt'
        rubric.write_text('Judge the supplied memory using the correctness rubric. Return JSON with score.', encoding='utf-8')
        cfg = {'engine':'enhanced', 'execution_mode':'hermes', 'dataset':[
            {'id':'case1', 'input':[{'type':'json', 'data':json.dumps([{'role':'user','content':'ACTUAL QUESTION'}])}],
             'output_weights':{'onlyllm':1}}]}
        patch_opt_judge()
        install_case_policy(cfg)
        class Judge:
            def generate(self, messages):
                prompt = messages[-1]['content']
                assert 'ACTUAL ANSWER' in prompt, prompt
                assert 'ACTUAL QUESTION' in prompt, prompt
                return '{"score":73,"reason":"partial correctness"}'
        analyzer = SessionAnalyzer(model_client=Judge())
        result = analyzer.analyze(case_id='case1', input_text='ACTUAL QUESTION',
            trajectory=[SimpleNamespace(role='assistant',content='ACTUAL ANSWER')],
            key_steps=[], expected_outputs={'onlyllm':str(rubric)},
            judgment_weights={'process':0,'conciseness':0,'result':1},output_weights={'onlyllm':1})
        assert result.output_scores['onlyllm'] == 73, result
    """)
    result = subprocess.run([sys.executable, "-c", script, str(backend), str(tmp_path)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
