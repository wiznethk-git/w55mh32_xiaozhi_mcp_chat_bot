# import time
import device_state
import button, json, asyncio, gc
from machine import Pin, I2S


_MODE_SPEAKER = const(0)
_MODE_MICROPHONE = const(1)
PIN_SCK, PIN_WS, PIN_SD = Pin('PB3'), Pin('PA15'), Pin('PB5')

# Recv Audio size is 640 bytes.
WS_AUDIO_BYTES = const(640)
RATIO_BYTES_WS_TO_RING = const(2)
_PKT_MAX = const(WS_AUDIO_BYTES * RATIO_BYTES_WS_TO_RING)
RING_N = const(7) # Follow ratio of 8/52 for smooth playback
_START_PKTS = const(5) # Follow ratio of 8/52 for smooth playback

class I2SDevice:
    def __init__(self, device):
        from config import config
        self.button = button.Button(config.get('RECORD_BUTTON', 'PG6'))
        self.mode  = _MODE_SPEAKER
        self.device = device

        # Actual I2S Device
        self.target = None
        
        # Store OPUS sample rate given by server hello msg
        self.format = 'opus'
        self.channels = 1
        self.sample_rate = 16000
        self.frame_duration = 60
        
        self.w_idx = 0
        self.r_idx = 0
        self.ring_buf = [bytearray(_PKT_MAX) for _ in range(RING_N)]
        self.sizes = [0] * RING_N
        self.packets = 0 # Packets are 
        
        # Asyncio Play
        self.swriter = None
        self.sreader = None
        self.started = False
        
        # Complete audio flag from server
        self.complete = False
        
                
    async def start(self):
        while True:
            await asyncio.sleep_ms(10)
            if self.device.state != device_state.LISTENING: continue
            if self.button.get_value() == button.BUTTON_PRESSED:
                self.device.use_microphone = True
                self._deinit_speaker()
                await asyncio.sleep_ms(500)
                self.set_mode(_MODE_MICROPHONE)
               
                await self.a_record_audio()
