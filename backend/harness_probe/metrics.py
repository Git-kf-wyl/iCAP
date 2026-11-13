"""Deterministic benchmark scoring, with explicit missing-evidence states.

Reference data is controller-owned and MUST NOT be mounted into agent workspaces.
This evaluator never substitutes a context-size heuristic for benchmark accuracy.
"""
from __future__ import annotations

import json
from typing import Any

METRICS = {
    'needle_retention': ('关键信息保留率', 'ContextBench / Needle Retention'),
    'retention_checks': ('信息保留相关检查通过率', 'TraceTrial-Bench / C2,C3'),
    'state_accuracy': ('状态维护正确率', 'ContextBench / Sudoku Sketchpad'),
    'state_transfer': ('状态传递相关检查通过率', 'TraceTrial-Bench / C5'),
    'history_accuracy': ('历史信息利用正确率', 'ContextBench / KV Store,Log Triage'),
    'truncation_recovery': ('截断恢复相关检查通过率', 'TraceTrial-Bench / C1'),
    'session_continuity': ('会话接续相关检查通过率', 'TraceTrial-Bench / C4'),
    'agent_isolation': ('隔离交接相关检查通过率', 'TraceTrial-Bench / C6'),
}


def messages(event):
    window = event.get('window', {})
    if isinstance(window, list):
        return window
    return window.get('system_messages', []) + window.get('context_messages', [])


def _lookup(value, path):
    for key in path:
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def evaluate(events: list[dict], specification: dict | None) -> list[dict]:
    """A reference defines explicit event selector, named checks and expected units.

    Scoring types: literal_in_context (verbatim needles), exact (boards/answers),
    roles_equal, excludes and checks (controller-produced boolean assertions).
    Every check is an expected unit. Missing outputs fail expected units; a
    missing entire reference or unfinished evidence never becomes a zero score.
    """
    definitions = (specification or {}).get('metrics', {})
    results = []
    for metric_id, (name, benchmark) in METRICS.items():
        base = {'id':metric_id, 'name':name, 'benchmark':benchmark, 'direction':'higher',
                'numerator':None, 'denominator':None, 'value':None, 'checks':[],
                'status':'missing_reference', 'reason':'未配置此任务的标准答案或检查项'}
        definition = definitions.get(metric_id)
        selector = (definition or {}).get('selector', {'kind':'context.window'})
        selected = [e for e in events if all(e.get(k) == v for k,v in selector.items())]
        base['evidence_count'] = len(selected)
        base['evidence_status'] = 'available' if selected else 'missing'
        if not definition:
            results.append(base)
            continue
        checks = definition.get('checks', [])
        if not checks or len({c['id'] for c in checks}) != len(checks):
            raise ValueError(f'{metric_id}: checks must have unique IDs and be nonempty')
        if not selected:
            base.update(status='missing_evidence', reason='等待匹配的真实采集事件')
            results.append(base)
            continue
        evidence = selected[-1]
        verdicts = []
        for check in checks:
            kind = check['type']
            candidates = [e for e in selected if all(e.get(k)==v for k,v in check.get('selector',{}).items())]
            index = check.get('occurrence', -1)
            evidence = candidates[index] if candidates and -len(candidates) <= index < len(candidates) else {
                'event_id': None, 'missing': True}
            try:
                if evidence.get('missing'): raise KeyError('expected event absent')
                if kind in {'literal_in_context', 'excludes'}:
                    # Serialize only actual message content, not model/tool metadata.
                    text = '\n'.join(str(m.get('content', '')) for m in messages(evidence))
                    passed = check['expected'] in text
                    if kind == 'excludes': passed = not passed
                elif kind == 'roles_equal':
                    passed = [m.get('role') for m in messages(evidence)] == check['expected']
                elif kind == 'exact':
                    passed = _lookup(evidence, check['path']) == check['expected']
                elif kind == 'checks':
                    # Only grader observations, never agent-supplied assertions.
                    if evidence.get('kind') != 'grader.checks':
                        raise ValueError('boolean checks require controller grader evidence')
                    passed = _lookup(evidence, check['path']) is True
                else:
                    raise ValueError(f'Unknown check type: {kind}')
            except (KeyError, IndexError, TypeError):
                passed = False
            verdicts.append({'id':check['id'], 'passed':passed, 'event_id':evidence['event_id'],
                             'trace_id':evidence.get('trace_id'), 'span_id':evidence.get('span_id')})
        numerator = sum(c['passed'] for c in verdicts)
        base.update(status='scored', reason='', numerator=numerator, denominator=len(verdicts),
                    value=numerator/len(verdicts), checks=verdicts,
                    reference_version=specification.get('version'), event_id=evidence['event_id'])
        results.append(base)
    return results


def aggregate(task_results: list[list[dict]]) -> list[dict]:
    """Micro-average scored units only; expose coverage and all missing states."""
    rows = []
    for metric_id, (name, benchmark) in METRICS.items():
        available = [m for task in task_results for m in task if m['id'] == metric_id]
        scored = [m for m in available if m['status'] == 'scored']
        numerator = sum(m['numerator'] for m in scored)
        denominator = sum(m['denominator'] for m in scored)
        rows.append({'id':metric_id, 'name':name, 'benchmark':benchmark,
                     'value':numerator/denominator if denominator else None,
                     'numerator':numerator if denominator else None,
                     'denominator':denominator or None,
                     'status':'scored' if denominator else 'unscored',
                     'scored_tasks':len(scored), 'total_tasks':len(available),
                     'missing_reference':sum(m['status']=='missing_reference' for m in available),
                     'evidence_tasks':sum(m['evidence_count'] > 0 for m in available),
                     'missing_evidence':sum(m['evidence_count'] == 0 for m in available)})
    return rows
