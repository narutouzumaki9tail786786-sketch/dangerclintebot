
from config import BOT_NAME, DEVELOPER, DEVELOPER_LINK

SPEEDS_LABEL = {500: "Slow (500ms)", 200: "Normal (200ms)", 50: "Fast (50ms)"}


def welcome_text(name: str) -> str:
    return (
        f"Welcome back, {name}! 🎉\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✨ 𝐃𝐀𝐍𝐆𝐄𝐑 𝐕𝐎𝐓𝐈𝐍𝐆 𝐁𝐎𝐓 ✨\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 Auto Voter — {BOT_NAME}\n\n"
        f"⚡ Features:\n"
        f"✅ React on posts\n"
        f"✅ Vote in polls\n"
        f"👁️ View stories/posts\n"
        f"➕ Auto Join groups/channels\n"
        f"📨 Bulk DM campaigns\n"
        f"⏰ Schedule campaigns\n\n"
        f"🚀 Fast • Reliable • Smart\n"
        f"👾 devloper:- {DEVELOPER}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 Choose an option below:🎮"
    )


def admin_panel_text() -> str:
    return (
        "🔥 ADMIN PANEL\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Select an option:"
    )


def add_account_text() -> str:
    return (
        "➕ Add Telegram Account\n\n"
        "How would you like to add an account?"
    )


def my_accounts_text(total=0, live=0, expired=0) -> str:
    return (
        "🎭 My Accounts – Live/Working\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Total: {total}\n"
        f"✅ Live: {live}\n"
        f"❌ Expired: {expired}"
    )


def no_accounts_text() -> str:
    return "❌ No active accounts found!\n\nPlease add an account first using ➕ Add Account."


def new_campaign_text() -> str:
    return (
        "🚀 New Campaign\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Choose campaign type:"
    )


def my_campaigns_text(campaigns: list) -> str:
    if not campaigns:
        return "📊 No campaigns yet!\n\nStart your first campaign using 🚀 New Campaign."
    text = "📊 My Campaigns\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for c in campaigns[:10]:
        status_emoji = "✅" if c['status'] == 'done' else "🔄" if c['status'] == 'running' else "⏸️"
        text += (
            f"{status_emoji} #{c['id']} — {c['action']}\n"
            f"   🎯 Target: {c['target'][:30]}...\n"
            f"   ✅ {c['success']} | ❌ {c['failed']} | Total: {c['total_accounts']}\n"
            f"   📅 {c['start_time']}\n\n"
        )
    return text


def scheduled_text() -> str:
    return (
        "⏰ SCHEDULED CAMPAIGNS\n\n"
        "Schedule your campaigns to run automatically at a specific time!\n\n"
        "📖 How to use:\n"
        "1. Click \"Schedule New Campaign\"\n"
        "2. Choose campaign type\n"
        "3. Enter target/post link\n"
        "4. Set date and time (DD/MM/YYYY HH:MM)\n"
        "5. Confirm schedule\n\n"
        "🕐 Time format: 25/12/2024 14:30 (24-hour format)"
    )


def my_stats_text(accounts=0, active=0, dead=0, campaigns=0) -> str:
    return (
        "📈 YOUR STATS\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎭 Accounts: {accounts}\n"
        f"✅ Active: {active}\n"
        f"❌ Dead: {dead}\n"
        f"🚀 Campaigns: {campaigns}"
    )


def settings_text(current_speed_ms=200) -> str:
    speed_label = SPEEDS_LABEL.get(current_speed_ms, "Normal (200ms)")
    return (
        "⚙️ SETTINGS\n\n"
        "⚡ Campaign Speed Control\n\n"
        "Choose how fast accounts should perform actions:\n\n"
        "🐢 Slow: 500ms delay (safer, less detectable)\n"
        "⚡ Normal: 200ms delay (balanced)\n"
        "🚀 Fast: 50ms delay (aggressive, may get flagged)\n\n"
        f"📌 Current setting: {speed_label}\n\n"
        "Current setting affects all running campaigns."
    )


