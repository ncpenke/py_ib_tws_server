from os import replace, stat
from ib_tws_server.api_definition import *
from ib_tws_server.util.type_util import full_type_name_for_annotation
import inspect
import re
from typing import Callable, List

class GeneratorUtils:
    @staticmethod
    def type_name(name: str):
        return name[0].upper() + name[1:]    
    
    @staticmethod
    def request_method_name(d: ApiDefinition, u: Callable, is_subscription: bool):
        if is_subscription and d.subscription_flag_name is not None:
                return f"{u.__name__}AsSubscription"
        return u.__name__

    @staticmethod
    def callback_types(d: ApiDefinition) -> List[str]:
        annotations = set()
        for e in d.callback_methods:
            annotation,is_wrapper=GeneratorUtils.callback_type(d, e)
            annotations.add(annotation)
        return list(annotations)        

    @staticmethod
    def response_type(d: ApiDefinition, is_subscription: bool):
        callback_types = GeneratorUtils.callback_types(d)
        if len(callback_types) > 1:
            response_type = f"Union[{','.join([a for a in callback_types])}]"""
        else:
            response_type = f"{callback_types[0]}"

        if not is_subscription and GeneratorUtils.response_is_list(d):
            response_type = f"List[{response_type}]"
        return response_type

    @staticmethod
    def get_num_params(u: Callable):
        return len(GeneratorUtils.signature(u).parameters.values())

    @staticmethod
    def callback_type(d: ApiDefinition, u: Callable):
        params = list(GeneratorUtils.signature(u).parameters.values())
        single_member = None
        all_cbs_have_same_parameter_count = True
        for cb in d.callback_methods:
            if GeneratorUtils.get_num_params(cb) != len(params):
                all_cbs_have_same_parameter_count = False
                break

        if all_cbs_have_same_parameter_count:
            if len(params) == 2:
                single_member = params[1]
            elif len(params) == 3 and d.uses_req_id:
                single_member = params[2]
        if single_member is not None:
            return (full_type_name_for_annotation(single_member.annotation, ibapi), False)
        return (f"{GeneratorUtils.type_name(u.__name__)}", True)

    @staticmethod
    def req_id_param_name(u: Callable):
        return list(GeneratorUtils.signature(u).parameters.values())[1].name

    @staticmethod
    def req_id_names(d: ApiDefinition):
        ret = []
        if not d.uses_req_id:
            return ret
        ret.append(GeneratorUtils.req_id_param_name(d.request_method))
        if d.callback_methods is not None:
            for m in d.callback_methods:
                ret.append(GeneratorUtils.req_id_param_name(m))
        return ret

    params_regex = re.compile("[\s]*def[\s]+[^(]+\(([^)]+)\)")
    _cached_signatures = {}
    @staticmethod
    def signature(u: object):
        if u in GeneratorUtils._cached_signatures:
            return GeneratorUtils._cached_signatures[u]
        sig = inspect.signature(u)
        if u.__name__ in OVERRIDDEN_METHOD_SIGNATURES:
            code = OVERRIDDEN_METHOD_SIGNATURES[u.__name__]
        else:
            code = inspect.getsource(u)
        params_raw = GeneratorUtils.params_regex.match(code).groups()[0].split(',')
        sig_params = list(sig.parameters.values())
        index = 0
        if len(sig_params) != len(params_raw):
            raise RuntimeError(f"Error in parameter parsing for method {sig}")
        for sp,raw in zip(sig_params, params_raw):
            raw = [ r.strip() for r in raw.split(":") ]
            if (raw[0] != sp.name):
                raise RuntimeError(f"Error in parameter parsing for method {sig} {raw[0]} {sp.name}")
            if raw[0] != "self":
                if len(raw) != 2:
                    raise RuntimeError(f"Error method missing annotation {sig}")
                annotation = raw[1]
                if annotation in OVERRIDDEN_TYPE_ALIASES:
                    annotation = OVERRIDDEN_TYPE_ALIASES[annotation]
                else:
                    annotation = full_type_name_for_annotation(annotation, ibapi)
                sig_params[index] = sp.replace(annotation=annotation)
            index += 1
        sig = sig.replace(parameters=sig_params)
        GeneratorUtils._cached_signatures[u] = sig
        return sig

    @staticmethod
    def data_class_members(d: ApiDefinition, methods: List[Callable], streaming_class: bool) -> List[inspect.Parameter]:
        to_skip = [ "self" ]
        if d.has_done_flag and d.callback_methods is not None and not streaming_class:
            to_skip.append("done")
        req_id_names = GeneratorUtils.req_id_names(d)
        if req_id_names is not None:
            to_skip.extend(req_id_names)
        ret = []
        processed = {}
        for m in methods:
            for v in GeneratorUtils.signature(m).parameters.values():
                if v.name not in to_skip:
                    if v.name in processed:
                        if processed[v.name] != v.annotation:
                            raise RuntimeError(f"{v.name} parameter in method {m.__name__} has different types in different callbacks {processed[v.name]} {v.annotation}")
                    else:
                        processed[v.name] = v.annotation
                        ret.append(v)
        return ret

    @staticmethod
    def forward_parameters(m: callable) -> str:
        params = [ v.name for v in GeneratorUtils.signature(m).parameters.values() ]
        return ','.join(params)

    @staticmethod
    def method_declaration(m: callable) -> str:
        return f"{m.__name__}{str(GeneratorUtils.signature(m))}"

    @staticmethod
    def doc_string(m: callable) -> str:
        return f'"""{m.__doc__}"""' if m.__doc__ is not None else '""""""'

    @staticmethod
    def response_is_list(d: ApiDefinition):
        return d.has_done_flag or d.done_method is not None

    @staticmethod
    def bind_method(func: callable) -> str:
        return f"functools.partial(EClient.{func.__name__},{GeneratorUtils.forward_parameters(func)})"

    @staticmethod
    def type_to_type_name_str(o: any) -> str:
        if hasattr(o, '__name__'):
            return getattr(o, '__name__')
        else:
            return str(o)

    @staticmethod
    def query_callback_response_params(d: ApiDefinition, u: Callable) -> List[inspect.Parameter]:
        params = GeneratorUtils.data_class_members(d, [u], False)
        if (d.has_done_flag or d.done_method is not None):
            return [ p.replace(annotation=f"List[{p.annotation}]") for p in params]
        return params

    @staticmethod
    def request_return_type(d: ApiDefinition, is_subscription: bool):
        if is_subscription:
            return "Subscription"
        elif (d.callback_methods is not None):
            return GeneratorUtils.response_type(d, is_subscription)
        else:
            return "None"

    @staticmethod
    def unqualified_type_name(s: str):
        return s.split(".")[-1]