import asyncio, json, gc
from urequest import urlopen
from config import config
from mcp_tools import MCPTool
from micropython import const
from machine import Pin

import device_state

TOOLS_AVAILABLE = const(4)

class MCPServer:
    def __init__(self):
        self.tools = []
        
        # Initialize tools here
        self.tools.append(MCPTool('self.list_tools', 'Run this when user ask for tools available for mcp', {}))
        self.tools.append(MCPTool('self.toggle_led', 'Turn onboard LED to on or off with values 1 as on, 0 as off.',
            {
             'type':'object',
             'properties': {
                 'value':{
                     'type':'integer',
                     'minimum':0,
                     'maximum':1
                     }
                 }
            }
        ))
# Some bugs in this. Need update
#         self.tools.append(
#             MCPTool('self.toggle_onboard_led',
#                     'Turn onboard LED on given PIN to on or off with values 1 as on, 0 as off.', {
#                         'type': 'object',
#                         'properties': {
#                             'pin':{
#                                 'type':'string',
#                                 'pattern':'^P[A-F](?:[1-9]|1[0-5])$'
#                             },
#                             
#                             'value': {
#                                 'type':'integer',
#                                 'minimum':0,
#                                 'maximum':1
#                             }
#                         },
#                         "required": ["pin", "value"]
#                     }
#                 ))
        
    async def create_tools(self):
        return
    
    async def init_connection(self, device):
        payload = {
            "session_id": device.session_id,
            "type":"mcp",
            "payload": {
              "jsonrpc": "2.0",
              "id": 1, 
              "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                  "tools": {} 
                },
                "serverInfo": {
                  "name": config.get('board_type'), 
                  "version": "0.0.1" 
                }
              }
            }
        }
        try:
            if await device.ws.open():
                gc.collect()
                await device.ws.send(json.dumps(payload))
        except OSError:
            raise OSError("!- Error in sending init mcp message")
        await self.register_tools(device)

    async def register_tools(self, device):
        payload = {
              "jsonrpc": "2.0",
              "id": 2,
              "result": {
                "tools": None
              }
        }
        try:
            if await device.ws.open():
                for tool in self.tools:
                    payload["result"]["tools"] = [tool.get_dict_format()]
                    msg = {
                        "session_id": device.session_id,
                        "type":"mcp",
                        "payload": payload      
                    }
                    gc.collect()
                    await device.ws.send(json.dumps(msg))                     
                    await asyncio.sleep_ms(10)
        except OSError:
            raise OSError("!- Error in sending init mcp tools")
        
    async def send_notification(self, device):
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/state_changed", 
            "params": {
                "newState": "listening",
                "oldState": "connecting"
          }          
        }
        msg = {
            "session_id": device.session_id,
            "type":"mcp",
            "payload": payload      
        }
        
        try:
            if await device.ws.open():
                gc.collect()
                await device.ws.send(json.dumps(msg))
                await asyncio.sleep_ms(500)
        except OSError:
            raise OSError("!- Error in sending init mcp message")
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("!- Error in receiving init mcp message")

    async def on_complete_send(self, device, success = False, func_msg = False, mcp_result = None):
        if success:
            payload = {
                "jsonrpc": "2.0",
                "id": mcp_result.get('id'),
                "result":{
                    "content": [{"type":"text","text":func_msg}],
                    "isError": False
                }
            }
        else:
            # To-Do: May have some issue.
            payload = {
                "jsonrpc": "2.0",
                "id": mcp_result.get('id'),
                "error":{
                    "code": -32601,
                    "message":func_msg
                }
            }
        
        msg = {
            "session_id": device.session_id,
            "type":"mcp",
            "payload": payload      
        }
        try:
            if await device.ws.open():
                gc.collect()
                await device.ws.send(json.dumps(msg))
                device.state = device_state.SPEAKING
        except OSError:
            raise OSError("!- Error in sending init mcp message")
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("!- Error in receiving init mcp message")
    
    #=========  All MCP Tools functions ==============
    
    async def list_tools(self, device, args = None):
        tool_fn = {}
        for i in self.tools:
            tool_fn[i.func_name] = i.description
        print(', '.join(name[5:] for name, descrp in tool_fn.items()))
        return {'success':True, 'message': tool_fn}
    
    async def toggle_led(self, device, args = None):
        # Pin for LED
        pin = Pin('PB11', Pin.OUT)
        if args.get('value', None):
            pin.value(args.get('value'))
        else:
            pin.value(1-pin.value())
        text ='on' if pin.value() else 'off'
        return {'success':True, 'message': f'The LED is now {text}'}
   
    async def toggle_onboard_led(self, device,  args = None):
        # Create LED if no led or same Pin, the pin string is in Pin(Pin.cpu.PIN, mode = MODE)
        # so only obtain the string inside and split them.
        args['pin'] = args['pin'].replace(" ", "")
        if not args['pin']:
            return {'success':False, 'message': 'Empty Pin Message.'}
        if not hasattr(Pin.board, args['pin']):
            return {'success':False, 'message': f'No Pin name { args["pin"] }.'}
        pin_name = args['pin']
        target_pin = getattr(Pin.board, pin_name)
        try:
            led = getattr(device, 'led')
            if led != target_pin:
                device.led = Pin(pin_name, Pin.OUT)
        except AttributeError:
            device.led = Pin(pin_name, Pin.OUT)
        device.led.value(args['value'])
        message = "LED is on" if args['value'] == 1 else "LED is off" # Maybe weird for PD14 because PD14 uses 0 for On and 1 for Off
        return {"success": True, "message": message }
            
            