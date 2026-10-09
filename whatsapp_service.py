import sys
import threading
import time
import segno
import logging
from typing import Optional, Callable

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Prevent any terminal encoding crashes from segno
try:
    import segno.writers
    segno.writers.write_terminal_compact = lambda *args, **kwargs: None
except Exception:
    pass

from neonize.client import NewClient
from neonize.events import ConnectedEv, MessageEv, DisconnectedEv, LoggedOutEv, Event
from neonize.proto.waE2E import WAWebProtobufsE2E_pb2 as wa_proto
from neonize.utils import build_jid

# Silence internal terminal QR printing
Event._Event__onqr = lambda self, client, data_qr: None

class WhatsAppManager:
    def __init__(self, db_name: str = "whatsapp_store.db"):
        self.db_name = db_name
        self.client: Optional[NewClient] = None
        self.qr_data_url: Optional[str] = None
        self.is_connected: bool = False
        self.user_phone: Optional[str] = None
        self.thread: Optional[threading.Thread] = None
        self.on_message_callback: Optional[Callable] = None
        self.on_status_callback: Optional[Callable] = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        
        self.thread = threading.Thread(target=self._run_client, daemon=True)
        self.thread.start()

    def _run_client(self):
        try:
            self.client = NewClient(self.db_name)

            @self.client.qr
            def on_qr(client, data_qr: bytes):
                try:
                    qr_str = data_qr.decode("utf-8") if isinstance(data_qr, bytes) else str(data_qr)
                    qr_img = segno.make(qr_str)
                    self.qr_data_url = qr_img.png_data_uri(scale=5)
                    self.is_connected = False
                    print(f"WHATSAPP QR CODE READY (length: {len(self.qr_data_url)})")
                    if self.on_status_callback:
                        self.on_status_callback({"status": "qr_ready", "qr": self.qr_data_url})
                except Exception as e:
                    print("Error generating QR image:", e)

            @self.client.event(ConnectedEv)
            def on_connected(client, ev: ConnectedEv):
                self.is_connected = True
                self.qr_data_url = None
                print("WHATSAPP CONNECTED SUCCESSFULLY!")
                try:
                    me = client.get_me()
                    if me:
                        self.user_phone = me.JID.User
                except Exception:
                    pass
                if self.on_status_callback:
                    self.on_status_callback({"status": "connected", "phone": self.user_phone})

            @self.client.event(DisconnectedEv)
            def on_disconnected(client, ev: DisconnectedEv):
                self.is_connected = False
                print("WHATSAPP DISCONNECTED")
                if self.on_status_callback:
                    self.on_status_callback({"status": "disconnected"})

            @self.client.event(LoggedOutEv)
            def on_logged_out(client, ev: LoggedOutEv):
                self.is_connected = False
                self.qr_data_url = None
                print("WHATSAPP LOGGED OUT")
                if self.on_status_callback:
                    self.on_status_callback({"status": "logged_out"})

            @self.client.event(MessageEv)
            def on_message(client, msg_ev: MessageEv):
                try:
                    info = msg_ev.Info
                    source = getattr(info, "MessageSource", None)

                    # Check if message is from me
                    is_from_me = False
                    if source and hasattr(source, "IsFromMe"):
                        is_from_me = bool(source.IsFromMe)
                    elif hasattr(info, "IsFromMe"):
                        is_from_me = bool(info.IsFromMe)

                    # Resolve sender and chat JID
                    chat_jid = getattr(source, "Chat", None) if source else None
                    sender_jid = (getattr(source, "Sender", None) if source else None) or chat_jid
                    if not sender_jid and hasattr(info, "Sender"):
                        sender_jid = info.Sender

                    if not sender_jid:
                        return

                    user_id = getattr(sender_jid, "User", "")
                    server = getattr(sender_jid, "Server", "")

                    if not user_id or user_id == "status" or "broadcast" in server:
                        return

                    # Chat target ID (for conversations)
                    chat_user = getattr(chat_jid, "User", user_id) if chat_jid else user_id
                    chat_server = getattr(chat_jid, "Server", server) if chat_jid else server

                    full_jid = f"{chat_user}@{chat_server}" if chat_server else chat_user
                    sender_id = chat_user

                    # Extract message text
                    text = ""
                    msg = msg_ev.Message
                    if getattr(msg, "conversation", None):
                        text = msg.conversation
                    elif msg.HasField("extendedTextMessage") and msg.extendedTextMessage.text:
                        text = msg.extendedTextMessage.text
                    elif msg.HasField("imageMessage"):
                        caption = msg.imageMessage.caption if msg.imageMessage.caption else ""
                        text = f"[รูปภาพ] {caption}".strip()
                    elif msg.HasField("documentMessage"):
                        fname = msg.documentMessage.fileName if msg.documentMessage.fileName else ""
                        text = f"[เอกสาร] {fname}".strip()
                    elif msg.HasField("audioMessage"):
                        text = "[ข้อความเสียง]"
                    elif msg.HasField("videoMessage"):
                        caption = msg.videoMessage.caption if msg.videoMessage.caption else ""
                        text = f"[วิดีโอ] {caption}".strip()
                    elif msg.HasField("stickerMessage"):
                        text = "[สติกเกอร์]"
                    elif msg.HasField("locationMessage"):
                        text = "[ตำแหน่งที่ตั้ง GPS]"
                    elif msg.HasField("contactMessage"):
                        text = "[รายชื่อติดต่อ]"

                    if not text.strip():
                        return

                    push_name = getattr(info, "Pushname", "") or f"WhatsApp (+{sender_id})"

                    print(f"WHATSAPP INCOMING: {push_name} ({sender_id}): {text}")

                    # ดึงรูปโปรไฟล์จริงจาก WhatsApp
                    avatar_url = ""
                    try:
                        pic_info = self.client.get_profile_picture(chat_jid or sender_jid)
                        if pic_info and getattr(pic_info, "URL", None):
                            avatar_url = pic_info.URL
                    except Exception as err:
                        print("Could not fetch WA profile picture:", err)

                    if self.on_message_callback:
                        self.on_message_callback(
                            sender_id=sender_id,
                            full_jid=full_jid,
                            push_name=push_name,
                            text=text,
                            avatar_url=avatar_url,
                            is_from_me=is_from_me
                        )
                except Exception as e:
                    print("Error processing incoming WhatsApp message:", e)

            # Start connection (blocking in this thread)
            self.client.connect()
        except Exception as e:
            print("WhatsApp client error:", e)

    def send_text_message(self, recipient_id: str, text: str) -> bool:
        if not self.client or not self.is_connected:
            return False
        try:
            # Build JID (e.g. 66812345678@s.whatsapp.net or group @g.us)
            server = "g.us" if "@g.us" in recipient_id or "-" in recipient_id else "s.whatsapp.net"
            user_part = recipient_id.split("@")[0].replace("+", "").strip()
            target_jid = build_jid(user_part, server)
            self.client.send_message(target_jid, text)
            return True
        except Exception as e:
            print(f"Error sending WhatsApp message to {recipient_id}:", e)
            return False

    def get_status(self) -> dict:
        return {
            "is_connected": self.is_connected,
            "qr_data_url": self.qr_data_url,
            "user_phone": self.user_phone
        }

whatsapp_manager = WhatsAppManager()
