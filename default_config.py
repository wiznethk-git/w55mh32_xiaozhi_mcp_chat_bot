import uuid
client_id = uuid.uuid4()
secret = {
    'Client-Id':client_id
}

config = {
        # General
        'is_secure': False,
        'async_timeout': 10,
        
        # I2S
        'I2S_ENABLED': True,
        
        # Websocket Specific
        'ws_delay_ms': 0,
        
        # MCP
        'mcp_enabled': True,
        
        # OTA Specific
        'board_type':'YOUR_BOARD_TYPE',
        
        # MQTT
        'MQTT_USERNAME': 'MQTT_USERNAME',
        'MQTT_PASSWORD': 'MQTT_PASSWORD',
        'MQTT_IP':'MQTT_HOST',
        'MQTT_ENABLED':True,
        
        'START_BUTTON':'PB9',
        'RECORD_BUTTON':'PB8',
}