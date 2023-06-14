
# Websocket URL
```bash
ws://localhost:8000/ws/telegram/
```

# Login
### Request:
```json
{
	"event": "login",
	"data": {
		"apiKey": "alkflknsdnfsjkn.ksalfjksdhksdsfdsdfsdf.lkszmlsknmskjdns"
	}
}
```

### Response(s):
- if `apiKey` matches the one in database (not implemented, hard coded for now):
```json
{
	"event": "login",
	"data": {
		"status": "success",
        	"message": "send phone number"
	}
}
```
- if `apiKey` does not match:
```json
{
	"event": "login",
	"data": {
		"status": "failed",
        	"message": "unauthorized"
	}
}
```
- if user already logged in:
```json
{
	"event": "login",
	"data": {
		"status": "success",
        	"message": "Already verified. Send data to 'telegram login' or 'users'."
	}
}
```
- if session already exists:
```json
{
	"event": "login",
	"data": {
		"status": "success",
        	"message": "session already exists, call 'users'."
	}
}
```

# Telegram Login
### Request:
```json
{
	"event": "telegram login",
	"data": {
		"phone": "+919876543210"
	}
}
```

### Response(s):
- if phone number is valid:
```json
{
	"event": "telegram login",
	"data": {
		"status": "success",
        	"message": "send code"
	}
}
```
- if invalid / wrong phone number provided: **(socket closed)**
```json
{
	"event": "telegram login",
	"data": {
		"status": "failed",
        	"message": "invalid phone number"
	}
}
```
- if code is valid
```json
{
	"event": "telegram login",
	"data": {
		"status": "success",
        	"message": "logged in successfully"
	}
}
```
- if invalid / wrong code provided: **(socket closed)**
```json
{
	"event": "telegram login",
	"data": {
		"status": "failed",
        	"message": "invalid code provided"
	}
}
```
- if user is not verified (apiKey login not done): **(socket closed)**
```json
{
	"event": "telegram login",
	"data": {
		"status": "failed",
        	"message": "verify your api key first"
	}
}
```
- if session already exists:
```json
{
	"event": "telegram login",
	"data": {
		"status": "success",
        	"message": "session alreay exists, call 'users'"
	}
}
```

# Users
### Request:
- Get all the users in a group(s)
```json
{
	"event": "users",
	"data": {
		"group": ["testgroup00001", "testgroup00002"],
		"status": ""
	}
}
```
- Get all the latest users in a group(s)
```json
{
	"event": "users",
	"data": {
		"group": ["testgroup00001", "testgroup00002"],
		"status": "latest"
	}
}
```

### Response(s):
- if group name is valid and is not a channel name:
```json
{
    "event": "users",
    "data": {
        "status": "success",
        "message": "sending users"
    }
}

...Data will be sent in this formar:
{
    "event": "users",
    "data": {
        "status": "success",
        "message": {
            "group": "group_name",
            "user": {
                "id": "userid",
                ...
            }
        }
    }
}
```
- if channel name is provided: **(socket closed)**
```json
{
    "event": "users",
    "data": {
        "status": "failed",
        "message": "{group} is a channel name"
    }
}
```
- if invalid group name provided: **(socket closed)**
```json
{
    "event": "users",
    "data": {
        "status": "failed",
        "message": "{group} does not exist"
    }
}
```

# Chats
### Request:
- Get all the chats in a group/channel(s)
```json
{
	"event": "chats",
	"data": {
		"group": [
			{
				"name": "UnderWorld4444",
				"status": ""
			}
		],
		"status": ""
	}
}
```
- Get all the latest chats in a group/channel(s) [latest from where you last left]
```json
{
	"event": "chats",
	"data": {
		"group": [
			{
				"name": "UnderWorld4444",
				"status": "latest"
			}
		],
		"status": ""
	}
}
```

### Response(s):
- if valid group/channel name provided:
```json
{
    "event": "chats",
    "data": {
        "status": "success",
        "message": "sending chats"
    }
}

...Data will be sent in this formar:
{
    "event": "chats",
    "data": {
        "status": "success",
        "message": {
            "group": "group_name",
            "chat": {
                "id": "messageid",
                ...
            }
        }
    }
}
```
- if invalid group/channel name provided: **(socket closed)**
```json
{
    "event": "chats",
    "data": {
        "status": "failed",
        "message": "invalid request"
    }
}
```