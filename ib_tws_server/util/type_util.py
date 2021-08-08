from ib_tws_server.ib_imports import *
import inspect
from typing import Type

def is_builtin_type(t: Type):
    return t in [ str, int, float, bool ]

def is_builtin_type_str(t: str):
    return t in [ 'str', 'int', 'float', 'bool' ]

def is_builtin_container_type(t: Type):
    return t in [ dict, set, list ]

def is_custom_type(t: Type):
    return not is_builtin_type(t) and not is_builtin_container_type(t)

def find_sym_from_full_name(s: str):
    syms = s.split(".")
    cur = globals()
    if len(syms) > 0:
        for s in syms:
            if isinstance(cur, dict):
                if s in cur:
                    cur = cur[s]
                else:
                    return None
            elif inspect.ismodule(cur):
                if hasattr(cur,s):
                    cur = getattr(cur,s)
                else:
                    return None
        return cur    
    return None

def find_sym_in_module(s: str, mod: any):
    for m in dir(mod):
        m = getattr(mod, m)
        if inspect.ismodule(m):
            if hasattr(m,s):
                return getattr(m,s)
    return None

def find_sym_from_full_name_or_module(s: str, mod: any):
    sym = find_sym_from_full_name(s)
    if sym is None:
        sym = find_sym_in_module(s, ibapi)
    return sym

# From https://stackoverflow.com/questions/2020014/get-fully-qualified-class-name-of-an-object-in-python
def full_class_name(o) -> str:
    if not inspect.isclass(o):
        klass = o.__class__
    else:
        klass = o
    module = klass.__module__
    if module == 'builtins':
        return klass.__qualname__ # avoid outputs like 'builtins.str'
    return module + '.' + klass.__qualname__

def full_type_name_for_annotation(annotation: str, module: any):
    ret = find_sym_in_module(annotation, module)
    if ret is not None:
        return full_class_name(ret)
    return annotation

