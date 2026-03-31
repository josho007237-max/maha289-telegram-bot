import asyncio
import html
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.types.input_file import FSInputFile
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip()
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip().lstrip("@")
DB_PATH = os.getenv("DB_PATH", "bot.db").strip()
ENV_ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID", "").strip()

# ===== [แก้บ่อย-01] รูปเมนู =====
PROMO_MENU_IMAGE = os.getenv("PROMO_MENU_IMAGE", "assets/promo_menu.jpg").strip()
POINT_MENU_IMAGE = os.getenv("POINT_MENU_IMAGE", "assets/point_menu.jpg").strip()
ADMIN_MENU_IMAGE = os.getenv("ADMIN_MENU_IMAGE", "assets/admin_menu.jpg").strip()
HELP_MENU_IMAGE = os.getenv("HELP_MENU_IMAGE", "assets/help_menu.jpg").strip()

# ===== [แก้บ่อย-02] ลิงก์หลัก =====
GAME_URL = os.getenv("GAME_URL", "https://www.maha289.com").strip()
POINT_URL = os.getenv("POINT_URL", "https://www.maha289.com").strip()
HELP_URL = os.getenv("HELP_URL", "https://www.maha289.com").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in .env")

router = Router()
dp = Dispatcher()
dp.include_router(router)

WELCOME_TEXT = """สวัสดีครับ ยินดีต้อนรับสู่ MAHA289

กรุณาเลือกเมนูที่ต้องการ:
• ข่าวล่าสุด
• โปรโมชั่น
• วิธีเริ่มต้น
• ติดต่อแอดมิน
• FAQ
"""

PROMO_TEXT = """โปรโมชั่นล่าสุด
กดเปิดช่องประกาศเพื่อดูโปรและข่าวอัปเดตล่าสุดได้เลยครับ"""

GETTING_STARTED_TEXT = """วิธีเริ่มต้น
1) ติดตามช่องประกาศ
2) ถ้าต้องการสอบถามส่วนตัว ให้กด 'ติดต่อแอดมิน'
3) ส่งรายละเอียดในห้องแชทนี้ได้เลย"""

FAQ_TEXT = """FAQ
• ติดตามข่าว: กดเมนู 'ข่าวล่าสุด'
• สอบถามแอดมิน: กดเมนู 'ติดต่อแอดมิน'
• ส่งหลักฐาน/รูปภาพ: ส่งในห้องนี้ได้เลยหลังเปิดเคส"""

# ===== [แก้บ่อย-03] หัวข้อเคส /admin =====
ADMIN_TOPICS = {
    "register_failed": {"label": "สมัครไม่ได้", "need_attachment": False},
    "verify_identity": {"label": "ยืนยันตัวตน", "need_attachment": True},
    "change_profile": {"label": "เปลี่ยนแปลงข้อมูล", "need_attachment": False},
    "deposit_missing": {"label": "ฝากเงินไม่เข้า", "need_attachment": True},
    "withdraw_failed": {"label": "ถอนเงินไม่ได้", "need_attachment": True},
    "other_contact": {"label": "ติดต่อเรื่องอื่น", "need_attachment": False},
    "site_issue": {"label": "แจ้งปัญหาภายในเว็บไซต์", "need_attachment": True},
}

# ===== [แก้บ่อย-04] ข้อความเมนู /admin =====
ADMIN_MENU_TEXT = """กรุณาเลือกหัวข้อที่ต้องการติดต่อแอดมิน

1) สมัครไม่ได้
2) ยืนยันตัวตน
3) เปลี่ยนแปลงข้อมูล
4) ฝากเงินไม่เข้า
5) ถอนเงินไม่ได้
6) ติดต่อเรื่องอื่น
7) แจ้งปัญหาภายในเว็บไซต์"""

class SupportFlow(StatesGroup):
    waiting_user_code = State()
    waiting_name = State()
    waiting_phone = State()
    waiting_detail = State()
    waiting_attachment = State()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                claimed_by INTEGER,
                card_message_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_message_map (
                admin_message_id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL
            )
            """
        )
        conn.commit()

def set_setting(key: str, value: str) -> None:
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()

def get_setting(key: str) -> Optional[str]:
    with db_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

def get_admin_group_id() -> Optional[int]:
    raw = ENV_ADMIN_GROUP_ID or get_setting("admin_group_id")
    if not raw:
        return None
    return int(raw)

def create_ticket(user_id: int, username: Optional[str], full_name: str, category: str) -> int:
    now = now_iso()
    with db_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tickets(user_id, username, full_name, category, status, claimed_by, card_message_id, created_at, updated_at)
            VALUES(?, ?, ?, ?, 'NEW', NULL, NULL, ?, ?)
            """,
            (user_id, username, full_name, category, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)

