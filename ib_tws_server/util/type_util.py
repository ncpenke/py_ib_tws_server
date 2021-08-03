from ib_tws_server.ib_imports import *
from typing import Type

def is_builtin_type(t: Type):
    return t in [ str, int, float, bool ]

def is_builtin_type_str(t: str):
    return t in [ 'str', 'int', 'float', 'bool' ]

def is_builtin_container_type(t: Type):
    return t in [ dict, set, list ]

def is_custom_type(t: Type):
    return not is_builtin_type(t) and not is_builtin_container_type(t)

def find_global_sym(s: str):
    syms = s.split(".")
    cur = globals()
    for s in syms:
        if isinstance(cur, dict):
            if s in cur:
                return cur[s]
            else:
                return None
        else:
            if hasattr(cur,s):
                cur = getattr(cur,s)
            else:
                return None
    return cur
