
# =============================================
#   DANGER VOTING BOT - CONFIG
#   Fill in your details below
# =============================================

# Get from @BotFather
BOT_TOKEN = "8950622905:AAHfhQhnHAWlqQdF7aPsqrdYc_yvRewd-3o"

# Your Telegram User IDs (Admins)
ADMIN_IDS = [8267676849, 8845150920]

# Pyrogram API credentials (from my.telegram.org)
API_ID = 37222808
API_HASH = "1a3fffd60cab9a4b30358a3d6db65fbe"

# Bot Settings
BOT_NAME = "Danger Voting Bot"
BOT_USERNAME = "@DangerVotingBot"
DEVELOPER = "@richnagi @BTWDANGER"
DEVELOPER_LINK = "https://t.me/richnagi | https://t.me/BTWDANGER"

# Database
MONGO_URI = "mongodb+srv://narutouzumaki9tail786786_db_user:kaByy8uKMXMFjv2b@cluster0.7uy4mvt.mongodb.net/?appName=Cluster0"
MONGO_DB_NAME = "danger_bot"
DB_NAME = "danger_bot.db"

# Default campaign speed (ms)
DEFAULT_SPEED = 200  # Normal

# Speed options
SPEEDS = {
    "slow": 500,
    "normal": 200,
    "fast": 50
}

# Campaign actions available
CAMPAIGN_ACTIONS = [
    "Auto Premium Reactions",
    "Auto Premium Reactions + View",
    "React Only",
    "Vote Only",
    "React + Vote",
    "Auto Different Reactions",
    "Auto Different Reactions + View",
    "View Only",
    "React + View",
    "Vote + View",
    "React + Vote + View",
    "Join Channel",
    "Leave Channel",
    "Bulk DM"
]