def get_ticket(ticket_id: int):
    with db_conn() as conn:
        return conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()

def get_active_ticket_for_user(user_id: int):
    with db_conn() as conn:
        return conn.execute(
            """
            SELECT * FROM tickets
            WHERE user_id=? AND status IN ('NEW', 'HUMAN')
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()

def update_ticket_status(ticket_id: int, status: str, claimed_by: Optional[int] = None) -> None:
    with db_conn() as conn:
        conn.execute(
            """
            UPDATE tickets
            SET status=?, claimed_by=?, updated_at=?
            WHERE id=?
            """,
            (status, claimed_by, now_iso(), ticket_id),
        )
        conn.commit()

def set_ticket_card_message_id(ticket_id: int, message_id: int) -> None:
    with db_conn() as conn:
        conn.execute(
            "UPDATE tickets SET card_message_id=?, updated_at=? WHERE id=?",
            (message_id, now_iso(), ticket_id),
        )
        conn.commit()

def map_admin_message(ticket_id: int, admin_message_id: int) -> None:
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO admin_message_map(admin_message_id, ticket_id)
            VALUES(?, ?)
            ON CONFLICT(admin_message_id) DO UPDATE SET ticket_id=excluded.ticket_id
            """,
            (admin_message_id, ticket_id),
        )
        conn.commit()

def find_ticket_id_by_admin_message(admin_message_id: int) -> Optional[int]:
    with db_conn() as conn:
        row = conn.execute(
            "SELECT ticket_id FROM admin_message_map WHERE admin_message_id=?",
            (admin_message_id,),
        ).fetchone()
        return int(row["ticket_id"]) if row else None

def status_label(status: str) -> str:
    return {
        "NEW": "รอแอดมิน",
        "HUMAN": "แอดมินกำลังดูแล",
        "CLOSED": "ปิดเคสแล้ว",
    }.get(status, status)

def safe_username(username: Optional[str]) -> str:
    return f"@{html.escape(username)}" if username else "-"

def ticket_card_text(ticket) -> str:
    return (
        f"🎫 <b>เคส #{ticket['id']}</b>\n"
        f"สถานะ: <b>{status_label(ticket['status'])}</b>\n"
        f"หมวด: {html.escape(ticket['category'])}\n"
        f"ลูกค้า: {html.escape(ticket['full_name'])}\n"
        f"username: {safe_username(ticket['username'])}\n"
        f"user_id: <code>{ticket['user_id']}</code>"
    )

def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="ข่าวล่าสุด", callback_data="menu:news"),
                InlineKeyboardButton(text="โปรโมชั่น", callback_data="menu:promo"),
            ],
            [
                InlineKeyboardButton(text="วิธีเริ่มต้น", callback_data="menu:getting_started"),
                InlineKeyboardButton(text="ติดต่อแอดมิน", callback_data="menu:admin"),
            ],
            [InlineKeyboardButton(text="FAQ", callback_data="menu:faq")],
        ]
    )

def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ กลับเมนูหลัก", callback_data="menu:home")]]
    )

def channel_link_kb() -> InlineKeyboardMarkup:
    if not CHANNEL_USERNAME:
        return back_home_kb()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 เปิดช่องประกาศ", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton(text="⬅️ กลับเมนูหลัก", callback_data="menu:home")],
        ]
    )

def admin_category_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1 สมัครไม่ได้", callback_data="admin:topic:register_failed")],
            [InlineKeyboardButton(text="2 ยืนยันตัวตน", callback_data="admin:topic:verify_identity")],
            [InlineKeyboardButton(text="3 เปลี่ยนแปลงข้อมูล", callback_data="admin:topic:change_profile")],
            [InlineKeyboardButton(text="4 ฝากเงินไม่เข้า", callback_data="admin:topic:deposit_missing")],
            [InlineKeyboardButton(text="5 ถอนเงินไม่ได้", callback_data="admin:topic:withdraw_failed")],
            [InlineKeyboardButton(text="6 ติดต่อเรื่องอื่น", callback_data="admin:topic:other_contact")],
            [InlineKeyboardButton(text="7 แจ้งปัญหาภายในเว็บไซต์", callback_data="admin:topic:site_issue")],
            [InlineKeyboardButton(text="⬅️ กลับเมนูหลัก", callback_data="menu:home")],
        ]
    )

