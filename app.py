from setup import SetUpWiznetChip
import asyncio, gc
import ota
from ws import AsyncWebsocketClient
from device import Device

try:
    from config import secret, config
except ImportError:
    print('Paste server secret to config.py before proceeding...')

def setup():
    # Refresh memory
    gc.collect()

    # Hardware Setup
    device = Device()
                 
    # MQTT + WebSocket Setup
    schema = 'https' if config.get('is_secure') else 'http'
    OTA_LINK = f"{schema}://ai.w5500.com/xiaozhi/ota/"
    OTA_PAYLOAD = ota.get_data_from_ota_using_request(OTA_LINK, device.mac_address)
    if not OTA_PAYLOAD:
        print('Error in OTA')
        return
    device.ws.ws_url = OTA_PAYLOAD.get('websocket').get('url')
    device.ws.token = OTA_PAYLOAD.get('websocket').get('token')
    return device

async def main():
    device = setup()
    gc.collect()
    
    while True:
        await device.run()
        gc.collect()
        
asyncio.run(main())

    