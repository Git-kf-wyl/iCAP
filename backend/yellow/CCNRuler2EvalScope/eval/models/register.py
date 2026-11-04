# Private iCAP Yellow implementation. Do not publish.
from .base_adapter import BaseModelAdapter
from .server_adapter import ServerModelAdapter
MODEL_ADAPTERS = {}

def register_model_adapter(name):
    """
    Decorator to register a model adapter with a given name.
    :param name: The name of the model adapter.
    """

    def decorator(adapter):
        if name in MODEL_ADAPTERS:
            raise ValueError(f"Model adapter '{name}' is already registered.")
        MODEL_ADAPTERS[name] = adapter
        return adapter
    return decorator

def get_model_adapter(name):
    """
    Retrieve a registered model adapter by name.
    :param name: The name of the model adapter.
    :return: The model adapter class or function.
    """
    optional={'aisf_clarify_server':('aisf_clarify_adapter','AISFClarifyModelAdapter'),'vla_server':('vla_server','VLAAdapter'),'aisf_function_call_server':('aisf_function_call_server','AISFFunctionCallAdapter'),'aisf_clarify_shopfood_server':('aisf_clarify_shopfood_adapter','AISFClarifyShopFoodModelAdapter')}
    if name not in MODEL_ADAPTERS and name in optional:
        import importlib
        module,cls=optional[name]
        MODEL_ADAPTERS[name]=getattr(importlib.import_module('.'+module,__package__),cls)
    if name not in MODEL_ADAPTERS:
        raise ValueError(f"Model adapter '{name}' is not registered. Available model adapters: {list(MODEL_ADAPTERS.keys())}")
    return MODEL_ADAPTERS[name]

def register_model_adapter_class(cls, name=None):
    """
    Register a model adapter class.
    :param cls: The model adapter class to register
    :param name: Optional name for the model adapter. If not provided, the class name will be used.
    """
    if name is None:
        name = cls.__name__
    if name in MODEL_ADAPTERS:
        raise ValueError(f"Model adapter class '{name}' is already registered.")
    MODEL_ADAPTERS[name] = cls
register_model_adapter_class(BaseModelAdapter, name='base')
register_model_adapter_class(ServerModelAdapter, name='server')
