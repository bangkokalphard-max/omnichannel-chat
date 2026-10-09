import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db

app = FastAPI(title="Omnichannel Multi-LINE Chat Inbox")

# Initialize database
db.init_db()

# บันทึกเริ่มต้น 5 LINE OA ลงฐานข้อมูล (แยกร้าน แยกสี แยก Webhook)
line_accounts = [
    {
        "id": "line-1",
        "name": "Alphardbangkok",
        "platform": "line",
        "access_token": "wbRHK5cGgJ/gh/fdmG6r9Udtb7H30Qw7/NjG6EpEaYtN5sHC7T8EEVWvt/yuh9AKe85evMsta6WeIhG1FwC1WQSXVf1sZ+evW9qKetVdpMaM6VXxJLU7YBjcAlvNVBj3J/K0oV/cBd+oECUR6HM0ywdB04t89/1O/w1cDnyilFU=",
        "channel_secret": "66a2a9ddfb0fa207779979d9a35e26c4",
        "color": "#10b981" # เขียวมรกต
    },
    {
        "id": "line-2",
        "name": "Bangkokalphard",
        "platform": "line",
        "access_token": "BQgGzbMkvk8LAOq0c7CmHJUyWXZ+5dkzaMnJ5Y3ydT/u0UrlakstkuXdSGGn2YQcigC4duj2cqlwfoCSVc9NEMk+yVvJ0G9rBgpbX+ygphmNlggRu6z+v5gBWUkTrC8UK3sr8VyJK2UBQ7f7OvAlEwdB04t89/1O/w1cDnyilFU=",
        "channel_secret": "4128ba6c6d33b3974c78566aa609a6de",
        "color": "#06b6d4" # ฟ้า Cyan
    },
    {
        "id": "line-3",
        "name": "LINE 3: VIP Alphard Rental",
        "platform": "line",
        "access_token": "", # รอใส่ Token
        "channel_secret": "",
        "color": "#8b5cf6" # ม่วง
    },
    {
        "id": "line-4",
        "name": "LINE 4: ฝ่ายขาย / จองรถ",
        "platform": "line",
        "access_token": "", # รอใส่ Token
        "channel_secret": "",
        "color": "#f59e0b" # ส้ม Amber
    },
    {
        "id": "line-5",
        "name": "LINE 5: บริการลูกค้า / แอดมิน",
        "platform": "line",
        "access_token": "",
        "channel_secret": "",
        "color": "#ec4899"
    },
    {
        "id": "fb-alphard",
        "name": "FB: Alphardbangkok",
        "platform": "facebook",
        "access_token": "EAAT5wZA8GQLIBSpDqDi2naOtlMqvc86iawnNa3vzOwIUC7xVcXnezVoxsxRphnzjT30upGh1e2tkMFY7nIHkcX3wh1fEt7Ez988QiHUAbWz6IO8K8R48GipztrUHpfMmYHuNUvZCghL60T47qfmLuNplj6uR99hTbd51zQb9ba9jnROakVsPCZBDEEKDtFCv3Qew5pu",
        "channel_secret": "",
        "color": "#1877f2" # Facebook Blue
    },
    {
        "id": "fb-sclass",
        "name": "FB: Sclassbangkok",
        "platform": "facebook",
        "access_token": "EAAT5wZA8GQLIBSuy9tWra0c6OHFZBMaKde7ZAfGVZAM8Nu0yLZAYh9F1uShwPaDOrda4SQDTBhPNtVdZCxxFe7j7tgaByZAaougvZAkhcuZAKxTf0k4uZA3rv2Eik3DTEwBuODOZCmDH3kACEZA16izSZCDvVqd59gkV7e40gxwfOq42bJtUEUXSBN4o1dzBv4qP7MdaX1EKctUqnUQZDZD",
        "channel_secret": "",
        "color": "#0284c7" # Deep Sky Blue
    },
    {
        "id": "ig-alphard",
        "name": "IG: Alphardbangkok",
        "platform": "instagram",
        "access_token": "EAAT5wZA8GQLIBSpDqDi2naOtlMqvc86iawnNa3vzOwIUC7xVcXnezVoxsxRphnzjT30upGh1e2tkMFY7nIHkcX3wh1fEt7Ez988QiHUAbWz6IO8K8R48GipztrUHpfMmYHuNUvZCghL60T47qfmLuNplj6uR99hTbd51zQb9ba9jnROakVsPCZBDEEKDtFCv3Qew5pu",
        "channel_secret": "",
        "color": "#c06c84" # Instagram Earth Rose
    },
    {
        "id": "ig-sclass",
        "name": "IG: Sclassbangkok",
        "platform": "instagram",
        "access_token": "EAAT5wZA8GQLIBSuy9tWra0c6OHFZBMaKde7ZAfGVZAM8Nu0yLZAYh9F1uShwPaDOrda4SQDTBhPNtVdZCxxFe7j7tgaByZAaougvZAkhcuZAKxTf0k4uZA3rv2Eik3DTEwBuODOZCmDH3kACEZA16izSZCDvVqd59gkV7e40gxwfOq42bJtUEUXSBN4o1dzBv4qP7MdaX1EKctUqnUQZDZD",
        "channel_secret": "",
        "color": "#9d4b68"
    },
    {
        "id": "whatsapp",
        "name": "WhatsApp",
        "platform": "whatsapp",
        "access_token": "local-neonize",
        "channel_secret": "",
        "color": "#25D366" # WhatsApp Green
    }
]

