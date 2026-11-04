"""Import the private upstream business implementation without its credentials or SSO.

Run locally; the upstream checkout is never included in a web/static directory.
"""
from pathlib import Path
import ast
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/icap/icap_yellow_source/backend')
DEST = ROOT / 'backend/yellow'
DEST.mkdir(exist_ok=True)

class Clean(ast.NodeTransformer):
    def visit_Constant(self, node):
        if not isinstance(node.value, str):
            return node
        value = node.value
        if re.search(r'(?:sk-[a-zA-Z0-9]{16,}|https?://[^/\s]+:[^/\s]+@)', value):
            return ast.copy_location(ast.Constant(''), node)
        if re.match(r'(?:https?|ldap|wss?)://(?:10\.|7\.|192\.168\.|127\.0\.0\.1:120|[^/]*huawei\.)', value):
            return ast.copy_location(ast.Constant('http://127.0.0.1:1/unconfigured'), node)
        return node

    def visit_Assign(self, node):
        names = {n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)}
        if names & {'proxy_url','PROXY_URL'}:
            node.value = ast.Constant('')
            return node
        if names & {'proxies','users'}:
            node.value = ast.Dict(keys=[], values=[])
            return node
        if names & {'private_key','public_key','scheduler'}:
            return None
        if names & {'WORK_DIR'}:
            node.value = ast.parse('os.getcwd()').body[0].value
        return self.generic_visit(node)

    def visit_Call(self, node):
        func = ast.unparse(node.func)
        if func in {'get_pem','scheduler.start','scheduler.add_job','atexit.register'}:
            return ast.copy_location(ast.Constant(None), node)
        self.generic_visit(node)
        if func in {'httpx.HTTPTransport','httpx.AsyncHTTPTransport'}:
            node.keywords = [kw for kw in node.keywords if kw.arg != 'proxy']
        for kw in node.keywords:
            if kw.arg == 'verify' and isinstance(kw.value,ast.Constant) and kw.value.value is False:
                kw.value = ast.Constant(True)
        return node

    def visit_ImportFrom(self, node):
        if node.module and 'ai_school' in node.module:
            return None
        return node

    def visit_If(self, node):
        if '__name__' in ast.unparse(node.test):
            return None
        return self.generic_visit(node)

for folder in ['services','utils']:
    shutil.copytree(SOURCE/folder,DEST/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.log','*.bak','*.xlsx','*.png','*.jpg','*.jpeg'))
for filename in ['server.py','run_test_server.py','paper_agent_server.py','huggingface_download_adapter.py','modelscope_download_adapter.py']:
    shutil.copy2(SOURCE/filename,DEST/filename)
for p in DEST.rglob('*.py'):
    try:
        source=p.read_text('utf-8-sig')
    except UnicodeDecodeError:
        source=p.read_text('gb18030')
    tree=Clean().visit(ast.parse(source))
    ast.fix_missing_locations(tree)
    p.write_text('# Private iCAP Yellow business implementation. Do not publish.\n'+ast.unparse(tree)+'\n',encoding='utf-8')

# No old model catalog, user logs, credentials, cached scores or historical tasks.
seeds = DEST/'seed'
seeds.mkdir(exist_ok=True)
for name in ['common_testcase_cfg.json','field_testcase_cfg.json','dev_testcase_cfg.json']:
    import json
    raw=(SOURCE/'config'/name).read_bytes()
    for encoding in ['utf-8-sig','gb18030']:
        try:
            obj=json.loads(raw.decode(encoding));break
        except (ValueError,UnicodeDecodeError):
            continue
    for row in obj.values():
        for key in ['register','viewer_users','editor_users']:
            row.pop(key,None)
        row['viewer_users']=[]
        row['editor_users']=[]
        row['register']='admin'
        row['is_published']=True
        row['availability']='dataset_required'
    (seeds/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print('Imported private business code and dataset definitions; excluded old credentials, accounts and scores.')
