import json, asyncio, time
import sys, select
import device_state
from micropython import const

_KEYBOARD_TIMEOUT  = const(0)  
_KEYBOARD_OVERRIDE = const(1)  # Result Code for when microphone is being used instead.

_TASK_RETURN = const(True)
_TASK_CONTINUE = const(False)

_KEYBOARD_CLOSE_TIME = const(30000)
_PING_PONG_TIME = const(5000)
    
async def on_wait_user_input(device):
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    start = time.ticks_ms()
    last_ping = start
    print('\nType in your message: ')
    while True:
        now = time.ticks_ms()
        
        # Close Keyboard Input if 
        if device.use_microphone == True:
            print('\n==== Microphone Mode detected and being overrided ====')
            poll.unregister(sys.stdin)
            return _KEYBOARD_OVERRIDE
        
        # Close input if 30 seconds passed
        if time.ticks_diff(now, start) >_KEYBOARD_CLOSE_TIME:
            print('\n==== Keyboard time reached ====')
            poll.unregister(sys.stdin)
            return _KEYBOARD_TIMEOUT
       
       # do Ping Pong every 5 seconds
        if time.ticks_diff(now, last_ping) >= _PING_PONG_TIME:
            await device.do_ping_pong()
            last_ping = now
       
        if poll.poll(0):
            line = sys.stdin.readline().strip('\n')
            # MicroPython/Thonny-error-handling -> 
            # It will create empty string whenever users typed in REPL
            # At the same time, force user to not be able to type empty stuff.
            if line == "":
                # Empty string is not allowed, produces error to LLMs
                continue
            poll.unregister(sys.stdin)
            return line
    
        if device.state == device_state.ABORT:
            print('Stop asking for input.')
            device.state = device_state.IDLE
            break
        await asyncio.sleep_ms(10)

async def clear_stdin_buffer():
    # print('Clearing previous buffer...')
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    while poll.poll(0):
        line = sys.stdin.readline()
        continue
    poll.unregister(sys.stdin)

async def create_text_payload(device):
    await clear_stdin_buffer()
    text = await on_wait_user_input(device)
    if text in (_KEYBOARD_TIMEOUT, _KEYBOARD_OVERRIDE):
        return text
    msg = {
        'session_id': device.session_id,
        'type': 'listen',
        'state': 'detect',
        'text': str(text)
        }
    payload = json.dumps(msg)
    return payload

async def handle_stop_reason(device, code):
    if code == _KEYBOARD_TIMEOUT:
        await device.send_abort_message()
        return _TASK_RETURN
    elif code == _KEYBOARD_OVERRIDE:
        return _TASK_CONTINUE
    
            
    