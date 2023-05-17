from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import StopConsumer

import json
import os.path
from datetime import datetime
from telethon import TelegramClient, errors, types

class TelegramScraper(AsyncWebsocketConsumer):
    room_name = "telegram_consumer"
    room_group_name = "telegram_consumer_group"
    apiKey = ""

    session_file_name = ""
    client = None
    phone = ""
    verified = False    # flag to check if the user sent the correct apiKey
    session_created = False # whether session was created successfully or not or if it exists

    api_hash = "e1cf9289e44fa9ec964d4e110dff729e"
    api_id = "26122974"

    async def connect(self):
        await(self.channel_layer.group_add)(
            self.room_name, self.room_group_name
        )
        await self.accept()
        await self.send(text_data=json.dumps({
            "status": "connected"
        }))
    
    async def receive(self, text_data):
        try:
            json_data = json.loads(text_data)
            event = json_data["event"]
            data = json_data["data"]

            match event:
                case "login":
                    self.apiKey = data["apiKey"]
                    await self.handle_token_login(event, self.apiKey)
                
                case "telegram login":
                    await self.handle_telegram_login(event, data)

                case "users":
                    await self.handle_users_scraping(event, data)

                case _:
                    await self.send_failed_notif(event, "unknown event")
        
        except KeyError as e:
            await self.send_failed_notif("JSON data error", f"Missing key: {e}")
            await self.close()
        except json.JSONDecodeError as e:
            await self.send_failed_notif("JSON parsing error", f"Error: {e}")
            await self.close()
    
    async def disconnect(self, close_code):
        print(f"DISCONNECTED : Close code {close_code}")

    
    # ========== RECIEVE FUNCTIONS ==========
    async def handle_token_login(self, event, apiKey):
        print("TOKEN LOGIN: Verifying apikey...")
        if self.verified:
            await self.send_success_notif(event, "Already verified. Send data to 'telegram login' or 'users'.")

        if self.verify_token(apiKey):
            print("TOKEN LOGIN: Verified User")
            file_offset = 5
            self.session_file_name = apiKey[:file_offset] + apiKey[-file_offset:]

            if not os.path.isfile(self.session_file_name + '.session'):
                await self.send_success_notif(event, "send phone number")
            else:
                self.client = TelegramClient(self.session_file_name, self.api_id, self.api_hash)
                await self.client.start()
                self.session_created = True
                await self.send_success_notif(event, "session already exists, call 'users'")
        else:
            print("TOKEN LOGIN: Unauthorized User")
            await self.send_failed_notif(event, "unauthorized")

    async def handle_telegram_login(self, event, data):
        print("TELEGRAM LOGIN: Creating session...")
        if not self.verified:
            await self.send_failed_notif(event, "verify your api key first")
            await self.close()
        else:
            if self.session_created:
                await self.send_success_notif(event, "session alreay exists, call 'users'")
            else:
                if "phone" in data:
                    print("TELEGRAM LOGIN: Initiating sesison...")
                    self.phone = data['phone']
                    await self.initiate_session(data["phone"])
                
                if "code" in data:
                    print("TELEGRAM LOGIN: Validating code...")
                    await self.validate_code(data['code'])

    async def handle_users_scraping(self, event, data):
        if not self.verified or not self.session_created:
            await self.send_failed_notif(event, "login required")
            await self.close()

        if "" == data["status"]:
            for group in data["group"]:
                if await self.is_channel(group):
                    print(f"USERS: Group name '{group}' is a channel")
                    await self.send_failed_notif(event, f"{group} is a channel name")
                    await self.close()
                    break

                if not await self.is_group(group):
                    print(f"USERS: Group name '{group}' does not exist")
                    await self.send_failed_notif(event, f"group {group} does not exist")
                    await self.close()
                    break

                if await self.is_group(group) and not await self.is_channel(group):
                    await self.send_group_users(group)
                    print(f"USERS: Data sent for group '{group}'")

        if "latest" == data["status"]:
            for group in data["group"]:
                if await self.is_channel(group):
                    print(f"USERS: Group name '{group}' is a channel")
                    await self.send_failed_notif(event, f"{group} is a channel name")
                    await self.close()
                    break

                if not await self.is_group(group):
                    print(f"USERS: Group name '{group}' does not exist")
                    await self.send_failed_notif(event, f"group {group} does not exist")
                    await self.close()
                    break

                if await self.is_group(group) and not await self.is_channel(group):
                    await self.send_success_notif(event, "sending users")
                    await self.send_group_users(group, True)
                    print(f"USERS: Data sent for group '{group}'")
    

    # ========== RECEIVE UTILITY FUNCTIONS ==========
    def verify_token(self, apiKey):
        # Logic to connect to database and verify the apiKey
        if "alkflknsdnfsjkn.ksalfjksdhksdsfdsdfsdf.lkszmlsknmskjdns" in apiKey:
            self.verified = True
            return True

        self.verified = False
        return False

    async def initiate_session(self, phone):
        self.client = TelegramClient(self.session_file_name, self.api_id, self.api_hash)
        try:
            connect_result = await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(phone)
                print("TELEGRAM LOGIN: Code sent...")
                await self.send_success_notif("telegram login", "send code")
            else:
                print("TELEGRAM LOGIN: User session available")
                await self.send_success_notif("telegram login", "logged in")
        except errors.PhoneCodeInvalidError:
            print("TELEGRAM LOGIN: Invalid phone number provided.")
            await self.send_failed_notif("telegram login", "invalid phone number")
            await self.close()

    async def validate_code(self, code):
        try:
            await self.client.sign_in(self.phone, code)
            self.session_created = True
            print("TELEGRAM LOGIN: Code verified. Session Created.")
            await self.send_success_notif("telegram login", "logged in successfully")
        except errors.SessionPasswordNeededError:
            self.session_created = False
            print("TELEGRAM LOGIN: Invalid code provided...")
            await self.send_failed_notif("telegram login", "invalid code provided")
            await self.close()

    async def send_group_users(self, group_name, latest=False):
        group_entity = await self.client.get_entity(group_name)
        async for user in self.client.iter_participants(group_entity):
            if not isinstance(user, types.User) or user is None:
                continue
            user_dict = await self.get_user_properties(user)
            await self.send_success_notif("users", {
                "group": group_name,
                "user": user_dict
            })


    # ========== GROUP USERS UTILITY FUNCTIONS ==========
    def convert_bytes(self, obj, encoding="utf-8"):
        if isinstance(obj, bytes):
            return obj.decode('iso-8859-1')
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, list):
            return [convert_bytes(item) for item in obj]
        elif isinstance(obj, dict):
            return {convert_bytes(key): convert_bytes(value) for key, value in obj.items()}
        else:
            return obj

    def get_user_status_dict(self, status):
        if isinstance(status, types.UserStatusEmpty):
            return {"_": "UserStatusEmpty"}
        elif isinstance(status, types.UserStatusOnline):
            return {
                "_": "UserStatusOnline",
                "expires": status.expires.isoformat(),
            }
        elif isinstance(status, types.UserStatusOffline):
            return {
                "_": "UserStatusOffline",
                "was_online": status.was_online.isoformat()
            }
        elif isinstance(status, types.UserStatusOffline):
            return {"_": "UserStatusOffline"}
        elif isinstance(status, types.UserStatusLastWeek):
            return {"_": "UserStatusLastWeek"}
        elif isinstance(status, types.UserStatusLastMonth):
            return {"_": "UserStatusLastMonth"}
        else:
            return None

    async def get_user_properties(self, user):
        return {
            "id": user.id if user.id else None,
            "first_name": user.first_name if user.first_name else None,
            "last_name": user.last_name if user.last_name else None,
            "username": user.username if user.username else None,
            "phone": user.phone if user.phone else None,
            'status': self.get_user_status_dict(user.status) if user.status else None,

            "is_self": user.is_self,
            "bot": user.bot,
            "contact": user.contact,
            "mutual_contact": user.mutual_contact,
            "deleted": user.deleted,
            "bot_chat_history": user.bot_chat_history,
            "bot_nochats": user.bot_nochats,
            "verified": user.verified,
            "restricted": user.restricted,
            "min": user.min,
            "bot_inline_geo": user.bot_inline_geo,
            "support": user.support,
            "scam": user.scam,
            "apply_min_photo": user.apply_min_photo,
            "fake": user.fake,
            "bot_attach_menu": user.bot_attach_menu,
            "premium": user.premium,
            "attach_menu_enabled": user.attach_menu_enabled,

            "photo": {
                "photo_id": user.photo.photo_id,
                "dc_id": user.photo.dc_id,
                "has_video": user.photo.has_video,
                "personal": user.photo.personal,
                "stripped_thumb": self.convert_bytes(user.photo.stripped_thumb),
            } if user.photo else None,
            "bot_info_version": user.bot_info_version if user.bot_info_version else None,
            "lang_code": user.lang_code if user.lang_code else None,
            "usernames": json.dumps(user.usernames) if user.usernames else json.dumps([]),
            "restriction_reason": [reason.to_dict() for reason in user.restriction_reason] if user.restriction_reason else None,
            "access_hash": user.access_hash,
        }


    # ========== UTILITY FUNCTIONS ==========
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

    async def is_channel(self, group):
        try:
            group_entity = await self.client.get_entity(group)
            if hasattr(group_entity, 'channel') and group_entity.channel:
                return True
            else:
                return False
        except (ValueError, AttributeError):
            return False

    async def is_group(self, group):
        try:
            group_entity = await self.client.get_entity(group)
            return True
        except (ValueError, AttributeError):
            return False