def profile_text(user_id, name, username, join_date, accounts=0, campaigns=0, speed=200, is_admin=False) -> str:
    speed_label = SPEEDS_LABEL.get(speed, "Normal (200ms)")
    role = "👑 ADMIN" if is_admin else "👤 USER"
    return (
        f"👤 PROFILE  {role}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 {user_id}\n"
        f"📛 {name}\n"
        f"💬 @{username or 'N/A'}\n"
        f"📅 {join_date}\n"
        f"🎭 Accounts: {accounts}\n"
        f"🚀 Campaigns: {campaigns}\n"
        f"⚡ Speed: {speed_label}"
    )


def help_text() -> str:
    return (
        "📖 HOW TO USE\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "➕ ADD ACCOUNTS (3 WAYS)\n"
        "• Phone + OTP — Add via phone number\n"
        "• Session String — Add via Telethon session\n"
        "• Bulk Sessions — Add multiple at once\n\n"
        "🚀 RUN CAMPAIGN\n"
        "1. Click 'New Campaign'\n"
        "2. Select action\n"
        "3. For Join/Leave: Send channel link or ID (-100xxxxxxxxx)\n"
        "4. For View: Send post link (no emoji, direct view)\n"
        "5. For React/Vote: Send post link, select emoji type\n"
        "6. For Normal Emoji: Select emojis or send custom emoji\n"
        "7. For Premium Emoji: Follow instructions, select premium emoji\n"
        "8. Select number of accounts\n"
        "9. Tap 'Run Campaign'\n\n"
        "⏰ SCHEDULE CAMPAIGN\n"
        "1. Click 'Scheduled'\n"
        "2. Click 'Schedule New Campaign'\n"
        "3. Choose campaign type\n"
        "4. Enter target/post link\n"
        "5. Set date and time (DD/MM/YYYY HH:MM)\n"
        "6. Confirm schedule\n"
        "7. Bot runs automatically!\n\n"
        "😊 NORMAL EMOJI MODE\n"
        "• Tap emojis to select multiple reactions\n"
        "• Or send a custom emoji as your reaction\n\n"
        "⭐ PREMIUM EMOJI MODE\n"
        "• Go to post/message\n"
        "• Right-click and manually react with premium emoji ONCE\n"
        "• Come back and select the premium emoji\n\n"
        "🎮 CAMPAIGN CONTROL\n"
        "• ⏸️ Pause — Pause running campaign\n"
        "• ⏹️ Stop — Stop running campaign\n"
        "• ⚡ Speed Control — Slow/Normal/Fast in Settings\n\n"
        "📋 AVAILABLE ACTIONS\n"
        "• 👍 React Only\n"
        "• 🗳️ Vote Only\n"
        "• 👍🗳️ React + Vote\n"
        "• 👁️ View Only (NO EMOJI)\n"
        "• 👍👁️ React + View\n"
        "• 🗳️👁️ Vote + View\n"
        "• 👍🗳️👁️ React + Vote + View\n"
        "• ➕ Join Channel\n"
        "• ➖ Leave Channel\n"
        "• 💬 Bulk DM\n\n"
        f"Developed by — {DEVELOPER_LINK}"
    )


def support_text() -> str:
    return (
        "🎧 SUPPORT\n"
        f"👾 Developed by — {DEVELOPER}\n\n"
        "Need help? Contact the developer above."
    )


def all_users_text(users: list) -> str:
    if not users:
        return "👥 No users found."
    text = f"👥 ALL USERS — Total: {len(users)}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in users[:20]:
        role = "👑" if u['is_admin'] else "👤"
        banned = "🚫" if u['is_banned'] else ""
        text += f"{role}{banned} {u['full_name']} | @{u.get('username','N/A')} | ID: {u['user_id']}\n"
    return text


def all_campaigns_text(campaigns: list) -> str:
    if not campaigns:
        return "📋 No campaigns found."
    text = "📋 ALL CAMPAIGNS\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for c in campaigns[:15]:
        text += (
            f"#{c['id']} — {c['action']}\n"
            f"👤 @{c.get('username','N/A')}\n"
            f"🎯 {c['target'][:25]}...\n"
            f"✅ {c['success']} ❌ {c['failed']} | {c['status']}\n"
            f"📅 {c['start_time']}\n\n"
        )
    return text
