"""Run the original code grader without exposing iCAP files, network or secrets."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import importlib.util


def check(sample,generation,timeout,debug=False):
    if os.name!='posix' or not shutil.which('bwrap'):
        raise RuntimeError('代码评测需要 Linux bubblewrap 隔离运行环境')
    count=len(json.loads(sample['input_output'])['inputs'])
    seconds=min(120,max(3,int(timeout)))
    deadline=min(300,(seconds+1)*max(1,count))
    numpy=Path(importlib.util.find_spec('numpy').origin).parent
    source=Path(__file__).parent/'CCNRuler1EvalScope/live_code_bench/testing_util.py'
    with tempfile.TemporaryDirectory(prefix='code-grader-') as folder:
        root=Path(folder)
        tester=source.read_text('utf-8').replace('from evalscope.utils.logger import get_logger','from logging import getLogger as get_logger')
        (root/'testing_util.py').write_text(tester,'utf-8')
        (root/'runner.py').write_text('''import sys,json,resource,contextlib,io
resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024**2,8*1024**2))
resource.setrlimit(resource.RLIMIT_NPROC,(32,32))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
from testing_util import run_test
body=json.load(sys.stdin)
with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
    result,meta=run_test(body['sample'],test=body['generation'],debug=False,timeout=body['timeout'])
print(json.dumps([result,meta],default=lambda v:v.item() if hasattr(v,'item') else str(v)))
''','utf-8')
        cmd=['bwrap','--unshare-all','--die-with-parent','--new-session','--clearenv',
             '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--proc','/proc','--dev','/dev',
             '--tmpfs','/tmp','--dir','/work','--dir','/numeric','--ro-bind',str(root),'/grader','--ro-bind',str(numpy),'/numeric/numpy',
             '--setenv','PATH','/usr/bin','--setenv','PYTHONPATH','/grader:/numeric',
             '--setenv','OPENBLAS_NUM_THREADS','1','--setenv','OMP_NUM_THREADS','1','--setenv','HOME','/work',
             '--chdir','/work']
        if Path('/lib64').exists():cmd+=['--ro-bind','/lib64','/lib64']
        for libs in numpy.parent.glob('numpy*.libs'):
            cmd+=['--ro-bind',str(libs),'/numeric/'+libs.name]
        cmd+=['/usr/bin/python3','/grader/runner.py']
        try:
            proc=subprocess.run(cmd,input=json.dumps({'sample':sample,'generation':generation,'timeout':seconds}),
                                text=True,capture_output=True,timeout=deadline,check=False)
        except subprocess.TimeoutExpired:
            return [-1]*max(1,count),{'error_code':-1,'error_message':'代码运行超时'}
        if proc.returncode:
            return [-4]*max(1,count),{'error_code':-4,'error_message':'隔离环境中的代码执行失败'}
        try:
            result,metadata=json.loads(proc.stdout)
            return result,metadata
        except (ValueError,TypeError):
            return [-4]*max(1,count),{'error_code':-4,'error_message':'代码评测结果无效'}
