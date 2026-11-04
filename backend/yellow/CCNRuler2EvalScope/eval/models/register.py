# Private iCAP Yellow implementation. Do not publish.
from .base_adapter import BaseModelAdapter
from .server_adapter import ServerModelAdapter
from .aisf_clarify_adapter import AISFClarifyModelAdapter
from .vla_server import VLAAdapter
from .aisf_function_call_server import AISFFunctionCallAdapter
from .aisf_clarify_shopfood_adapter import AISFClarifyShopFoodModelAdapter
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
register_model_adapter_class(AISFClarifyModelAdapter, name='aisf_clarify_server')
register_model_adapter_class(VLAAdapter, name='vla_server')
register_model_adapter_class(AISFFunctionCallAdapter, name='aisf_function_call_server')
register_model_adapter_class(AISFClarifyShopFoodModelAdapter, name='aisf_clarify_shopfood_server')
