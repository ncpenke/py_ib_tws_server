from ib_tws_server.api_definition import *
from typing import Type  

def object_member_type(obj:object, member_name: str, val: any) -> Type:
    if hasattr(OverriddenMemberTypeHints, obj.__class__.__name__):
        hints = getattr(OverriddenMemberTypeHints, obj.__class__.__name__)
        if hasattr(hints,member_name):
            return getattr(hints, member_name)
    if val is not None:
        return type(val)
    else:
        raise RuntimeError(f"Could not determine type {obj.__class__.__name__} for member {member_name}")

# TODO support nested objects
def dict_to_object(d: dict, cls: Type):
    ret = cls()
    for k,v in d.items():
        ret.__setattr__(k, v)
    return ret