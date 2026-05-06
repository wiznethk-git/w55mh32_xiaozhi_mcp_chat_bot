import asyncio, json
from machine import Pin
DEFAULT_SCHEMA = { "type": "object", "additionalProperties": False }
class MCPTool:
    def __init__(self, name, description, params = {}):
        self.func_name = name
        self.description = description
        self.parameters = params if params != {} else DEFAULT_SCHEMA
        
    def get_dict_format(self):
        jsonMsg = {
            'name':self.func_name,
            'description': self.description,
            'inputSchema':self.parameters
        }
        return jsonMsg