from whatsapp_service import whatsapp_manager


for acc in line_accounts:
    db.upsert_channel(
        channel_id=acc["id"],
        name=acc["name"],
        platform=acc["platform"],
        access_token=acc["access_token"],
        channel_secret=acc["channel_secret"],
        color=acc["color"]
    )

# Connection manager for real-time WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                pass

manager = ConnectionManager()

main_loop: Optional[asyncio.AbstractEventLoop] = None

@app.on_event("startup")
async def startup_event():
    global main_loop
    try:
        main_loop = asyncio.get_running_loop()
    except Exception:
        main_loop = asyncio.get_event_loop()
    # Start WhatsApp client in background thread
    whatsapp_manager.start()

def handle_whatsapp_incoming(sender_id: str, full_jid: str, push_name: str, text: str, avatar_url: str = "", is_from_me: bool = False):
    if not avatar_url:
        import urllib.parse
        enc = urllib.parse.quote(push_name or "WA")
        avatar_url = f"https://ui-avatars.com/api/?name={enc}&background=3d3832&color=f5ede2&bold=true"

    conv_id = db.get_or_create_conversation(
        channel_id="whatsapp",
        platform="whatsapp",
        user_id=sender_id,
        customer_name=push_name,
        avatar_url=avatar_url
    )
    sender_type = "agent" if is_from_me else "customer"
    saved_msg = db.save_message(conv_id, sender=sender_type, text=text)
    if main_loop and main_loop.is_running():
        event_type = "new_message" if is_from_me else "incoming_customer_message"
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({
                "type": event_type,
                "conversation_id": conv_id,
                "message": saved_msg
            }),
            main_loop
        )

def handle_whatsapp_status(status_data: dict):
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({
                "type": "whatsapp_status",
                "status": status_data
            }),
            main_loop
        )

whatsapp_manager.on_message_callback = handle_whatsapp_incoming
whatsapp_manager.on_status_callback = handle_whatsapp_status


# Helper: Fetch LINE user profile
async def get_line_profile(token: str, user_id: str) -> dict:
    import urllib.parse
    enc = urllib.parse.quote(user_id[-4:])
    fallback_avatar = f"https://ui-avatars.com/api/?name={enc}&background=3d3832&color=f5ede2&bold=true"

    if not token or not token.strip():
        return {"displayName": f"ลูกค้า LINE ({user_id[-4:]})", "pictureUrl": fallback_avatar}
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    headers = {"Authorization": f"Bearer {token.strip()}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("pictureUrl"):
                    data["pictureUrl"] = fallback_avatar
                return data
    except Exception as e:
        print(f"Error fetching profile: {e}")
    return {"displayName": f"ลูกค้า LINE ({user_id[-4:]})", "pictureUrl": fallback_avatar}

# Helper: Push reply to customer via specific LINE token
async def send_line_message(token: str, user_id: str, text: str):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}]
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            print("LINE push response:", resp.status_code, resp.text)
            return resp.status_code == 200
    except Exception as e:
        print(f"Error sending LINE message: {e}")
        return False

@app.get("/api/conversations")
async def get_conversations():
    return db.fetch_conversations_with_messages()

@app.get("/api/channels")
async def get_channels():
    return db.get_all_channels()

class AgentReply(BaseModel):
    conversation_id: str
    message: str

# Helper: Push reply to customer via Facebook Graph API
async def send_facebook_message(token: str, recipient_id: str, text: str):
    url = f"https://graph.facebook.com/v21.0/me/messages?access_token={token}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
            print("FB Send response:", resp.status_code, resp.text)
            return resp.status_code == 200
    except Exception as e:
        print(f"Error sending FB message: {e}")
        return False

