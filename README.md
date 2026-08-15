# 🔥 Danger Voting Bot

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram)
![License](https://img.shields.io/badge/License-Private-red?style=for-the-badge)

**⚡ Advanced Telegram Automation Bot — React • Vote • View • DM • Join/Leave**

*Developer: [@richnagi](https://t.me/richnagi)*

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 👍 **React** | Auto-react on posts with custom/premium emojis |
| 🗳️ **Vote** | Auto-vote on polls/inline buttons |
| 👁️ **View** | Auto-view stories and posts |
| 💬 **Bulk DM** | Send bulk direct messages to users |
| ➕ **Join** | Auto-join channels/groups |
| ➖ **Leave** | Auto-leave channels/groups |
| 📅 **Scheduled** | Schedule campaigns with date/time |
| 🎭 **Multi-Account** | Run campaigns across multiple accounts |
| 🔥 **Admin Panel** | Full admin controls with user management |
| ⚡ **Speed Control** | Slow / Normal / Fast campaign speed |

---

## 🚀 Setup

### Requirements

```
python 3.10+
pyrogram
python-telegram-bot
```

### Installation

```bash
# Clone the repo
git clone https://github.com/OGAbdulOfficial/dangerclintebot.git
cd dangerclintebot

# Install dependencies
pip install -r requirements.txt

# Configure the bot
cp config.py.example config.py
# Edit config.py with your credentials
```

### Configuration (`config.py`)

```python
BOT_TOKEN = "your_bot_token_here"       # From @BotFather
ADMIN_IDS = [123456789]                  # Your Telegram User ID
API_ID = 12345                           # From my.telegram.org
API_HASH = "your_api_hash"               # From my.telegram.org
BOT_NAME = "Danger Voting Bot"
DEVELOPER = "@richnagi"
DEVELOPER_LINK = "https://t.me/richnagi"
```

### Run

```bash
python bot.py
```

---

## 📖 Usage

### Adding Accounts

1. Open the bot → **➕ Add Account**
2. Choose method:
   - 📱 **Phone + OTP** — Enter phone number and verification code
   - 🔑 **Session String** — Paste existing Pyrogram session string
   - 📦 **Bulk Sessions** — Add multiple sessions at once

### Running a Campaign

1. Click **🚀 New Campaign**
2. Select campaign type (React / Vote / View / DM / Join / Leave)
3. Enter post/poll/channel link
4. Set target count
5. Run immediately or schedule for later

### Campaign Types

| Type | What it does |
|------|-------------|
| 👍 React Only | React on a post with selected emoji |
| 🗳️ Vote Only | Click inline poll/vote button |
| 👍🗳️ React + Vote | React AND vote |
| 👁️ View Only | View story/post |
| 💬 Bulk DM | DM all users in a group |
| ➕ Join Channel | Join a channel/group |
| ➖ Leave Channel | Leave a channel/group |

### Admin Panel

Admin users get access to:
- 📢 Run campaigns on **ALL accounts** in the bot
- 🎯 Run campaigns for a **specific user's accounts**
- 👥 View/manage all users
- ✅ Make/Remove admins
- 🚫 Ban/Unban users
- 🔍 Check session health
- 🧹 Clean expired sessions
- ⚡ Control global speed

---

## 🗂️ Project Structure

```
dangerclintebot/
├── bot.py          # Main bot logic, handlers, campaign engine
├── database.py     # SQLite database operations
├── config.py       # Bot configuration (not committed)
├── messages.py     # Message text templates
├── keyboards.py    # PTB keyboard builders (legacy)
├── requirements.txt
└── README.md
```

---

## ⚙️ Tech Stack

- **[Pyrogram](https://pyrogram.org/)** — MTProto Telegram client (for user account actions)
- **Telegram Bot API** — Raw HTTP polling (no PTB dependency)
- **SQLite** — Local database for accounts, campaigns, users
- **Python Threading** — Concurrent campaign execution

---

## 🔒 Security Notes

> [!CAUTION]
> - Never share your `config.py` or `danger_bot.db` files — they contain sensitive tokens and session data
> - Session strings give full account access — treat them like passwords
> - This bot is for **educational/personal use only**

---

## 📞 Support

- Developer: [@richnagi](https://t.me/richnagi)

---

<div align="center">
Made with ❤️ by <b>@richnagi</b>
</div>
