# To-Do: Add Display driver for running the screen.
# This class only sets up the driver and output contents to the screen
class Display:
    def __init__(self, PIN = None):
        self.emoji = None
        self.text = None
        self.pin = PIN
    
    async def set_text(self, text):
        return True
    
    async def set_emoji(self, emotion):
        # To-Do: Preset Happy, Sad, Thinking and Sleepy emoji.
        return True
    
    async def disconnect(self):
        return
    
    async def init_screen(self):
        return True
    
    async def clear_display(self):
        return
    
    async def reset_display(self):
        return
    