
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


# ── MAIN MENU REPLY KEYBOARD ─────────────────────────────────

def main_menu_keyboard(is_admin=False):
    keyboard = []
    if is_admin:
        keyboard.append(["🔥 ADMIN PANEL"])
    keyboard += [
        ["➕ Add Account", "🎭 My Accounts"],
        ["🚀 New Campaign", "📊 My Campaigns"],
        ["⚡ Scheduled", "🔥 My Stats"],
        ["⚙️ Settings", "👤 My Profile"],
        ["❓ Help & Guide", "🎧 Support"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ── ADMIN PANEL INLINE KEYBOARD ──────────────────────────────

def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Campaign (All Accounts)", callback_data="admin_campaign_all")],
        [InlineKeyboardButton("🎯 Campaign (By User ID)", callback_data="admin_campaign_user")],
        [InlineKeyboardButton("📋 All Campaigns", callback_data="admin_all_campaigns")],
        [InlineKeyboardButton("✅ Make Admin", callback_data="admin_make_admin"),
         InlineKeyboardButton("❌ Remove Admin", callback_data="admin_remove_admin")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban_user"),
         InlineKeyboardButton("✅ Unban User", callback_data="admin_unban_user")],
        [InlineKeyboardButton("👥 All Users", callback_data="admin_all_users")],
        [InlineKeyboardButton("⚡ Speed Control", callback_data="admin_speed_control")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── ADD ACCOUNT INLINE KEYBOARD ──────────────────────────────

def add_account_keyboard():
    keyboard = [
        [InlineKeyboardButton("📱 Phone + OTP", callback_data="add_phone_otp")],
        [InlineKeyboardButton("🔑 Session String", callback_data="add_session_string")],
        [InlineKeyboardButton("📦 Bulk Sessions", callback_data="add_bulk_sessions")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── MY ACCOUNTS INLINE KEYBOARD ──────────────────────────────

def my_accounts_keyboard(live=0, expired=0):
    keyboard = [
        [InlineKeyboardButton(f"✅ Live ({live})", callback_data="accounts_live"),
         InlineKeyboardButton(f"❌ Expired ({expired})", callback_data="accounts_expired")],
        [InlineKeyboardButton("🗑️ Remove", callback_data="accounts_remove"),
         InlineKeyboardButton("🗑️ REMOVE ALL", callback_data="accounts_remove_all")],
        [InlineKeyboardButton("➕ Add Another", callback_data="add_account")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── NEW CAMPAIGN INLINE KEYBOARD ─────────────────────────────

def campaign_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("👑 Auto Premium Reactions", callback_data="camp_auto_prem_react")],
        [InlineKeyboardButton("👑👁️ Auto Premium React + View", callback_data="camp_auto_prem_react_view")],
        [InlineKeyboardButton("🔀 Auto Different Reactions", callback_data="camp_auto_diff_react")],
        [InlineKeyboardButton("🔀👁️ Auto Diff React + View", callback_data="camp_auto_diff_react_view")],
        [InlineKeyboardButton("👍 React Only", callback_data="camp_react_only")],
        [InlineKeyboardButton("🗳️ Vote Only", callback_data="camp_vote_only")],
        [InlineKeyboardButton("👍🗳️ React + Vote", callback_data="camp_react_vote")],
        [InlineKeyboardButton("👁️ View Only", callback_data="camp_view_only")],
        [InlineKeyboardButton("👍👁️ React + View", callback_data="camp_react_view")],
        [InlineKeyboardButton("🗳️👁️ Vote + View", callback_data="camp_vote_view")],
        [InlineKeyboardButton("👍🗳️👁️ React + Vote + View", callback_data="camp_react_vote_view")],
        [InlineKeyboardButton("➕ Join Channel", callback_data="camp_join")],
        [InlineKeyboardButton("➖ Leave Channel", callback_data="camp_leave")],
        [InlineKeyboardButton("💬 Bulk DM", callback_data="camp_bulk_dm")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def emoji_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("😊 Normal Emoji", callback_data="emoji_normal")],
        [InlineKeyboardButton("⭐ Premium Emoji", callback_data="emoji_premium")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def run_campaign_keyboard(camp_id):
    keyboard = [
        [InlineKeyboardButton("▶️ Run Campaign", callback_data=f"run_camp_{camp_id}")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def campaign_control_keyboard(camp_id):
    keyboard = [
        [InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_camp_{camp_id}"),
         InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_camp_{camp_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── MY CAMPAIGNS INLINE KEYBOARD ─────────────────────────────

def my_campaigns_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 MAIN", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── SCHEDULED INLINE KEYBOARD ────────────────────────────────

def scheduled_keyboard():
    keyboard = [
        [InlineKeyboardButton("📅 Schedule New Campaign", callback_data="sched_new")],
        [InlineKeyboardButton("📋 My Scheduled Campaigns", callback_data="sched_list")],
        [InlineKeyboardButton("❌ Cancel Schedule", callback_data="sched_cancel")],
        [InlineKeyboardButton("🏠 Back to Main", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── SETTINGS / SPEED INLINE KEYBOARD ────────────────────────

def speed_keyboard():
    keyboard = [
        [InlineKeyboardButton("🐢 Slow (500ms)", callback_data="speed_slow")],
        [InlineKeyboardButton("⚡ Normal (200ms)", callback_data="speed_normal")],
        [InlineKeyboardButton("🚀 Fast (50ms)", callback_data="speed_fast")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── SIMPLE BACK/CANCEL KEYBOARDS ────────────────────────────

def back_keyboard(callback="main_menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data=callback)]])


def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]])


def main_inline_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 MAIN", callback_data="main_menu")]])


def confirm_keyboard(yes_cb, no_cb="cancel"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ YES", callback_data=yes_cb),
         InlineKeyboardButton("❌ NO", callback_data=no_cb)]
    ])