def attachment_step_kb(required: bool) -> InlineKeyboardMarkup:
    rows = []
    if not required:
        rows.append([InlineKeyboardButton(text="ข้ามไม่แนบหลักฐาน", callback_data="admin:skip_attachment")])
    rows.append([InlineKeyboardButton(text="⬅️ กลับเมนูหลัก", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ticket_action_kb(ticket_id: int, closed: bool = False) -> Optional[InlineKeyboardMarkup]:
    if closed:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ รับเคส", callback_data=f"ticket:claim:{ticket_id}"),
                InlineKeyboardButton(text="🤖 คืนให้บอท", callback_data=f"ticket:bot:{ticket_id}"),
            ],
            [
                InlineKeyboardButton(text="🔒 ปิดเคส", callback_data=f"ticket:close:{ticket_id}")
            ],
        ]
    )

async def refresh_ticket_card(bot: Bot, ticket_id: int) -> None:
    ticket = get_ticket(ticket_id)
    admin_group_id = get_admin_group_id()
    if not ticket or not admin_group_id or not ticket["card_message_id"]:
        return
    try:
        await bot.edit_message_text(
            chat_id=admin_group_id,
            message_id=ticket["card_message_id"],
            text=ticket_card_text(ticket),
            reply_markup=ticket_action_kb(ticket_id, closed=ticket["status"] == "CLOSED"),
        )
    except TelegramBadRequest:
        pass

def fs_file_or_none(path: str) -> Optional[FSInputFile]:
    if path and os.path.isfile(path):
        return FSInputFile(path)
    return None

async def send_menu_photo_or_text(message: Message, image_path: str, caption: str, reply_markup: InlineKeyboardMarkup):
    photo = fs_file_or_none(image_path)
    if photo:
        await message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    else:
        await message.answer(caption, reply_markup=reply_markup)

async def send_menu_photo_or_text_callback(callback: CallbackQuery, image_path: str, caption: str, reply_markup: InlineKeyboardMarkup):
    photo = fs_file_or_none(image_path)
    if photo:
        await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
        try:
            await callback.message.delete()
        except Exception:
            pass
    else:
        await callback.message.edit_text(caption, reply_markup=reply_markup)

async def send_main_menu(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=menu_kb())

def normalize_phone(raw: str) -> str:
    return re.sub(r"\D", "", raw)

def admin_summary_text(ticket_id: int, data: dict) -> str:
    return (
        f"📌 <b>รายละเอียดลูกค้า</b>\n"
        f"เคส: <b>#{ticket_id}</b>\n"
        f"หัวข้อ: <b>{html.escape(data.get('topic_label', '-'))}</b>\n"
        f"USER: <code>{html.escape(data.get('user_code', '-'))}</code>\n"
        f"ชื่อ: {html.escape(data.get('customer_name', '-'))}\n"
        f"เบอร์โทร: <code>{html.escape(data.get('phone', '-'))}</code>\n"
        f"username telegram: {safe_username(data.get('telegram_username'))}\n"
        f"user_id: <code>{data.get('telegram_user_id')}</code>\n"
        f"\n<b>รายละเอียดปัญหา</b>\n{html.escape(data.get('detail', '-'))}"
    )

async def open_admin_menu_message(message: Message, state: FSMContext):
    await state.clear()
    await send_menu_photo_or_text(message, ADMIN_MENU_IMAGE, ADMIN_MENU_TEXT, admin_category_kb())

async def open_admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_menu_photo_or_text_callback(callback, ADMIN_MENU_IMAGE, ADMIN_MENU_TEXT, admin_category_kb())
    await callback.answer()

@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def on_start(message: Message, state: FSMContext):
    await state.clear()
    start_param = ""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        start_param = parts[1].strip().lower()

    if start_param == "support":
        await open_admin_menu_message(message, state)
        return

    await send_main_menu(message)

@router.message(Command("news"), F.chat.type == ChatType.PRIVATE)
async def cmd_news(message: Message):
    text = "กดปุ่มด้านล่างเพื่อเปิดช่องประกาศครับ" if CHANNEL_USERNAME else "ยังไม่ได้ตั้งค่า CHANNEL_USERNAME ใน .env"
    await message.answer(text, reply_markup=channel_link_kb())

@router.message(Command("promo"), F.chat.type == ChatType.PRIVATE)
async def cmd_promo(message: Message):
    await message.answer(PROMO_TEXT, reply_markup=channel_link_kb())

