"""Model-advertised thinking options shared by chat and benchmark launch."""
from fastapi import HTTPException


def capabilities(model):
    endpoints=model.get('endpoints',[])
    supported=bool(endpoints) and all(bool(e.get('thinking_schema')) for e in endpoints)
    efforts=list(dict.fromkeys(model.get('effort_levels') or [])) if supported else []
    return {'id':model['id'],'label':model.get('name',model['id']),
            'supports_thinking':supported,'thinking_modes':['enabled','disabled'] if supported else [],
            'reasoning_efforts':efforts,'default_thinking':'disabled',
            'default_effort':'high' if 'high' in efforts else (efforts[0] if efforts else None)}


def validate(model,enabled,effort):
    config=capabilities(model)
    if enabled and not config['supports_thinking']:
        raise HTTPException(422,'此模型未声明支持思考模式，请先配置模型能力')
    if effort is not None:
        if not enabled:raise HTTPException(422,'关闭思考时不能设置思考档位')
        if effort not in config['reasoning_efforts']:
            raise HTTPException(422,'此模型不支持所选思考档位')
    return config


def apply(payload,model,endpoint,enabled,effort=None):
    validate(model,enabled,effort)
    payload.update((endpoint.get('thinking_schema') or {}).get('enabled' if enabled else 'disabled',{}))
    if enabled and effort is not None:payload['reasoning_effort']=effort
    elif not enabled:payload.pop('reasoning_effort',None)
    return payload
