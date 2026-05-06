import json, device_state

# Message type available from Xiaozhi ESP 32
HANDLER_TYPES = (
    "hello", 	# Initialize / Handshake
    "stt",		# Reply when server received your 
    "llm",		# Emoji change
    "tts",		# Display text on screen and voice msg
    "mcp",		# MCP tools callback
    "system",	# Rebooting
    "pong"
)

Handlers = {}

def register_handler(name):
    def decorator(func):
        Handlers[name] = func
        async def wrapper(device, msg):
            return await func(*args, msg)
        return wrapper
    return decorator

@register_handler('hello')
async def handle_init(device, msg):
    if msg.get('type') == 'hello':

        audio_param = msg.get('audio_params')
        if device.i2s_device is not None:
            device.i2s_device.format = audio_param.get('format')
            device.i2s_device.sample_rate = int(audio_param.get('sample_rate'))
            device.i2s_device.channels = int(audio_param.get('channels'))
            device.i2s_device.frame_duration = audio_param.get('frame_duration')
            device.i2s_device.set_mode(0)
         
        device.websocket_connected = True
        device.session_id = msg.get('session_id') or None
        device.state = device_state.IDLE
        return True
    else:
        print('!- Failed Hello Message. Check your config.py file')
        raise ValueError('Failed Hello Message. Check your config.py file')
    return False

@register_handler('tts')
async def handle_tts(device, msg):
    if msg['state'] == 'stop':
        if device.state == device_state.ABORT:
            # Let device become IDLE if I manually sent ABORT msg to server
            
            if device.i2s_device: device.i2s_device.complete = True
            device.ws.do_audio = False
            device.state = device_state.IDLE            
            device.ws.close()
            await device.reset_websocket()
            
        else:
            if device.i2s_device: device.i2s_device.complete = True
            # Let device become listening again if server completes sending msgs
            device.state = device_state.LISTENING
            device.ws.do_audio = False         
        return False
    else:
        text = msg.get('text') or None
    
        if text:
            device.ws.do_audio = False
            # TO-DO: print to display
            device.display.set_text(text)
            print(text)
    return True    

@register_handler('stt')
async def handle_stt(device, msg):
    device.display.set_text(msg.get('text'))
    return True

@register_handler('llm')
async def handle_llm(device, msg):
    emoji = msg.get('text')  # UTF-16 code
    if not emoji: return False
    # To-do: Set Emoji
    device.display.set_emoji(emoji)
#     print(repr(emoji))
    return True

@register_handler('pong')
async def handle_pong(device, msg):
    device.ping_pong_complete = True
    return True

@register_handler('mcp')
async def handle_mcp(device, msg):
    mcp_msg = msg.get("payload")
    if mcp_msg.get('method') != 'tools/call': return
    print('\n==== Received mcp message ====')
    is_success = False
    for tool in device.mcp.tools:
        if tool.func_name != mcp_msg.get('params').get('name'): continue
        func = getattr(device.mcp, tool.func_name[5:]) # Remove leading 'self.'
        args = mcp_msg.get('params').get('arguments') or None
        tool_message = None or await func(device, args)
#     for tool in device.mcp.tools:
#         if tool.get_func_name() != mcp_msg.get('params').get('name'): continue
#         func = getattr(device.mcp, tool.get_func_name()[5:]) # Remove leading 'self.'
#         args = mcp_msg.get('params').get('arguments') or None
#         device.state = device_state.MCPSTATE
#         tool_message = None or await func(device, args) 
#         
    if mcp_msg.get('error'):
        print("!-", mcp_msg.get('error').get('message'))
        return False
    
    await device.mcp.on_complete_send(device, tool_message['success'], tool_message['message'], mcp_msg)
    # await device.mcp.send_notification(device)
    return True 
