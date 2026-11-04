import base64
import json
import os
from pathlib import Path
import pickle
import shutil
import sys
import zlib

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'yellow'))
from safe_data import compressed_pickle_text

def test_legacy_pickled_text_cannot_construct_objects():
    safe=base64.b64encode(zlib.compress(pickle.dumps('[{"input":"1","output":"1"}]'))).decode()
    assert json.loads(compressed_pickle_text(safe))[0]['input']=='1'
    class Executable:
        def __reduce__(self):return (eval,('1+1',))
    malicious=base64.b64encode(zlib.compress(pickle.dumps(Executable()))).decode()
    with pytest.raises(ValueError):compressed_pickle_text(malicious)

@pytest.mark.skipif(os.name!='posix' or not shutil.which('bwrap'),reason='Linux bubblewrap runtime required')
@pytest.mark.parametrize('generation,expected',[
    ('a,b=map(int,input().split());print(a+b)','3'),
    ("import pathlib;print(pathlib.Path('/opt/icap/current/backend/adapter.py').exists())",'False'),
    ("import os;print('DEEPSEEK_API_KEY' in os.environ)",'False'),
    ("import socket\ns=socket.socket()\ntry:s.connect(('1.1.1.1',53));print('connected')\nexcept OSError:print('blocked')",'blocked'),
])
def test_generated_code_isolated(generation,expected):
    from code_sandbox import check
    sample={'input_output':json.dumps({'inputs':['1 2'],'outputs':[expected],'fn_name':None})
    result,_=check(sample,generation,3)
    assert result==[True]
