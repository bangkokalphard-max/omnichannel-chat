import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

BKK_TZ = timezone(timedelta(hours=7))

def get_bkk_time() -> str:
    return datetime.now(BKK_TZ).strftime("%H:%M")

DB_PATH = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. ตาราง Channels (รองรับหลาย LINE OA / FB / IG)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        platform TEXT NOT NULL,
        access_token TEXT NOT NULL,
        channel_secret TEXT DEFAULT '',
        color TEXT DEFAULT '#10b981'
    )
    """)
    
    # 2. ตารางห้องสนทนา (Conversations)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        channel_id TEXT NOT NULL,
        platform TEXT NOT NULL,
        platform_user_id TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        customer_avatar TEXT,
        tags TEXT DEFAULT '[]',
        notes TEXT DEFAULT '',
        unread_count INTEGER DEFAULT 0,
        updated_at TEXT NOT NULL,
        is_pinned INTEGER DEFAULT 0,
        last_activity_timestamp INTEGER DEFAULT 0,
        FOREIGN KEY (channel_id) REFERENCES channels (id)
    )
    """)
    
    # Check and add columns if migrating
    try:
        cursor.execute("ALTER TABLE conversations ADD COLUMN is_pinned INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE conversations ADD COLUMN last_activity_timestamp INTEGER DEFAULT 0")
    except Exception:
        pass
    
    # 3. ตารางบันทึกข้อความสนทนาทั้งหมดตลอดไป (Messages)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        sender TEXT NOT NULL, -- 'customer' หรือ 'agent'
        text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations (id)
    )
    """)
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# เพิ่มหรืออัปเดต LINE OA Channel
def upsert_channel(channel_id: str, name: str, platform: str, access_token: str, channel_secret: str = '', color: str = '#10b981'):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO channels (id, name, platform, access_token, channel_secret, color)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        name=excluded.name,
        access_token=excluded.access_token,
        channel_secret=excluded.channel_secret,
        color=excluded.color
    """, (channel_id, name, platform, access_token, channel_secret, color))
    conn.commit()
    conn.close()

def get_channel(channel_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_channels():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM channels")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ดึงหรือสร้างห้องสนทนา
def get_or_create_conversation(channel_id: str, platform: str, user_id: str, customer_name: str, avatar_url: str):
    conn = get_db()
    cursor = conn.cursor()
    conv_id = f"{channel_id}_{user_id}"
    time_display = get_bkk_time()
    current_ts = int(datetime.now().timestamp())
    
    cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("""
        INSERT INTO conversations (id, channel_id, platform, platform_user_id, customer_name, customer_avatar, updated_at, unread_count, is_pinned, last_activity_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
        """, (conv_id, channel_id, platform, user_id, customer_name, avatar_url, time_display, current_ts))
    else:
        existing_name = row["customer_name"]
        # ถ้าชื่อเดิมไม่ใช่ชื่อ placeholder ไม่ต้องทับด้วย placeholder
        new_name = customer_name
        if existing_name and not existing_name.startswith("ลูกค้า Facebook") and not existing_name.startswith("ลูกค้า LINE"):
            if customer_name.startswith("ลูกค้า Facebook") or customer_name.startswith("ลูกค้า LINE"):
                new_name = existing_name

        existing_avatar = row["customer_avatar"]
        new_avatar = avatar_url
        if existing_avatar and "unsplash" not in existing_avatar:
            if "unsplash" in avatar_url or not avatar_url:
                new_avatar = existing_avatar

        cursor.execute("""
        UPDATE conversations 
        SET customer_name = ?, customer_avatar = ?, updated_at = ?, unread_count = unread_count + 1, last_activity_timestamp = ?
        WHERE id = ?
        """, (new_name, new_avatar, time_display, current_ts, conv_id))

        
    conn.commit()
    conn.close()
    return conv_id

def update_customer_name(conv_id: str, new_name: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET customer_name = ? WHERE id = ?", (new_name, conv_id))
    conn.commit()
    conn.close()

# ปักหมุด / เลิกปักหมุด แชท
def toggle_pin_conversation(conv_id: str) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_pinned FROM conversations WHERE id = ?", (conv_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    current_val = row["is_pinned"] if "is_pinned" in row.keys() else 0
    new_pinned = 0 if current_val else 1
    cursor.execute("UPDATE conversations SET is_pinned = ? WHERE id = ?", (new_pinned, conv_id))
    conn.commit()
    conn.close()
    return bool(new_pinned)

# ลบห้องแชทพร้อมประวัติข้อความทั้งหมด
def delete_conversation(conv_id: str) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()
    return True

# บันทึกข้อความลง DB ถาวร และอัปเดตเวลากิจกรรมล่าสุด
def save_message(conv_id: str, sender: str, text: str, msg_id: str = None):
    conn = get_db()
    cursor = conn.cursor()
    time_display = get_bkk_time()
    current_ts = int(datetime.now().timestamp())
    
    if not msg_id:
        import uuid
        msg_id = str(uuid.uuid4())[:8]
        
    cursor.execute("""
    INSERT INTO messages (id, conversation_id, sender, text, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (msg_id, conv_id, sender, text, time_display))
    
    cursor.execute("""
    UPDATE conversations SET updated_at = ?, last_activity_timestamp = ? WHERE id = ?
    """, (time_display, current_ts, conv_id))
    
    conn.commit()
    conn.close()
    return {"id": msg_id, "sender": sender, "text": text, "time": time_display}

# ดึงรายการสนทนาทั้งหมดพร้อมข้อความ (เรียง: ปักหมุดก่อน -> ล่าสุดอยู่บนเสมอ)
def fetch_conversations_with_messages():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.*, ch.name as channel_name, ch.color as channel_color
    FROM conversations c
    LEFT JOIN channels ch ON c.channel_id = ch.id
    ORDER BY c.is_pinned DESC, c.last_activity_timestamp DESC, c.rowid DESC
    """)
    conv_rows = cursor.fetchall()

    
    result = []
    for cr in conv_rows:
        conv = dict(cr)
        # ดึง messages ของห้องนี้
        cursor.execute("SELECT id, sender, text, created_at as time FROM messages WHERE conversation_id = ? ORDER BY rowid ASC", (conv["id"],))
        conv["messages"] = [dict(m) for m in cursor.fetchall()]
        conv["tags"] = [] # Simple for now
        result.append(conv)
        
    conn.close()
    return result

# เคลียร์ unread count
def mark_read(conv_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET unread_count = 0 WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()
