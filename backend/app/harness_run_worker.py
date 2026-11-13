"""Supervise benchmark process and persist exit status, including signal exits."""
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


def main():
    path=Path(sys.argv[1])
    meta=json.loads(path.read_text())
    meta['pid']=os.getpid()
    meta['pid_start_ticks']=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
    tmp=path.with_suffix('.worker.tmp');tmp.write_text(json.dumps(meta,ensure_ascii=False,indent=2));tmp.replace(path)
    child=None
    def stop(signum, frame):
        # child shares this supervisor's group: normal iCAP stop signals both.
        if child is not None:
            child.terminate()
    signal.signal(signal.SIGTERM, stop)
    try:
        child=subprocess.Popen(meta['command'], cwd=meta['repo'], stdin=subprocess.DEVNULL)
        code=child.wait()
    except OSError as exc:
        code=127
        print('Benchmark launch failed:',type(exc).__name__,flush=True)
    if code != 0:
        try:
            listing=subprocess.run(['docker','ps','-aq','--filter',
                                    'label=org.harnessbench.run_id='+meta['id']],
                                   capture_output=True,text=True,timeout=15,check=True)
            ids=[i for i in listing.stdout.splitlines() if i]
            if ids:subprocess.run(['docker','rm','--force',*ids],timeout=45,check=False)
        except (OSError,subprocess.SubprocessError):
            pass
    fresh=json.loads(path.read_text())
    if fresh.get('status') != 'stopped':
        fresh['status']='finished' if code==0 else 'failed'
    fresh.update(exit_code=code, finished_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    tmp=path.with_suffix('.worker.tmp');tmp.write_text(json.dumps(fresh,ensure_ascii=False,indent=2));tmp.replace(path)
    # API scores are idempotent and only derived from controller-held references.
    try:
        from .harness_observability import RunEvidence, LangfuseClient
        evidence=RunEvidence(path.parent.parent)
        scores=evidence.metrics(fresh['id'])
        import hashlib
        for task in scores['tasks']:
            tids={r['id'] for r in evidence.trace_ids(fresh['id']) if r['task_id']==task['task_id']}
            for score in task['metrics']:
                if score['status']!='scored': continue
                # A metric's checks can reference one trace; do not copy scores to unrelated rounds.
                related={c.get('trace_id') for c in score['checks']} & tids
                for tid in related:
                    identity=f"{fresh['id']}:{task['task_id']}:{score['id']}:{tid}:{score.get('reference_version')}"
                    LangfuseClient().request('POST','scores',json={
                        'id':hashlib.sha256(identity.encode()).hexdigest(),'traceId':tid,
                        'name':score['id'],'value':score['value'],'dataType':'NUMERIC',
                        'comment':json.dumps(score,ensure_ascii=False)})
        fresh['score_export']='complete'
    except Exception as exc:
        fresh['score_export']='failed'
        fresh['score_export_error']=type(exc).__name__
    tmp=path.with_suffix('.worker.tmp');tmp.write_text(json.dumps(fresh,ensure_ascii=False,indent=2));tmp.replace(path)


if __name__=='__main__': main()
