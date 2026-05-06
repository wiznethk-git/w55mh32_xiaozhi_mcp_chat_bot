import socket, gc, asyncio, select
from config import config

HOST = config.get('UDP_HOST')
PORT = config.get('UDP_PORT')

TIMEOUT = 1000

class UDPServer:
    def __init__(self, device):
        
        # Belongs to
        self.device = device
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', PORT))
        self.start = False  
        self.poller = select.poll()
        self.poller.register(self.sock, select.POLLIN)
      
    async def run(self):
        gc_count = 0
        while True:
            await asyncio.sleep_ms(0)
         
            if gc_count >= 5:
                gc_count = 0
                gc.collect()
            gc_count += 1
    
            if not self.poller.poll(10):
                continue
            data , _  = self.sock.recvfrom(960)
            continue
            if data == None:
                await asyncio.sleep_ms(0)
                continue
            await self.device.i2s_device.write_to_ring_buf(data)
    
    async def close(self):
        self.sock.close()
        self.poller.unregister(self.sock)
            