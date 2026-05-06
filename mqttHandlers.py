import json
from config import config
from machine import Pin
import gc
TOPIC_HANDLERS = {}
class MQTTHandler:
    
    def __init__(self, device):
        self.device = device
    
    def topic(topic):
        def handle(func):
            TOPIC_HANDLERS[topic] = func
            return func
        return handle

#     @topic(f'{config.get("MQTT_USERNAME")}/Xiaozhi_LED')
    @topic('Arnold/Xiaozhi_LED')
    def handle_light(self, msg):
        data = json.loads(msg)
        pin, value = data.get('pin'), data.get('value')
        # Create LED if no led or same Pin, the pin string is in Pin(Pin.cpu.PIN, mode = MODE)
        if not hasattr(self.device, 'led') or ( pin[1:] != str(self.device.led)[4:-1].split(',')[0].split('.')[-1]):
            self.device.led = Pin(pin, Pin.OUT)  
        self.device.led.value(int(value))
        gc.collect()
        return 

    def mqtt_callbacks(self, topic, message):
        fn = TOPIC_HANDLERS.get(topic.decode('utf-8'))
        if fn == None:
            print(f'Function for topic {topic} is not implemented.')
            return None
        return fn(self, message)
    
    def subscribe(self, client):
        for topic, fn in TOPIC_HANDLERS.items():
            client.subscribe(topic)
