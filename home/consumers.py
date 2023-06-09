import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from telegram.models import Telegram
from user.models import User
from asgiref.sync import sync_to_async
import os
import json
from datetime import datetime
from telethon import TelegramClient, errors, types

connected_clients = []

class TelegramScraper(AsyncWebsocketConsumer):
    room_name = "telegram_consumer"
    room_group_name = "telegram_consumer_group"
    apiKey = ""

    session_file_name = ""
    client = None
    phone = ""
    verified = False    # flag to check if the user sent the correct apiKey
    session_created = False # whether session was created successfully or not or if it exists
    logout = False # whether the user requested to terminate the session or not

    # keep track of how many groups are left to scrape
    user_scraping_count = 0
    chat_scraping_count = 0

    api_hash = "e1cf9289e44fa9ec964d4e110dff729e"
    api_id = "26122974"

    async def websocket_connect(self, event):
        # Add client to the list of connected clients
        await(self.channel_layer.group_add)(
            self.room_name, self.room_group_name
        )
        await self.accept()

        connected_clients.append(self.channel_name)
        print(connected_clients)
        await self.send(text_data=json.dumps({
            'status': 'connected'
        }))
    
    async def receive(self, text_data):
        try:
            json_data = json.loads(text_data)
            event = json_data["event"]
            data = json_data["data"]
  
            if event == "login":
                self.apiKey = data["apiKey"]
                await self.handle_token_login(event, self.apiKey)
                
            elif event == "telegram login":
                await self.handle_telegram_login(event, data)

            elif event == "users":
                await self.handle_users_scraping(event, data)

            elif event == "chats":
                await self.handle_chats_scraping(event, data)

            elif event == "logout":
                await self.handle_logout(event, data)

            else:
                await self.send_failed_notif(event, "unknown event")
            
        except KeyError as e:
            await self.send_failed_notif("JSON data error", f"Missing key: {e}")
            await self.close()
        except json.JSONDecodeError as e:
            await self.send_failed_notif("JSON parsing error", f"Error: {e}")
            await self.close()
        except Exception as e:
            print("RECEIVE: Unknown exception: ", e)
            await self.send_failed_notif("Error", "Unknown Error")
            await self.close()

    async def websocket_disconnect(self, event):
        self.logout = True
        print("DISCONNECTED : CLIENT REMOVED: ", self.channel_name)
        # Remove client from the list of connected clients
        connected_clients.remove(self.channel_name)
        # Disconnect Telegram Client and close WebSocket Connection
        if self.channel_name not in connected_clients:
            if self.session_created:
                self.client.disconnect()
            self.close()
        await super().websocket_disconnect(event)
    
    async def disconnect(self, close_code):
        print(f"DISCONNECTED : Close code {close_code}")


    # ========== RECIEVE FUNCTIONS ==========
    async def handle_token_login(self, event, apiKey):
        print("TOKEN LOGIN: Verifying apikey...")
        if self.verified:
            await self.send_success_notif(event, "Already verified. Send data to 'telegram login' or 'users'.")

        if await self.verify_token(apiKey):
            print("TOKEN LOGIN: Verified User")
            if self.session_created:
                await self.send_success_notif(event, "successfully logged in")
            else:
                await self.send_success_notif(event, "send phone number")
        else:
            print("TOKEN LOGIN: Unauthorized User")
            await self.send_failed_notif(event, "unauthorized")
            await self.close()

    async def handle_telegram_login(self, event, data):
        print("TELEGRAM LOGIN: Creating session...")
        if not self.verified:
            await self.send_failed_notif(event, "verify your api key first")
            await self.close()
        else:
            if self.session_created:
                await self.send_success_notif(event, "successfully logged")
            else:
                if "phone" in data:
                    print("TELEGRAM LOGIN: Initiating sesison...")
                    self.phone = data['phone']
                    await self.initiate_session(data["phone"])
                
                if "code" in data:
                    print("TELEGRAM LOGIN: Validating code...")
                    await self.validate_code(data['code'])

    async def handle_users_scraping(self, event, data):
        if not self.session_created:
            await self.send_failed_notif(event, "login required")
            await self.close()

        self.user_scraping_count = len(data["group"])

        for group in data["group"]:
            await self.group_name_validity(event, group)

            if self.logout:
                return

            try:
                print(f"USERS: Sending users from {group}")
                await self.send_success_notif(event, f"sending users from {group}")
                asyncio.create_task(self.send_group_users(group))
            except Exception as e:
                print(f"USERS: Exception occured for group {group}")
                print(e)
                print("USERS: Restarting scraping for all groups")
                await self.send_failed_notif(event, "Unexpected error, resending for all groups.")
                await self.handle_users_scraping(event, data)

    async def handle_chats_scraping(self, event, data):
        if not self.session_created:
            await self.send_failed_notif(event, "login required")
            await self.close()

        self.chat_scraping_count = len(data["group"])

        if data["status"] == "":
            for group in data["group"]:
                await self.group_name_validity(event, group)
                
                if self.logout:
                    return
                
                if group["status"] == "":
                    try:
                        print(f"CHATS: Sending chats from {group}")
                        await self.send_success_notif(event, f"sending chats from {group['name']}")
                        asyncio.create_task(self.send_group_chats(group["name"]))
                    except Exception as e:
                        print(f"CHATS: Exception occured for group {group}")
                        print(e)
                        print(f"CHATS: Restarting scraping for {group}")
                        await self.send_failed_notif(event, "Unexpected error, resending.")
                        await self.handle_chats_scraping(event, data)

                elif group["status"] == "latest":
                    group_entity = await self.client.get_entity(await self.get_chat_id(group["name"].strip()))
                    group_id = str(group_entity.id)
                    
                    # get from db
                    telegram_user = await sync_to_async(Telegram.objects.using)('telegramdb')
                    telegram_user = await sync_to_async(telegram_user.exclude)(group_name='')
                    telegram_user = await sync_to_async(telegram_user.filter)(api_key=self.apiKey, group_name=group_id)
                    telegram_user = await sync_to_async(telegram_user.first)()

                    message_id = telegram_user.message_id if telegram_user else 0

                    try:
                        print(f"CHATS: Sending chats from {group}")
                        await self.send_success_notif(event, f"sending chats from {group['name']}")
                        asyncio.create_task(self.send_group_chats(group["name"], min_id=message_id))
                        print(f"CHATS: Data sent for {group['name']}")
                    except Exception as e:
                        print(f"CHATS: Exception occured for group {group}")
                        print(e)
                        print("CHATS: Restarting scraping for all groups")
                        await self.handle_chats_scraping(event, data)
                
                else:
                    await self.send_failed_notif(event, "invalid status")
        else:
            await self.send_failed_notif(event, "status should be empty string")
            
    async def handle_logout(self, event, data):
        if data["status"] == "disconnect":
            if not (self.verified or self.session_created):
                await self.send_failed_notif(event, "unauthorized")
                return
                
            self.logout = True
            self.verified = False
            self.session_created = False
            self.client.disconnect()
            await self.send_success_notif("logout", "disconnected")
            await self.close()
            print("LOGOUT: Successfully logged out")
        else:
            self.logout = False
            await self.send_failed_notif("logout", "invalid logout status")
            print("LOGOUT: Invalid logout status")


    # ========== RECEIVE UTILITY FUNCTIONS ==========
    async def verify_token(self, apiKey):
        try:
            await sync_to_async(User.objects.using('userdb').get)(api_key=apiKey)
            self.verified = True
            return True
        except User.DoesNotExist:
            self.verified = False
            return False

    async def initiate_session(self, phone):
        if self.logout:
            return
        
        self.client = TelegramClient(phone[1:], self.api_id, self.api_hash)
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(phone)
                print("TELEGRAM LOGIN: Code sent...")
                await self.send_success_notif("telegram login", "send code")
            else:
                print("TELEGRAM LOGIN: User session available")
                await self.send_success_notif("telegram login", "logged in")
                self.session_created = True
        except errors.rpcerrorlist.PhoneNumberInvalidError:
            print("TELEGRAM LOGIN: Invalid phone number provided")
            await self.send_failed_notif("telegram login", "invalid phone number")
            await self.client.disconnect()
            await self.close()
        except (errors.rpcerrorlist.PhoneCodeInvalidError, errors.rpcerrorlist.PhoneCodeEmptyError, errors.rpcerrorlist.PhoneCodeInvalidError):
            print("TELEGRAM LOGIN: Invalid verification code provided.")
            await self.send_failed_notif("telegram login", "invalid verification code")
            await self.client.disconnect()
            await self.close()
        except errors.rpcerrorlist.AuthKeyDuplicatedError:
            print("TELEGRAM LOGIN: Duplicate Authorization Key")
            await self.send_failed_notif("telegram login", "duplicate session detected, login again")
            # Delete session file as the one currently cannot be used anymore (new session will need to be made)
            await self.close()
            await self.client.disconnect()
            await sync_to_async(os.remove)(f"{phone[1:]}.session")
        except errors.rpcerrorlist:
            print("TELEGRAM LOGIN: RPCE ERROR")
            await self.send_failed_notif("telegram login", "rpce error")
            await self.client.disconnect()
            await self.close()
        except Exception as e:
            print("TELEGRAM LOGIN: Some other exception occured")
            print(e)
            await self.send_failed_notif("telegram login", "Unknown Error")
            await self.client.disconnect()
            await self.close()

    async def validate_code(self, code):
        if self.logout:
            return
        
        try:
            await self.client.sign_in(self.phone, code)
            self.session_created = True
            print("TELEGRAM LOGIN: Code verified. Session Created.")
            await self.send_success_notif("telegram login", "logged in successfully")

            # INSERT THE API KEY IN TELEGRAMDB
            defaults = {
                'group_name': '',
                'message_id': ''
            }

            result = await sync_to_async(Telegram.objects.using('telegramdb').filter)(api_key=self.apiKey)
            result = await sync_to_async(result.first)()
            if not result:
                result = Telegram.objects.create(api_key=self.apiKey, defaults=defaults)
                print("TELEGRAM LOGIN: Record was created")
            else:
                print("TELEGRAM LOGIN: Record already exists")
        except (errors.SessionPasswordNeededError, errors.SendCodeUnavailableError, errors.PhoneCodeEmptyError, errors.PhoneCodeExpiredError, errors.PhoneCodeInvalidError):
            self.session_created = False
            print("TELEGRAM LOGIN: Invalid code provided...")
            await self.send_failed_notif("telegram login", "invalid code provided")
            await self.client.disconnect()
            await self.close()
        except Exception as e:
            print("TELEGRAM LOGIN: Some other exception occured")
            print(e)
            await self.send_failed_notif("telegram login", "Unknown Error")
            await self.client.disconnect()
            await self.close()

    async def send_group_users(self, group_name):
        group_name = group_name.strip()
        group_entity = await self.client.get_entity(await self.get_chat_id(group_name))

        api_calls = await sync_to_async(User.objects.using('userdb').get)(api_key=self.apiKey)
        api_calls = api_calls.api_calls

        update_or_create = sync_to_async(User.objects.using('userdb').update_or_create)
        entry, created = await update_or_create(api_key=self.apiKey, defaults={'api_calls': api_calls + 1})
        
        if created:
            # The record was created
            pass
        else:
            # The record already exists
            pass

        try:
            count = 0
            async for user in self.client.iter_participants(group_entity):
                if not isinstance(user, types.User) or user is None:
                    continue

                if self.logout:
                    print("=====================================")
                    print(f"USERS: Data Sent for {group_name}")
                    print(f"USERS: Total users sent: {count}")
                    print("USERS: Client Disconnected")
                    print("=====================================")
                    return

                user_dict = await self.get_user_properties(user)
                
                await self.send_success_notif("users", {
                    "group": group_name,
                    "user": user_dict
                })
                count += 1
            print(f"USERS: Data sent for group '{group_name}'")
            print("COUNT : ",count)
            await self.send_success_notif("users", f"All users sent from {group_name}")
            self.user_scraping_count -= 1

            if self.user_scraping_count == 0:
                await self.client.disconnect()
                await self.close()
        except errors.ChatAdminRequiredError:
            print(f"USERS: Admin privilege required to get users for {group_name}")
            await self.send_failed_notif("users", f"Admin privilege required for {group_name}. Connection terminated.")
            await self.client.disconnect()
            await self.close()
        except Exception as e:
            print("USERS: Unknown Exception: ", e)
            await self.send_failed_notif("users", "Unexpected error")
            await self.client.disconnect()
            await self.close()

    async def send_group_chats(self, group_name, min_id=0):
        group_name = group_name.strip()
        group_entity = await self.client.get_entity(await self.get_chat_id(group_name))

        api_calls = await sync_to_async(User.objects.using('userdb').get)(api_key=self.apiKey)
        api_calls = api_calls.api_calls

        update_or_create = sync_to_async(User.objects.using('userdb').update_or_create)
        entry, created = await update_or_create(api_key=self.apiKey, defaults={'api_calls': api_calls + 1})
        
        if created:
            # The record was created
            pass
        else:
            # The record already exists
            pass
        try:
            count = 0
            min_id = int(min_id)
            async for message in self.client.iter_messages(entity=group_entity, min_id=min_id, reverse=True):
                if not isinstance(message, types.Message) or message is None:
                    continue
                
                if self.logout:
                    print("=====================================")
                    print(f"CHATS: Data Sent for {group_name}")
                    print(f"CHATS: Last Message ID Sent: {message.id}")
                    print(f"CHATS: Total messages sent: {count}")
                    print("CHATS: Client Disconnected")
                    print("=====================================")
                    return

                message_dict = await self.get_message_properties(message)
                await self.send_success_notif("chats", {
                    "group": group_name,
                    "chat": message_dict
                })
                count += 1
                update_or_create = sync_to_async(Telegram.objects.using('telegramdb').update_or_create)
                entry, created = await update_or_create(api_key=self.apiKey, group_name=str(group_entity.id), defaults={'message_id': message_dict["id"]})
                
                if created:
                    # The record was created
                    pass
                else:
                    # The record already exists
                    pass
            print(f"CHATS: Data sent for {group_name}")
            print("Chats : ",count)
            await self.send_success_notif("chats", f"All chats sent from {group_name}")
            self.chat_scraping_count -= 1

            if self.chat_scraping_count == 0:
                await self.client.disconnect()
                await self.close()
        except errors.ChatAdminRequiredError:
            print(f"CHATS: Admin privilege required to get users for {group_name}")
            await self.send_failed_notif("chats", f"Admin privilege required for {group_name}")
            await self.client.disconnect()
            await self.close()
        except Exception as e:
            print("CHATS: Unknown Exception: ", e)
            await self.send_failed_notif("chats", "Unexpected error")
            await self.client.disconnect()
            await self.close()


    # ========== GROUP USERS UTILITY FUNCTIONS ==========
    def get_peer_dict(self, peer):
        if isinstance(peer, types.PeerUser):
            return {"_": "peerUser", "user_id": peer.user_id}
        elif isinstance(peer, types.PeerChat):
            return {"_": "peerChat", "chat_id": peer.chat_id}
        elif isinstance(peer, types.PeerChannel):
            return {"_": "peerChannel", "channel_id": peer.channel_id}
        else:
            return None

    def get_entity_dict(self, entity):
        return entity.to_dict()
    
    def convert_bytes(self, obj, encoding="utf-8"):
        if isinstance(obj, bytes):
            return obj.decode('iso-8859-1')
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, list):
            return [self.convert_bytes(item) for item in obj]
        elif isinstance(obj, dict):
            return {self.convert_bytes(key): self.convert_bytes(value) for key, value in obj.items()}
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

    def get_reply_markup_dict(self, reply_markup):
        if reply_markup is None:
            return None
        
        # Convert bytes to strings in the reply_markup
        reply_markup_dict = reply_markup.to_dict()
        reply_markup_dict = self.convert_bytes(reply_markup_dict)

        return reply_markup_dict

    def get_media_dict(self, media):
        if media is None:
            return None
        
        media = media.to_dict()
        media = self.convert_bytes(media, "iso-8859-1")

        return media

    def get_replies_dict(self, replies):
        return (
            {
                "replies": replies.replies,
                "replies_pts": replies.replies_pts,
                "comments": replies.comments,
                "recent_repliers": [r.to_dict() for r in replies.recent_repliers] if replies.recent_repliers else [],
                "channel_id": replies.channel_id,
                "max_id": replies.max_id,
                "read_max_id": replies.read_max_id
            }
            if replies
            else None
        )

    def get_restriction_reason_list(self, restriction_reason):
        if restriction_reason is None:
            return None
        return [reason.to_dict() for reason in restriction_reason]

    def get_forwards_dict(self, forwards):
        if not isinstance(forwards, types.MessageFwdHeader) or forwards is None:
            return None
        
        return {
            "from_id": forwards.from_id if forwards.from_id else None,
            "from_name": forwards.from_name if forwards.from_name else None,
            "date": forwards.date.isoformat() if forwards.date else None,
            "channel_id": forwards.channel_id if forwards.channel_id else None,
            "channel_post": forwards.channel_post if forwards.channel_post else None,
            "post_author": forwards.post_author if forwards.post_author else None,
        }

    def get_fwd_from_dict(self, fwd):
        if not fwd:
            return None

        return {
            'from_id': self.get_peer_dict(fwd.from_id) if fwd.from_id else None,
            'date': fwd.date.isoformat() if fwd.date else None,
            'saved_from_peer': {
                'user_id': self.get_peer_dict(fwd.saved_from_peer) if fwd.saved_from_peer else None,
                'channel_id': fwd.saved_from_peer.channel_id if fwd.saved_from_peer.channel_id else None
            } if fwd.saved_from_peer else None,
            'saved_from_msg_id': fwd.saved_from_msg_id if fwd.saved_from_msg_id else None,
        }

    async def get_user_by_id(self, client, user_id):
        user_entity = await client.get_entity(types.PeerUser(user_id))
        return user_entity
    
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
            "usernames": [username.to_dict() for username in user.usernames] if user.usernames else None,
            "restriction_reason": [reason.to_dict() for reason in user.restriction_reason] if user.restriction_reason else None,
            "access_hash": user.access_hash,
        }

    async def get_message_properties(self, message):        
        fromId = self.get_peer_dict(message.from_id) if message.from_id else None
        if fromId is not None and "user_id" in fromId:
            fromId = await self.get_user_by_id(self.client, fromId["user_id"])
            fromId = await self.get_user_properties(fromId)

        return {
            "id": message.id if message.id else None,
            "peer_id": self.get_peer_dict(message.peer_id) if message.peer_id else None,
            "date": message.date.isoformat() if message.date else None,
            "edit_date": message.edit_date.isoformat() if message.edit_date else None,
            "message": message.message if message.message else None,

            "out": message.out,
            "mentioned": message.mentioned,
            "media_unread": message.media_unread,
            "silent": message.silent,
            "post": message.post,
            "from_scheduled": message.from_scheduled,
            "legacy": message.legacy,
            "edit_hide": message.edit_hide,
            "pinned": message.pinned,
            "noforwards": message.noforwards,

            "from_id": fromId,
            "fwd_from": self.get_fwd_from_dict(message.fwd_from),
            "via_bot_id": message.via_bot_id.to_dict() if message.via_bot_id else None,
            "reply_to": message.reply_to.to_dict() if message.reply_to else None,
            "entities": [self.get_entity_dict(entity) for entity in message.entities or []],
            "reply_markup": self.get_reply_markup_dict(message.reply_markup) if message.reply_markup else None,
            "media": self.get_media_dict(message.media) if message.media else None,
            "post_author": self.get_peer_dict(message.post_author),
            "views": message.views if message.views is not None else None,
            "forwards": self.get_forwards_dict(message.forwards) if message.forwards else None,
            "replies": self.get_replies_dict(message.replies),
            "grouped_id": message.grouped_id if message.grouped_id else None,
            "reactions": message.reactions.to_dict() if message.reactions else None,
            "restriction_reason": [reason.to_dict() for reason in message.restriction_reason] if message.restriction_reason else None,
            "ttl_period": message.ttl_period if message.ttl_period is not None and message.ttl_period != 0 else None
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

    async def get_chat_id(self, group):
        async for dialog in self.client.iter_dialogs():
            if group.lower() in dialog.name.lower():
                return int(dialog.id)

    async def dialog_exists(self, group):
        try:
            async for dialog in self.client.iter_dialogs():
                if group.lower() in dialog.name.lower():
                    return True
            return False
        except (ValueError, AttributeError):
            return False
    
    async def is_group(self, group):
        try:
            group_entity = await self.client.get_entity(group)
            return True
            # if hasattr(group_entity, 'group') and group_entity.group:
            #     return True
            # else:
            #     return False
        except (ValueError, AttributeError):
            return False

    async def group_name_validity(self, event, group_name):
        group = group_name
        if type(group_name) is dict:
            group = group_name["name"]
        
        if not group.strip():
            await self.send_failed_notif(event, "Group name must be provided")
            print(f"{event.upper()}: Group name not provided")
            await self.client.disconnect()
            await self.close()

        if not await self.dialog_exists(group):
            await self.send_failed_notif(event, "Invalid group/channel name")
            print(f"{event.upper()}: '{group}' is an invalid group/channel name")
            await self.client.disconnect()
            await self.close()