@app.post("/api/send-reply")
async def send_reply(reply: AgentReply):
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT c.*, ch.access_token, ch.platform FROM conversations c JOIN channels ch ON c.channel_id = ch.id WHERE c.id = ?", (reply.conversation_id,))
    conv = cursor.fetchone()
    conn.close()

    if not conv:
        return JSONResponse(status_code=404, content={"error": "Conversation not found"})

    conv_data = dict(conv)
    # บันทึกลง SQLite ถาวร
    new_msg = db.save_message(reply.conversation_id, sender="agent", text=reply.message)

    # ส่งออกตาม Platform
    if conv_data["platform"] == "line" and conv_data.get("access_token"):
        asyncio.create_task(send_line_message(conv_data["access_token"], conv_data["platform_user_id"], reply.message))
    elif conv_data["platform"] in ["facebook", "instagram"] and conv_data.get("access_token"):
        asyncio.create_task(send_facebook_message(conv_data["access_token"], conv_data["platform_user_id"], reply.message))
    elif conv_data["platform"] == "whatsapp":
        whatsapp_manager.send_text_message(conv_data["platform_user_id"], reply.message)

    await manager.broadcast({
        "type": "new_message",
        "conversation_id": reply.conversation_id,
        "message": new_msg
    })
    return {"status": "success", "message": new_msg}

@app.post("/api/mark-read/{conv_id}")
async def mark_read_api(conv_id: str):
    db.mark_read(conv_id)
    return {"status": "ok"}

class CustomerNameUpdate(BaseModel):
    conversation_id: str
    new_name: str

@app.post("/api/update-customer-name")
async def update_customer_name_api(payload: CustomerNameUpdate):
    db.update_customer_name(payload.conversation_id, payload.new_name)
    await manager.broadcast({
        "type": "customer_name_updated",
        "conversation_id": payload.conversation_id,
        "new_name": payload.new_name
    })
    return {"status": "ok", "new_name": payload.new_name}

@app.post("/api/conversations/{conv_id}/pin")
async def pin_conversation_api(conv_id: str):
    is_pinned = db.toggle_pin_conversation(conv_id)
    await manager.broadcast({
        "type": "conversation_pinned",
        "conversation_id": conv_id,
        "is_pinned": is_pinned
    })
    return {"status": "ok", "is_pinned": is_pinned}

@app.delete("/api/conversations/{conv_id}")
async def delete_conversation_api(conv_id: str):
    db.delete_conversation(conv_id)
    await manager.broadcast({
        "type": "conversation_deleted",
        "conversation_id": conv_id
    })
    return {"status": "ok"}
    
@app.get("/api/whatsapp/status")
async def get_whatsapp_status():
    return whatsapp_manager.get_status()

@app.post("/api/whatsapp/start")
async def start_whatsapp():
    whatsapp_manager.start()
    return {"status": "started"}




# --- Webhook สำหรับ Meta (Facebook Messenger & Instagram) ---
VERIFY_TOKEN = "OMNICHANNEL_SECRET_2026"

@app.get("/webhook/meta")
async def verify_meta_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("META WEBHOOK VERIFIED SUCCESSFULLY!")
        return HTMLResponse(content=challenge, status_code=200)
    return HTMLResponse(content="Verification failed", status_code=403)

# Helper: Fetch Facebook user profile
async def get_facebook_profile(token: str, user_id: str) -> dict:
    url = f"https://graph.facebook.com/v21.0/{user_id}?fields=first_name,last_name,name,profile_pic&access_token={token}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"Error fetching FB profile: {e}")
    import urllib.parse
    enc = urllib.parse.quote(user_id[-4:])
    return {"name": f"ลูกค้า Facebook ({user_id[-4:]})", "profile_pic": f"https://ui-avatars.com/api/?name={enc}&background=3d3832&color=f5ede2&bold=true"}

# Helper: Fetch Instagram user profile
async def get_instagram_profile(token: str, user_id: str) -> dict:
    url = f"https://graph.facebook.com/v21.0/{user_id}?fields=name,username,profile_pic&access_token={token}"
    import urllib.parse
    enc = urllib.parse.quote(user_id[-4:])
    fallback_avatar = f"https://ui-avatars.com/api/?name={enc}&background=3d3832&color=f5ede2&bold=true"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("name") or data.get("username")
                pic = data.get("profile_pic") or fallback_avatar
                return {"name": name, "profile_pic": pic}
    except Exception as e:
        print(f"Error fetching IG profile: {e}")
    return {"name": f"ลูกค้า Instagram ({user_id[-4:]})", "profile_pic": fallback_avatar}

