import asyncio
import device_state
from machine import Pin
from micropython import const

BUTTON_PRESSED = const(0)
BUTTON_RELEASE = const(1)

class Button:
    def __init__(self, pin):
        self.pin = Pin(pin, Pin.IN, Pin.PULL_UP) 
        self.state = self.pin.value()
        self.initial_value = self.pin.value()
    
    def get_value(self):
        self.state = self.pin.value()
        return self.state

class StartButton(Button):
    async def handle_button_press(self, device):
        if not device.ws_task and device.state == device_state.IDLE:
            print('Start Xiaozhi Task.')
            await device.on_first_connect()
            device.ws_task = asyncio.create_task(device.talk_to_xiaozhi())
            return
        print('Cancel Xiaozhi Task.')
        if not device.ws_task: return
        await device.cancel_keyboard_task()
        await device.send_abort_message()
        

class SpeakerButton(Button):
    async def handle_button_press(self):
        pass
 