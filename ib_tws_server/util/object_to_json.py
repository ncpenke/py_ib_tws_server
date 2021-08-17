import json

class JsonEncoder(json.JSONEncoder):
    """
    Default JSON encoder to debug responses
    """
    def default(self, o):
        if isinstance(o, set):
            return list(o)
        return o.__dict__

def object_to_json(o):
    return json.dumps(o, cls=JsonEncoder)

def object_to_pretty_json(o):
    return json.dumps(o, cls=JsonEncoder, indent="    ")