#                 await self.send_audio()
                
                # Send STOP message after finish recording + sending
                try:
                   if await self.device.ws.open():
                        stop_msg = {'session_id':self.device.session_id, 'type':'listen', 'state':'stop'}
                        gc.collect()
                        await self.device.ws.send(json.dumps(stop_msg))
                        
                except OSError as e:
                    raise OSError('!- Error in sending STOP message after recording audio')
                gc.collect()
                self._deinit_microphone()
                self.set_mode(_MODE_SPEAKER)
                self.device.use_microphone = False
                self.device.state = device_state.SPEAKING
    
    # =========== Microphone ===============
    def _init_microphone(self):
        print('==== Microphone Mode ====')
        self.target = I2S(
                3,
                sck=PIN_SCK,
                ws=PIN_WS,
                sd=PIN_SD,
                mode=I2S.RX,
                bits=16,
                format= I2S.MONO if self.channels == 1 else I2S.STEREO,
                rate= 16000,
                ibuf= 6000
            )
        self.sreader = asyncio.StreamReader(self.target)
    
    def _deinit_microphone(self):
        self.sreader.close()
        self.sreader = None
        self.target.deinit()
    
    async def send_audio(self):
        buf = bytearray(1024)
        mv =  memoryview(buf)
        with open('/sd/microphone.pcm', 'rb') as f:
            while True:
                num_bytes_read_from_mic = f.readinto(mv)
                if num_bytes_read_from_mic == 0: break
                gc.collect()
                await self.device.ws.send(bytes(mv[:num_bytes_read_from_mic]))
            
    async def record_audio(self):
        assert self.mode == _MODE_MICROPHONE
        buf = bytearray(1024)
        mv = memoryview(buf)
        path = '/sd/microphone.pcm'
        f = open(path, 'wb')
        print('==== Start Recording ====')
        try:
            while True:
                if self.button.get_value() == button.BUTTON_RELEASE:
                    print('==== Mic button released ====')
                    f.close()
                    break
                n = self.target.readinto(mv)
                gc.collect()
                f.write(mv[:n])
                await asyncio.sleep_ms(0)
        except OSError as e:
            raise OSError('!- Error in sending audio msgs')
    
    async def a_record_audio(self):
        assert self.mode == _MODE_MICROPHONE
        self.device.ws.do_record = True
        buf = bytearray(2048)
        mv = memoryview(buf)
        print('==== Start Recording ====')
        try:
            while True:
                if self.button.get_value() == button.BUTTON_RELEASE:
                    print('==== Mic button released ====')
                    self.device.ws.do_record = False
                    break
                n = await self.sreader.readinto(mv)
                
                if await self.device.ws.open():
                    gc.collect()
                    await self.device.ws.send(mv[:n])
        except OSError as e:
            self.device.ws.do_record = False
            raise OSError('!- Error in sending audio msgs')     
    
    
    async def decode_audio(self):
        return
    
    # =========== Speaker ===============
    
    def _init_speaker(self):
        print('==== Speaker Mode ====')
        gc.collect()
        self.target = I2S(
                3,
                sck=PIN_SCK,
                ws=PIN_WS,
                sd=PIN_SD,
                mode=I2S.TX,
                bits=16,
                format=I2S.MONO if self.channels == 1 else I2S.STEREO,
                rate = self.sample_rate,
                ibuf = 4096
            )
        gc.collect()
        self.swriter = asyncio.StreamWriter(self.target)
        self.reset_audio_buffer()
    
    def _deinit_speaker(self):
        self.swriter.close()
        self.swriter = None
        self.reset_audio_buffer()
        self.target.deinit()
        
 
    async def play(self):
        assert self.mode == _MODE_SPEAKER
        buf = bytearray(1024)
        mv = memoryview(buf)
        with open('/sd/xiaozhi.pcm', 'rb') as f:
            while True:
                gc.collect()
                n = f.readinto(mv)
                if n == 0: break
                self.target.write(mv[:n])
                await asyncio.sleep_ms(0)
                
    def increment_write_index(self):
        # Only increment write index if whole bytearray is full
        if self.packets % RATIO_BYTES_WS_TO_RING  == 0:
            self.w_idx = (self.w_idx + 1) % RING_N
        
    
    async def write_to_ring_buf(self, data):
        while True:
            
            # Wait for free slots
            if self.packets >= RING_N:
                await asyncio.sleep_ms(0)
                continue
            else:
                break
        
        # Save Data and len(Data) to buffers
        
        
        n = len(data)
        self.sizes[self.w_idx] = n
        gc.collect()
        self.ring_buf[self.w_idx][:n] = data
        self.w_idx = (self.w_idx + 1) % RING_N
        self.packets += 1
            
    async def a_play(self):
        while True:
            if self.target is None or self.mode != _MODE_SPEAKER:
                await asyncio.sleep_ms(0)
                continue
            
       
            # Each two packets is responsible for one bytearray.
            # Here I minus two from start packets so that
            #  the Drain does not happen only to one single Frame lost but 3.
            if  self.packets / RATIO_BYTES_WS_TO_RING  < (_START_PKTS - 2):
                await asyncio.sleep_ms(0)
                continue
            
            # No more packets to read
            if self.packets == 0:
                self.started = False
                await asyncio.sleep_ms(0)
                continue
            
            # Don't play audio if not a full package
            if self.packets % RATIO_BYTES_WS_TO_RING != 0:
                await asyncio.sleep_ms(0)
                continue

            n = self.sizes[self.r_idx]
            mv = memoryview(self.ring_buf[self.r_idx])[:n]
            # print('Writing ',n , 'bytes to audio from index ', self.r_idx)
            
            # Writing
            self.swriter.write(mv)
            await self.swriter.drain()
            
            self.sizes[self.r_idx] = 0
            self.r_idx = (self.r_idx + 1) % RING_N
            
            # Use up two packets.
            self.packets -= RATIO_BYTES_WS_TO_RING

    
    def reset_audio_buffer(self):
        self.w_idx = 0
        self.r_idx = 0
        self.packets = 0
        for i in range(RING_N):
            self.sizes[i] = 0
        self.started = False
        
            
    async def is_packets_empty(self):
        while self.packets != 0:
            await asyncio.sleep_ms(0)
        self.device.sentence_start = True
        return
    
    async def wait_until_ring_buf_can_write(self):
        # If packets/2 (meaning number of bytearray is filled with packets) filled up the whole ring, wait until can be written.
        while self.packets / RATIO_BYTES_WS_TO_RING >= RING_N:
            await asyncio.sleep_ms(0)
        
       
    def set_mode(self , mode):
        self.mode = mode
        if self.mode == _MODE_MICROPHONE:
            self._init_microphone()
        else:
            self._init_speaker()
    
        
        
    
        
    

            