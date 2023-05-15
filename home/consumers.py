from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import async_to_sync
import json
from telethon import TelegramClient, errors

class TelegramScraper(AsyncWebsocketConsumer):
    room_name = "telegram_consumer"
    room_group_name = "telegram_consumer_group"
    session_file_name = ""
    client = None
    phone = ""
    verified = False    # flag to check if the user sent the correct apiKey
    session_created = False # whether session was created successfully or not or if it exists

    async def connect(self):
        await(self.channel_layer.group_add)(
            self.room_name, self.room_group_name
        )
        await self.accept()
        await self.send(text_data=json.dumps({
            "status": "connected"
        }))
    
    async def receive(self, text_data):
        json_data = json.loads(text_data)
        
        event = json_data["event"]
        data = json_data["data"]

        match event:
            case "login":
                print("TOKEN LOGIN: Verifying apikey...")
                if self.verify_token(data["apiKey"]):
                    print("TOKEN LOGIN: Verified User")
                    apiKey = data["apiKey"]
                    self.session_file_name = apiKey[:5] + apiKey[-5:]
                    await self.send_success_notif(event, "send phone number, api hash and api id")
                else:
                    print("TOKEN LOGIN: Unauthorized User")
                    await self.send_failed_notif(event, "unauthorized")
            
            case "telegram login":
                print("TELEGRAM LOGIN: Creating session...")
                if not self.verified:
                    await self.send_failed_notif(event, "verify your api key first")
                else:
                    if all(key in data for key in ("phone", "api_hash", "api_id")):
                        print("TELEGRAM LOGIN: Initiating sesison...")
                        self.phone = data['phone']
                        await self.initiate_session(data["phone"], data["api_id"], data["api_hash"])
                    
                    if "code" in data:
                        print("TELEGRAM LOGIN: Validating code...")
                        await self.validate_code(data['code'])
    
    async def disconnect(self, close_code):
        print("Disconnected")
    

    def verify_token(self, apiKey):
        # Logic to connect to database and verify the apiKey
        if "alkflknsdnfsjkn.ksalfjksdhksdsfdsdfsdf.lkszmlsknmskjdns" in apiKey:
            self.verified = True
            return True

        self.verified = False
        return False

    async def send_success_notif(self, event, message):
        await self.send(text_data=json.dumps({
            "event": event,
            "data": {
                "status": "success",
                "message": message
            }
        }))

    async def send_failed_notif(self, event, message):
        await self.send(text_data=json.dumps({
            "event": event,
            "data": {
                "status": "failed",
                "message": message
            }
        }))

    async def initiate_session(self, phone, api_id, api_hash):
        # Create session
        self.client = TelegramClient(self.session_file_name, api_id, api_hash)
        try:
            connect_result = await self.client.connect()
            print(connect_result)
            if not self.client.is_user_authorized():
                self.session_created = True
                await self.client.send_code_request(phone)
                await self.send_success_notif("telegram login", "send code")
        except errors.PhoneCodeInvalidError:
            self.session_created = False
            print("TELEGRAM LOGIN: Invalid phone number provided.")
            await self.send_failed_notif("telegram login", "invalid phone number")

    async def validate_code(self, code):
        try:
            await self.client.sign_in(self.phone, code)
            print("TELEGRAM LOGIN: Code verified. Session Created.")
            await self.send_success_notif("telegram login", "logged in successfully")
        except errors.SessionPasswordNeededError:
            print("TELEGRAM LOGIN: Invalid code provided...")
            self.send_failed_notif("telegram login", "invalid code provided")