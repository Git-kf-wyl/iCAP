"""Context-window probe shared by openJiuwen and MetaAgent containers."""
from .capture import install, bind_identity, record, flush

__all__ = ['install', 'bind_identity', 'record', 'flush']
