import json, asyncio, select, gc
import display, keyboard, button
import device_state
from machine import Pin

from ws import AsyncWebsocketClient
from config import config, secret
from setup import SetUpWiznetChip
import time

if config.get('MQTT_ENABLED', False):
    from mqttHandlers import MQTTHandler

if config.get('UDP_ENABLED', False):
    from udp import UDPServer
    
if config.get('mcp_enabled', False):
    from mcp import MCPServer

if config.get('I2S_ENABLED', False):
    from i2s_microphone_speaker_switch import I2SDevice

# Constants

ASYNC_TIMEOUT = config.get('async_timeout')


class Device:
    def __init__(self):

        self.nic = SetUpWiznetChip()
        self.mac_address = ':'.join(['%02x' % b for b in self.nic.config('mac')])
        self.state = device_state.IDLE
        
        self.i2s_device = None
        if config.get('I2S_ENABLED', False):
            self.i2s_device = I2SDevice(self)
        self.use_microphone = False
        
        # Websockets
        self.ws = AsyncWebsocketClient(self, config.get('ws_delay_ms'))
        self.handshake = False
        self.websocket_connected = False
        self.session_id = None
        self.ping_pong_complete = True
        
        # File Operation on SD Card
        self.file_opened = False
        self.audio_file = None
        
        # Xiaozhi send text task
        self.ws_task = None
        self.poll = None
        self.polled = False
        
        # MQTT
        self.mqtt_client = None
        if config.get('MQTT_ENABLED',False):
            self.mqtt_client = self.init_mqtt_client()
        
        # MCP
        if config.get('mcp_enabled', False):
            self.mcp = MCPServer()
    
        # Add other setup here
        self.button= button.StartButton(config.get('START_BUTTON','PD11'))
        self.display = display.Display()

        
        # UDP
        self.udp_server = None
        if config.get('UDP_ENABLED', False):
            self.udp_server = UDPServer(self)
        
        
    async def init_handshake(self, uri , token):
        if self.handshake: return
        # Server-required headers
        query_params = {}
        
        # Case for non-authorized server
        if token != '' or token is not None:
            query_params['Authorization'] = 'Bearer ' + token
        query_params['Device-Id'] = self.mac_address
        query_params['Client-Id'] = secret['Client-Id'] or None
        try:
            self.state = device_state.CONNECTING
            if await self.ws.handshake(uri = uri, headers = query_params):
                self.state = device_state.IDLE 
                self.handshake = True
                print('==== Handshake Completed ====')
        except OSError as e:
            print('Exception:  ', e)
            self.state = device_state.IDLE 
        gc.collect()            
    
    async def init_connection(self):
        init_msg = {
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "features": {
                "mcp": config.get('mcp_enabled', False)
            },
            "audio_params": {
                "format": "pcm",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60
            }
        }
        if self.websocket_connected: return
        if not self.handshake:
            await asyncio.sleep(5)
            return
        try:
            if await self.ws.open():
                gc.collect()
                await self.ws.send(json.dumps(init_msg))
        except OSError:
            print('Error in sending init msg')
            raise OSError()
        except asyncio.TimeoutError:
            print('Timeout in receiving hello msg')
            raise OSError()      
        except Exception as e:
            print('Exception: ', e)
            await self.ws.close()        
        gc.collect()

    async def _reroute_data_to_handler(self, data):
        
        if isinstance(data, bytes):
             self.ws.do_audio = True if self.i2s_device is not None else False
        elif isinstance(data, str):
            from msgTypeHandler import Handlers, HANDLER_TYPES
            msg = json.loads(data)
            if msg.get('type') not in HANDLER_TYPES or msg.get('type') == None:
                print('!- Message type not found in reply.')
                raise ValueError('Message type not found in reply.')             
            handler = Handlers.get(msg.get('type'))
            if not handler:
                print('Message type not implemented')
                return False
            is_success = await handler(self, msg)
            msg = None
            data = None
            return is_success
        return True
    
    async def talk_to_xiaozhi(self):
        try:              
            if await self.ws.open():
                gc.collect()
                await self.ws.send(json.dumps({'session_id':self.session_id, 'type':'listen','state':'start', 'mode':'manual'}))
        except OSError:
            raise Exception('!- Error in sending payload')
        await asyncio.sleep_ms(500)
        self.state = device_state.LISTENING
        while True:
            await asyncio.sleep_ms(100)
            if self.state != device_state.LISTENING: continue
            if self.use_microphone: continue
            payload = await keyboard.create_text_payload(self)
            if not isinstance(payload, str):
                need_return = await keyboard.handle_stop_reason(self, payload)
                if need_return is True:
                    return
                else:
                    continue
            if await self.ws.open():
                try:
                    gc.collect()
                    await self.ws.send(payload)
                    self.state = device_state.SPEAKING
                    await asyncio.sleep_ms(500)
                except Exception as e:
                    raise Exception('!- Error during sending payload. Restarting websocket...')
        
    
    async def on_first_connect(self):
        await self.init_handshake(self.ws.ws_url, self.ws.token)
        await asyncio.sleep_ms(500)
        await self.init_connection()
        await asyncio.sleep_ms(500)
        if config.get('mcp_enabled',False):
            print('\n=== Accessing MCP ===')
            await self.mcp.init_connection(self)
            await asyncio.sleep_ms(500)
            print('==== MCP Successfully Initialized ====')

    async def do_ping_pong(self):
        # Do Ping every 5 seconds
        try:
            gc.collect()
            await self.ws.send(json.dumps({'type':'ping'}))
            self.ping_pong_complete = False
        except:
            raise Exception('Error in sending ping...')
        
    async def send_abort_message(self):
        if await self.ws.open():
            try:
                gc.collect()
                await asyncio.wait_for(self.ws.send(json.dumps({'session_id':self.session_id, 'type':'abort'})), ASYNC_TIMEOUT)
            except OSError as e:
                raise Exception("!- Error in sending abort message.")
            except asyncio.TimeoutError:
                raise Exception('!- Timeout during abort message.')
            
            gc.collect()
            self.state = device_state.ABORT
            if hasattr(self, 'speaker'):
                music.stop(self.speaker)
                
               
    async def _button_loop(self):
        print('\n==== Waiting Button Press ====')
        print('==== Press button at ', config.get('START_BUTTON', 'PB6') ,' to record audio ====')
        while True:
            await asyncio.sleep_ms(10)
            init_button_state = self.button.get_value()
            await asyncio.sleep_ms(100)
            final_button_state = self.button.get_value()
            if init_button_state != final_button_state and final_button_state == button.BUTTON_PRESSED:
                await self.button.handle_button_press(self)         
    
    async def websocket_recv(self):
        # Note: websocket will still have sound msg when aborting,
        # allow websocket_recv to keep reciving bytes but don't play it.
        gc_count= 0
        while True:
            if gc_count > 5:
                gc.collect()
                gc_count = 0
            gc_count += 1
            
            # This is used so that if currently is not playing audio
            # Let other task run.
            if not self.ws.do_audio:
                await asyncio.sleep_ms(0)
            
            # Due to nonblocking is not available on this firmware,
            # we use this to disallow ws recv to 'stuck' the program.
            if self.state == device_state.LISTENING and self.ping_pong_complete == True: 
                continue
        
            if not self.handshake:
                continue
            
            if not self.polled:
                self.poll = select.poll()
                self.poll.register(self.ws.sock, select.POLLIN)
                self.polled = True
            
            try:
                if not self.poll.poll(0):
                    await asyncio.sleep_ms(0)
                    continue
                data = await asyncio.wait_for(self.ws.recv(), ASYNC_TIMEOUT)
                await self._reroute_data_to_handler(data)
            except MemoryError as e:
                raise MemoryError('!- Memorry Error during recv.')
            except asyncio.TimeoutError:
                raise Exception('!- Timeout during recv.')
            except ValueError as e:
                print(e)
                raise Exception('!- Value error from server.')
            except Exception as e:
                raise Exception('!- Unstated error:  ', e)
                
    async def run(self):
        # Events needed
        # Interrupt/Await Button for listen
        # Voice Input
        gc.collect()
        group_tasks = [
            asyncio.create_task(self._button_loop()),
            asyncio.create_task(self.websocket_recv()),
        ]
        # MQTT
        if self.mqtt_client is not None:
            group_tasks.append( asyncio.create_task(self._mqtt_loop()))
        # I2S
        if self.i2s_device:
            group_tasks.append(asyncio.create_task(self.i2s_device.start()))
            group_tasks.append(asyncio.create_task(self.i2s_device.a_play()))
        # UDP
        if self.udp_server:
            group_tasks.append(asyncio.create_task(self.udp_server.run()))
        try:
            await asyncio.gather(*group_tasks)
        except Exception as e:
            print('Error occured: ', e)
            for t in group_tasks:
                t.cancel()
        if self.file_opened: self.audio_file.close()
        self.state = device_state.IDLE
        await self.reset_websocket()
        if self.udp_server:
            await self.udp_server.close()
        gc.collect()
        print('Run Loop terminated.')

    async def _on_exit_connection_loop(self):
        self.websocket_connected = False
        self.session_id = None
        await self.ws.close()
        
    async def reset_websocket(self):
        print('Resetting Websocket...')
        await self.ws.close()
        self.websocket_connected = False
        self.handshake = False
        if self.poll != None:
            self.poll.unregister(self.ws.sock)
            self.poll = None
            self.polled = False
        self.use_microphone = False
        await self.cancel_keyboard_task()
        print('\n==== Waiting Button Press ====') 
        
        
    async def _mqtt_loop(self):
        while True:
            self.mqtt_client.check_msg()
            await asyncio.sleep_ms(2000)
    
    async def cancel_keyboard_task(self):
        if not self.ws_task: return
        self.ws_task.cancel()
        try:
            await self.ws_task
        except asyncio.CancelledError:
            print('\n==== WS Task cancelled ====')
        self.ws_task = None
    
    def init_mqtt_client(self):
        from umqttsimple import MQTTClient
        client = MQTTClient(self.mac_address, config.get('MQTT_IP'), user = config.get('MQTT_USERNAME'), password = config.get('MQTT_PASSWORD')) 
        client.connect()
        handler = MQTTHandler(self)
        client.set_callback(handler.mqtt_callbacks)
        handler.subscribe(client)
        return client
    
    