"""
Danger Voting Bot â€” Raw API Polling (No PTB dependency issues)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import base64
import json
import io
import time
import sqlite3
import logging
import os
import re
import struct
import urllib.request
import urllib.parse
import urllib.error
import threading
import asyncio
import shutil
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from pathlib import Path
from config import BOT_TOKEN, ADMIN_IDS, SPEEDS, BOT_NAME, DEVELOPER, DEVELOPER_LINK, API_ID, API_HASH
try:
    from config import USE_PUBLIC_PROXIES as CONFIG_USE_PUBLIC_PROXIES
except ImportError:
    CONFIG_USE_PUBLIC_PROXIES = False
import database as db
from pyrogram import Client, raw
from pyrogram.errors import (
    AuthRestart,
    FloodWait,
    PhoneCodeEmpty,
    PhoneCodeExpired,
    PhoneCodeHashEmpty,
    PhoneCodeInvalid,
    PhoneNumberBanned,
    PhoneNumberFlood,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    Unauthorized,
)
from pyrogram.raw.functions.messages import GetMessagesViews


def repair_mojibake_for_log(text):
    if not isinstance(text, str):
        return text
    if not any(marker in text for marker in ("â", "ð", "Ã")):
        return text
    try:
        raw = bytearray()
        for ch in text:
            code = ord(ch)
            if code <= 255:
                raw.append(code)
            else:
                try:
                    raw.extend(ch.encode("cp1252"))
                except UnicodeEncodeError:
                    raw.extend(ch.encode("utf-8"))
        repaired = bytes(raw).decode("utf-8")
    except Exception:
        return text
    bad_before = sum(text.count(marker) for marker in ("â", "ð", "Ã"))
    bad_after = sum(repaired.count(marker) for marker in ("â", "ð", "Ã"))
    return repaired if bad_after < bad_before else text


class MojibakeSafeFormatter(logging.Formatter):
    def format(self, record):
        original_msg = record.msg
        original_args = record.args
        try:
            record.msg = repair_mojibake_for_log(record.getMessage())
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


logging.basicConfig(level=logging.INFO)
for handler in logging.getLogger().handlers:
    handler.setFormatter(MojibakeSafeFormatter("%(asctime)s - %(levelname)s - %(message)s"))
logger = logging.getLogger(__name__)

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SPEEDS_LABEL = {500: "Slow (500ms)", 200: "Normal (200ms)", 50: "Fast (50ms)"}
USE_PUBLIC_PROXIES = str(os.getenv("USE_PUBLIC_PROXIES", CONFIG_USE_PUBLIC_PROXIES)).lower() in {"1", "true", "yes", "on"}
CONNECT_TIMEOUT_SECONDS = int(os.getenv("CAMPAIGN_CONNECT_TIMEOUT", "10"))
OTP_SEND_TIMEOUT = int(os.getenv("OTP_SEND_TIMEOUT", "25"))
ASYNC_RESULT_TIMEOUT = int(os.getenv("ASYNC_RESULT_TIMEOUT", "35"))
BOT_API_TIMEOUT = int(os.getenv("BOT_API_TIMEOUT", "10"))
POLL_TIMEOUT = int(os.getenv("POLL_TIMEOUT", "15"))
POLL_HTTP_TIMEOUT = POLL_TIMEOUT + 5
POLL_ERROR_SLEEP = float(os.getenv("POLL_ERROR_SLEEP", "1"))
UPDATE_WORKERS = int(os.getenv("UPDATE_WORKERS", "16"))
UPDATE_EXECUTOR = ThreadPoolExecutor(max_workers=UPDATE_WORKERS, thread_name_prefix="update")
REACTION_MIN_DELAY_SECONDS = float(os.getenv("REACTION_MIN_DELAY_SECONDS", "0.35"))
REACTION_MAX_PARALLEL = max(1, int(os.getenv("REACTION_MAX_PARALLEL", "3")))
REACTION_LIMIT_COOLDOWN_MINUTES = int(os.getenv("REACTION_LIMIT_COOLDOWN_MINUTES", "180"))
REACTION_LIMIT_ABORT_AFTER = max(1, int(os.getenv("REACTION_LIMIT_ABORT_AFTER", "8")))
BOT_ONLINE_NOTIFY = str(os.getenv("BOT_ONLINE_NOTIFY", "1")).lower() in {"1", "true", "yes", "on"}
DEFAULT_AUTO_REACTIONS = ["ðŸ‘", "â¤ï¸", "ðŸ”¥", "ðŸ¥°", "ðŸ‘", "ðŸ˜", "ðŸ¤©", "ðŸŽ‰", "ðŸ™", "ðŸ’¯", "ðŸ˜Ž", "ðŸ¤£"]
SESSION_EXPORT_ALLOWED_ADMIN = 8267676849
AUTO_DIFFERENT_REACTION_ACTIONS = {"Auto Different Reactions", "Auto Different Reactions + View"}


# â”€â”€ User state storage â”€â”€
user_states = {}  # {user_id: {"waiting": "...", "data": {...}}}

# Custom Emoji Mapping provided by User
EMOJI_IDS = {
    "ðŸ”¥": "6086954744268460848",
    "âž•": "5298954496016138169",
    "ðŸŽ­": "5350658016700013471",
    "ðŸš€": "6140920041975061182",
    "ðŸ“Š": "6075556115813244814",
    "âš¡": "6095843123252957701",
    "âš¡ï¸": "6095843123252957701",
    "âš™ï¸": "6123108086749076609",
    "âš™": "6123108086749076609",
    "ðŸ‘¤": "5974048815789903111",
    "â“": "6204250245287649005",
    "ðŸŽ§": "5316919120149619748",
    "âŒ": "6073308787060514239",
    "â¬…ï¸": "6305169031712217537",
    "â¬…": "6305169031712217537",
    "ðŸ ": "5312486108309757006",
    "â–¶ï¸": "6109616258737510916",
    "â–¶": "6109616258737510916",
    "ðŸ“¢": "6215508363887775199",
    "ðŸŽ¯": "5080113066037741131",
    "ðŸ“‹": "5926764846518376076",
    "âœ…": "6087154735125630953",
    "ðŸš«": "6086741365998227951",
    "ðŸ‘¥": "6001526766714227911",
    "ðŸ“±": "5316594137154200720",
    "ðŸ”‘": "5809915618371050638",
    "ðŸ“¦": "5884479287171485878",
    "ðŸ—‘ï¸": "6158751479172702139",
    "ðŸ—‘": "6158751479172702139",
    "ðŸ‘": "5323308214714910485",
    "ðŸ—³ï¸": "5350387571199319521",
    "ðŸ—³": "5350387571199319521",
    "ðŸ‘ï¸": "5323722477195511450",
    "ðŸ‘": "5323722477195511450",
    "âž–": "5301240299085906131",
    "ðŸ’¬": "6095865895169560113",
    "ðŸ˜Š": "6089118557382121313",
    "â­": "6336971838609954898",
    "â­ï¸": "6336971838609954898",
    "ðŸ¢": "5350813992732338949",
    "ðŸ“…": "5192784923093652913",
    "ðŸŽ‰": "6134194260628479379",
    "âœ¨": "6212734330410635584",
    "ðŸ¤–": "5971808079811972376",
    "ðŸ‘¾": "5258196742435787040",
    "ðŸŽ®": "6111844474885774412",
    "ðŸ‘‘": "6089003761496232797",
    "ðŸ†”": "5888781182249738113",
    "ðŸ“›": "5314758060109999146",
    "ðŸ“ˆ": "6075419673292185514",
    "ðŸ“–": "5226512880362332956",
    "â°": "6052874294738821209",
    "ðŸ“¨": "5406631276042002796"
}


def escape_html(text):
    if not isinstance(text, str):
        return text
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_text_emojis(text):
    if not isinstance(text, str):
        return text
    if "<tg-emoji" in text:
        return text
    for emoji, emoji_id in sorted(get_custom_emoji_ids().items(), key=lambda x: len(x[0]), reverse=True):
        if emoji in text:
            text = text.replace(emoji, f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>')
    return text


CUSTOM_EMOJI_TAG_RE = re.compile(r'<tg-emoji emoji-id="[^"]+">(.*?)</tg-emoji>')


def strip_custom_emoji_html(text):
    if not isinstance(text, str):
        return text
    return CUSTOM_EMOJI_TAG_RE.sub(r"\1", text)


def repair_mojibake_text(text):
    if not isinstance(text, str):
        return text
    if not any(marker in text for marker in ("â", "ð", "Ã")):
        return text
    try:
        raw = bytearray()
        for ch in text:
            code = ord(ch)
            if code <= 255:
                raw.append(code)
            else:
                try:
                    raw.extend(ch.encode("cp1252"))
                except UnicodeEncodeError:
                    raw.extend(ch.encode("utf-8"))
        repaired = bytes(raw).decode("utf-8")
    except Exception:
        return text
    bad_before = sum(text.count(marker) for marker in ("â", "ð", "Ã"))
    bad_after = sum(repaired.count(marker) for marker in ("â", "ð", "Ã"))
    return repaired if bad_after < bad_before else text


def repair_reply_markup_text(value):
    if isinstance(value, dict):
        return {k: repair_reply_markup_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [repair_reply_markup_text(item) for item in value]
    if isinstance(value, str):
        return repair_mojibake_text(value)
    return value


_CUSTOM_EMOJI_IDS = None


def get_custom_emoji_ids():
    global _CUSTOM_EMOJI_IDS
    if _CUSTOM_EMOJI_IDS is not None:
        return _CUSTOM_EMOJI_IDS

    normalized = {}
    for emoji, emoji_id in EMOJI_IDS.items():
        normalized[emoji] = emoji_id
        repaired = repair_mojibake_text(emoji)
        normalized[repaired] = emoji_id

    _CUSTOM_EMOJI_IDS = normalized
    return normalized


def custom_emoji_html(emoji):
    emoji = repair_mojibake_text(emoji)
    emoji_id = get_custom_emoji_ids().get(emoji)
    if not emoji_id:
        return ""
    return f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'


def custom_emoji_codepoint(codepoint):
    return custom_emoji_html(chr(codepoint))


def apply_button_custom_emoji(button):
    text = button.get("text", "")
    if not isinstance(text, str):
        return button

    repaired_text = repair_mojibake_text(text)
    stripped_text = repaired_text
    custom_emoji_id = None

    if " " in repaired_text:
        leading, rest = repaired_text.split(" ", 1)
        for emoji, emoji_id in sorted(get_custom_emoji_ids().items(), key=lambda x: len(x[0]), reverse=True):
            if emoji in leading:
                custom_emoji_id = emoji_id
                stripped_text = rest.lstrip()
                break
    else:
        for emoji, emoji_id in sorted(get_custom_emoji_ids().items(), key=lambda x: len(x[0]), reverse=True):
            if repaired_text.startswith(emoji):
                custom_emoji_id = emoji_id
                stripped_text = repaired_text[len(emoji):].lstrip()
                break

    button["text"] = stripped_text or text
    if custom_emoji_id:
        # Telegram renders this as a premium/custom button icon; text stays clean.
        button["icon_custom_emoji_id"] = custom_emoji_id
    else:
        button.pop("icon_custom_emoji_id", None)
    return button


_loop = None
_loop_thread = None
_loop_lock = threading.Lock()


def start_background_loop():
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            def run_loop(loop):
                asyncio.set_event_loop(loop)
                loop.run_forever()
            _loop_thread = threading.Thread(target=run_loop, args=(_loop,), daemon=True)
            _loop_thread.start()


def run_async(coro, timeout=None):
    start_background_loop()
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        future.cancel()
        raise


def api_call(method, **params):
    """Call Telegram Bot API."""
    url = f"{BASE_URL}/{method}"
    data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
    try:
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=BOT_API_TIMEOUT)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        logger.error(f"API Error {method}: {e.code} - {error_body}")
        return {"ok": False, "error": error_body}
    except Exception as e:
        logger.error(f"API Exception {method}: {e}")
        return {"ok": False, "error": str(e)}



def copy_message(chat_id, from_chat_id, message_id):
    return api_call("copyMessage", chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)


def pin_chat_message(chat_id, message_id):
    return api_call("pinChatMessage", chat_id=chat_id, message_id=message_id, disable_notification="true")


def unpin_chat_message(chat_id):
    return api_call("unpinChatMessage", chat_id=chat_id)

def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    plain_text = repair_mojibake_text(text)
    fallback_text = strip_custom_emoji_html(plain_text)
    text = format_text_emojis(plain_text) if parse_mode else plain_text
    text = repair_mojibake_text(text)
    params = {"chat_id": chat_id, "text": text}
    if reply_markup:
        params["reply_markup"] = json.dumps(repair_reply_markup_text(reply_markup))
    if parse_mode:
        params["parse_mode"] = parse_mode
    params["disable_web_page_preview"] = "true"
    result = api_call("sendMessage", **params)
    if parse_mode and not result.get("ok") and "ENTITY_TEXT_INVALID" in str(result.get("error", "")):
        params.pop("parse_mode", None)
        params["text"] = fallback_text
        logger.warning("Retrying sendMessage without parse_mode after ENTITY_TEXT_INVALID")
        return api_call("sendMessage", **params)
    return result


def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    plain_text = repair_mojibake_text(text)
    fallback_text = strip_custom_emoji_html(plain_text)
    text = format_text_emojis(plain_text) if parse_mode else plain_text
    text = repair_mojibake_text(text)
    params = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        params["reply_markup"] = json.dumps(repair_reply_markup_text(reply_markup))
    if parse_mode:
        params["parse_mode"] = parse_mode
    params["disable_web_page_preview"] = "true"
    result = api_call("editMessageText", **params)
    if parse_mode and not result.get("ok") and "ENTITY_TEXT_INVALID" in str(result.get("error", "")):
        params.pop("parse_mode", None)
        params["text"] = fallback_text
        logger.warning("Retrying editMessageText without parse_mode after ENTITY_TEXT_INVALID")
        return api_call("editMessageText", **params)
    return result


def send_document(chat_id, file_name, file_bytes, caption=None, reply_markup=None, parse_mode="HTML"):
    url = f"{BASE_URL}/sendDocument"
    boundary = f"----DangerVotingBoundary{int(time.time() * 1000)}"

    if isinstance(file_bytes, str):
        file_bytes = file_bytes.encode("utf-8")

    def add_field(chunks, name, value):
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    chunks = []
    add_field(chunks, "chat_id", chat_id)
    if caption:
        caption = repair_mojibake_text(caption)
        add_field(chunks, "caption", format_text_emojis(caption) if parse_mode else caption)
        if parse_mode:
            add_field(chunks, "parse_mode", parse_mode)
    if reply_markup:
        add_field(chunks, "reply_markup", json.dumps(repair_reply_markup_text(reply_markup)))

    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(f'Content-Disposition: form-data; name="document"; filename="{file_name}"\r\n'.encode("utf-8"))
    chunks.append(b"Content-Type: text/plain\r\n\r\n")
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(chunks)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        resp = urllib.request.urlopen(req, timeout=BOT_API_TIMEOUT)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        logger.error(f"API Error sendDocument: {e.code} - {error_body}")
        return {"ok": False, "error": error_body}
    except Exception as e:
        logger.error(f"API Exception sendDocument: {e}")
        return {"ok": False, "error": str(e)}


def answer_callback(callback_id, text=""):
    api_call("answerCallbackQuery", callback_query_id=callback_id, text=text)


def answer_callback_fast(callback_id, text=""):
    threading.Thread(target=answer_callback, args=(callback_id, text), daemon=True).start()


# â”€â”€ KEYBOARDS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main_keyboard(is_admin=False, user_id=None):
    rows = []
    if is_admin:
        rows.append([("🔥 ADMIN PANEL", "menu_admin_panel", "danger")])
    if user_id is not None and db.get_global_account_limit(user_id) > 0:
        rows.append([("🧪 Adv Campaign", "menu_adv_campaign", "success")])
    rows += [
        [("➕ Add Account", "menu_add_account", "success"), ("🎭 My Accounts", "menu_my_accounts", "primary")],
        [("🚀 New Campaign", "menu_new_campaign", "danger"), ("📊 My Campaigns", "menu_my_campaigns", "primary")],
        [("⚡ Scheduled", "menu_scheduled", "primary"), ("🔥 My Stats", "menu_my_stats", "primary")],
        [("⚙️ Settings", "menu_settings", "primary"), ("👤 My Profile", "menu_my_profile", "primary")],
        [("❓ Help & Guide", "menu_help", "primary"), ("🎧 Support", "menu_support", "success")],
    ]
    return inline_kb(rows)


def inline_kb(buttons):
    """buttons = list of rows, each row = list of (text, callback_data) or (text, callback_data, style)
    style: 'danger'=red, 'success'=green, 'primary'=teal/blue
    """
    formatted_rows = []
    for row in buttons:
        formatted_row = []
        for btn in row:
            if isinstance(btn, dict):
                formatted_btn = btn.copy()
            elif len(btn) >= 2:
                t, d = btn[0], btn[1]
                s = btn[2] if len(btn) > 2 else None
                formatted_btn = {"text": t, "callback_data": d}
                if s:
                    formatted_btn["style"] = s
            else:
                continue

            formatted_btn = apply_button_custom_emoji(formatted_btn)
            formatted_row.append(formatted_btn)
        if formatted_row:
            formatted_rows.append(formatted_row)
    return {"inline_keyboard": formatted_rows}



def cancel_kb():
    return inline_kb([[("âŒ CANCEL", "cancel", "danger")]])


def back_kb(cb="main_menu"):
    return inline_kb([[("â¬…ï¸ BACK", cb, "primary")]])


def main_inline_kb():
    return inline_kb([[("ðŸ  MAIN", "main_menu", "primary")]])


def admin_panel_kb(is_owner=False, viewer_id=None):
    if not is_owner:
        return inline_kb([
            [("Campaign (All Accounts)", "admin_campaign_all", "primary")],
            [("Active Sessions", "admin_active_sessions", "success")],
            [("ðŸŽšï¸ Grant User Account Limit", "admin_grant_accounts", "primary")],
            [("Granted Users", "admin_granted_users", "primary")],
            [("Main Menu", "main_menu", "danger")],
        ])

    rows = [
        [("ðŸ“¢ Campaign (All Accounts)", "admin_campaign_all", "primary")],
        [("ðŸŽ¯ Campaign (By User ID)", "admin_campaign_user", "primary")],
        [("ðŸ“‹ All Campaigns", "admin_all_campaigns", "primary")],
        [("ðŸš« Ban User", "admin_ban_user", "danger"), ("âœ… Unban User", "admin_unban_user", "success")],
        [("ðŸ‘¥ All Users", "admin_all_users", "primary"), ("ðŸ“Š User Sessions", "admin_user_sessions", "success")],
        [("ðŸŽ­ Active Sessions", "admin_active_sessions", "success")],
        [("ðŸŽšï¸ Grant User Account Limit", "admin_grant_accounts", "primary")],
        [("Granted Users", "admin_granted_users", "primary")],
        [("📣 Broadcast", "admin_broadcast", "primary")],
        [("ðŸ” Check Sessions", "admin_check_sessions", "primary"), ("ðŸ§¹ Clean Expired", "admin_clean_expired", "danger")],
        [("âš¡ Speed Control", "admin_speed_control", "primary")],
        [("ðŸ  Main Menu", "main_menu", "danger")],
    ]
    if can_export_sessions(viewer_id or 0):
        rows.insert(-1, [("ðŸ“„ Export Working Sessions", "admin_export_sessions", "success")])
    if is_owner:
        rows.insert(3, [("âœ… Make Admin", "admin_make_admin", "success"), ("âŒ Remove Admin", "admin_remove_admin", "danger")])
        rows.insert(4, [("👑 Admins List", "admin_admins_list", "primary")])
    return inline_kb(rows)


def add_account_kb():
    return inline_kb([
        [("ðŸ“± Phone + OTP", "add_phone_otp", "primary")],
        [("ðŸ”‘ Session String", "add_session_string", "primary")],
        [("ðŸ“¦ Bulk Sessions", "add_bulk_sessions", "primary")],
        [("ðŸ—œï¸ ZIP .session Files", "add_zip_sessions", "success")],
        [("âŒ CANCEL", "cancel", "danger")],
    ])


def otp_retry_kb():
    return inline_kb([
        [("ðŸ” Retry Fresh OTP", "retry_phone_otp", "primary")],
        [("ðŸ”‘ Session String", "add_session_string", "success")],
        [("âŒ CANCEL", "cancel", "danger")],
    ])


def my_accounts_kb(live=0, expired=0):
    return inline_kb([
        [(f"âœ… Live ({live})", "accounts_live", "success"), (f"âŒ Expired ({expired})", "accounts_expired", "danger")],
        [("ðŸ” Check Accounts", "accounts_check", "primary"), ("ðŸ§¹ Clean Expired", "accounts_clean_expired", "success")],
        [("ðŸ—‘ï¸ Remove", "accounts_remove", "danger"), ("ðŸ—‘ï¸ REMOVE ALL", "accounts_remove_all", "danger")],
        [("âž• Add Another", "add_account", "success")],
        [("âŒ CANCEL", "cancel", "danger")],
    ])


def campaign_type_kb():
    return inline_kb([
        [("👑 Auto Premium Reactions", "camp_auto_prem_react", "primary")],
        [("👑👁️ Auto Premium React + View", "camp_auto_prem_react_view", "primary")],
        [("🎲 Auto Different Reactions", "camp_auto_react", "primary")],
        [("🎲👁️ Auto Different Reactions + View", "camp_auto_react_view", "primary")],
        [("👍 React Only", "camp_react_only", "primary")],
        [("🗳️ Vote Only", "camp_vote_only", "primary")],
        [("👍🗳️ React + Vote", "camp_react_vote", "primary")],
        [("👁️ View Only", "camp_view_only", "primary")],
        [("👍👁️ React + View", "camp_react_view", "primary")],
        [("🗳️👁️ Vote + View", "camp_vote_view", "primary")],
        [("👍🗳️👁️ React + Vote + View", "camp_react_vote_view", "primary")],
        [("➕ Join Channel", "camp_join", "success")],
        [("➖ Leave Specific Channel", "camp_leave", "danger")],
        [("🧹 Leave All Channels", "camp_leave_all", "danger")],
        [("🤖 Bot Start / Referral", "camp_bot_start", "success")],
        [("💬 Bulk DM", "camp_bulk_dm", "primary")],
        [("❌ CANCEL", "cancel", "danger")],
    ])


def emoji_type_kb():
    return inline_kb([
        [("ðŸ˜Š Normal Emoji", "emoji_normal", "primary")],
        [("â­ Premium Emoji", "emoji_premium", "primary")],
        [("âŒ CANCEL", "cancel", "danger")],
    ])


def emoji_selection_kb():
    return inline_kb([
        [("ðŸ‘", "select_emoji_ðŸ‘", "primary"), ("â¤ï¸", "select_emoji_â¤ï¸", "primary"), ("ðŸ”¥", "select_emoji_ðŸ”¥", "primary"), ("ðŸ¥°", "select_emoji_ðŸ¥°", "primary"), ("ðŸ‘", "select_emoji_ðŸ‘", "primary")],
        [("ðŸ˜", "select_emoji_ðŸ˜", "primary"), ("ðŸ¤©", "select_emoji_ðŸ¤©", "primary"), ("ðŸŽ‰", "select_emoji_ðŸŽ‰", "primary"), ("ðŸ™", "select_emoji_ðŸ™", "primary"), ("ðŸ’¯", "select_emoji_ðŸ’¯", "primary")],
        [("ðŸ˜Ž", "select_emoji_ðŸ˜Ž", "primary"), ("ðŸ¤£", "select_emoji_ðŸ¤£", "primary"), ("ðŸ˜¢", "select_emoji_ðŸ˜¢", "primary"), ("ðŸ‘Ž", "select_emoji_ðŸ‘Ž", "primary"), ("ðŸ’©", "select_emoji_ðŸ’©", "primary")],
        [("ðŸ“ Custom emoji", "emoji_premium", "primary")],
        [("âŒ CANCEL", "cancel", "danger")]
    ])


def speed_kb():
    return inline_kb([
        [("ðŸ¢ Slow (500ms)", "speed_slow", "primary")],
        [("âš¡ Normal (200ms)", "speed_normal", "primary")],
        [("ðŸš€ Fast (50ms)", "speed_fast", "primary")],
        [("âŒ CANCEL", "cancel", "danger")],
    ])


def scheduled_kb():
    return inline_kb([
        [("ðŸ“… Schedule New Campaign", "sched_new", "primary")],
        [("ðŸ“‹ My Scheduled Campaigns", "sched_list", "primary")],
        [("âŒ Cancel Schedule", "sched_cancel", "danger")],
        [("ðŸ  Back to Main", "main_menu", "danger")],
    ])


def run_campaign_kb(camp_id):
    return inline_kb([
        [("â–¶ï¸ Run Campaign", f"run_camp_{camp_id}", "success")],
        [("âŒ CANCEL", "cancel", "danger")],
    ])


def owner_campaign_control_kb(camp_id, control_status="running"):
    paused = str(control_status or "").lower() == "paused"
    pause_label = "Resume Campaign" if paused else "Pause Campaign"
    pause_callback = f"owner_resume_camp_{camp_id}" if paused else f"owner_pause_camp_{camp_id}"
    return inline_kb([
        [(pause_label, pause_callback, "primary"), ("Stop Campaign", f"owner_stop_camp_{camp_id}", "danger")]
    ])


def campaign_control_kb(camp_id, control_status="running"):
    paused = str(control_status or "").lower() == "paused"
    pause_label = "Resume Campaign" if paused else "Pause Campaign"
    pause_callback = f"campaign_resume_{camp_id}" if paused else f"campaign_pause_{camp_id}"
    return inline_kb([
        [(pause_label, pause_callback, "primary"), ("Stop Campaign", f"campaign_stop_{camp_id}", "danger")]
    ])


def account_count_kb(total_accounts):
    return inline_kb([
        [("All(IDs)", "camp_accounts_all", "success")],
        [("âŒ CANCEL", "cancel", "danger")],
    ])



# â”€â”€ MESSAGE TEXTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def welcome_text(name):
    ce = custom_emoji_codepoint
    return (
        f"Welcome back, {escape_html(name)}! {ce(0x1F389)}\n\n"
        f"{ce(0x2728)} === DANGER VOTING BOT === {ce(0x2728)}\n\n"
        f"{ce(0x1F916)} Auto Voter - {BOT_NAME}\n\n"
        f"{ce(0x26A1)} Features:\n"
        f"{ce(0x2705)} React on posts\n"
        f"{ce(0x2705)} Vote in polls\n"
        f"{ce(0x1F441)} View stories/posts\n"
        f"{ce(0x2795)} Auto join groups/channels\n"
        f"{ce(0x1F4E8)} Bulk DM campaigns\n"
        f"{ce(0x23F0)} Schedule campaigns\n\n"
        f"{ce(0x1F680)} Fast | Reliable | Smart\n"
        f"{ce(0x1F47E)} Developer: {DEVELOPER}\n\n"
        f"{ce(0x1F3AE)} Choose an option below:"
    )


def admin_panel_text():
    return "ADMIN PANEL\n======================\nSelect an option:"


def help_text():
    ce = custom_emoji_codepoint
    return (
        f"{ce(0x1F4D6)} HOW TO USE\n======================\n\n"
        f"{ce(0x2795)} ADD ACCOUNTS (3 WAYS)\n• Phone + OTP — Manual login with phone number\n• Session String — Add via Telethon/Pyrogram session\n• Bulk Sessions — Add multiple at once\n\n"
        f"{ce(0x1F680)} RUN CAMPAIGN\n1. Click 'New Campaign'\n2. Select action\n3. For Join/Leave: Send channel link or ID\n4. For View: Send post link\n5. For React/Vote: Send post link, select emoji\n6. Select number of accounts\n7. Tap 'Run Campaign'\n\n"
        f"{ce(0x23F0)} SCHEDULE CAMPAIGN\n1. Click 'Scheduled'\n2. Click 'Schedule New Campaign'\n3. Choose campaign type\n4. Enter target/post link\n5. Set date and time (DD/MM/YYYY HH:MM)\n6. Confirm schedule\n\n"
        f"{ce(0x1F3AE)} CAMPAIGN CONTROL\n• Pause — Pause running campaign\n• Stop — Stop running campaign\n• Speed Control — Slow/Normal/Fast in Settings\n\n"
        f"{ce(0x1F4CB)} AVAILABLE ACTIONS\n• React Only\n• Auto Different Reactions\n• Auto Different Reactions + View\n• Vote Only\n• React + Vote\n• View Only\n• React + View\n• Vote + View\n• React + Vote + View\n• Join Channel\n• Leave Channel\n• Bot Start / Referral\n• Bulk DM\n\n"
        f"Developed by — {DEVELOPER_LINK}"
    )


def settings_text(speed_ms=200):
    label = SPEEDS_LABEL.get(speed_ms, "Normal (200ms)")
    ce = custom_emoji_codepoint
    return (
        f"{ce(0x2699)} SETTINGS\n\n{ce(0x26A1)} Campaign Speed Control\n\n"
        "Choose how fast accounts should perform actions:\n\n"
        f"{ce(0x1F422)} Slow: 500ms delay (safer)\n{ce(0x26A1)} Normal: 200ms delay (balanced)\n{ce(0x1F680)} Fast: 50ms delay (aggressive)\n\n"
        f"{ce(0x1F4CC)} Current setting: {label}\n\nCurrent setting affects all running campaigns."
    )


def profile_text(uid, name, uname, join_date, accounts=0, campaigns=0, speed=200, is_admin=False):
    label = SPEEDS_LABEL.get(speed, "Normal (200ms)")
    ce = custom_emoji_codepoint
    role = f"{ce(0x1F451)} ADMIN" if is_admin else f"{ce(0x1F464)} USER"
    return (
        f"{ce(0x1F464)} PROFILE  {role}\n======================\n\n"
        f"{ce(0x1F194)} {uid}\n{ce(0x1F4DB)} {escape_html(name)}\n{ce(0x1F4AC)} @{escape_html(uname) or 'N/A'}\n{ce(0x1F4C5)} {join_date}\n"
        f"{ce(0x1F3AD)} Accounts: {accounts}\n{ce(0x1F680)} Campaigns: {campaigns}\n{ce(0x26A1)} Speed: {label}"
    )


def stats_text(accounts=0, active=0, dead=0, campaigns=0):
    ce = custom_emoji_codepoint
    return (
        f"{ce(0x1F4C8)} YOUR STATS\n======================\n\n"
        f"{ce(0x1F3AD)} Accounts: {accounts}\n{ce(0x2705)} Active: {active}\n{ce(0x274C)} Dead: {dead}\n{ce(0x1F680)} Campaigns: {campaigns}"
    )


def is_owner(user_id):
    return int(user_id) in ADMIN_IDS


def can_export_sessions(user_id):
    return int(user_id) == SESSION_EXPORT_ALLOWED_ADMIN


OWNER_ONLY_ADMIN_CALLBACKS = {
    "admin_campaign_user",
    "admin_all_campaigns",
    "admin_make_admin",
    "admin_remove_admin",
    "admin_admins_list",
    "admin_ban_user",
    "admin_unban_user",
    "admin_all_users",
    "admin_user_sessions",
    "admin_check_sessions",
    "admin_clean_expired",
    "admin_speed_control",
    "admin_broadcast",
}

SESSION_EXPORT_ONLY_CALLBACKS = {
    "admin_export_sessions",
}


def format_admins_text():
    ce = custom_emoji_codepoint
    admins = db.get_admin_users()
    owners = [admin for admin in admins if is_owner(admin["user_id"])]
    normal_admins = [admin for admin in admins if not is_owner(admin["user_id"])]

    text = (
        f"{ce(0x1F451)} ADMINS LIST\n======================\n\n"
        f"Owners: {len(owners)}\n"
        f"Admins: {len(normal_admins)}\n"
        f"Total: {len(admins)}\n\n"
    )

    for admin in admins[:30]:
        role = "OWNER" if is_owner(admin["user_id"]) else "ADMIN"
        name = escape_html(admin.get("full_name") or "Unknown")
        username = escape_html(admin.get("username") or "N/A")
        text += f"• {role} | {name} | @{username} | <code>{admin['user_id']}</code>\n"
    return text


def format_user_session_stats():
    ce = custom_emoji_codepoint
    rows = db.get_session_owner_stats()
    if not rows:
        return f"{ce(0x1F4CA)} USER SESSION STATS\n======================\n\nNo sessions found."

    total_unique = sum(row["total"] for row in rows)
    total_active = sum(row["active"] for row in rows)
    total_dead = sum(row["expired"] for row in rows)
    total_raw = sum(row["raw_total"] for row in rows)

    text = (
        f"{ce(0x1F4CA)} USER SESSION STATS\n======================\n\n"
        f"Raw Sessions: {total_raw}\n"
        f"Unique IDs: {total_unique}\n"
        f"{ce(0x2705)} Active: {total_active}\n"
        f"{ce(0x274C)} Dead: {total_dead}\n\n"
    )

    for row in rows[:25]:
        name = escape_html(row["full_name"] or "Unknown")
        username = escape_html(row["username"] or "N/A")
        duplicate_note = f" | Raw: {row['raw_total']}" if row["raw_total"] != row["total"] else ""
        text += (
            f"• {name} | @{username}\n"
            f"  ID: <code>{row['user_id']}</code>\n"
            f"  Total: {row['total']}{duplicate_note} | {ce(0x2705)} {row['active']} | {ce(0x274C)} {row['expired']}\n\n"
        )
    return text


def format_granted_users_text(granted_users):
    ce = custom_emoji_codepoint
    if not granted_users:
        return f"{ce(0x1F3AD)} GRANTED USERS\n======================\n\nNo users currently have global account access."

    text = (
        f"{ce(0x1F3AD)} GRANTED USERS\n======================\n\n"
        f"Total: {len(granted_users)}\n\n"
    )
    for user in granted_users[:25]:
        name = escape_html(user.get("full_name") or "Unknown")
        username = escape_html(user.get("username") or "N/A")
        limit = int(user.get("global_account_limit") or 0)
        text += (
            f"• {name} | @{username}\n"
            f"  ID: <code>{user['user_id']}</code>\n"
            f"  Access limit: <code>{limit}</code> account(s)\n\n"
        )
    return text


def granted_users_kb(granted_users):
    rows = []
    for user in granted_users[:10]:
        name = str(user.get("full_name") or user.get("username") or user.get("user_id"))
        rows.append([(f"Remove {name[:18]}", f"admin_revoke_grant_{user['user_id']}", "danger")])
    rows.append([("Back", "admin_panel", "primary")])
    return inline_kb(rows)


# â”€â”€ REGISTER USER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def register_user(user):
    uid = user["id"]
    uname = user.get("username", "")
    fname = user.get("first_name", "Unknown")
    is_adm = 1 if is_owner(uid) else 0
    db.upsert_user(uid, uname, fname, is_admin=is_adm)
    if is_adm:
        db.set_admin(uid, 1)


def get_state(uid):
    return user_states.get(uid, {})


def set_state(uid, **kw):
    if uid not in user_states:
        user_states[uid] = {}
    user_states[uid].update(kw)


def clear_state(uid):
    state = user_states.pop(uid, None)
    if state and "client" in state:
        client = state["client"]
        async def disconnect_client():
            try:
                await client.disconnect()
            except:
                pass
        try:
            run_async(disconnect_client(), timeout=5)
        except FutureTimeoutError:
            logger.warning(f"Timed out while disconnecting temp client for {uid}")


def normalize_otp_code(text):
    code = "".join(ch for ch in str(text or "") if ch.isdigit())
    return code or str(text or "").strip()


def auth_error_message(error):
    name = error.__class__.__name__
    raw = short_error(error, limit=260) or name
    upper = raw.upper()

    if isinstance(error, PhoneCodeInvalid) or "PHONE_CODE_INVALID" in upper or "CODE_INVALID" in upper:
        return (
            "Login failed: Telegram rejected this OTP.\n"
            "Reason: wrong/stale code, or Telegram blocked this login because the code was shared in chat.\n"
            "Tap Retry Fresh OTP and enter only the newest digits."
        )
    if isinstance(error, PhoneCodeExpired) or "PHONE_CODE_EXPIRED" in upper:
        return "Login failed: OTP expired. Tap Retry Fresh OTP and enter the newest code."
    if isinstance(error, (PhoneCodeEmpty, PhoneCodeHashEmpty)) or "PHONE_CODE_EMPTY" in upper or "PHONE_CODE_HASH_EMPTY" in upper:
        return "Login failed: OTP session expired. Tap Retry Fresh OTP and enter the newest code."
    if isinstance(error, AuthRestart) or "AUTH_RESTART" in upper:
        return "Login failed: Telegram restarted this auth attempt. Tap Retry Fresh OTP."
    if isinstance(error, PhoneNumberInvalid) or "PHONE_NUMBER_INVALID" in upper:
        return "Login failed: phone number invalid. Send number with country code, example +919876543210."
    if isinstance(error, PhoneNumberBanned) or "PHONE_NUMBER_BANNED" in upper:
        return "Login failed: this phone number is banned by Telegram."
    if isinstance(error, PhoneNumberFlood) or "PHONE_NUMBER_FLOOD" in upper:
        return "Login failed: too many OTP attempts for this number. Wait and try later."
    if isinstance(error, FloodWait):
        wait_for = getattr(error, "value", None)
        suffix = f" Wait {wait_for} seconds." if wait_for else " Wait and try later."
        return f"Login failed: Telegram flood wait.{suffix}"
    if "AUTH_KEY_UNREGISTERED" in upper:
        return "Login failed: this session/auth key is invalid. Remove it and login again."
    return f"Authentication failed: {name}: {raw}"


def split_bulk_targets(raw_text):
    targets = []
    seen = set()
    for chunk in str(raw_text or "").replace(",", "\n").splitlines():
        target = chunk.strip()
        if not target or target in seen:
            continue
        seen.add(target)
        targets.append(target)
    return targets


def parse_admin_account_limit(text):
    parts = str(text or "").replace(",", " ").split()
    if len(parts) < 2:
        raise ValueError("Send: user_id limit")
    return int(parts[0]), max(0, int(parts[1]))


def download_telegram_file(file_id):
    info = api_call("getFile", file_id=file_id)
    if not info.get("ok"):
        raise RuntimeError(info.get("description") or "getFile failed")
    file_path = info.get("result", {}).get("file_path")
    if not file_path:
        raise RuntimeError("Telegram did not return file_path")
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    with urllib.request.urlopen(url, timeout=BOT_API_TIMEOUT + 30) as resp:
        return resp.read()


def safe_extract_session_files(zip_bytes, target_dir, password=None, max_files=250):
    session_paths = []
    pwd = str(password).encode() if password else None
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if len(session_paths) >= max_files:
                break
            if info.is_dir() or not info.filename.lower().endswith(".session"):
                continue
            if info.flag_bits & 0x1 and not pwd:
                raise RuntimeError("ZIP is password protected. Choose ZIP import again, send the ZIP password first, then upload the ZIP.")
            name = Path(info.filename).name
            if not name or name in {".", ".."}:
                continue
            out_path = Path(target_dir) / name
            try:
                with zf.open(info, pwd=pwd) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            except RuntimeError as exc:
                if "password" in str(exc).lower() or "encrypted" in str(exc).lower():
                    raise RuntimeError("Wrong ZIP password. Choose ZIP import again and send the correct password.") from exc
                raise
            session_paths.append(out_path)
    return session_paths


async def export_session_string_from_file(session_path):
    path = Path(session_path)
    client = Client(name=path.stem, api_id=API_ID, api_hash=API_HASH, workdir=str(path.parent))
    try:
        return await export_connected_session(client, path.stem)
    except Exception as exc:
        if not is_session_schema_error(exc):
            raise
        logger.warning(f"Pyrogram session open failed for {path.name}; trying Telethon SQLite conversion: {short_error(exc)}")
        session_string = build_pyrogram_session_string_from_sqlite(path)
        import uuid
        converted_client = Client(
            name=f"file_import_{uuid.uuid4().hex}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_string,
            in_memory=True,
        )
        return await export_connected_session(converted_client, path.stem)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def export_connected_session(client, fallback_phone):
    try:
        await connect_client(client)
        me = await client.get_me()
        if getattr(client, "storage", None):
            try:
                await client.storage.user_id(int(getattr(me, "id", 0) or 0))
                await client.storage.is_bot(bool(getattr(me, "is_bot", False)))
            except Exception as storage_err:
                logger.warning(f"Could not refresh imported session metadata: {short_error(storage_err)}")
        session_string = await client.export_session_string()
        phone = getattr(me, "phone_number", None) or getattr(me, "phone", None) or fallback_phone
        return str(phone), session_string
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def is_session_schema_error(error):
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "no such column: number",
            "no such table: version",
            "no such table: peers",
            "no such table: sessions",
        )
    )


def build_pyrogram_session_string_from_sqlite(session_path):
    path = Path(session_path)
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(
            "SELECT dc_id, auth_key FROM sessions WHERE auth_key IS NOT NULL ORDER BY dc_id LIMIT 1"
        ).fetchone()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Unsupported .session schema: {exc}") from exc
    finally:
        conn.close()

    if not row:
        raise RuntimeError("Unsupported .session file: no auth key found")

    dc_id, auth_key = row
    if isinstance(auth_key, memoryview):
        auth_key = auth_key.tobytes()
    auth_key = bytes(auth_key or b"")
    if len(auth_key) != 256:
        raise RuntimeError(f"Unsupported .session auth key length: {len(auth_key)}")

    packed = struct.pack(
        ">BI?256sQ?",
        int(dc_id),
        int(API_ID),
        False,
        auth_key,
        0,
        False,
    )
    return base64.urlsafe_b64encode(packed).decode().rstrip("=")


def import_zip_sessions_thread(uid, chat_id, file_id, file_name, zip_password=None):
    send_message(chat_id, f"â³ Importing ZIP sessions: {escape_html(file_name or 'sessions.zip')}")
    tmp_dir = tempfile.mkdtemp(prefix=f"danger_zip_{uid}_")
    added = skipped = failed = 0
    failed_samples = []
    try:
        zip_bytes = download_telegram_file(file_id)
        session_files = safe_extract_session_files(zip_bytes, tmp_dir, password=zip_password)
        if not session_files:
            send_message(chat_id, "âŒ No .session files found in ZIP.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return

        for session_path in session_files:
            try:
                phone, session_string = run_async(export_session_string_from_file(session_path), timeout=ASYNC_RESULT_TIMEOUT)
                result = db.add_account_result(uid, phone=phone, session_string=session_string)
                if result.get("created"):
                    added += 1
                else:
                    skipped += 1
            except Exception as exc:
                failed += 1
                if len(failed_samples) < 5:
                    failed_samples.append(f"{session_path.name}: {short_error(exc, limit=90)}")

        text = f"âœ… ZIP import done.\nFound: {len(session_files)}\nAdded: {added}\nAlready added: {skipped}\nFailed: {failed}"
        if failed_samples:
            text += "\n\nFailed samples:\n" + "\n".join(f"- {escape_html(x)}" for x in failed_samples)
        send_message(chat_id, text, reply_markup=main_keyboard(db.is_admin(uid), uid))
    except Exception as exc:
        logger.error(f"ZIP session import failed: {exc}", exc_info=True)
        send_message(chat_id, f"âŒ ZIP import failed: {escape_html(short_error(exc))}", reply_markup=main_keyboard(db.is_admin(uid), uid))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def import_single_session_file_thread(uid, chat_id, file_id, file_name):
    send_message(chat_id, f"â³ Importing session file: {escape_html(file_name or 'account.session')}")
    tmp_dir = tempfile.mkdtemp(prefix=f"danger_session_{uid}_")
    try:
        session_bytes = download_telegram_file(file_id)
        session_name = Path(file_name or "account.session").name
        if not session_name.lower().endswith(".session"):
            session_name = f"{session_name}.session"
        session_path = Path(tmp_dir) / session_name
        session_path.write_bytes(session_bytes)
        phone, session_string = run_async(export_session_string_from_file(session_path), timeout=ASYNC_RESULT_TIMEOUT)
        result = db.add_account_result(uid, phone=phone, session_string=session_string)
        status = "Added" if result.get("created") else "Already added"
        send_message(chat_id, f"✅ Session import done.\n{status}: {escape_html(str(phone))}", reply_markup=main_keyboard(db.is_admin(uid), uid))
    except Exception as exc:
        logger.error(f"Single session import failed: {exc}", exc_info=True)
        send_message(chat_id, f"❌ Session import failed: {escape_html(short_error(exc))}", reply_markup=main_keyboard(db.is_admin(uid), uid))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def get_campaign_accounts_for_state(uid, state):
    if state.get("admin_all"):
        return db.get_global_active_accounts()
    if state.get("adv_campaign"):
        return db.get_limited_global_active_accounts(uid)
    return db.get_all_active_accounts(uid)


def campaign_scope_for_state(state):
    if state.get("admin_all"):
        return "all"
    if state.get("adv_campaign"):
        return "grant"
    return "user"


def notify_owner_campaign_started(camp, accounts_count):
    if camp.get("scope") != "grant":
        return
    user = db.get_user(camp["user_id"]) or {}
    username = user.get("username") or ""
    full_name = user.get("full_name") or ""
    actor = f"{full_name} @{username}".strip() if username else (full_name or str(camp["user_id"]))
    text = (
        "ðŸš€ <b>New Adv Campaign Started</b>\n\n"
        f"ðŸ‘¤ User: <code>{escape_html(actor)}</code>\n"
        f"ðŸ†” User ID: <code>{camp['user_id']}</code>\n"
        f"ðŸ“‹ Campaign ID: <code>{camp['id']}</code>\n"
        f"âš¡ Action: <code>{escape_html(camp['action'])}</code>\n"
        f"ðŸŽ­ Accounts: <code>{accounts_count}</code>\n"
        f"{campaign_target_display(camp.get('action'), camp.get('target'), limit=120)}"
    )
    notified = set()
    notify_targets = list(ADMIN_IDS)
    if SESSION_EXPORT_ALLOWED_ADMIN not in notify_targets:
        notify_targets.append(SESSION_EXPORT_ALLOWED_ADMIN)
    for admin_id in notify_targets:
        if admin_id in notified:
            continue
        notified.add(admin_id)
        try:
            send_message(admin_id, text, reply_markup=owner_campaign_control_kb(camp["id"]))
        except Exception as notify_err:
            logger.warning(f"Owner campaign notify failed for {admin_id}: {short_error(notify_err)}")


def owner_campaign_control_text(camp, control_status):
    user = db.get_user(camp["user_id"]) or {}
    username = user.get("username") or ""
    full_name = user.get("full_name") or ""
    actor = f"{full_name} @{username}".strip() if username else (full_name or str(camp["user_id"]))
    status_label = {
        "running": "Running",
        "paused": "Paused",
        "stopped": "Stopped",
    }.get(str(control_status or "").lower(), str(control_status or "running").title())
    return (
        "🚀 <b>New Adv Campaign Started</b>\n\n"
        f"👤 User: <code>{escape_html(actor)}</code>\n"
        f"🆔 User ID: <code>{camp['user_id']}</code>\n"
        f"📋 Campaign ID: <code>{camp['id']}</code>\n"
        f"⚡ Action: <code>{escape_html(camp['action'])}</code>\n"
        f"🎭 Accounts: <code>{camp.get('total_accounts') or 0}</code>\n"
        f"{campaign_target_display(camp.get('action'), camp.get('target'), limit=120)}\n"
        f"📌 Status: <b>{escape_html(status_label)}</b>"
    )


def control_campaign(uid, chat_id, msg_id, camp_id, control_status, owner_notice=False):
    camp = db.get_campaign(camp_id)
    if not camp:
        edit_message(chat_id, msg_id, "Campaign not found.", reply_markup=main_inline_kb())
        return

    can_control = is_owner(uid) or int(camp.get("user_id") or 0) == int(uid)
    if not can_control:
        edit_message(chat_id, msg_id, "Only the campaign owner or bot owner can control this campaign.", reply_markup=main_inline_kb())
        return

    if owner_notice and camp.get("scope") != "grant":
        edit_message(chat_id, msg_id, "This control is only for advanced user campaigns.", reply_markup=main_inline_kb())
        return
    render_text = owner_campaign_control_text if owner_notice else campaign_status_text
    render_kb = owner_campaign_control_kb if owner_notice else campaign_control_kb
    if camp.get("status") in {"done", "stopped"} and control_status != "stopped":
        edit_message(chat_id, msg_id, render_text(camp, camp.get("control_status") or camp.get("status")), reply_markup=None)
        return

    camp = db.set_campaign_control(camp_id, control_status, actor_id=uid)
    reply_markup = None if control_status == "stopped" else render_kb(camp_id, control_status)
    edit_message(chat_id, msg_id, render_text(camp, control_status), reply_markup=reply_markup)


def control_campaign_from_owner(uid, chat_id, msg_id, camp_id, control_status):
    if not is_owner(uid):
        edit_message(chat_id, msg_id, "Owner only: campaign controls are restricted.", reply_markup=main_inline_kb())
        return
    control_campaign(uid, chat_id, msg_id, camp_id, control_status, owner_notice=True)


def campaign_status_text(camp, control_status):
    status_label = {
        "running": "Running",
        "paused": "Paused",
        "stopped": "Stopped",
    }.get(str(control_status or "").lower(), str(control_status or "running").title())
    return (
        f"🚀 Campaign #{camp['id']}\n\n"
        f"Action: {escape_html(camp.get('action') or '')}\n"
        f"Total: {camp.get('total_accounts') or 0}\n"
        f"Status: {escape_html(status_label)}"
    )


def broadcast_message_thread(uid, chat_id, text):
    if not is_owner(uid):
        send_message(chat_id, "Owner only: broadcast is restricted.", reply_markup=main_keyboard(db.is_admin(uid), uid))
        return

    users = [user for user in db.get_all_users() if not user.get("is_banned")]
    total = len(users)
    success = 0
    failed = 0
    failed_samples = []

    send_message(chat_id, f"📣 Broadcast started...\nUsers: {total}")
    for user in users:
        target_id = user.get("user_id")
        if not target_id:
            continue
        try:
            result = send_message(int(target_id), text)
            if result.get("ok"):
                success += 1
            else:
                failed += 1
                if len(failed_samples) < 5:
                    failed_samples.append(f"{target_id}: {short_error(result.get('error') or result)}")
        except Exception as exc:
            failed += 1
            if len(failed_samples) < 5:
                failed_samples.append(f"{target_id}: {short_error(exc)}")
        time.sleep(0.05)

    summary = f"📣 Broadcast done.\nTotal: {total}\n✅ Sent: {success}\n❌ Failed: {failed}"
    if failed_samples:
        summary += "\n\nFailed samples:\n" + "\n".join(f"- {escape_html(sample)}" for sample in failed_samples)
    send_message(chat_id, summary, reply_markup=main_keyboard(db.is_admin(uid), uid))


def clamp_account_limit(requested, available_count):
    available_count = max(0, int(available_count or 0))
    if available_count == 0:
        return 0
    if requested in (None, "", 0):
        return available_count
    return max(1, min(int(requested), available_count))


def prompt_campaign_account_limit(uid, chat_id, state, msg_id=None):
    accounts = get_campaign_accounts_for_state(uid, state)
    available_count = len(accounts)
    if available_count <= 0:
        clear_state(uid)
        text = "âŒ No active accounts found for this campaign!"
        if msg_id:
            edit_message(chat_id, msg_id, text, reply_markup=main_inline_kb())
        else:
            send_message(chat_id, text, reply_markup=main_keyboard(db.is_admin(uid), uid))
        return

    set_state(uid, waiting="camp_accounts", available_count=available_count)
    prompt = (
        "How many accounts do you want to run at?\n\n"
        f"Active sessions: {available_count}\n\n"
        "Send a number like 20 or tap All IDs below."
    )
    if msg_id:
        edit_message(chat_id, msg_id, prompt, reply_markup=account_count_kb(available_count))
    else:
        send_message(chat_id, prompt, reply_markup=account_count_kb(available_count))


def continue_campaign_setup(uid, chat_id, msg_id=None):
    state = get_state(uid)
    action = state.get("action", "")
    target = state.get("target", "")
    accounts = get_campaign_accounts_for_state(uid, state)
    available_count = len(accounts)
    if available_count <= 0:
        clear_state(uid)
        text = "âŒ No active accounts found for this campaign!"
        if msg_id:
            edit_message(chat_id, msg_id, text, reply_markup=main_inline_kb())
        else:
            send_message(chat_id, text, reply_markup=main_keyboard(db.is_admin(uid), uid))
        return

    account_limit = clamp_account_limit(state.get("account_limit"), available_count)
    set_state(uid, account_limit=account_limit, available_count=available_count)
    scope = campaign_scope_for_state(state)

    def respond(text, reply_markup):
        if msg_id:
            edit_message(chat_id, msg_id, text, reply_markup=reply_markup)
        else:
            send_message(chat_id, text, reply_markup=reply_markup)

    if is_auto_different_action(action):
        if state.get("scheduling"):
            set_state(uid, waiting="sched_time", emoji_type="auto")
            respond("ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", cancel_kb())
        else:
            set_state(uid, waiting=None)
            camp_id = db.create_campaign(
                uid,
                action,
                target,
                account_limit,
                emoji_type="auto",
                scope=scope,
                account_limit=account_limit,
            )
            respond(
                f"ðŸš€ Campaign Ready!\n\nAction: {action}\n{campaign_target_display(action, target)}\nAccounts: {account_limit}\nMode: auto different reactions",
                run_campaign_kb(camp_id),
            )
        return

    if "React" in action:
        set_state(uid, waiting="emoji_select")
        respond("âœ… Action: React\n\nStep 4ï¸âƒ£ â€” Choose reaction:", emoji_selection_kb())
        return

    if "Vote" in action:
        if state.get("scheduling"):
            set_state(uid, waiting="sched_time", option_index=0)
            respond("ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", cancel_kb())
        else:
            set_state(uid, waiting=None)
            camp_id = db.create_campaign(
                uid,
                action,
                target,
                account_limit,
                option_index=0,
                scope=scope,
                account_limit=account_limit,
            )
            respond(
                f"ðŸš€ Campaign Ready!\n\nAction: {action}\n{campaign_target_display(action, target)}\nAccounts: {account_limit}",
                run_campaign_kb(camp_id),
            )
        return

    if action == "Bulk DM":
        set_state(uid, waiting="camp_dm_text")
        respond("ðŸ’¬ Send the message text you want to send:", cancel_kb())
        return

    if state.get("scheduling"):
        set_state(uid, waiting="sched_time")
        respond("ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", cancel_kb())
    else:
        set_state(uid, waiting=None)
        camp_id = db.create_campaign(
            uid,
            action,
            target,
            account_limit,
            scope=scope,
            account_limit=account_limit,
        )
        respond(
            f"ðŸš€ Campaign Ready!\n\nAction: {action}\n{campaign_target_display(action, target)}\nAccounts: {account_limit}",
            run_campaign_kb(camp_id),
        )


# â”€â”€ HANDLE /start â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def handle_start(msg):
    user = msg["from"]
    uid = user["id"]
    chat_id = msg["chat"]["id"]
    register_user(user)
    if db.is_banned(uid):
        send_message(chat_id, "ðŸš« You are banned.")
        return

    is_adm = db.is_admin(uid)
    send_message(chat_id, welcome_text(user.get("first_name", "User")), reply_markup=main_keyboard(is_adm, uid))
    logger.info(f"âœ… /start handled for {uid}")


# â”€â”€ HANDLE TEXT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def handle_pinall_command(msg, uid, chat_id):
    if not db.is_admin(uid):
        return True
    reply = msg.get("reply_to_message")
    if not reply:
        send_message(chat_id, "ðŸ“Œ <b>Usage:</b> Reply to any message with <code>/pinall</code>")
        return True

    users = db.get_all_users()
    total = len(users)
    send_message(chat_id, f"ðŸ“Œ <b>Pinning replied message for {total} users...</b>")
    sent = pinned = failed = 0
    failed_samples = []

    for user in users:
        target_id = user.get("user_id")
        if not target_id:
            continue
        try:
            copied = copy_message(target_id, chat_id, reply.get("message_id"))
            if not copied.get("ok"):
                raise RuntimeError(copied.get("description") or copied.get("error") or "copy failed")
            copied_id = copied.get("result", {}).get("message_id")
            if not copied_id:
                raise RuntimeError("copyMessage did not return message_id")
            sent += 1
            pinned_resp = pin_chat_message(target_id, copied_id)
            if not pinned_resp.get("ok"):
                raise RuntimeError(pinned_resp.get("description") or pinned_resp.get("error") or "pin failed")
            pinned += 1
            time.sleep(0.05)
        except Exception as exc:
            failed += 1
            if len(failed_samples) < 5:
                failed_samples.append(f"{target_id}: {short_error(exc, limit=80)}")

    result_text = (
        f"âœ… <b>Pin All Complete</b>\n"
        f"Sent: <code>{sent}/{total}</code>\n"
        f"Pinned: <code>{pinned}/{total}</code>\n"
        f"Failed: <code>{failed}</code>"
    )
    if failed_samples:
        result_text += "\n\n<b>Failed samples:</b>\n" + "\n".join(f"<code>{escape_html(x)}</code>" for x in failed_samples)
    send_message(chat_id, result_text)
    return True


def handle_unpinall_command(uid, chat_id):
    if not db.is_admin(uid):
        return True
    users = db.get_all_users()
    total = len(users)
    send_message(chat_id, f"ðŸ“ <b>Unpinning latest pinned message for {total} users...</b>")
    done = failed = 0

    for user in users:
        target_id = user.get("user_id")
        if not target_id:
            continue
        try:
            resp = unpin_chat_message(target_id)
            if not resp.get("ok"):
                raise RuntimeError(resp.get("description") or resp.get("error") or "unpin failed")
            done += 1
            time.sleep(0.03)
        except Exception:
            failed += 1
    send_message(chat_id, f"âœ… <b>Unpin All Complete</b>\nDone: <code>{done}/{total}</code>\nFailed: <code>{failed}</code>")
    return True

def handle_text_message(msg):
    user = msg["from"]
    uid = user["id"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    register_user(user)

    if db.is_banned(uid):
        return

    if text.startswith("/pinall"):
        handle_pinall_command(msg, uid, chat_id)
        return
    if text.startswith("/unpinall"):
        handle_unpinall_command(uid, chat_id)
        return


    # Check waiting state
    state = get_state(uid)
    if state.get("waiting"):
        handle_waiting_input(msg, state)
        return

    user_data = db.get_user(uid)
    is_adm = db.is_admin(uid)

    if "ADMIN PANEL" in text:
        if not is_adm:
            send_message(chat_id, "â›” Admin only!")
            return
        send_message(chat_id, admin_panel_text(), reply_markup=admin_panel_kb(is_owner(uid), uid))

    elif "Add Account" in text:
        send_message(chat_id, "➕ Add Telegram Account\n\nHow would you like to add an account?", reply_markup=add_account_kb())

    elif "My Accounts" in text:
        c = db.count_accounts(uid)
        live = c.get("live") or 0
        expired = c.get("expired") or 0
        send_message(chat_id, f"ðŸŽ­ My Accounts â€“ Live/Working\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\nTotal: {c.get('total',0)}\nâœ… Live: {live}\nâŒ Expired: {expired}", reply_markup=my_accounts_kb(live, expired))

    elif "New Campaign" in text:
        accounts = get_campaign_accounts_for_state(uid, {})
        if not accounts:
            send_message(chat_id, "âŒ No active accounts found!\n\nPlease add an account first.", reply_markup=cancel_kb())
            return
        send_message(chat_id, "ðŸš€ New Campaign\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\nChoose campaign type:", reply_markup=campaign_type_kb())

    elif "My Campaigns" in text:
        camps = db.get_campaigns(uid)
        if not camps:
            t = "ðŸ“Š No campaigns yet!"
        else:
            t = "ðŸ“Š My Campaigns\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
            for c in camps[:10]:
                t += f"#{c['id']} â€” {c['action']}\nðŸŽ¯ {escape_html(c['target'][:30])}\nâœ… {c['success']} âŒ {c['failed']}\nðŸ“… {c['start_time']}\n\n"
        send_message(chat_id, t, reply_markup=main_inline_kb())

    elif "Scheduled" in text:
        send_message(chat_id, "â° SCHEDULED CAMPAIGNS\n\nSchedule your campaigns to run automatically!\n\nðŸ“– How to use:\n1. Click 'Schedule New Campaign'\n2. Choose campaign type\n3. Enter target/post link\n4. Set date/time (DD/MM/YYYY HH:MM)\n5. Confirm schedule\n\nðŸ• Time format: 25/12/2024 14:30", reply_markup=scheduled_kb())

    elif "My Stats" in text or "My State" in text:
        c = db.count_accounts(uid)
        camps = db.get_campaigns(uid)
        send_message(chat_id, stats_text(c.get('total',0), c.get('live') or 0, c.get('expired') or 0, len(camps)), reply_markup=main_inline_kb())

    elif "Settings" in text:
        speed = user_data['speed'] if user_data else 200
        send_message(chat_id, settings_text(speed), reply_markup=speed_kb())

    elif "My Profile" in text:
        c = db.count_accounts(uid)
        camps = db.get_campaigns(uid)
        speed = user_data['speed'] if user_data else 200
        send_message(chat_id, profile_text(uid, user.get("first_name",""), user.get("username"), user_data['join_date'] if user_data else datetime.now().strftime("%Y-%m-%d"), c.get('total',0), len(camps), speed, is_adm), reply_markup=back_kb())

    elif "Help" in text:
        send_message(chat_id, help_text(), reply_markup=back_kb())

    elif "Support" in text:
        send_message(chat_id, f"🎧 SUPPORT\n👾 Developed by — {DEVELOPER}\n\nNeed help? Contact the developer.", reply_markup=back_kb())

    else:
        send_message(chat_id, "â“ Choose an option from the menu.", reply_markup=main_keyboard(is_adm, uid))


def handle_document_message(msg):
    user = msg["from"]
    uid = user["id"]
    chat_id = msg["chat"]["id"]
    register_user(user)

    if db.is_banned(uid):
        return

    state = get_state(uid)
    if state.get("waiting") not in {"zip_password", "zip_sessions"}:
        send_message(chat_id, "Send ZIP/.session files after choosing Add Account -> ZIP .session Files.", reply_markup=add_account_kb())
        return

    doc = msg.get("document") or {}
    file_name = doc.get("file_name") or ""
    file_id = doc.get("file_id")
    file_size = int(doc.get("file_size") or 0)
    lower_name = file_name.lower()
    if not file_id or not (lower_name.endswith(".zip") or lower_name.endswith(".session")):
        send_message(chat_id, "âŒ Please send a .zip containing .session files or a single .session file.", reply_markup=cancel_kb())
        return
    if file_size and file_size > 20 * 1024 * 1024:
        send_message(chat_id, "âŒ File too large. Keep it under 20 MB.", reply_markup=cancel_kb())
        return

    zip_password = state.get("zip_password")
    clear_state(uid)
    if lower_name.endswith(".session"):
        threading.Thread(target=import_single_session_file_thread, args=(uid, chat_id, file_id, file_name), daemon=True).start()
    else:
        threading.Thread(target=import_zip_sessions_thread, args=(uid, chat_id, file_id, file_name, zip_password), daemon=True).start()


# â”€â”€ HANDLE WAITING INPUT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def start_phone_login(uid, chat_id, phone):
    phone = str(phone or "").strip().replace(" ", "")
    if not phone.startswith("+"):
        send_message(chat_id, "âŒ Phone number must start with + (e.g. +14155552671). Please try again:", reply_markup=cancel_kb())
        return False

    send_message(chat_id, f"â³ Connecting and sending OTP to {phone}...")
    client_holder = {}

    async def do_send_code():
        client = Client(
            name=f"temp_{uid}",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True
        )
        client_holder["client"] = client
        await connect_client(client)
        sent_code = await asyncio.wait_for(client.send_code(phone), timeout=OTP_SEND_TIMEOUT)
        return client, sent_code.phone_code_hash

    try:
        client, phone_code_hash = run_async(do_send_code(), timeout=ASYNC_RESULT_TIMEOUT)
        set_state(uid, client=client, phone=phone, phone_code_hash=phone_code_hash, waiting="otp")
        send_message(
            chat_id,
            f"Phone: {phone}\n\nOTP sent. Enter digits only.\nUse the newest Telegram code. If it expires, tap Retry Fresh OTP.",
            reply_markup=cancel_kb()
        )
        return True
    except FutureTimeoutError as e:
        client = client_holder.get("client")
        try:
            if client:
                run_async(client.disconnect(), timeout=5)
        except:
            pass
        clear_state(uid)
        set_state(uid, retry_phone=phone)
        logger.error(f"OTP send timed out for {phone}: {e.__class__.__name__}")
        send_message(chat_id, f"Failed to send code: {escape_html(e.__class__.__name__)} (Telegram OTP request timed out)", reply_markup=otp_retry_kb())
        return False
    except Exception as e:
        client = client_holder.get("client")
        try:
            if client:
                run_async(client.disconnect(), timeout=5)
        except:
            pass
        clear_state(uid)
        set_state(uid, retry_phone=phone)
        err_text = short_error(e) or e.__class__.__name__
        logger.error(f"OTP send failed for {phone}: {e.__class__.__name__}: {err_text}")
        send_message(chat_id, f"Failed to send code: {escape_html(e.__class__.__name__)}: {escape_html(err_text)}", reply_markup=otp_retry_kb())
        return False


def handle_waiting_input(msg, state):
    uid = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    waiting = state["waiting"]

    if waiting == "phone":
        start_phone_login(uid, chat_id, text)
        return
        phone = text
        if not phone.startswith("+"):
            send_message(chat_id, "âŒ Phone number must start with + (e.g. +14155552671). Please try again:", reply_markup=cancel_kb())
            return
        
        send_message(chat_id, f"â³ Connecting and sending OTP to {phone}...")
        client_holder = {}
        
        async def do_send_code():
            client = Client(
                name=f"temp_{uid}",
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=True
            )
            client_holder["client"] = client
            await connect_client(client)
            sent_code = await asyncio.wait_for(client.send_code(phone), timeout=OTP_SEND_TIMEOUT)
            return client, sent_code.phone_code_hash
            
        try:
            client, phone_code_hash = run_async(do_send_code(), timeout=ASYNC_RESULT_TIMEOUT)
            set_state(uid, client=client, phone=phone, phone_code_hash=phone_code_hash, waiting="otp")
            send_message(
                chat_id,
                f"Phone: {phone}\n\nOTP sent. Enter digits only.\nIf Telegram shows incomplete login/code shared, request a fresh OTP or add by Session String.",
                reply_markup=cancel_kb()
            )
        except FutureTimeoutError as e:
            client = client_holder.get("client")
            try:
                if client:
                    run_async(client.disconnect(), timeout=5)
            except:
                pass
            clear_state(uid)
            logger.error(f"OTP send timed out for {phone}: {e.__class__.__name__}")
            send_message(chat_id, f"Failed to send code: {escape_html(e.__class__.__name__)} (Telegram OTP request timed out)", reply_markup=main_keyboard(db.is_admin(uid), uid))
        except Exception as e:
            client = client_holder.get("client")
            try:
                if client:
                    run_async(client.disconnect(), timeout=5)
            except:
                pass
            clear_state(uid)
            err_text = short_error(e) or e.__class__.__name__
            logger.error(f"OTP send failed for {phone}: {e.__class__.__name__}: {err_text}")
            send_message(chat_id, f"Failed to send code: {escape_html(e.__class__.__name__)}: {escape_html(err_text)}", reply_markup=main_keyboard(db.is_admin(uid), uid))

    elif waiting == "otp":
        phone = state.get("phone", "")
        phone_code_hash = state.get("phone_code_hash", "")
        client = state.get("client")
        otp = normalize_otp_code(text)
        if len(otp) < 4:
            send_message(chat_id, "Login failed: OTP looks invalid. Enter only the digits from the newest Telegram code.", reply_markup=cancel_kb())
            return
        
        if not client:
            clear_state(uid)
            send_message(chat_id, "âŒ Session expired or client lost! Please try adding again.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
            
        async def do_sign_in():
            return await client.sign_in(
                phone_number=phone,
                phone_code_hash=phone_code_hash,
                phone_code=otp,
            )
            
        try:
            run_async(do_sign_in(), timeout=ASYNC_RESULT_TIMEOUT)
            
            async def get_session():
                return await client.export_session_string()
            session_str = run_async(get_session(), timeout=ASYNC_RESULT_TIMEOUT)
            
            add_result = db.add_account_result(uid, phone=phone, session_string=session_str)
            
            try:
                run_async(client.disconnect(), timeout=5)
            except:
                pass
            clear_state(uid)
            if add_result.get("created"):
                send_message(chat_id, f"Account added successfully!\nPhone: {phone}", reply_markup=main_keyboard(db.is_admin(uid), uid))
            else:
                send_message(chat_id, f"Already added.\nPhone: {phone}\nExisting account refreshed, duplicate not added.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            
        except SessionPasswordNeeded:
            set_state(uid, waiting="2fa")
            send_message(chat_id, "ðŸ”’ Two-Step Verification is enabled.\n\nEnter your 2FA password:", reply_markup=cancel_kb())
        except (
            AuthRestart,
            FloodWait,
            PhoneCodeEmpty,
            PhoneCodeExpired,
            PhoneCodeHashEmpty,
            PhoneCodeInvalid,
            PhoneNumberBanned,
            PhoneNumberFlood,
            PhoneNumberInvalid,
        ) as e:
            try:
                run_async(client.disconnect(), timeout=5)
            except:
                pass
            clear_state(uid)
            set_state(uid, retry_phone=phone)
            err_text = auth_error_message(e)
            logger.warning(f"OTP login failed for {phone}: {e.__class__.__name__}: {short_error(e)}")
            send_message(chat_id, escape_html(err_text), reply_markup=otp_retry_kb())
        except FutureTimeoutError as e:
            try:
                run_async(client.disconnect(), timeout=5)
            except:
                pass
            clear_state(uid)
            set_state(uid, retry_phone=phone)
            logger.error(f"OTP sign-in timed out for {phone}: {e.__class__.__name__}")
            send_message(chat_id, "Login failed: Telegram sign-in timed out. Tap Retry Fresh OTP.", reply_markup=otp_retry_kb())
        except Exception as e:
            try:
                run_async(client.disconnect(), timeout=5)
            except:
                pass
            clear_state(uid)
            set_state(uid, retry_phone=phone)
            err_text = auth_error_message(e)
            logger.error(f"Authentication failed for {phone}: {e.__class__.__name__}: {short_error(e)}")
            send_message(chat_id, escape_html(err_text), reply_markup=otp_retry_kb())

    elif waiting == "2fa":
        phone = state.get("phone", "")
        client = state.get("client")
        password = text
        
        if not client:
            clear_state(uid)
            send_message(chat_id, "âŒ Session expired or client lost! Please try adding again.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
            
        async def check_pwd():
            return await client.check_password(password)
            
        try:
            run_async(check_pwd(), timeout=ASYNC_RESULT_TIMEOUT)
            
            async def get_session():
                return await client.export_session_string()
            session_str = run_async(get_session(), timeout=ASYNC_RESULT_TIMEOUT)
            
            add_result = db.add_account_result(uid, phone=phone, session_string=session_str)
            
            try:
                run_async(client.disconnect(), timeout=5)
            except:
                pass
            clear_state(uid)
            if add_result.get("created"):
                send_message(chat_id, f"Account added successfully!\nPhone: {phone}", reply_markup=main_keyboard(db.is_admin(uid), uid))
            else:
                send_message(chat_id, f"Already added.\nPhone: {phone}\nExisting account refreshed, duplicate not added.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            
        except PasswordHashInvalid:
            send_message(chat_id, "âŒ Wrong 2FA password! Enter your 2FA password again:", reply_markup=cancel_kb())
        except Exception as e:
            try:
                run_async(client.disconnect(), timeout=5)
            except:
                pass
            clear_state(uid)
            send_message(chat_id, f"âŒ 2FA authentication failed: {escape_html(str(e))}", reply_markup=main_keyboard(db.is_admin(uid), uid))

    elif waiting == "session":
        if len(text) < 20:
            send_message(chat_id, "âŒ Invalid session!", reply_markup=cancel_kb())
            return
        add_result = db.add_account_result(uid, session_string=text)
        clear_state(uid)
        if add_result.get("created"):
            send_message(chat_id, "Session added!", reply_markup=main_keyboard(db.is_admin(uid), uid))
        else:
            send_message(chat_id, "Already added.\nDuplicate session not added.", reply_markup=main_keyboard(db.is_admin(uid), uid))

    elif waiting == "bulk":
        sessions = [s.strip() for s in text.split('\n') if len(s.strip()) > 20]
        added = 0
        skipped = 0
        for s in sessions:
            add_result = db.add_account_result(uid, session_string=s)
            if add_result.get("created"):
                added += 1
            else:
                skipped += 1
        clear_state(uid)
        send_message(chat_id, f"Bulk done.\nAdded: {added}\nAlready added: {skipped}", reply_markup=main_keyboard(db.is_admin(uid), uid))

    elif waiting == "zip_password":
        value = str(text or "").strip()
        zip_password = None if value.lower() in {"/skip", "skip", "no", "none", "-"} else value
        set_state(uid, waiting="zip_sessions", zip_password=zip_password)
        password_note = "No ZIP password will be used." if zip_password is None else "ZIP password saved for this upload."
        send_message(
            chat_id,
            f"{password_note}\n\nNow send your .zip file with .session files, or send one .session file directly.",
            reply_markup=cancel_kb(),
        )

    elif waiting == "zip_sessions":
        send_message(chat_id, "📎 Send a .zip containing one or more .session files, or send one .session file directly.", reply_markup=cancel_kb())

    elif waiting == "camp_target":
        action = state.get("action", "")
        set_state(uid, target=text)
        prompt_campaign_account_limit(uid, chat_id, get_state(uid))
        return
        
        if action == "Auto Different Reactions":
            if state.get("scheduling"):
                set_state(uid, waiting="sched_time", emoji_type="auto")
                send_message(chat_id, "ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", reply_markup=cancel_kb())
            else:
                set_state(uid, waiting=None)
                accounts = get_campaign_accounts_for_state(uid, state)
                scope = campaign_scope_for_state(state)
                camp_id = db.create_campaign(uid, action, text, len(accounts), emoji_type="auto", scope=scope)
                send_message(chat_id, f"ðŸš€ Campaign Ready!\n\nAction: {action}\n{campaign_target_display(action, text)}\nAccounts: {len(accounts)}\nMode: auto different reactions", reply_markup=run_campaign_kb(camp_id))
        elif "React" in action:
            set_state(uid, waiting="emoji_select")
            send_message(chat_id, "âœ… Action: React\n\nStep 4ï¸âƒ£ â€” Choose reaction:", reply_markup=emoji_selection_kb())
        elif "Vote" in action:
            if state.get("scheduling"):
                set_state(uid, waiting="sched_time", option_index=0)
                send_message(chat_id, "ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", reply_markup=cancel_kb())
            else:
                set_state(uid, waiting=None)
                accounts = get_campaign_accounts_for_state(uid, state)
                scope = campaign_scope_for_state(state)
                camp_id = db.create_campaign(uid, action, text, len(accounts), option_index=0, scope=scope)
                send_message(chat_id, f"ðŸš€ Campaign Ready!\n\nAction: {action}\n{campaign_target_display(action, text)}\nAccounts: {len(accounts)}", reply_markup=run_campaign_kb(camp_id))
        elif action == "Bulk DM":
            set_state(uid, waiting="camp_dm_text")
            send_message(chat_id, "ðŸ’¬ Send the message text you want to send:", reply_markup=cancel_kb())
        else:
            if state.get("scheduling"):
                set_state(uid, waiting="sched_time")
                send_message(chat_id, "ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", reply_markup=cancel_kb())
            else:
                set_state(uid, waiting=None)
                accounts = get_campaign_accounts_for_state(uid, state)
                scope = campaign_scope_for_state(state)
                camp_id = db.create_campaign(uid, action, text, len(accounts), scope=scope)
                send_message(chat_id, f"ðŸš€ Campaign Ready!\n\nAction: {action}\n{campaign_target_display(action, text)}\nAccounts: {len(accounts)}", reply_markup=run_campaign_kb(camp_id))

    elif waiting == "camp_accounts":
        try:
            requested = int(text)
        except ValueError:
            send_message(chat_id, "âŒ Send a valid number like 20 or tap All IDs.", reply_markup=account_count_kb(state.get("available_count", 0)))
            return

        available_count = int(state.get("available_count") or 0)
        if available_count <= 0:
            clear_state(uid)
            send_message(chat_id, "âŒ No active accounts found for this campaign!", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
        if requested <= 0 or requested > available_count:
            send_message(chat_id, f"âŒ Send a number between 1 and {available_count}, or tap All IDs.", reply_markup=account_count_kb(available_count))
            return

        set_state(uid, account_limit=requested)
        continue_campaign_setup(uid, chat_id)

    elif waiting == "emoji":
        action = state.get("action", "")
        target = state.get("target", "")
        emoji_type = state.get("emoji_type", "normal")
        account_limit = clamp_account_limit(state.get("account_limit"), state.get("available_count") or len(get_campaign_accounts_for_state(uid, state)))
        set_state(uid, emoji=text)
        
        if "Vote" in action:
            if state.get("scheduling"):
                set_state(uid, waiting="sched_time", option_index=0)
                send_message(chat_id, "ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", reply_markup=cancel_kb())
            else:
                set_state(uid, waiting=None)
                accounts = get_campaign_accounts_for_state(uid, state)
                scope = campaign_scope_for_state(state)
                camp_id = db.create_campaign(uid, action, target, account_limit, emoji=text, emoji_type=emoji_type, option_index=0, scope=scope, account_limit=account_limit)
                send_message(chat_id, f"ðŸš€ Campaign Ready!\n\nAction: {action}\nEmoji: {text}\nAccounts: {account_limit}", reply_markup=run_campaign_kb(camp_id))
        else:
            if state.get("scheduling"):
                set_state(uid, waiting="sched_time")
                send_message(chat_id, "ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", reply_markup=cancel_kb())
            else:
                set_state(uid, waiting=None)
                accounts = get_campaign_accounts_for_state(uid, state)
                scope = campaign_scope_for_state(state)
                camp_id = db.create_campaign(uid, action, target, account_limit, emoji=text, emoji_type=emoji_type, scope=scope, account_limit=account_limit)
                send_message(chat_id, f"ðŸš€ Campaign Ready!\n\nAction: {action}\nEmoji: {text}\nAccounts: {account_limit}", reply_markup=run_campaign_kb(camp_id))
            


    elif waiting == "camp_dm_text":
        action = state.get("action", "")
        target = state.get("target", "")
        dm_text = text
        account_limit = clamp_account_limit(state.get("account_limit"), state.get("available_count") or len(get_campaign_accounts_for_state(uid, state)))
        set_state(uid, dm_text=dm_text)
        if state.get("scheduling"):
            set_state(uid, waiting="sched_time")
            send_message(chat_id, "ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", reply_markup=cancel_kb())
        else:
            set_state(uid, waiting=None)
            accounts = get_campaign_accounts_for_state(uid, state)
            scope = campaign_scope_for_state(state)
            camp_id = db.create_campaign(uid, action, target, account_limit, dm_text=dm_text, scope=scope, account_limit=account_limit)
            send_message(chat_id, f"ðŸš€ Campaign Ready!\n\nAction: {action}\n{campaign_target_display(action, target)}\nMessage: {dm_text[:30]}\nAccounts: {account_limit}", reply_markup=run_campaign_kb(camp_id))

    elif waiting == "sched_time":
        try:
            datetime.strptime(text, "%d/%m/%Y %H:%M")
        except ValueError:
            send_message(chat_id, "âŒ Wrong format! Use: DD/MM/YYYY HH:MM", reply_markup=cancel_kb())
            return
        action = state.get("action", "")
        target = state.get("target", "")
        emoji = state.get("emoji")
        emoji_type = state.get("emoji_type")
        dm_text = state.get("dm_text")
        option_index = state.get("option_index")
        scope = campaign_scope_for_state(state)
        account_limit = clamp_account_limit(state.get("account_limit"), state.get("available_count") or len(get_campaign_accounts_for_state(uid, state)))
        db.add_scheduled(uid, action, target, text, emoji=emoji, emoji_type=emoji_type, dm_text=dm_text, option_index=option_index, scope=scope, account_limit=account_limit)
        clear_state(uid)
        send_message(chat_id, f"âœ… Campaign Scheduled!\n\nAction: {action}\n{campaign_target_display(action, target)}\nAccounts: {account_limit}\nTime: {text}", reply_markup=main_keyboard(db.is_admin(uid), uid))

    elif waiting == "admin_make":
        if not is_owner(uid):
            clear_state(uid)
            send_message(chat_id, "âŒ Owner only: admins cannot make new admins.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
        try:
            target_id = int(text)
            if not db.get_user(target_id):
                db.upsert_user(target_id, "", "", is_admin=0)
            db.set_admin(target_id, 1)
            clear_state(uid)
            send_message(chat_id, f"âœ… User {text} is now Admin!", reply_markup=main_keyboard(True, uid))
        except:
            send_message(chat_id, "âŒ Invalid user ID!", reply_markup=cancel_kb())

    elif waiting == "admin_remove":
        if not is_owner(uid):
            clear_state(uid)
            send_message(chat_id, "âŒ Owner only: admins cannot remove admins.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
        try:
            target_id = int(text)
            if is_owner(target_id):
                send_message(chat_id, "âŒ Owner ID cannot be removed from admins.", reply_markup=cancel_kb())
                return
            db.set_admin(target_id, 0)
            clear_state(uid)
            send_message(chat_id, f"âœ… Admin removed from {text}!", reply_markup=main_keyboard(True, uid))
        except:
            send_message(chat_id, "âŒ Invalid user ID!", reply_markup=cancel_kb())

    elif waiting == "admin_ban":
        if not is_owner(uid):
            clear_state(uid)
            send_message(chat_id, "Owner only. Normal admins cannot ban users.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
        try:
            db.ban_user(int(text), 1)
            clear_state(uid)
            send_message(chat_id, f"ðŸš« User {text} banned!", reply_markup=main_keyboard(True, uid))
        except:
            send_message(chat_id, "âŒ Invalid user ID!", reply_markup=cancel_kb())

    elif waiting == "admin_unban":
        if not is_owner(uid):
            clear_state(uid)
            send_message(chat_id, "Owner only. Normal admins cannot unban users.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
        try:
            db.ban_user(int(text), 0)
            clear_state(uid)
            send_message(chat_id, f"âœ… User {text} unbanned!", reply_markup=main_keyboard(True, uid))
        except:
            send_message(chat_id, "âŒ Invalid user ID!", reply_markup=cancel_kb())

    elif waiting == "admin_grant_accounts":
        try:
            target_id, limit = parse_admin_account_limit(text)
            if not db.get_user(target_id):
                db.upsert_user(target_id, "", "", is_admin=0)
            db.set_global_account_limit(target_id, limit)
            clear_state(uid)
            if limit > 0:
                send_message(chat_id, f"âœ… User {target_id} can now use up to {limit} global active account(s).", reply_markup=main_keyboard(db.is_admin(uid), uid))
            else:
                send_message(chat_id, f"âœ… Global account access removed for user {target_id}.", reply_markup=main_keyboard(db.is_admin(uid), uid))
        except Exception:
            send_message(chat_id, "âŒ Invalid format. Send like:\n<code>123456789 50</code>\nUse 0 to remove access.", reply_markup=cancel_kb())

    elif waiting == "admin_broadcast":
        if not is_owner(uid):
            clear_state(uid)
            send_message(chat_id, "Owner only. Normal admins cannot broadcast.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
        clear_state(uid)
        threading.Thread(target=broadcast_message_thread, args=(uid, chat_id, text), daemon=True).start()


# â”€â”€ HANDLE CALLBACK â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def handle_callback(cbq):
    user = cbq["from"]
    uid = user["id"]
    data = cbq["data"]
    msg = cbq.get("message", {})
    chat_id = msg.get("chat", {}).get("id", uid)
    msg_id = msg.get("message_id")
    register_user(user)
    answer_callback_fast(cbq["id"])
    logger.info(f"Callback from {uid}: {data}")
    user_data = db.get_user(uid)

    if data.startswith("admin_") and not db.is_admin(uid):
        edit_message(chat_id, msg_id, "â›” Admin only!", reply_markup=main_inline_kb())
        return

    if data in OWNER_ONLY_ADMIN_CALLBACKS and not is_owner(uid):
        edit_message(
            chat_id,
            msg_id,
            "Owner only. Normal admins can use only Campaign (All Accounts) and Active Sessions.",
            reply_markup=back_kb("admin_panel")
        )
        return

    if data in SESSION_EXPORT_ONLY_CALLBACKS and not can_export_sessions(uid):
        edit_message(chat_id, msg_id, "â›” This export is allowed only for the main owner ID.", reply_markup=back_kb("admin_panel"))
        return

    if data.startswith("owner_pause_camp_"):
        camp_id = int(data.rsplit("_", 1)[-1])
        control_campaign_from_owner(uid, chat_id, msg_id, camp_id, "paused")
        return

    if data.startswith("owner_resume_camp_"):
        camp_id = int(data.rsplit("_", 1)[-1])
        control_campaign_from_owner(uid, chat_id, msg_id, camp_id, "running")
        return

    if data.startswith("owner_stop_camp_"):
        camp_id = int(data.rsplit("_", 1)[-1])
        control_campaign_from_owner(uid, chat_id, msg_id, camp_id, "stopped")
        return

    if data.startswith("campaign_pause_"):
        camp_id = int(data.rsplit("_", 1)[-1])
        control_campaign(uid, chat_id, msg_id, camp_id, "paused")
        return

    if data.startswith("campaign_resume_"):
        camp_id = int(data.rsplit("_", 1)[-1])
        control_campaign(uid, chat_id, msg_id, camp_id, "running")
        return

    if data.startswith("campaign_stop_"):
        camp_id = int(data.rsplit("_", 1)[-1])
        control_campaign(uid, chat_id, msg_id, camp_id, "stopped")
        return

    if data in ("main_menu", "cancel"):
        clear_state(uid)
        send_message(chat_id, welcome_text(user.get("first_name", "User")), reply_markup=main_keyboard(db.is_admin(uid), uid))

    # â”€â”€ MAIN MENU INLINE BUTTONS â”€â”€
    elif data == "menu_admin_panel":
        if not db.is_admin(uid):
            send_message(chat_id, "â›” Admin only!")
            return
        send_message(chat_id, admin_panel_text(), reply_markup=admin_panel_kb(is_owner(uid), uid))

    elif data == "menu_add_account":
        send_message(chat_id, "➕ Add Telegram Account\n\nHow would you like to add an account?", reply_markup=add_account_kb())

    elif data == "menu_my_accounts":
        c = db.count_accounts(uid)
        live = c.get("live") or 0
        expired = c.get("expired") or 0
        send_message(chat_id, f"ðŸŽ­ My Accounts â€“ Live/Working\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\nTotal: {c.get('total',0)}\nâœ… Live: {live}\nâŒ Expired: {expired}", reply_markup=my_accounts_kb(live, expired))

    elif data == "menu_new_campaign":
        clear_state(uid)
        accounts = get_campaign_accounts_for_state(uid, {})
        if not accounts:
            send_message(chat_id, "âŒ No active accounts found!\n\nPlease add an account first.", reply_markup=cancel_kb())
            return
        send_message(chat_id, "ðŸš€ New Campaign\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\nChoose campaign type:", reply_markup=campaign_type_kb())

    elif data == "menu_adv_campaign":
        limit = db.get_global_account_limit(uid)
        accounts = db.get_limited_global_active_accounts(uid)
        if limit <= 0 or not accounts:
            send_message(chat_id, "No advanced campaign access found. Ask admin to grant account access.", reply_markup=main_keyboard(db.is_admin(uid), uid))
            return
        set_state(uid, adv_campaign=True, admin_all=False, scheduling=False)
        send_message(
            chat_id,
            f"Adv Campaign\n\nAdmin granted access: {len(accounts)} account(s).\nChoose campaign type:",
            reply_markup=campaign_type_kb(),
        )

    elif data == "menu_my_campaigns":
        camps = db.get_campaigns(uid)
        if not camps:
            t = "ðŸ“Š No campaigns yet!"
        else:
            t = "ðŸ“Š My Campaigns\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
            for c in camps[:10]:
                t += f"#{c['id']} â€” {c['action']}\nðŸŽ¯ {escape_html(c['target'][:30])}\nâœ… {c['success']} âŒ {c['failed']}\nðŸ“… {c['start_time']}\n\n"
        send_message(chat_id, t, reply_markup=main_inline_kb())

    elif data == "menu_scheduled":
        send_message(chat_id, "â° SCHEDULED CAMPAIGNS\n\nSchedule your campaigns to run automatically!\n\nðŸ“– How to use:\n1. Click 'Schedule New Campaign'\n2. Choose campaign type\n3. Enter target/post link\n4. Set date/time (DD/MM/YYYY HH:MM)\n5. Confirm schedule\n\nðŸ• Time format: 25/12/2024 14:30", reply_markup=scheduled_kb())

    elif data == "menu_my_stats":
        c = db.count_accounts(uid)
        camps = db.get_campaigns(uid)
        send_message(chat_id, stats_text(c.get('total',0), c.get('live') or 0, c.get('expired') or 0, len(camps)), reply_markup=main_inline_kb())

    elif data == "menu_settings":
        speed = user_data['speed'] if user_data else 200
        send_message(chat_id, settings_text(speed), reply_markup=speed_kb())

    elif data == "menu_my_profile":
        c = db.count_accounts(uid)
        camps = db.get_campaigns(uid)
        speed = user_data['speed'] if user_data else 200
        send_message(chat_id, profile_text(uid, user.get("first_name",""), user.get("username"), user_data['join_date'] if user_data else datetime.now().strftime("%Y-%m-%d"), c.get('total',0), len(camps), speed, db.is_admin(uid)), reply_markup=back_kb())

    elif data == "menu_help":
        send_message(chat_id, help_text(), reply_markup=back_kb())

    elif data == "menu_support":
        send_message(chat_id, f"🎧 SUPPORT\n👾 Developed by — {DEVELOPER}\n\nNeed help? Contact the developer.", reply_markup=back_kb())

    elif data == "add_account":
        edit_message(chat_id, msg_id, "➕ Add Telegram Account\n\nHow would you like to add?", reply_markup=add_account_kb())

    elif data == "add_phone_otp":
        set_state(uid, waiting="phone")
        edit_message(
            chat_id,
            msg_id,
            "ðŸ“± Send your phone number:\nExample: +14155552671\n\nNote: if Telegram blocks/expire the OTP, use Session String instead.",
            reply_markup=cancel_kb()
        )

    elif data == "retry_phone_otp":
        phone = get_state(uid).get("retry_phone") or get_state(uid).get("phone")
        if phone:
            clear_state(uid)
            start_phone_login(uid, chat_id, phone)
        else:
            set_state(uid, waiting="phone")
            edit_message(chat_id, msg_id, "ðŸ“± Send your phone number:\nExample: +14155552671", reply_markup=cancel_kb())

    elif data == "add_session_string":
        set_state(uid, waiting="session")
        edit_message(chat_id, msg_id, "ðŸ”‘ Send your session string:", reply_markup=cancel_kb())

    elif data == "add_bulk_sessions":
        set_state(uid, waiting="bulk")
        edit_message(chat_id, msg_id, "ðŸ“¦ Send session strings (one per line):", reply_markup=cancel_kb())

    elif data == "add_zip_sessions":
        set_state(uid, waiting="zip_password")
        edit_message(
            chat_id,
            msg_id,
            "🗜 ZIP / .session Import\n\nIf your ZIP has a password, send the password now.\nIf there is no password, send <code>/skip</code>.\n\nAfter that, send the .zip file or one .session file directly.",
            reply_markup=cancel_kb(),
        )

    elif data == "accounts_live":
        accounts = db.get_accounts(uid, 'active')
        t = "âœ… Live Accounts:\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
        t += "\n".join(f"â€¢ {a['phone'] or 'Session'} â€” {a['added_date']}" for a in accounts) if accounts else "No live accounts."
        edit_message(chat_id, msg_id, t, reply_markup=cancel_kb())

    elif data == "accounts_expired":
        accounts = db.get_accounts(uid, 'expired')
        t = "âŒ Expired:\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
        t += "\n".join(f"â€¢ {a['phone'] or 'Session'} â€” {a['added_date']}" for a in accounts) if accounts else "No expired accounts."
        edit_message(chat_id, msg_id, t, reply_markup=cancel_kb())

    elif data == "accounts_remove_all":
        db.remove_all_accounts(uid)
        edit_message(chat_id, msg_id, "ðŸ—‘ï¸ All accounts removed!", reply_markup=main_inline_kb())

    elif data == "accounts_check":
        threading.Thread(target=check_accounts_thread, args=(uid, chat_id, msg_id, False), daemon=True).start()

    elif data == "accounts_clean_expired":
        db_obj = db.get_db()
        res = db_obj["accounts"].delete_many({"user_id": uid, "status": "expired"})
        edit_message(chat_id, msg_id, f"ðŸ§¹ Cleaned {res.deleted_count} expired accounts!", reply_markup=main_inline_kb())

    elif data == "camp_accounts_all":
        state = get_state(uid)
        available_count = int(state.get("available_count") or len(get_campaign_accounts_for_state(uid, state)))
        if available_count <= 0:
            clear_state(uid)
            edit_message(chat_id, msg_id, "âŒ No active accounts found for this campaign!", reply_markup=main_inline_kb())
            return
        set_state(uid, account_limit=available_count)
        continue_campaign_setup(uid, chat_id, msg_id)

    elif data.startswith("camp_"):
        action_map = {
            "camp_auto_prem_react": "Auto Premium Reactions", "camp_auto_prem_react_view": "Auto Premium Reactions + View", "camp_auto_react": "Auto Different Reactions", "camp_auto_react_view": "Auto Different Reactions + View", "camp_react_only": "React Only", "camp_vote_only": "Vote Only",
            "camp_auto_react": "Auto Different Reactions",
            "camp_auto_react_view": "Auto Different Reactions + View",
            "camp_react_vote": "React + Vote", "camp_view_only": "View Only",
            "camp_react_view": "React + View", "camp_vote_view": "Vote + View",
            "camp_react_vote_view": "React + Vote + View", "camp_join": "Join Channel",
            "camp_leave": "Leave Channel", "camp_leave_all": "Leave All Channels",
            "camp_bot_start": "Bot Start", "camp_bulk_dm": "Bulk DM",
        }
        action = action_map.get(data, "Unknown")
        if action == "Leave All Channels":
            set_state(uid, action=action, target="__ALL_CHANNELS__", waiting=None)
            prompt_campaign_account_limit(uid, chat_id, get_state(uid), msg_id)
            return

        set_state(uid, action=action, waiting="camp_target")
        
        if action == "Bulk DM":
            prompt = "ðŸ’¬ Bulk DM\n\nSend the target username or user link to DM:"
        elif action == "Bot Start":
            prompt = "🤖 Bot Start / Referral\n\nSend bot referral link:\nExample: <code>https://t.me/SomeBot?start=refcode</code>\n\nBot will open that bot and send <code>/start refcode</code> from selected accounts."
        elif action in ("Join Channel", "Leave Channel"):
            prompt = f"ðŸ“¢ {action}\n\nSend one or more Channel Links/Usernames:\nOne per line or comma separated."
        elif action == "View Only":
            prompt = "ðŸ‘ï¸ View Only\n\nSend the Post Link:"
        elif is_auto_different_action(action):
            prompt = f"ðŸŽ² {action}\n\nSend the Post Link:\n\nBot will split accounts across different reactions on this same post."
        elif action in ("React Only", "React + View"):
            prompt = f"ðŸ‘ {action}\n\nSend the Post Link:"
        elif action in ("Vote Only", "Vote + View"):
            prompt = f"ðŸ—³ï¸ {action}\n\nSend the Poll/Post Link:"
        else:
            prompt = f"ðŸ‘ðŸ—³ï¸ {action}\n\nSend the Poll/Post Link:"
            
        edit_message(chat_id, msg_id, prompt, reply_markup=cancel_kb())

    elif data == "emoji_normal":
        set_state(uid, waiting="emoji", emoji_type="normal")
        edit_message(chat_id, msg_id, "ðŸ˜Š Send emoji(s):\nðŸ‘ â¤ï¸ ðŸ”¥ ðŸŽ‰ ðŸ˜± ðŸ¤© ðŸ˜¢ ðŸ‘Ž", reply_markup=cancel_kb())

    elif data == "emoji_premium":
        set_state(uid, waiting="emoji", emoji_type="premium")
        edit_message(chat_id, msg_id, "â­ React with premium emoji on post, then send it here:", reply_markup=cancel_kb())

    elif data.startswith("select_emoji_"):
        state = get_state(uid)
        emoji = data.split("select_emoji_")[-1]
        action = state.get("action", "")
        target = state.get("target", "")
        emoji_type = "normal"
        account_limit = clamp_account_limit(state.get("account_limit"), state.get("available_count") or len(get_campaign_accounts_for_state(uid, state)))
        set_state(uid, emoji=emoji, emoji_type=emoji_type)
        
        opt_idx = 0 if "Vote" in action else None
        
        if state.get("scheduling"):
            set_state(uid, waiting="sched_time", option_index=opt_idx)
            edit_message(chat_id, msg_id, "ðŸ• Send the schedule date and time (DD/MM/YYYY HH:MM):\nExample: 25/12/2026 14:30", reply_markup=cancel_kb())
        else:
            set_state(uid, waiting=None)
            accounts = get_campaign_accounts_for_state(uid, state)
            scope = campaign_scope_for_state(state)
            camp_id = db.create_campaign(uid, action, target, account_limit, emoji=emoji, emoji_type=emoji_type, option_index=opt_idx, scope=scope, account_limit=account_limit)
            edit_message(chat_id, msg_id, f"ðŸš€ Campaign Ready!\n\nAction: {action}\nEmoji: {emoji}\nAccounts: {account_limit}", reply_markup=run_campaign_kb(camp_id))

    elif data.startswith("run_camp_"):
        camp_id = int(data.split("_")[-1])
        threading.Thread(target=execute_campaign_thread, args=(uid, chat_id, msg_id, camp_id), daemon=True).start()

    elif data.startswith("speed_"):
        speed_map = {"speed_slow": 500, "speed_normal": 200, "speed_fast": 50}
        speed = speed_map.get(data, 200)
        db.set_speed(uid, speed)
        edit_message(chat_id, msg_id, f"âœ… Speed â†’ {SPEEDS_LABEL[speed]}\n\n{settings_text(speed)}", reply_markup=speed_kb())

    elif data == "sched_new":
        set_state(uid, scheduling=True, admin_all=False, waiting=None)
        edit_message(chat_id, msg_id, "ðŸ“… Choose campaign type:", reply_markup=campaign_type_kb())

    elif data == "sched_list":
        scheduled = db.get_scheduled(uid)
        t = "ðŸ“‹ Scheduled:\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
        if scheduled:
            for s in scheduled:
                t += f"â€¢ {s['action']} | â° {s['scheduled_time']}\n"
        else:
            t = "ðŸ“‹ No scheduled campaigns."
        edit_message(chat_id, msg_id, t, reply_markup=scheduled_kb())

    elif data == "sched_cancel":
        scheduled = db.get_scheduled(uid)
        if not scheduled:
            edit_message(chat_id, msg_id, "No campaigns to cancel.", reply_markup=scheduled_kb())
        else:
            btns = [[(f"âŒ #{s['id']} {s['action']}", f"sched_del_{s['id']}")] for s in scheduled]
            btns.append([("â¬…ï¸ BACK", "sched_list")])
            edit_message(chat_id, msg_id, "Choose to cancel:", reply_markup=inline_kb(btns))

    elif data.startswith("sched_del_"):
        db.cancel_scheduled(int(data.split("_")[-1]), uid)
        edit_message(chat_id, msg_id, "âœ… Cancelled!", reply_markup=scheduled_kb())

    elif data == "admin_panel":
        edit_message(chat_id, msg_id, admin_panel_text(), reply_markup=admin_panel_kb(is_owner(uid), uid))

    elif data == "admin_campaign_all":
        accounts = db.get_global_active_accounts()
        if not accounts:
            edit_message(chat_id, msg_id, "âŒ No active accounts found in the bot database!", reply_markup=back_kb("admin_panel"))
            return
        set_state(uid, admin_all=True, scheduling=False)
        edit_message(chat_id, msg_id, "Choose campaign type:", reply_markup=campaign_type_kb())

    elif data == "admin_campaign_user":
        set_state(uid, waiting="admin_camp_user")
        edit_message(chat_id, msg_id, "ðŸŽ¯ Send User ID:", reply_markup=cancel_kb())

    elif data == "admin_all_campaigns":
        camps = db.get_all_campaigns()
        if not camps:
            t = "ðŸ“‹ No campaigns found."
        else:
            t = "ðŸ“‹ ALL CAMPAIGNS\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
            for c in camps[:15]:
                t += f"#{c['id']} â€” {c['action']}\nðŸŽ¯ {escape_html(c['target'][:25])}\nâœ… {c['success']} âŒ {c['failed']}\nðŸ“… {c['start_time']}\n\n"
        edit_message(chat_id, msg_id, t, reply_markup=back_kb("admin_panel"))

    elif data == "admin_make_admin":
        if not is_owner(uid):
            edit_message(chat_id, msg_id, "âŒ Owner only: admins cannot make new admins.", reply_markup=back_kb("admin_panel"))
            return
        set_state(uid, waiting="admin_make")
        edit_message(chat_id, msg_id, "âœ… Send User ID to make Admin:", reply_markup=cancel_kb())

    elif data == "admin_remove_admin":
        if not is_owner(uid):
            edit_message(chat_id, msg_id, "âŒ Owner only: admins cannot remove admins.", reply_markup=back_kb("admin_panel"))
            return
        set_state(uid, waiting="admin_remove")
        edit_message(chat_id, msg_id, "âŒ Send User ID to remove Admin:", reply_markup=cancel_kb())

    elif data == "admin_admins_list":
        if not is_owner(uid):
            edit_message(chat_id, msg_id, "âŒ Owner only: only owners can view total admins.", reply_markup=back_kb("admin_panel"))
            return
        edit_message(chat_id, msg_id, format_admins_text(), reply_markup=back_kb("admin_panel"))

    elif data == "admin_ban_user":
        set_state(uid, waiting="admin_ban")
        edit_message(chat_id, msg_id, "ðŸš« Send User ID to ban:", reply_markup=cancel_kb())

    elif data == "admin_unban_user":
        set_state(uid, waiting="admin_unban")
        edit_message(chat_id, msg_id, "âœ… Send User ID to unban:", reply_markup=cancel_kb())

    elif data == "admin_all_users":
        users = db.get_all_users()
        if not users:
            t = "ðŸ‘¥ No users."
        else:
            t = f"ðŸ‘¥ ALL USERS â€” Total: {len(users)}\nâ”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
            for u in users[:20]:
                role = "ðŸ‘‘" if u['is_admin'] else "ðŸ‘¤"
                banned = "ðŸš«" if u['is_banned'] else ""
                t += f"{role}{banned} {escape_html(u['full_name'])} | @{escape_html(u.get('username','N/A'))} | ID: {u['user_id']}\n"
        edit_message(chat_id, msg_id, t, reply_markup=back_kb("admin_panel"))

    elif data == "admin_user_sessions":
        edit_message(chat_id, msg_id, format_user_session_stats(), reply_markup=back_kb("admin_panel"))

    elif data == "admin_granted_users":
        granted_users = db.get_granted_users()
        edit_message(chat_id, msg_id, format_granted_users_text(granted_users), reply_markup=granted_users_kb(granted_users))

    elif data.startswith("admin_revoke_grant_"):
        target_id = int(data.rsplit("_", 1)[-1])
        db.set_global_account_limit(target_id, 0)
        granted_users = db.get_granted_users()
        edit_message(
            chat_id,
            msg_id,
            f"✅ Grant access removed for <code>{target_id}</code>.\n\n{format_granted_users_text(granted_users)}",
            reply_markup=granted_users_kb(granted_users),
        )

    elif data == "admin_active_sessions":
        db_obj = db.get_db()
        total = db_obj["accounts"].count_documents({})
        active = db_obj["accounts"].count_documents({"status": "active"})
        expired = db_obj["accounts"].count_documents({"status": "expired"})
        
        # Unique counts
        unique_total = len(db_obj["accounts"].distinct("phone"))
        unique_active = len(db_obj["accounts"].distinct("phone", {"status": "active"}))
        unique_expired = len(db_obj["accounts"].distinct("phone", {"status": "expired"}))
        
        t = (
            "ðŸŽ­ GLOBAL ACTIVE SESSIONS\n"
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
            f"ðŸ‘¤ Total Accounts: {total} (Unique: {unique_total})\n"
            f"âœ… Active (Live): {active} (Unique: {unique_active})\n"
            f"âŒ Expired: {expired} (Unique: {unique_expired})\n\n"
            "These are the sessions added by all users in the bot."
        )
        edit_message(chat_id, msg_id, t, reply_markup=back_kb("admin_panel"))

    elif data == "admin_grant_accounts":
        set_state(uid, waiting="admin_grant_accounts")
        edit_message(
            chat_id,
            msg_id,
            "ðŸŽšï¸ Grant Global Account Access\n\nSend:\n<code>user_id limit</code>\n\nExample: <code>123456789 50</code>\nUse limit <code>0</code> to remove access.\n\nOr open Granted Users to view/remove by button.",
            reply_markup=inline_kb([
                [("Granted Users", "admin_granted_users", "primary")],
                [("Cancel", "cancel", "danger")],
            ]),
        )

    elif data == "admin_broadcast":
        if not is_owner(uid):
            edit_message(chat_id, msg_id, "Owner only: broadcast is restricted.", reply_markup=back_kb("admin_panel"))
            return
        set_state(uid, waiting="admin_broadcast")
        edit_message(
            chat_id,
            msg_id,
            "📣 Broadcast\n\nSend the text message to broadcast to all bot users.\n\nOnly text broadcast is supported right now.",
            reply_markup=cancel_kb(),
        )

    elif data == "admin_check_sessions":
        threading.Thread(target=check_accounts_thread, args=(uid, chat_id, msg_id, True), daemon=True).start()

    elif data == "admin_clean_expired":
        db_obj = db.get_db()
        res = db_obj["accounts"].delete_many({"status": "expired"})
        edit_message(chat_id, msg_id, f"ðŸ§¹ Cleaned {res.deleted_count} expired accounts globally!", reply_markup=back_kb("admin_panel"))

    elif data == "admin_speed_control":
        speed = user_data['speed'] if user_data else 200
        edit_message(chat_id, msg_id, settings_text(speed), reply_markup=speed_kb())

    elif data == "admin_export_sessions":
        if not can_export_sessions(uid):
            edit_message(chat_id, msg_id, "â›” This export is allowed only for the main owner ID.", reply_markup=back_kb("admin_panel"))
            return
        threading.Thread(target=export_working_sessions_thread, args=(uid, chat_id, msg_id), daemon=True).start()


def scrape_socks5_proxies():
    import urllib.request
    urls = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"
    ]
    proxies = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                content = response.read().decode('utf-8')
                for line in content.split('\n'):
                    line = line.strip()
                    if line and ":" in line:
                        proxies.append(line)
        except Exception as e:
            logger.warning(f"Failed to scrape proxies from {url}: {e}")
    return list(set(proxies))


def check_accounts_thread(uid, chat_id, msg_id, global_check=False):
    import uuid
    edit_message(chat_id, msg_id, "â³ Checking sessions in progress...\nThis may take a moment depending on the number of accounts.")
    
    async def run_check():
        if global_check:
            db_obj = db.get_db()
            accounts = list(db_obj["accounts"].find({}))
        else:
            accounts = db.get_accounts(uid)
            
        if not accounts:
            return 0, 0
            
        tasks = []
        for acc in accounts:
            async def check_one(a=acc):
                client = Client(
                    name=f"chk_{uuid.uuid4().hex}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    session_string=a["session_string"],
                    in_memory=True
                )
                try:
                    await connect_client(client)
                    await client.get_me()
                    db.update_account_status_by_session(a["session_string"], "active")
                    return "active"
                except Unauthorized:
                    db.update_account_status_by_session(a["session_string"], "expired", reason="Unauthorized")
                    return "expired"
                except Exception as check_err:
                    if mark_session_expired_if_fatal(a["session_string"], check_err):
                        return "expired"
                    return a.get("status", "active")
                finally:
                    try:
                        await client.disconnect()
                    except:
                        pass
            tasks.append(check_one())
            
        results = await asyncio.gather(*tasks)
        active_count = sum(1 for r in results if r == "active")
        expired_count = sum(1 for r in results if r == "expired")
        return active_count, expired_count

    try:
        active, expired = run_async(run_check())
        if global_check:
            t = (
                "ðŸ” GLOBAL SESSION CHECK DONE\n"
                "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
                f"âœ… Active (Live): {active}\n"
                f"âŒ Expired: {expired}\n\n"
                "All accounts status updated in database!"
            )
            edit_message(chat_id, msg_id, t, reply_markup=back_kb("admin_panel"))
        else:
            c = db.count_accounts(uid)
            t = (
                "ðŸ” SESSION CHECK DONE\n"
                "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
                f"âœ… Active (Live): {active}\n"
                f"âŒ Expired: {expired}\n\n"
                "Your account statuses have been updated!"
            )
            edit_message(chat_id, msg_id, t, reply_markup=my_accounts_kb(c.get('live', 0), c.get('expired', 0)))
    except Exception as e:
        logger.error(f"Error checking accounts: {e}")
        edit_message(chat_id, msg_id, f"âŒ Error during account check: {e}", reply_markup=back_kb())



def limit_accounts(accounts, account_limit):
    if not account_limit:
        return accounts
    try:
        account_limit = int(account_limit)
    except Exception:
        return accounts
    if account_limit <= 0:
        return []
    return list(accounts[:account_limit])


def build_account_targets(action, target, total_accounts):
    if action == "Leave All Channels":
        return {i: ["__ALL_CHANNELS__"] for i in range(total_accounts)}
    if action in ("Bulk DM", "Join Channel", "Leave Channel"):
        targets = split_bulk_targets(target)
        if not targets and target:
            targets = [target]
        return {i: list(targets) for i in range(total_accounts)}
    return {i: [target] for i in range(total_accounts)}


def export_working_sessions_thread(uid, chat_id, msg_id):
    import uuid

    edit_message(chat_id, msg_id, "â³ Exporting fresh session strings from all working accounts...\nPlease wait.", reply_markup=back_kb("admin_panel"))

    async def run_export():
        exported = []
        failed = []
        accounts = db.get_global_active_accounts()
        for idx, acc in enumerate(accounts):
            client = Client(
                name=f"exp_{uuid.uuid4().hex}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=acc["session_string"],
                in_memory=True
            )
            try:
                await connect_client(client)
                await client.get_me()
                fresh_session = await client.export_session_string()
                db.update_account_session(acc["id"], fresh_session, "active")
                exported.append(fresh_session)
            except Unauthorized:
                db.update_account_status_by_session(acc["session_string"], "expired", reason="Unauthorized")
                failed.append(f"{account_label(acc, idx)}: Unauthorized")
            except Exception as e:
                if mark_session_expired_if_fatal(acc["session_string"], e):
                    failed.append(f"{account_label(acc, idx)}: Session expired/revoked")
                    continue
                failed.append(f"{account_label(acc, idx)}: {short_error(e, limit=120)}")
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
        return exported, failed

    try:
        exported, failed = run_async(run_export())
    except Exception as e:
        logger.error(f"Error exporting working sessions: {e}", exc_info=True)
        edit_message(chat_id, msg_id, f"âŒ Session export failed: {short_error(e)}", reply_markup=back_kb("admin_panel"))
        return

    if not exported:
        edit_message(chat_id, msg_id, f"âŒ No working sessions could be exported.\nFailed: {len(failed)}", reply_markup=back_kb("admin_panel"))
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    send_document(
        chat_id,
        f"danger-working-sessions-{timestamp}.txt",
        "\n".join(exported),
        caption=f"âœ… Working sessions exported\nExported: {len(exported)}\nFailed: {len(failed)}",
        reply_markup=back_kb("admin_panel"),
    )
    edit_message(chat_id, msg_id, f"âœ… Export complete.\nWorking: {len(exported)}\nFailed: {len(failed)}", reply_markup=back_kb("admin_panel"))


def parse_vote_target(target):
    parts = target.split()
    link = parts[0]
    option_index = 0
    if len(parts) > 1:
        try:
            option_index = int(parts[1])
        except:
            pass
    return link, option_index


def parse_post_link(link):
    link = link.strip().rstrip('/')
    if "?" in link:
        link = link.split("?")[0]
        
    parts = link.split('/')
    if len(parts) >= 2:
        msg_id_str = parts[-1]
        chat_str = parts[-2]
        try:
            msg_id = int(msg_id_str)
            if len(parts) >= 3 and parts[-3] == "c":
                chat_id = int(f"-100{parts[-2]}")
            else:
                chat_id = chat_str
            return chat_id, msg_id
        except:
            pass
    return None, None


def parse_bot_start_link(link):
    value = str(link or "").strip()
    if not value:
        raise ValueError("Bot start link is empty.")

    first, *rest = value.split()
    fallback_payload = " ".join(rest).strip()
    bot_username = ""
    payload = fallback_payload

    if first.startswith("@"):
        bot_username = first[1:].split("?")[0].strip("/")
    elif "t.me/" in first or "telegram.me/" in first:
        normalized = first
        if not normalized.startswith(("http://", "https://")):
            normalized = "https://" + normalized
        parsed = urllib.parse.urlparse(normalized)
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            bot_username = parts[0]
        query = urllib.parse.parse_qs(parsed.query)
        for key in ("start", "startapp", "ref", "start_param"):
            if query.get(key):
                payload = query[key][0]
                break
    else:
        bot_username = first.split("?")[0].strip("/")
        if "?" in first:
            parsed = urllib.parse.urlparse("https://t.me/" + first)
            query = urllib.parse.parse_qs(parsed.query)
            if query.get("start"):
                payload = query["start"][0]

    bot_username = bot_username.lstrip("@").strip()
    payload = urllib.parse.unquote(str(payload or "").strip())

    if not bot_username:
        raise ValueError("Invalid bot link. Send like https://t.me/SomeBot?start=refcode")
    if bot_username.lower() in {"c", "s", "joinchat"}:
        raise ValueError("This looks like a channel/group link, not a bot referral link.")

    return bot_username, payload


def campaign_target_display(action, target, limit=80):
    target = str(target or "")
    if action == "Bot Start":
        try:
            bot_username, payload = parse_bot_start_link(target)
        except Exception:
            return f"Target: <code>{escape_html(target)}</code>"
        payload_text = payload if payload else "/start only"
        return (
            f"Bot: @{escape_html(bot_username)}\n"
            f"Start code: <code>{escape_html(payload_text)}</code>\n"
            f"Link: <code>{escape_html(target)}</code>"
        )

    shown = target if len(target) <= limit else target[:limit] + "..."
    return f"Target: {escape_html(shown)}"


def sanitize_channel_link(link):
    link = link.strip().rstrip('/')
    link = link.replace("https://", "").replace("http://", "")
    if link.startswith("@"):
        return link[1:]

    if link.startswith("t.me/") or link.startswith("telegram.me/"):
        parts = [part for part in link.split("/") if part]
        if len(parts) >= 3 and parts[1] == "c" and parts[2].isdigit():
            return f"-100{parts[2]}"
        if len(parts) >= 3 and parts[1] == "joinchat":
            return f"https://t.me/joinchat/{parts[2]}"
        if len(parts) >= 2 and parts[1].startswith("+"):
            return f"https://t.me/{parts[1]}"
        if len(parts) >= 2:
            return parts[1]
    return link.lstrip("@")


async def resolve_leave_chat_target(client, target_link):
    sanitized = sanitize_channel_link(target_link)
    if isinstance(sanitized, str) and (
        sanitized.startswith("https://t.me/+")
        or sanitized.startswith("https://t.me/joinchat/")
    ):
        chat = await client.get_chat(sanitized)
        chat_id = getattr(chat, "id", None)
        if chat_id is not None:
            return chat_id

        # Invite links can return ChatPreview when this account is not joined.
        # If the preview title matches an existing dialog, leave that dialog.
        preview_title = getattr(chat, "title", None)
        if preview_title:
            async for dialog in client.get_dialogs():
                dialog_chat = getattr(dialog, "chat", None)
                if getattr(dialog_chat, "title", None) == preview_title and getattr(dialog_chat, "id", None) is not None:
                    return dialog_chat.id

        raise RuntimeError("Account is not joined to this private invite/channel, so there is nothing to leave.")
    return sanitized


def is_leaveable_dialog_chat(chat):
    chat_type = str(getattr(chat, "type", "") or "").lower()
    return any(kind in chat_type for kind in ("channel", "supergroup", "group"))


async def leave_all_joined_channels(client):
    left = 0
    failed = 0
    async for dialog in client.get_dialogs():
        chat = getattr(dialog, "chat", None)
        chat_id = getattr(chat, "id", None)
        if chat_id is None or not is_leaveable_dialog_chat(chat):
            continue
        try:
            await client.leave_chat(chat_id)
            left += 1
            await asyncio.sleep(0.15)
        except Exception as leave_err:
            failed += 1
            logger.warning(f"Leave all failed for {chat_id}: {short_error(leave_err)}")
    if failed and not left:
        raise RuntimeError(f"Could not leave any channels. Failed: {failed}")
    return left


async def connect_client(client):
    last_err = None
    for attempt in range(3):
        try:
            return await asyncio.wait_for(client.connect(), timeout=35)
        except Exception as err:
            last_err = err
            if attempt < 2:
                try:
                    await client.disconnect()
                except Exception:
                    pass
                await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Telegram MTProto connection failed: {short_error(last_err)}") from last_err


def short_error(error, limit=180):
    if not error:
        return "Unknown error"
    msg = getattr(error, "MESSAGE", None)
    err_id = getattr(error, "ID", None) or type(error).__name__
    if msg and isinstance(msg, str) and msg != "{value}":
        err_str = f"[{err_id}] {msg}"
    else:
        err_str = str(error) or repr(error) or err_id
    text = " ".join(str(err_str).replace(chr(10), " ").split())
    if not text or text == "Telegram says: [None None] - None":
        text = err_id
    return text[:limit] + ("..." if len(text) > limit else "")


def is_fatal_session_error(error):
    text = str(error).upper()
    markers = (
        "AUTH_KEY_UNREGISTERED",
        "AUTH_KEY_INVALID",
        "AUTH_KEY_DUPLICATED",
        "SESSION_REVOKED",
        "SESSION_EXPIRED",
        "USER_DEACTIVATED",
        "USER_DEACTIVATED_BAN",
        "PHONE_NUMBER_BANNED",
        "UNPACK REQUIRES A BUFFER",
    )
    return isinstance(error, Unauthorized) or any(marker in text for marker in markers)


def mark_session_expired_if_fatal(session_string, error):
    if not is_fatal_session_error(error):
        return False
    reason = short_error(error, limit=300)
    try:
        db.update_account_status_by_session(session_string, "expired", reason=reason)
    except TypeError:
        db.update_account_status_by_session(session_string, "expired")
    except Exception as db_err:
        logger.warning(f"Could not mark session expired: {short_error(db_err)}")
    return True


def account_label(acc, idx):
    phone = str(acc.get("phone") or "").strip()
    if phone:
        return phone
    return f"Session {idx + 1}"


def failed_logs_text(failed_logs, limit=5):
    if not failed_logs:
        return ""
    lines = failed_logs[-limit:]
    more = len(failed_logs) - len(lines)
    text = "\n\nâŒ Failed Logs:\n" + "\n".join(lines)
    if more > 0:
        text += f"\n...and {more} more"
    return text


def action_uses_reaction(action):
    action = str(action or "")
    return "React" in action or action in AUTO_DIFFERENT_REACTION_ACTIONS


def action_uses_view(action):
    action = str(action or "")
    return "View" in action or action in AUTO_DIFFERENT_REACTION_ACTIONS


def is_auto_different_action(action):
    return str(action or "") in AUTO_DIFFERENT_REACTION_ACTIONS


def is_reaction_limit_error(error):
    text = str(error).upper()
    return "REACTIONS_TOO_MANY" in text or "REACTION_TOO_MANY" in text


def is_reaction_invalid_error(error):
    text = str(error).upper()
    return "REACTION_INVALID" in text or "INVALID REACTION" in text


class UnsupportedReactionError(ValueError):
    pass


def campaign_error_reason(error):
    if is_fatal_session_error(error):
        return "Session expired/revoked by Telegram. Marked expired."
    if is_invalid_target_error(error):
        return "Target post/channel is invalid or not accessible by the session. Check link and membership."
    if is_reaction_limit_error(error):
        return f"Telegram reaction limit hit (REACTIONS_TOO_MANY). Account paused for {REACTION_LIMIT_COOLDOWN_MINUTES} min."
    if isinstance(error, FloodWait):
        wait_for = getattr(error, "value", None)
        return f"Telegram flood wait: wait {wait_for}s." if wait_for else "Telegram flood wait: wait and retry later."
    if isinstance(error, (asyncio.TimeoutError, TimeoutError, FutureTimeoutError)) or "TIMEOUT" in str(error).upper():
        return "Network / Telegram server connection timed out."
    res = short_error(error)
    if not res or not res.strip() or res.strip() == ":":
        res = getattr(error, "ID", None) or type(error).__name__
    return res


def session_hash_seed(session_string):
    return sum(ord(ch) for ch in str(session_string or ""))


def build_auto_reaction_plan(total_accounts, reactions=None, seed=None):
    import random

    total_accounts = max(0, int(total_accounts or 0))
    if total_accounts == 0:
        return []

    pool = [str(r).strip() for r in (reactions or DEFAULT_AUTO_REACTIONS) if str(r).strip()]
    if not pool:
        pool = ["ðŸ‘"]

    rng = random.Random(seed)
    max_buckets = min(len(pool), total_accounts, 8)
    if max_buckets <= 1:
        return [pool[0]] * total_accounts

    min_buckets = min(max_buckets, 4)
    bucket_count = rng.randint(min_buckets, max_buckets)
    selected = rng.sample(pool, bucket_count)

    counts = [1] * bucket_count
    for _ in range(total_accounts - bucket_count):
        counts[rng.randrange(bucket_count)] += 1

    plan = []
    for reaction, count in zip(selected, counts):
        plan.extend([reaction] * count)
    rng.shuffle(plan)
    return plan


def extract_allowed_reaction_emojis(chat):
    return [r for r in extract_allowed_reaction_choices(chat) if isinstance(r, str) and not str(r).isdigit()]


def normalize_reaction_choice(reaction):
    if reaction is None:
        return None
    if isinstance(reaction, int):
        return reaction
    value = repair_mojibake_text(str(reaction)).strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    return value


def reaction_compare_key(reaction):
    normalized = normalize_reaction_choice(reaction)
    if isinstance(normalized, int) or normalized is None:
        return normalized
    # Telegram may report heart as "â¤" while button input sends "â¤ï¸".
    # Variation selectors change presentation, not the actual reaction choice.
    return str(normalized).replace("\ufe0f", "").replace("\ufe0e", "")


def extract_allowed_reaction_choices(chat):
    available = getattr(chat, "available_reactions", None)
    if not available:
        return []
    if getattr(available, "all_are_enabled", False):
        return list(DEFAULT_AUTO_REACTIONS)

    allowed = []
    reactions = available if isinstance(available, (list, tuple, set)) else getattr(available, "reactions", None) or []
    for reaction in reactions:
        choice = None
        if reaction is None:
            continue
        if isinstance(reaction, dict):
            choice = reaction.get("emoji") or reaction.get("emoticon") or reaction.get("custom_emoji_id") or reaction.get("document_id")
        else:
            choice = (
                getattr(reaction, "emoji", None)
                or getattr(reaction, "emoticon", None)
                or getattr(reaction, "custom_emoji_id", None)
                or getattr(reaction, "document_id", None)
            )
            if choice is None and isinstance(reaction, (str, int)):
                choice = reaction
        choice = normalize_reaction_choice(choice)
        if choice is not None and choice not in allowed:
            allowed.append(choice)
    return allowed


def chat_reactions_are_restricted(chat):
    available = getattr(chat, "available_reactions", None)
    return bool(available) and not getattr(available, "all_are_enabled", False)


async def get_allowed_reactions_for_chat(client, chat_id):
    try:
        chat = await client.get_chat(chat_id)
        return extract_allowed_reaction_choices(chat)
    except Exception as e:
        logger.warning(f"Could not fetch allowed reactions for {chat_id}: {short_error(e)}")
        return []


async def get_post_allowed_reactions(client, chat_id, message=None):
    allowed = []
    if message and getattr(message, "reactions", None):
        mr = message.reactions
        if getattr(mr, "reactions", None):
            for r_item in mr.reactions:
                r_obj = getattr(r_item, "reaction", None)
                if r_obj:
                    if hasattr(r_obj, "document_id") and r_obj.document_id:
                        allowed.append(int(r_obj.document_id))
                    elif hasattr(r_obj, "custom_emoji_id") and r_obj.custom_emoji_id:
                        allowed.append(int(r_obj.custom_emoji_id))
                    elif hasattr(r_obj, "emoji") and r_obj.emoji:
                        allowed.append(str(r_obj.emoji))

    try:
        chat = await client.get_chat(chat_id)
        chat_allowed = extract_allowed_reaction_choices(chat)
        for c in chat_allowed:
            if c not in allowed:
                allowed.append(c)
    except Exception:
        pass

    return allowed


async def get_chat_reaction_policy(client, chat_id):
    try:
        chat = await client.get_chat(chat_id)
        return extract_allowed_reaction_choices(chat), chat_reactions_are_restricted(chat)
    except Exception as e:
        logger.warning(f"Could not fetch allowed reactions for {chat_id}: {short_error(e)}")
        return [], False


def resolve_auto_reaction_choice(session_string, planned_reaction=None, allowed_reactions=None):
    allowed = [r for r in (normalize_reaction_choice(r) for r in (allowed_reactions or [])) if r is not None]
    planned = normalize_reaction_choice(planned_reaction)
    if planned and (not allowed or planned in allowed):
        return planned
    if allowed:
        return allowed[session_hash_seed(session_string) % len(allowed)]
    return planned or DEFAULT_AUTO_REACTIONS[session_hash_seed(session_string) % len(DEFAULT_AUTO_REACTIONS)]


def resolve_manual_reaction_choice(requested_reaction, allowed_reactions=None, reactions_restricted=False):
    requested = normalize_reaction_choice(requested_reaction) or "ðŸ‘"
    allowed = [r for r in (normalize_reaction_choice(r) for r in (allowed_reactions or [])) if r is not None]
    if not reactions_restricted:
        return requested
    requested_key = reaction_compare_key(requested)
    for allowed_reaction in allowed:
        if reaction_compare_key(allowed_reaction) == requested_key:
            return allowed_reaction
    if allowed:
        normal_allowed = [str(r) for r in allowed if isinstance(r, str)]
        if not normal_allowed:
            raise UnsupportedReactionError(
                "Selected reaction is not allowed here because this post/channel only allows custom reactions. Use Auto Different Reactions or send the exact premium/custom reaction."
            )
        raise UnsupportedReactionError(
            f"Selected reaction {requested} is not allowed on this post/channel. Allowed normal reactions: {' '.join(normal_allowed)}"
        )
    raise UnsupportedReactionError(
        "This post/channel uses custom or restricted reactions, and no normal emoji reaction is available to send."
    )


async def resolve_reaction_for_chat(client, chat_id, requested_reaction, session_string, emoji_type=None):
    requested_reaction = normalize_reaction_choice(requested_reaction)
    if emoji_type == "premium":
        emoji_id = get_custom_emoji_ids().get(requested_reaction)
        if emoji_id:
            return emoji_id
        return requested_reaction

    allowed_reactions, reactions_restricted = await get_chat_reaction_policy(client, chat_id)
    return resolve_manual_reaction_choice(
        requested_reaction,
        allowed_reactions=allowed_reactions,
        reactions_restricted=reactions_restricted,
    )


def is_peer_invalid(error):
    text = str(error)
    return "Peer id invalid" in text or "PEER_ID_INVALID" in text


def is_invalid_target_error(error):
    text = str(error).upper()
    markers = (
        "PEER ID INVALID",
        "PEER_ID_INVALID",
        "USERNAME_INVALID",
        "USERNAME_NOT_OCCUPIED",
        "CHANNEL_INVALID",
        "CHANNEL_PRIVATE",
        "CHAT_INVALID",
        "MSG_ID_INVALID",
        "MESSAGE_ID_INVALID",
    )
    return any(marker in text for marker in markers)


async def resolve_cached_chat(client, chat_id):
    if not isinstance(chat_id, int):
        return chat_id

    try:
        chat = await client.get_chat(chat_id)
        return chat.id
    except Exception as direct_err:
        if not is_peer_invalid(direct_err):
            return chat_id

    async for dialog in client.get_dialogs():
        dialog_chat = getattr(dialog, "chat", None)
        if dialog_chat and getattr(dialog_chat, "id", None) == chat_id:
            logger.info(f"Resolved cached peer for {chat_id} via dialogs")
            return dialog_chat.id

    return chat_id


async def get_message_with_peer_retry(client, chat_id, msg_id):
    try:
        return await client.get_messages(chat_id, msg_id), chat_id
    except Exception as first_err:
        if not is_peer_invalid(first_err):
            raise

        resolved_chat_id = await resolve_cached_chat(client, chat_id)
        return await client.get_messages(resolved_chat_id, msg_id), resolved_chat_id


async def send_reaction_with_peer_retry(client, chat_id, msg_id, reaction):
    try:
        await send_reaction_value(client, chat_id, msg_id, reaction)
        return chat_id
    except Exception as first_err:
        if not is_peer_invalid(first_err):
            raise

        resolved_chat_id = await resolve_cached_chat(client, chat_id)
        await send_reaction_value(client, resolved_chat_id, msg_id, reaction)
        return resolved_chat_id


async def send_reaction_value(client, chat_id, msg_id, reaction):
    if isinstance(reaction, int) or str(reaction).isdigit():
        await client.invoke(
            raw.functions.messages.SendReaction(
                peer=await client.resolve_peer(chat_id),
                msg_id=msg_id,
                reaction=[raw.types.ReactionCustomEmoji(document_id=int(reaction))],
            )
        )
        return True

    await client.send_reaction(chat_id, message_id=msg_id, emoji=str(reaction))
    return True


async def increment_post_view_with_peer_retry(client, chat_id, msg_id):
    try:
        peer = await client.resolve_peer(chat_id)
        await client.invoke(GetMessagesViews(peer=peer, id=[msg_id], increment=True))
        return chat_id
    except Exception as first_err:
        if not is_peer_invalid(first_err):
            raise

        resolved_chat_id = await resolve_cached_chat(client, chat_id)
        peer = await client.resolve_peer(resolved_chat_id)
        await client.invoke(GetMessagesViews(peer=peer, id=[msg_id], increment=True))
        return resolved_chat_id


async def perform_account_action(session_string, action, target_link, emoji=None, emoji_type=None, dm_text=None, option_index=None, proxy=None):
    import uuid
    import binascii
    session_string = str(session_string or "").strip()
    if not session_string or len(session_string) < 40:
        if session_string:
            db.update_account_status_by_session(session_string, "expired")
        raise ValueError("Invalid/truncated session string. Account marked as expired.")
    
    missing_padding = len(session_string) % 4
    if missing_padding:
        session_string += "=" * (4 - missing_padding)

    try:
        session_string.encode("ascii")
    except (UnicodeEncodeError, binascii.Error, Exception) as session_err:
        db.update_account_status_by_session(session_string, "expired")
        raise ValueError("Session string corrupted. Account marked as expired.") from session_err

    proxy_obj = None
    if proxy:
        try:
            h, p = proxy.split(":")
            proxy_obj = dict(scheme="socks5", hostname=h, port=int(p))
        except Exception:
            pass
            
    client = Client(
        name=f"runner_{uuid.uuid4().hex}",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_string,
        in_memory=True,
        proxy=proxy_obj
    )
    
    try:
        try:
            try:
                await connect_client(client)
            except Unauthorized as auth_err:
                logger.warning(f"Account auth failed (Unauthorized), marking as expired: {auth_err}")
                db.update_account_status_by_session(session_string, "expired", reason=auth_err)
                raise auth_err
        except Exception as proxy_err:
            if isinstance(proxy_err, Unauthorized):
                raise proxy_err
            if proxy_obj:
                logger.warning(f"Proxy connection failed, retrying without proxy: {proxy_err}")
                try:
                    await client.disconnect()
                except:
                    pass
                client = Client(
                    name=f"runner_{uuid.uuid4().hex}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    session_string=session_string,
                    in_memory=True
                )
                try:
                    await connect_client(client)
                except Unauthorized as auth_err:
                    logger.warning(f"Account auth failed on retry (Unauthorized), marking as expired: {auth_err}")
                    db.update_account_status_by_session(session_string, "expired", reason=auth_err)
                    raise auth_err
            else:
                raise proxy_err
                
        if action == "Join Channel":
            sanitized = sanitize_channel_link(target_link)
            for attempt in range(2):
                try:
                    await asyncio.wait_for(client.join_chat(sanitized), timeout=25)
                    break
                except (asyncio.TimeoutError, TimeoutError):
                    if attempt == 1:
                        raise TimeoutError("Telegram Join Channel request timed out.")
                    await asyncio.sleep(1.0)
                except Exception as join_err:
                    join_err_text = str(join_err)
                    if "INVITE_REQUEST_SENT" in join_err_text:
                        logger.info("Invite request sent successfully (INVITE_REQUEST_SENT caught).")
                        break
                    elif "USER_ALREADY_PARTICIPANT" in join_err_text:
                        logger.info("Account is already a participant; counting join as success.")
                        break
                    else:
                        raise join_err
            
        elif action == "Leave Channel":
            leave_target = await resolve_leave_chat_target(client, target_link)
            await client.leave_chat(leave_target)

        elif action == "Leave All Channels":
            await leave_all_joined_channels(client)

        elif action == "Bot Start":
            bot_username, start_payload = parse_bot_start_link(target_link)
            start_text = "/start" if not start_payload else f"/start {start_payload}"
            try:
                await client.send_message(bot_username, start_text)
            except Exception as bot_start_err:
                if "USER_IS_BLOCKED" in str(bot_start_err).upper():
                    try:
                        await client.unblock_user(bot_username)
                        await asyncio.sleep(0.5)
                        await client.send_message(bot_username, start_text)
                    except Exception as retry_err:
                        raise RuntimeError(f"Bot start failed after unblock: {retry_err}") from retry_err
                else:
                    raise RuntimeError(f"Bot start failed: {bot_start_err}") from bot_start_err
            
        elif action in ("React Only", "Auto Different Reactions", "Auto Different Reactions + View", "Vote Only", "React + Vote", "View Only",
                        "React + View", "Vote + View", "React + Vote + View"):
            
            # Always split "post_link option_index" so a selected emoji flow still
            # accepts targets like "https://t.me/channel/123 0".
            link, parsed_opt_idx = parse_vote_target(target_link)
            opt_idx = parsed_opt_idx if option_index is None else option_index
                
            chat_id, msg_id = parse_post_link(link)
            if not chat_id or not msg_id:
                raise ValueError("Invalid Telegram post link format!")
            
            # Auto-join public channel if username is extracted and not joined
            if isinstance(chat_id, str) and not chat_id.startswith("-"):
                try:
                    await client.join_chat(chat_id)
                except Exception as join_err:
                    logger.warning(f"Auto-join failed/already joined for public channel {chat_id}: {join_err}")
                
            # View
            message = None
            if action_uses_view(action) or action_uses_reaction(action) or "Vote" in str(action or ""):
                try:
                    message, chat_id = await get_message_with_peer_retry(client, chat_id, msg_id)
                except Exception as view_err:
                    logger.warning(f"View failed: {view_err}")
                    if is_invalid_target_error(view_err):
                        raise RuntimeError(f"Target not accessible: {view_err}") from view_err
                else:
                    try:
                        await client.read_chat_history(chat_id, max_id=msg_id)
                    except Exception as read_err:
                        logger.warning(f"Read history failed: {read_err}")
                    if action_uses_view(action):
                        try:
                            chat_id = await increment_post_view_with_peer_retry(client, chat_id, msg_id)
                        except Exception as inc_err:
                            logger.warning(f"View increment failed: {inc_err}")
                            if is_invalid_target_error(inc_err):
                                raise RuntimeError(f"Target not accessible: {inc_err}") from inc_err
            
            # React
            if action_uses_reaction(action):
                reaction = emoji or "ðŸ‘"
                try:
                    if emoji_type == "auto" or "Auto Premium" in str(action) or "Auto Different" in str(action):
                        allowed_reactions = await get_post_allowed_reactions(client, chat_id, message)
                        reaction = resolve_auto_reaction_choice(
                            session_string,
                            planned_reaction=reaction,
                            allowed_reactions=allowed_reactions,
                        )
                        if isinstance(reaction, int) or str(reaction).isdigit():
                            emoji_type = "premium"
                        else:
                            emoji_type = "normal"
                    elif emoji_type != "premium":
                        reaction = await resolve_reaction_for_chat(
                            client,
                            chat_id,
                            reaction,
                            session_string,
                            emoji_type=emoji_type,
                        )

                    if emoji_type == "premium":
                        if reaction in EMOJI_IDS:
                            reaction = EMOJI_IDS[reaction]

                        if str(reaction).isdigit():
                            chat_id = await send_reaction_with_peer_retry(client, chat_id, msg_id, int(reaction))
                        else:
                            chat_id = await send_reaction_with_peer_retry(client, chat_id, msg_id, reaction)
                    else:
                        chat_id = await send_reaction_with_peer_retry(client, chat_id, msg_id, reaction)
                except Exception as react_err:
                    if is_reaction_limit_error(react_err):
                        raise RuntimeError("React failed: Telegram reaction limit hit (REACTIONS_TOO_MANY). Wait/cooldown before reusing this account/post.") from react_err
                    if isinstance(react_err, UnsupportedReactionError):
                        raise RuntimeError(f"React failed: {react_err}") from react_err
                    if is_reaction_invalid_error(react_err):
                        raise RuntimeError(
                            "React failed: selected reaction is not allowed by this post/channel. Choose a reaction already enabled on the post, or use a supported premium/custom reaction."
                        ) from react_err
                    raise RuntimeError(f"React failed: {react_err}") from react_err
                    
            # Vote
            if "Vote" in action:
                try:
                    if message is None:
                        message, chat_id = await get_message_with_peer_retry(client, chat_id, msg_id)
                    if message.poll:
                        idx = int(opt_idx)
                        if idx < len(message.poll.options):
                            await client.vote_poll(chat_id, msg_id, idx)
                        else:
                            raise ValueError(f"Option index {idx} out of poll options range!")
                    elif message.reply_markup and message.reply_markup.inline_keyboard:
                        idx = int(opt_idx)
                        buttons = []
                        for row in message.reply_markup.inline_keyboard:
                            for btn in row:
                                buttons.append(btn)
                        if idx < len(buttons):
                            target_btn = buttons[idx]
                            # If it's a URL button, open URL or treat as clicked without callback wait
                            if getattr(target_btn, "url", None):
                                logger.info(f"Button {idx} is a URL button ({target_btn.url}). Registered click.")
                            else:
                                try:
                                    click_res = await asyncio.wait_for(message.click(idx), timeout=8)
                                    if click_res and getattr(click_res, "message", None):
                                        msg_text = click_res.message.lower()
                                        if any(w in msg_text for w in ("took", "back", "remove", "retract", "cancel")):
                                            logger.info(f"Vote was toggled off (message: {click_res.message}). Sleeping 1.5s and clicking again to vote back on...")
                                            await asyncio.sleep(1.5)
                                            try:
                                                await asyncio.wait_for(message.click(idx), timeout=8)
                                            except Exception:
                                                pass
                                except (asyncio.TimeoutError, TimeoutError) as timeout_err:
                                    logger.info(f"Vote callback timed out after sending click for button {idx}, proceeding as voted.")
                                except Exception as click_err:
                                    err_str = str(click_err).lower()
                                    if "timed out" in err_str or "timeout" in err_str:
                                        logger.info(f"Vote callback timed out ({click_err}), proceeding as voted.")
                                    else:
                                        raise
                        else:
                            raise ValueError(f"Button index {idx} out of range! Total buttons: {len(buttons)}")
                    else:
                        raise ValueError("Target post does not contain a poll or inline buttons!")
                except Exception as vote_err:
                    raise RuntimeError(f"Vote failed: {vote_err}") from vote_err
                    
        elif action == "Bulk DM":
            target_user = target_link.strip()
            if "t.me/" in target_user or "telegram.me/" in target_user:
                target_user = target_user.split('/')[-1]
            if not dm_text:
                raise ValueError("Message text for Bulk DM is missing!")
            await client.send_message(target_user, dm_text)
    except Exception as action_err:
        if mark_session_expired_if_fatal(session_string, action_err):
            logger.warning(f"Session marked expired during action: {short_error(action_err)}")
        raise
    finally:
        try:
            await client.disconnect()
        except:
            pass


def execute_campaign_thread(uid, chat_id, msg_id, camp_id):
    db_obj = db.get_db()
    camp = db_obj["campaigns"].find_one({"id": camp_id})
    if not camp:
        send_message(chat_id, "âŒ Campaign not found in database!")
        return
        
    action = camp["action"]
    target = camp["target"]
    emoji = camp.get("emoji")
    emoji_type = camp.get("emoji_type")
    dm_text = camp.get("dm_text")
    option_index = camp.get("option_index")
    account_limit = camp.get("account_limit")
    
    scope = camp.get("scope", "user")
    if scope == "all":
        accounts = db.get_global_active_accounts()
    elif scope == "grant":
        accounts = db.get_limited_global_active_accounts(uid)
    else:
        accounts = get_campaign_accounts_for_state(uid, {})
    accounts = limit_accounts(accounts, account_limit)
    notify_owner_campaign_started(camp, len(accounts))

    reaction_action = action_uses_reaction(action)
    cooldown_skipped = 0
    if reaction_action:
        db.clear_expired_reaction_cooldowns()
        accounts, cooldown_accounts = db.split_reaction_ready_accounts(accounts)
        cooldown_skipped = len(cooldown_accounts)
        if cooldown_skipped:
            logger.info(f"Campaign #{camp_id}: skipped {cooldown_skipped} accounts still in reaction cooldown")
        db_obj["campaigns"].update_one({"id": camp_id}, {"$set": {"total_accounts": len(accounts), "cooldown_skipped": cooldown_skipped}})
        if cooldown_skipped and accounts:
            edit_message(
                chat_id,
                msg_id,
                f"ðŸš€ Campaign #{camp_id} Preparing...\nAction: {action}\nReady: {len(accounts)}\nâ³ Cooldown skipped: {cooldown_skipped}",
                reply_markup=campaign_control_kb(camp_id),
            )
    if not accounts:
        db.finish_campaign(camp_id, 0, 0)
        msg = "âŒ No active accounts found to run the campaign!"
        if reaction_action and cooldown_skipped:
            msg = f"â³ All active accounts are in Telegram reaction cooldown. Skipped: {cooldown_skipped}. Try again later."
        send_message(chat_id, msg, reply_markup=main_keyboard(db.is_admin(uid), uid))
        return
        
    user_data = db.get_user(uid)
    speed = user_data.get("speed", 200) if user_data else 200
    delay_seconds = speed / 1000.0
    if reaction_action:
        delay_seconds = max(delay_seconds, REACTION_MIN_DELAY_SECONDS)
    
    async def run_campaign_async():
        import random
        success_count = 0
        failed_count = 0
        completed_count = 0
        failed_logs = []
        total = len(accounts)
        skipped_count = cooldown_skipped
        reaction_limit_hits = 0
        stop_scheduling = asyncio.Event()
        auto_reaction_plan = build_auto_reaction_plan(total, seed=camp_id) if is_auto_different_action(action) else []
        auto_reaction_counts = {}
        reaction_semaphore = asyncio.Semaphore(min(20, REACTION_MAX_PARALLEL if reaction_action else 20))
        if auto_reaction_plan:
            for reaction in auto_reaction_plan:
                auto_reaction_counts[reaction] = auto_reaction_counts.get(reaction, 0) + 1
            logger.info(f"Auto reaction plan for campaign #{camp_id}: {auto_reaction_counts}")

        async def wait_for_campaign_control():
            pause_logged = False
            while True:
                control_status = str(db.get_campaign_control_status(camp_id) or "running").lower()
                if control_status == "stopped":
                    stop_scheduling.set()
                    return False
                if control_status == "paused":
                    if not pause_logged:
                        logger.info(f"Campaign #{camp_id}: paused by owner control")
                        pause_logged = True
                    await asyncio.sleep(2)
                    continue
                if pause_logged:
                    logger.info(f"Campaign #{camp_id}: resumed by owner control")
                return True
        
        proxies = []
        if USE_PUBLIC_PROXIES:
            try:
                logger.info("Scraping public SOCKS5 proxies...")
                proxies = scrape_socks5_proxies()
                logger.info(f"Scraped {len(proxies)} proxies successfully.")
            except Exception as proxy_err:
                logger.error(f"Error scraping proxies: {proxy_err}")
        else:
            logger.info("Public SOCKS5 proxies disabled; running campaign with direct session connections.")

        account_targets = build_account_targets(action, target, len(accounts))
            
        last_update_time = [time.time()]
        
        async def worker(acc, acc_index):
            nonlocal success_count, failed_count, completed_count, reaction_limit_hits
            if stop_scheduling.is_set():
                return
            if not await wait_for_campaign_control():
                return
            acc_targets = account_targets[acc_index]
            if not acc_targets:
                completed_count += 1
                return

            if action == "Join Channel":
                await asyncio.sleep(random.uniform(0.1, 0.3) * (acc_index % 6))
                
            acc_proxy = random.choice(proxies) if proxies else None
            account_emoji = auto_reaction_plan[acc_index] if auto_reaction_plan else emoji
            account_emoji_type = "auto" if auto_reaction_plan else emoji_type
            try:
                async with reaction_semaphore:
                    for target_item in acc_targets:
                        for action_attempt in range(2):
                            try:
                                await perform_account_action(
                                    acc["session_string"],
                                    action,
                                    target_item,
                                    emoji=account_emoji,
                                    emoji_type=account_emoji_type,
                                    dm_text=dm_text,
                                    option_index=option_index,
                                    proxy=acc_proxy
                                )
                                break
                            except (asyncio.TimeoutError, TimeoutError, FutureTimeoutError) as timeout_err:
                                if action_attempt == 1:
                                    raise timeout_err
                                await asyncio.sleep(1.2)
                                acc_proxy = None
                        if len(acc_targets) > 1:
                            await asyncio.sleep(1.0)
                        
                success_count += 1
            except Exception as e:
                label = account_label(acc, acc_index)
                reason = campaign_error_reason(e)
                if not reason or not str(reason).strip():
                    reason = getattr(e, "ID", None) or type(e).__name__
                if is_invalid_target_error(e):
                    reason = f"{reason} Continuing with next account."
                if reaction_action and is_reaction_limit_error(e):
                    reaction_limit_hits += 1
                    db.mark_account_reaction_cooldown(acc["session_string"], REACTION_LIMIT_COOLDOWN_MINUTES, reason)
                    if reaction_limit_hits >= REACTION_LIMIT_ABORT_AFTER:
                        stop_scheduling.set()
                        reason = f"{reason} Limit wave detected; pausing remaining accounts."
                failed_logs.append(f"- {label}: {reason}")
                logger.error(f"Account {label} failed action: {reason}")
                failed_count += 1
            finally:
                completed_count += 1
                now = time.time()
                # Update progress at most every 1.5 seconds to avoid spamming Bot API
                if now - last_update_time[0] >= 1.5 or completed_count == total:
                    last_update_time[0] = now
                    progress_text = (
                        f"ðŸš€ Campaign #{camp_id} Running...\n\n"
                        f"Action: {action}\n"
                        f"Total: {total}\n"
                        f"âœ… Success: {success_count} | âŒ Failed: {failed_count}"
                        f"{f' | â³ Skipped: {skipped_count}' if skipped_count else ''}\n"
                        f"Progress: {completed_count}/{total}"
                        f"{failed_logs_text(failed_logs)}"
                    )
                    edit_message(
                        chat_id,
                        msg_id,
                        escape_html(progress_text),
                        reply_markup=campaign_control_kb(camp_id, db.get_campaign_control_status(camp_id)),
                    )
                    
        tasks = []
        plan_text = ""
        if auto_reaction_counts:
            plan_text = "\nReactions: " + " ".join(f"{r}x{c}" for r, c in auto_reaction_counts.items())
        skipped_text = f"\nâ³ Cooldown skipped: {cooldown_skipped}" if cooldown_skipped else ""
        edit_message(
            chat_id,
            msg_id,
            f"ðŸš€ Campaign #{camp_id} Starting...\nAction: {action}\nTotal: {total}{skipped_text}{plan_text}",
            reply_markup=campaign_control_kb(camp_id),
        )
        
        for idx, acc in enumerate(accounts):
            if not await wait_for_campaign_control():
                skipped_now = total - idx
                skipped_count += skipped_now
                logger.warning(f"Campaign #{camp_id}: stopped by owner control; skipped {skipped_now} remaining accounts")
                break
            if stop_scheduling.is_set():
                skipped_now = total - idx
                skipped_count += skipped_now
                logger.warning(f"Campaign #{camp_id}: stopped scheduling {skipped_now} accounts after reaction limit wave")
                break
            task = asyncio.create_task(worker(acc, idx))
            tasks.append(task)
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
                
        if tasks:
            await asyncio.gather(*tasks)
        return success_count, failed_count, failed_logs, skipped_count

    try:
        success_count, failed_count, failed_logs, skipped_count = run_async(run_campaign_async())
    except Exception as run_err:
        logger.error(f"Error executing campaign {camp_id}: {run_err}", exc_info=True)
        success_count, failed_count = 0, len(accounts)
        skipped_count = 0
        failed_logs = [f"- Campaign: {short_error(run_err)}"]
        
    db.finish_campaign(camp_id, success_count, failed_count)
    clear_state(uid)
    done_text = (
        f"âœ… Campaign #{camp_id} Done!\n\n"
        f"ðŸ“‹ Action: {action}\n"
        f"{campaign_target_display(action, target)}\n\n"
        f"âœ… Success: {success_count}\n"
        f"âŒ Failed: {failed_count}"
        f"{f'\nâ³ Skipped: {skipped_count}' if skipped_count else ''}"
        f"{failed_logs_text(failed_logs)}"
    )
    send_message(chat_id, escape_html(done_text), reply_markup=main_keyboard(db.is_admin(uid), uid))


def run_scheduler_loop():
    logger.info("â° Background Scheduler Loop started...")
    while True:
        try:
            pending = db.get_pending_scheduled()
            for s in pending:
                logger.info(f"â° Executing scheduled campaign #{s['id']} for user {s['user_id']}")
                db.mark_scheduled_done(s["id"])
                
                uid = s["user_id"]
                action = s["action"]
                target = s["target"]
                emoji = s.get("emoji")
                emoji_type = s.get("emoji_type")
                dm_text = s.get("dm_text")
                option_index = s.get("option_index")
                account_limit = s.get("account_limit")
                
                scope = s.get("scope", "user")
                if scope == "all":
                    accounts = db.get_global_active_accounts()
                elif scope == "grant":
                    accounts = db.get_limited_global_active_accounts(uid)
                else:
                    accounts = get_campaign_accounts_for_state(uid, {})
                accounts = limit_accounts(accounts, account_limit)
                    
                if not accounts:
                    logger.warning(f"No active accounts for scheduled campaign #{s['id']} of user {uid}")
                    continue
                    
                camp_id = db.create_campaign(uid, action, target, len(accounts), emoji=emoji, emoji_type=emoji_type, dm_text=dm_text, option_index=option_index, scope=scope, account_limit=account_limit)
                chat_id = uid
                
                msg_resp = send_message(chat_id, f"â° Scheduled campaign #{s['id']} is starting now!\nAction: {action}\n{campaign_target_display(action, target)}")
                msg_id = msg_resp.get("result", {}).get("message_id") if msg_resp.get("ok") else None
                
                if msg_id:
                    threading.Thread(target=execute_campaign_thread, args=(uid, chat_id, msg_id, camp_id), daemon=True).start()
                else:
                    def run_without_telegram():
                        user_data = db.get_user(uid)
                        speed = user_data.get("speed", 200) if user_data else 200
                        delay_seconds = speed / 1000.0
                        
                        async def run_camp_async():
                            success_count = 0
                            failed_count = 0
                            tasks = []
                            auto_reaction_plan = []
                            
                            account_targets = build_account_targets(action, target, len(accounts))
                            if is_auto_different_action(action):
                                auto_reaction_plan = build_auto_reaction_plan(len(accounts), seed=camp_id)
                                
                            async def worker(acc, acc_index):
                                nonlocal success_count, failed_count
                                acc_targets = account_targets[acc_index]
                                if not acc_targets:
                                    return
                                account_emoji = auto_reaction_plan[acc_index] if auto_reaction_plan else emoji
                                account_emoji_type = "auto" if auto_reaction_plan else emoji_type
                                try:
                                    for target_item in acc_targets:
                                        await perform_account_action(
                                            acc["session_string"],
                                            action,
                                            target_item,
                                            emoji=account_emoji,
                                            emoji_type=account_emoji_type,
                                            dm_text=dm_text,
                                            option_index=option_index
                                        )
                                        if len(acc_targets) > 1:
                                            await asyncio.sleep(1.0)
                                    success_count += 1
                                except:
                                    failed_count += 1
                            
                            for idx, acc in enumerate(accounts):
                                tasks.append(asyncio.create_task(worker(acc, idx)))
                                if delay_seconds > 0:
                                    await asyncio.sleep(delay_seconds)
                            await asyncio.gather(*tasks)
                            return success_count, failed_count
                            
                        try:
                            success_count, failed_count = run_async(run_camp_async())
                        except Exception as e:
                            success_count, failed_count = 0, len(accounts)
                            
                        db.finish_campaign(camp_id, success_count, failed_count)
                        
                    threading.Thread(target=run_without_telegram, daemon=True).start()
                    
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            
        time.sleep(30)


# â”€â”€ POLLING LOOP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def process_update(update):
    try:
        if "message" in update:
            msg = update["message"]
            text = msg.get("text", "")
            if text.startswith("/start"):
                handle_start(msg)
            elif "document" in msg:
                handle_document_message(msg)
            elif text:
                handle_text_message(msg)
        elif "callback_query" in update:
            handle_callback(update["callback_query"])
    except Exception as e:
        logger.error(f"Error processing update {update.get('update_id')}: {e}", exc_info=True)


def notify_bot_online():
    if not BOT_ONLINE_NOTIFY:
        return
    targets = list(ADMIN_IDS)
    if SESSION_EXPORT_ALLOWED_ADMIN not in targets:
        targets.append(SESSION_EXPORT_ALLOWED_ADMIN)
    seen = set()
    text = (
        "✅ Bot Online\n\n"
        "Danger Voting Machine is running.\n"
        f"Reaction speed: min {REACTION_MIN_DELAY_SECONDS}s, parallel {REACTION_MAX_PARALLEL}."
    )
    for admin_id in targets:
        if admin_id in seen:
            continue
        seen.add(admin_id)
        try:
            send_message(admin_id, text)
        except Exception as exc:
            logger.warning(f"Bot online notify failed for {admin_id}: {short_error(exc)}")


def poll():
    db.init_db()
    start_background_loop()
    threading.Thread(target=run_scheduler_loop, daemon=True).start()
    logger.info("ðŸš€ Danger Voting Bot started! Polling...")
    threading.Thread(target=notify_bot_online, daemon=True).start()
    offset = 0

    while True:
        try:
            url = f"{BASE_URL}/getUpdates?timeout={POLL_TIMEOUT}&offset={offset}"
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=POLL_HTTP_TIMEOUT)
            data = json.loads(resp.read())

            if not data.get("ok"):
                logger.error(f"getUpdates error: {data}")
                time.sleep(POLL_ERROR_SLEEP)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                UPDATE_EXECUTOR.submit(process_update, update)

        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(POLL_ERROR_SLEEP)


if __name__ == "__main__":
    poll()
