"""iCAP-authenticated bridge to private Langfuse and controller probe artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from harness_probe.metrics import evaluate, aggregate

_RUN_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
_TRACE_ID = re.compile(r'^[0-9a-f]{32}$')


class LangfuseClient:
    def __init__(self):
        self.base = os.getenv('LANGFUSE_HOST', 'http://127.0.0.1:3100').rstrip('/')
        self.auth = (os.getenv('LANGFUSE_PUBLIC_KEY',''), os.getenv('LANGFUSE_SECRET_KEY',''))

    def request(self, method, path, **kwargs):
        if not all(self.auth):
            raise HTTPException(503, 'Langfuse 后端凭据尚未配置')
        try:
            with httpx.Client(auth=self.auth, trust_env=False, timeout=30) as client:
                response = client.request(method, self.base+'/api/public/'+path, **kwargs)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, 'Langfuse 暂不可用，请稍后重试') from exc

    def observations(self, trace_id):
        rows, cursor, seen, cursors = [], None, set(), set()
        while True:
            params = {'traceId':trace_id, 'limit':100, 'fields':'core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context'}
            if cursor: params['cursor'] = cursor
            page = self.request('GET', 'v2/observations', params=params)
            for row in page.get('data', []):
                if row.get('traceId') != trace_id:
                    raise HTTPException(502, 'Langfuse 返回了不匹配的调用链')
                if row['id'] not in seen:
                    seen.add(row['id']); rows.append(row)
            next_cursor = page.get('meta', {}).get('cursor')
            if not next_cursor: break
            if next_cursor in cursors: raise HTTPException(502, 'Langfuse 分页未前进')
            cursors.add(next_cursor)
            cursor = next_cursor
        return rows


class RunEvidence:
    def __init__(self, runs_dir, references=None):
        self.runs = Path(runs_dir).resolve()
        self.references = Path(references or os.getenv('HARNESS_REFERENCE_DIR','/var/lib/icap/harness_references')).resolve()

    def directory(self, run_id):
        if not _RUN_ID.fullmatch(run_id): raise HTTPException(422, '运行 ID 无效')
        path = (self.runs/run_id).resolve()
        if not path.is_relative_to(self.runs) or not (path/'run.json').is_file():
            raise HTTPException(404, '运行不存在')
        return path

    def events(self, run_id):
        path = self.directory(run_id)
        meta = json.loads((path/'run.json').read_text())
        selected = meta.get('task_ids') or str(meta.get('task_id','')).split(',')
        rows = []
        # Walk only selected task directories; reject symlink escapes.
        for task_id in selected:
            if not _RUN_ID.fullmatch(task_id): continue
            task_path = (path/'artifacts/tasks'/task_id).resolve()
            if not task_path.is_relative_to(path): continue
            for source in sorted(task_path.glob('trace/round-*/context-probe.jsonl')):
                if not source.resolve().is_relative_to(path): continue
                with source.open() as stream:
                    for line in stream:
                        try: row = json.loads(line)
                        except ValueError: continue  # An in-flight final append is retried on next poll.
                        if row.get('run_id') == run_id and row.get('task_id') == task_id:
                            rows.append(row)
            # Grader evidence is controller-owned, never read boolean verdicts from agent trace.
            grader_path = task_path/'context-grader.json'
            if grader_path.is_file() and grader_path.resolve().is_relative_to(path):
                payload=json.loads(grader_path.read_text())
                for row in payload.get('events',[]):
                    rows.append({**row,'kind':'grader.checks','run_id':run_id,'task_id':task_id})
        return meta, rows

    def trace_ids(self, run_id):
        _, rows = self.events(run_id)
        result = {}
        for row in rows:
            tid = row.get('trace_id')
            if tid and _TRACE_ID.fullmatch(tid):
                entry = result.setdefault(tid, {'id':tid,'task_id':row['task_id'],
                    'round':row.get('round'), 'started_at':row.get('timestamp'), 'probe_events':0})
                entry['probe_events'] += 1
        return list(result.values())

    def metrics(self, run_id):
        meta, rows = self.events(run_id)
        tasks = []
        for task_id in meta.get('task_ids') or str(meta.get('task_id','')).split(','):
            if not _RUN_ID.fullmatch(task_id): continue
            reference_path = (self.references/(task_id+'.json')).resolve()
            reference = None
            if reference_path.is_relative_to(self.references) and reference_path.is_file():
                reference = json.loads(reference_path.read_text())
            task_rows = [r for r in rows if r['task_id']==task_id]
            scores = evaluate(task_rows, reference)
            tasks.append({'task_id':task_id, 'reference_configured':reference is not None,
                          'context_windows':sum(r['kind']=='context.window' for r in task_rows),
                          'metrics':scores})
        windows = [r for r in rows if r['kind']=='context.window']
        return {'run_id':run_id, 'metrics':aggregate([t['metrics'] for t in tasks]), 'tasks':tasks,
                'process':{'probe_events':len(rows),'context_windows':len(windows),
                           'context_errors':sum(r['kind']=='context.error' for r in rows),
                           'hook_latency_ms':sum(r.get('elapsed_ms',0) for r in windows),
                           'trace_count':len(self.trace_ids(run_id))},
                'diagnostics':{'reference_tasks':sum(t['reference_configured'] for t in tasks),
                               'selected_tasks':len(tasks),
                               'scoring_ready':any(m['status']=='scored' for t in tasks for m in t['metrics']),
                               'reference_requirement':'ContextBench / TraceTrial-Bench 专用任务标准答案及检查项；通用 Harness outcome_score 不能代替这八项准确率'},
                'sampled_at':__import__('time').time()}


def router(auth_dep, runs_dir):
    api = APIRouter(prefix='/api/harness-eval', tags=['harness-observability'],
                    dependencies=[Depends(auth_dep)])
    evidence = RunEvidence(runs_dir)

    @api.get('/model-capabilities')
    def model_capabilities(request:Request, actor=Depends(auth_dep)):
        from .model_thinking import capabilities
        return {'models':[capabilities(m) for m in request.app.state.registry.list_models(actor)]}


    @api.get('/runs/{run_id}/traces')
    def traces(run_id: str):
        return {'traces':evidence.trace_ids(run_id)}

    @api.get('/runs/{run_id}/traces/{trace_id}')
    def trace(run_id: str, trace_id: str):
        if trace_id not in {r['id'] for r in evidence.trace_ids(run_id)}:
            raise HTTPException(404,'此调用链不属于所选评测')
        client=LangfuseClient()
        observations=client.observations(trace_id)
        meta,rows=evidence.events(run_id)
        snapshots={r['span_id']:r for r in rows if r['kind']=='context.window' and r.get('trace_id')==trace_id}
        for observation in observations:
            snapshot=snapshots.get(observation['id'])
            if snapshot:
                # The local hook preserves full context even if transport attribute limits apply.
                observation['input']={'messages':snapshot.get('before')}
                observation['output']=snapshot['window']
                metadata=observation.get('metadata') or {}
                if isinstance(metadata,dict):
                    observation['metadata']={**metadata,'icap_local_evidence':snapshot['event_id']}
        expected={r['span_id'] for r in rows if r['kind']=='trace.observation' and r.get('trace_id')==trace_id}
        actual={o['id'] for o in observations}
        complete=bool(expected) and expected.issubset(actual) and meta.get('status') in {'finished','failed','stopped'}
        # v4 events_only deployments have no legacy /traces/{id} REST endpoint.
        # Build the native trace summary from real root observations instead.
        roots=[o for o in observations if not o.get('parentObservationId')]
        root=min(roots or observations,key=lambda o:o['startTime']) if observations else None
        if root is None:raise HTTPException(404,'调用链尚在入库，请稍后刷新')
        project=os.getenv('LANGFUSE_PROJECT_ID','openjiuwen-demo')
        scores=[]
        # v4 also disables legacy score-read REST routes; the controller's
        # reference-scored evidence remains the authoritative score source.
        for task in evidence.metrics(run_id)['tasks']:
            for metric in task['metrics']:
                if metric['status']!='scored' or not any(c.get('trace_id')==trace_id for c in metric['checks']):continue
                identity=f"{run_id}:{task['task_id']}:{metric['id']}:{trace_id}:{metric.get('reference_version')}"
                scores.append({'id':hashlib.sha256(identity.encode()).hexdigest(),'traceId':trace_id,
                               'name':metric['id'],'value':metric['value'],'dataType':'NUMERIC',
                               'timestamp':root['startTime'],'source':'API',
                               'comment':json.dumps(metric,ensure_ascii=False)})
        summary={'id':trace_id,'projectId':project,'timestamp':root['startTime'],
                 'name':root.get('traceName') or root.get('name'),'input':root.get('input'),'output':root.get('output'),
                 'metadata':root.get('metadata') or {},'environment':root.get('environment','default'),
                 'sessionId':root.get('sessionId'),'rootObservationId':root['id'],
                 'rootObservationType':root.get('type'),'scores':scores}
        return {'trace':summary,
                'observations':observations, 'complete':complete,
                'expected_observations':len(expected), 'received_observations':len(actual),
                'projectId':os.getenv('LANGFUSE_PROJECT_ID','openjiuwen-demo')}

    @api.get('/runs/{run_id}/metrics')
    def metrics(run_id: str):
        return evidence.metrics(run_id)

    @api.get('/runs/{run_id}/context')
    def context(run_id: str):
        _,rows=evidence.events(run_id)
        return {'events':rows}

    return api