@router.message(Command("faq"), F.chat.type == ChatType.PRIVATE)
async def cmd_faq(message: Message):
    await message.answer(FAQ_TEXT, reply_markup=back_home_kb())

# ===== [แก้บ่อย-05] /admin และ /support ใช้เมนูเดียวกัน =====
@router.message(Command("admin"), F.chat.type == ChatType.PRIVATE)
async def cmd_admin(message: Message, state: FSMContext):
    await open_admin_menu_message(message, state)

@router.message(Command("support"), F.chat.type == ChatType.PRIVATE)
async def cmd_support(message: Message, state: FSMContext):
    await open_admin_menu_message(message, state)

@router.message(Command("binddesk"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_binddesk(message: Message):
    set_setting("admin_group_id", str(message.chat.id))
    await message.answer(
        f"ผูกห้องนี้เป็น Support Desk แล้ว\nADMIN_GROUP_ID = <code>{message.chat.id}</code>"
    )

@router.message(Command("publish"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_publish(message: Message, bot: Bot):
    admin_group_id = get_admin_group_id()
    if admin_group_id is None or message.chat.id != admin_group_id:
        await message.answer("ใช้คำสั่งนี้ได้เฉพาะในกลุ่ม Support Desk")
        return

    text = (message.text or "").split(maxsplit=1)
    if len(text) < 2 or not text[1].strip():
        await message.answer("วิธีใช้:\n/publish ข้อความที่จะประกาศ")
        return

    if not CHANNEL_USERNAME:
        await message.answer("ยังไม่ได้ตั้งค่า CHANNEL_USERNAME ใน .env")
        return

    await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=text[1].strip())
    await message.answer("โพสต์ลงช่องประกาศแล้ว ✅")

@router.callback_query(F.data == "menu:home")
async def cb_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=menu_kb())
    await callback.answer()

@router.callback_query(F.data == "menu:news")
async def cb_news(callback: CallbackQuery):
    text = "กดปุ่มด้านล่างเพื่อเปิดช่องประกาศครับ" if CHANNEL_USERNAME else "ยังไม่ได้ตั้งค่า CHANNEL_USERNAME ใน .env"
    await callback.message.edit_text(text, reply_markup=channel_link_kb())
    await callback.answer()

@router.callback_query(F.data == "menu:promo")
async def cb_promo(callback: CallbackQuery):
    await callback.message.edit_text(PROMO_TEXT, reply_markup=channel_link_kb())
    await callback.answer()

@router.callback_query(F.data == "menu:getting_started")
async def cb_getting_started(callback: CallbackQuery):
    await callback.message.edit_text(GETTING_STARTED_TEXT, reply_markup=back_home_kb())
    await callback.answer()

@router.callback_query(F.data == "menu:faq")
async def cb_faq(callback: CallbackQuery):
    await callback.message.edit_text(FAQ_TEXT, reply_markup=back_home_kb())
    await callback.answer()

@router.callback_query(F.data == "menu:admin")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    await open_admin_menu_callback(callback, state)

@router.callback_query(F.data.startswith("admin:topic:"))
async def cb_admin_topic(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":")[-1]
    topic = ADMIN_TOPICS.get(key)
    if not topic:
        await callback.answer("ไม่พบหัวข้อ", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        topic_key=key,
        topic_label=topic["label"],
        need_attachment=topic["need_attachment"],
        telegram_username=callback.from_user.username or "",
        telegram_user_id=callback.from_user.id,
    )
    await state.set_state(SupportFlow.waiting_user_code)
    await callback.message.answer(
        f"คุณเลือก: {topic['label']}\n\nเพื่อความรวดเร็ว โปรดแจ้งข้อมูลตามลำดับ\n\nข้อ 1/4 กรุณาส่ง USER ลูกค้ามาก่อนครับ"
    )
    await callback.answer()

@router.message(SupportFlow.waiting_user_code, F.chat.type == ChatType.PRIVATE)
async def support_wait_user_code(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("กรุณากรอก USER ลูกค้าก่อนครับ")
        return
    await state.update_data(user_code=text)
    await state.set_state(SupportFlow.waiting_name)
    await message.answer("ข้อ 2/4 กรุณาส่งชื่อที่สมัครครับ")

@router.message(SupportFlow.waiting_name, F.chat.type == ChatType.PRIVATE)
async def support_wait_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("ชื่อสั้นเกินไปครับ กรุณากรอกใหม่")
        return
    await state.update_data(customer_name=text)
    await state.set_state(SupportFlow.waiting_phone)
    await message.answer("ข้อ 3/4 กรุณาส่งเบอร์โทรที่สมัครครับ\nตัวอย่าง: 0812345678")

@router.message(SupportFlow.waiting_phone, F.chat.type == ChatType.PRIVATE)
async def support_wait_phone(message: Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if len(phone) < 9 or len(phone) > 10:
        await message.answer("เบอร์โทรไม่ถูกต้องครับ กรุณาส่งเป็นตัวเลข 9-10 หลัก")
        return
    await state.update_data(phone=phone)
    await state.set_state(SupportFlow.waiting_detail)
    await message.answer("ข้อ 4/4 กรุณาพิมพ์รายละเอียดปัญหาให้ครบครับ")

@router.message(SupportFlow.waiting_detail, F.chat.type == ChatType.PRIVATE)
async def support_wait_detail(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("รายละเอียดสั้นเกินไปครับ กรุณาพิมพ์เพิ่มอีกนิด")
        return

    await state.update_data(detail=text)
    data = await state.get_data()
    need_attachment = bool(data.get("need_attachment"))

    await state.set_state(SupportFlow.waiting_attachment)
    if need_attachment:
        await message.answer(
            "กรุณาแนบสลิปหรือภาพหลักฐาน 1 รูป/ไฟล์ได้เลยครับ",
            reply_markup=attachment_step_kb(required=True),
        )
    else:
        await message.answer(
            "ถ้ามีสลิปหรือภาพหลักฐาน ให้ส่งได้เลย\nถ้าไม่มี กดปุ่ม 'ข้ามไม่แนบหลักฐาน'",
            reply_markup=attachment_step_kb(required=False),
        )

@router.callback_query(F.data == "admin:skip_attachment")
async def cb_skip_attachment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if data.get("need_attachment"):
        await callback.answer("หัวข้อนี้ต้องแนบหลักฐานครับ", show_alert=True)
        return
    await finalize_admin_ticket(callback.message, state, bot)
    await callback.answer()

@router.message(SupportFlow.waiting_attachment, F.chat.type == ChatType.PRIVATE, F.photo)
async def support_wait_photo(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(first_attachment_message_id=message.message_id)
    await finalize_admin_ticket(message, state, bot)

@router.message(SupportFlow.waiting_attachment, F.chat.type == ChatType.PRIVATE, F.document)
async def support_wait_document(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(first_attachment_message_id=message.message_id)
    await finalize_admin_ticket(message, state, bot)

@router.message(SupportFlow.waiting_attachment, F.chat.type == ChatType.PRIVATE)
async def support_wait_attachment_invalid(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("need_attachment"):
        await message.answer("หัวข้อนี้ต้องแนบหลักฐานครับ\nกรุณาส่งเป็นรูปภาพหรือไฟล์เอกสาร")
    else:
        await message.answer("กรุณาส่งเป็นรูปภาพ/ไฟล์ หรือกดปุ่ม 'ข้ามไม่แนบหลักฐาน'")

async def finalize_admin_ticket(message: Message, state: FSMContext, bot: Bot):
    admin_group_id = get_admin_group_id()
    if not admin_group_id:
        await message.answer(
            "ยังไม่ได้ตั้งค่า Support Desk\nให้ไปพิมพ์ /binddesk ในกลุ่ม MAHA289 Support Desk ก่อน"
        )
        await state.clear()
        return

    data = await state.get_data()
    topic_label = data.get("topic_label", "อื่นๆ")

    ticket_id = create_ticket(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        category=topic_label,
    )
    ticket = get_ticket(ticket_id)

    card = await bot.send_message(
        admin_group_id,
        ticket_card_text(ticket),
        reply_markup=ticket_action_kb(ticket_id),
    )
    set_ticket_card_message_id(ticket_id, card.message_id)
    map_admin_message(ticket_id, card.message_id)

    summary = await bot.send_message(
        admin_group_id,
        admin_summary_text(ticket_id, data),
    )
    map_admin_message(ticket_id, summary.message_id)

    if data.get("first_attachment_message_id"):
        copied = await bot.copy_message(
            chat_id=admin_group_id,
            from_chat_id=message.chat.id,
            message_id=data["first_attachment_message_id"],
        )
        map_admin_message(ticket_id, copied.message_id)

    await state.clear()
    await message.answer(
        f"ระบบได้รับข้อมูลเรียบร้อยแล้ว ✅\nเลขที่เคส: #{ticket_id}\n\nรอสักครู่ เรากำลังตรวจสอบให้ครับ",
        reply_markup=menu_kb(),
    )

@router.callback_query(F.data.startswith("ticket:"))
async def cb_ticket_action(callback: CallbackQuery, bot: Bot):
    _, action, ticket_id_raw = callback.data.split(":")
    ticket_id = int(ticket_id_raw)
    ticket = get_ticket(ticket_id)

    if not ticket:
        await callback.answer("ไม่พบเคส", show_alert=True)
        return

    if action == "claim":
        first_claim = ticket["status"] != "HUMAN"
        update_ticket_status(ticket_id, "HUMAN", callback.from_user.id)
        await refresh_ticket_card(bot, ticket_id)
        if first_claim:
            await bot.send_message(
                ticket["user_id"],
                f"แอดมินเข้ารับเคส #{ticket_id} แล้วครับ\nพิมพ์ข้อความต่อในห้องนี้ได้เลย",
            )
        await callback.answer("รับเคสแล้ว")
        return

    if action == "bot":
        update_ticket_status(ticket_id, "NEW", None)
        await refresh_ticket_card(bot, ticket_id)
        await bot.send_message(
            ticket["user_id"],
            f"เคส #{ticket_id} ถูกคืนเข้าสู่คิวดูแลแล้วครับ",
        )
        await callback.answer("คืนให้บอทแล้ว")
        return

    if action == "close":
        update_ticket_status(ticket_id, "CLOSED", callback.from_user.id)
        await refresh_ticket_card(bot, ticket_id)
        await bot.send_message(
            ticket["user_id"],
            f"เคส #{ticket_id} ถูกปิดเรียบร้อยแล้วครับ\nหากต้องการสอบถามเพิ่มเติม พิมพ์ข้อความใหม่ได้ตลอด",
        )
        await callback.answer("ปิดเคสแล้ว")
        return

@router.message(F.chat.type == ChatType.PRIVATE)
async def relay_private_user_messages(message: Message, bot: Bot):
    if not message.from_user or message.from_user.is_bot:
        return
    if (message.text or "").startswith("/"):
        return

    ticket = get_active_ticket_for_user(message.from_user.id)
    if not ticket:
        await send_main_menu(message)
        return

    admin_group_id = get_admin_group_id()
    if not admin_group_id:
        await message.answer("ยังไม่ได้ตั้งค่า Support Desk")
        return

    header = await bot.send_message(
        admin_group_id,
        f"📨 ข้อความใหม่จากเคส #{ticket['id']}\nตอบกลับโดยกด Reply ใต้ข้อความที่คัดลอกด้านล่างได้เลย",
    )
    map_admin_message(ticket["id"], header.message_id)

    copied = await bot.copy_message(
        chat_id=admin_group_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    map_admin_message(ticket["id"], copied.message_id)

@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def relay_admin_replies(message: Message, bot: Bot):
    admin_group_id = get_admin_group_id()
    if not admin_group_id or message.chat.id != admin_group_id:
        return
    if not message.from_user or message.from_user.is_bot:
        return
    if not message.reply_to_message:
        return
    if (message.text or "").startswith("/"):
        return

    ticket_id = find_ticket_id_by_admin_message(message.reply_to_message.message_id)
    if not ticket_id:
        return

    ticket = get_ticket(ticket_id)
    if not ticket:
        return

    if ticket["status"] == "CLOSED":
        await message.reply(f"เคส #{ticket_id} ปิดแล้ว")
        return

    if ticket["status"] != "HUMAN":
        update_ticket_status(ticket_id, "HUMAN", message.from_user.id)
        await refresh_ticket_card(bot, ticket_id)
        await bot.send_message(
            ticket["user_id"],
            f"แอดมินเข้ารับเคส #{ticket_id} แล้วครับ\nพิมพ์ข้อความต่อในห้องนี้ได้เลย",
        )

    await bot.copy_message(
        chat_id=ticket["user_id"],
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )

async def on_startup(bot: Bot):
    init_db()
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="เริ่มต้นใช้งาน"),
                BotCommand(command="news", description="ข่าวล่าสุด"),
                BotCommand(command="promo", description="โปรโมชั่น"),
                BotCommand(command="support", description="ติดต่อแอดมิน"),
                BotCommand(command="faq", description="คำถามที่พบบ่อย"),
            ]
        )
    except Exception as e:
        logging.warning(f"set_my_commands ข้ามไปก่อน: {e}")

    logging.info("Bot is ready")

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await on_startup(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
