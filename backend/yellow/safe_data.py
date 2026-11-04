"""Legacy benchmark data may contain pickled strings, never Python objects."""
import base64
import io
import pickle
import zlib

class DataUnpickler(pickle.Unpickler):
    def find_class(self,module,name):
        raise ValueError('数据集不能包含可执行 Python 对象')

def compressed_pickle_text(value):
    if len(value)>16*1024**2:raise ValueError('测试数据过大')
    decoder=zlib.decompressobj()
    raw=decoder.decompress(base64.b64decode(value),32*1024**2)
    if decoder.unconsumed_tail:raise ValueError('解压后的测试数据过大')
    result=DataUnpickler(io.BytesIO(raw)).load()
    if not isinstance(result,str):raise ValueError('测试数据必须是 JSON 字符串')
    return result
