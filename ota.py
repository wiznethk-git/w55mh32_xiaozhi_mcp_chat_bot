import socket
import urequest
import json
import gc
try:
    from config import secret, config
except ImportError:
    print('Paste server secret to config.py before proceeding...')

# Constants
BOARD_TYPE = config.get('board_type')

def get_data_from_ota_using_request(url, mac_addr):
    if not (url.startswith('http://')  or url.startswith('https://')):
        print('Not HTTP or HTTPS request. Terminating program...')
        return False
    headers = {
        'Content-Type':'application/json',
        'Device-Id':mac_addr,
        'Client-Id':secret['Client-Id'],
        'User-Agent':BOARD_TYPE       
    }
    payload = {'message':'hi'}
    gc.collect()
    sock = urequest.urlopen(url, data = json.dumps(payload),  method = 'POST', headers = headers)
    read_data = b''
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                break
            read_data = read_data + data
        except OSError:
            break
    try:
        payload = json.loads(read_data)
    except ValueError:
        print('Unable to serialize payload.')
        sock.close()
        return False
    if payload.get('code') == '500' or payload.get('code') == '400':
        print('Error in payload.')
        sock.close()
        return False
    sock.close()
    return payload

# TO-DO: OTA upagrade firmware
