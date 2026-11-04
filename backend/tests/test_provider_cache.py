import threading
import time
import httpx
from app.model_registry import ModelRegistry
from app.store import Store


def test_provider_catalog_is_persistent_and_refresh_does_not_block(tmp_path,monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-only-provider-key')
    store=Store(tmp_path)
    monkeypatch.setattr(httpx,'get',lambda *a,**k:httpx.Response(200,json={'data':[{'id':'real-discovered-model'}]},request=httpx.Request('GET','https://provider.test/models')))
    registry=ModelRegistry(store)
    discovered=registry._remote_models()
    assert discovered[0]['id']=='real-discovered-model'
    restored=ModelRegistry(store)
    assert restored._catalog_cache==discovered
    entered=threading.Event();release=threading.Event()
    def unavailable(*args,**kwargs):
        entered.set();release.wait(3)
        raise httpx.ConnectError('provider unavailable')
    monkeypatch.setattr(httpx,'get',unavailable)
    started=time.perf_counter()
    assert restored._remote_models()==discovered
    assert time.perf_counter()-started<.3,'Cached catalog must not wait for the upstream network'
    assert entered.wait(1)
    release.set()
    deadline=time.monotonic()+3
    while restored._catalog_refreshing and time.monotonic()<deadline:time.sleep(.01)
    assert not restored._catalog_refreshing
    store.close()