@app.post("/webhook/meta")
async def handle_meta_webhook(request: Request):
    try:
        body = await request.json()
        print("RECEIVED META EVENT OK:", json.dumps(body, ensure_ascii=False))
        
        is_instagram = body.get("object") == "instagram"
        entries = body.get("entry", [])
        for entry in entries:
            messaging = entry.get("messaging", [])
            for msg_item in messaging:
                sender_id = msg_item.get("sender", {}).get("id")
                recipient_id = msg_item.get("recipient", {}).get("id")
                message = msg_item.get("message", {})
                text = message.get("text")
                
                # ถ้ามีข้อความทักเข้ามา (และไม่ใช่ echo)
                if text and sender_id and not message.get("is_echo"):
                    target_id = str(entry.get("id") or recipient_id or "")
                    
                    if is_instagram:
                        platform = "instagram"
                        if target_id == "429912036877958" or "sclass" in target_id.lower():
                            channel_id = "ig-sclass"
                        else:
                            channel_id = "ig-alphard"
                        
                        channel = db.get_channel(channel_id)
                        token = channel["access_token"] if channel else ""
                        profile = await get_instagram_profile(token, sender_id)
                        customer_real_name = profile.get("name") or f"ลูกค้า Instagram ({sender_id[-4:]})"
                        customer_real_avatar = profile.get("profile_pic")
                    else:
                        platform = "facebook"
                        if target_id == "429912036877958":
                            channel_id = "fb-sclass"
                        elif target_id == "106886601678652":
                            channel_id = "fb-alphard"
                        else:
                            channel_id = "fb-sclass" if "sclass" in target_id.lower() else "fb-alphard"
                        
                        channel = db.get_channel(channel_id)
                        token = channel["access_token"] if channel else ""
                        fb_profile = await get_facebook_profile(token, sender_id)
                        customer_real_name = fb_profile.get("name") or f"ลูกค้า Facebook ({sender_id[-4:]})"
                        customer_real_avatar = fb_profile.get("profile_pic")

                    print(f"META MESSAGE: is_instagram={is_instagram}, target_id={target_id} -> channel_id={channel_id}")

                    conv_id = db.get_or_create_conversation(
                        channel_id=channel_id,
                        platform=platform,
                        user_id=sender_id,
                        customer_name=customer_real_name,
                        avatar_url=customer_real_avatar
                    )
                    saved_msg = db.save_message(conv_id, sender="customer", text=text)
                    await manager.broadcast({
                        "type": "incoming_customer_message",
                        "conversation_id": conv_id,
                        "message": saved_msg
                    })
    except Exception as e:
        print("Error processing Meta webhook:", e)
    return {"status": "ok"}

# --- Webhook สำหรับ LINE OA แต่ละบัญชี ---
@app.post("/webhook/line/{channel_id}")
@app.post("/webhook/{channel_id}")
@app.post("/webhook/line")
async def line_webhook_multi(request: Request, channel_id: str = "line-1"):
    try:
        body = await request.json()
        print(f"RECEIVED WEBHOOK FOR [{channel_id}]:", json.dumps(body, ensure_ascii=False))
    except Exception:
        return {"status": "ignored"}

    channel = db.get_channel(channel_id)
    token = channel["access_token"] if channel else ""

    events = body.get("events", [])
    for event in events:
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            user_id = event["source"].get("userId")
            text = event["message"]["text"]
            
            # ดึงโปรไฟล์จริงของลูกค้า
            profile = await get_line_profile(token, user_id)
            customer_name = profile.get("displayName", f"LINE ({user_id[-4:]})")
            avatar_url = profile.get("pictureUrl") or "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&h=100&fit=crop&crop=faces"

            # สร้างหรืออัปเดตห้องสนทนาใน SQLite
            conv_id = db.get_or_create_conversation(
                channel_id=channel_id,
                platform="line",
                user_id=user_id,
                customer_name=customer_name,
                avatar_url=avatar_url
            )

            # บันทึกข้อความลง DB ถาวร
            saved_msg = db.save_message(conv_id, sender="customer", text=text)

            # Broadcast ไปที่หน้าจอ UI เรียลไทม์
            await manager.broadcast({
                "type": "incoming_customer_message",
                "conversation_id": conv_id,
                "message": saved_msg
            })



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
