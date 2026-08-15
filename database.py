import pymongo
from pymongo import MongoClient, ReturnDocument
from datetime import datetime, timedelta
from config import MONGO_URI, MONGO_DB_NAME, DEFAULT_SPEED

_client = None


def get_connection():
    global _client
    if _client is None:
        _client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=8000,
            maxPoolSize=50,
        )
    return _client


def get_db():
    client = get_connection()
    return client[MONGO_DB_NAME]


def init_db():
    db = get_db()
    # Create unique indexes
    db["users"].create_index("user_id", unique=True)
    db["accounts"].create_index("id", unique=True)
    db["accounts"].create_index([("user_id", 1), ("phone", 1)])
    db["accounts"].create_index([("user_id", 1), ("session_string", 1)])
    db["campaigns"].create_index("id", unique=True)
    db["scheduled"].create_index("id", unique=True)


def get_next_sequence(name):
    db = get_db()
    counter = db["counters"].find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return counter["seq"]


# ── USER FUNCTIONS ──────────────────────────────────────────

def get_user(user_id):
    db = get_db()
    return db["users"].find_one({"user_id": int(user_id)})


def upsert_user(user_id, username, full_name, is_admin=0):
    db = get_db()
    user_id = int(user_id)
    existing = get_user(user_id)
    if not existing:
        db["users"].insert_one({
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "is_admin": is_admin,
            "is_banned": 0,
            "speed": DEFAULT_SPEED,
            "global_account_limit": 0,
            "join_date": datetime.now().strftime("%Y-%m-%d"),
            "total_campaigns": 0
        })
    else:
        db["users"].update_one(
            {"user_id": user_id},
            {"$set": {"username": username, "full_name": full_name}}
        )


def is_admin(user_id):
    user = get_user(user_id)
    return user and user.get("is_admin") == 1


def is_banned(user_id):
    user = get_user(user_id)
    return user and user.get("is_banned") == 1


def set_admin(user_id, value=1):
    db = get_db()
    db["users"].update_one({"user_id": int(user_id)}, {"$set": {"is_admin": value}})


def ban_user(user_id, value=1):
    db = get_db()
    db["users"].update_one({"user_id": int(user_id)}, {"$set": {"is_banned": value}})


def set_speed(user_id, speed):
    db = get_db()
    db["users"].update_one({"user_id": int(user_id)}, {"$set": {"speed": speed}})


def set_global_account_limit(user_id, limit):
    db = get_db()
    user_id = int(user_id)
    limit = max(0, int(limit or 0))
    db["users"].update_one(
        {"user_id": user_id},
        {"$set": {"global_account_limit": limit}},
    )
    return limit


def get_global_account_limit(user_id):
    user = get_user(user_id)
    if not user:
        return 0
    try:
        return max(0, int(user.get("global_account_limit") or 0))
    except Exception:
        return 0


def get_granted_users():
    db = get_db()
    return list(
        db["users"]
        .find({"global_account_limit": {"$gt": 0}})
        .sort("global_account_limit", -1)
    )


def get_all_users():
    db = get_db()
    return list(db["users"].find().sort("join_date", -1))


def get_admin_users():
    db = get_db()
    return list(db["users"].find({"is_admin": 1}).sort("join_date", -1))


# ── ACCOUNT FUNCTIONS ────────────────────────────────────────

def _account_unique_key(account):
    phone = account.get("phone")
    if phone:
        return ("phone", str(phone).strip())

    session = account.get("session_string")
    if session:
        return ("session", session)

    return ("id", account.get("id") or str(account.get("_id")))


def unique_accounts(accounts):
    unique = []
    seen = set()
    for account in sorted(accounts, key=lambda a: a.get("id", 0), reverse=True):
        key = _account_unique_key(account)
        if key in seen:
            continue
        seen.add(key)
        unique.append(account)
    return unique


def find_existing_account(user_id, phone=None, session_string=None):
    db = get_db()
    user_id = int(user_id)
    phone = str(phone).strip() if phone else None

    if phone:
        existing = db["accounts"].find_one({"user_id": user_id, "phone": phone}, sort=[("id", -1)])
        if existing:
            return existing

    if session_string:
        existing = db["accounts"].find_one({"user_id": user_id, "session_string": session_string}, sort=[("id", -1)])
        if existing:
            return existing

    return None


def add_account_result(user_id, phone=None, session_string=None):
    db = get_db()
    user_id = int(user_id)
    phone = str(phone).strip() if phone else None

    existing = find_existing_account(user_id, phone=phone, session_string=session_string)
    if existing:
        update = {"status": "active"}
        if phone and not existing.get("phone"):
            update["phone"] = phone
        if session_string:
            update["session_string"] = session_string
        db["accounts"].update_one({"id": existing["id"]}, {"$set": update})
        return {"id": existing["id"], "created": False, "account": existing}

    acc_id = get_next_sequence("accounts")
    account = {
        "id": acc_id,
        "user_id": user_id,
        "phone": phone,
        "session_string": session_string,
        "status": "active",
        "added_date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    db["accounts"].insert_one(account)
    return {"id": acc_id, "created": True, "account": account}


def add_account(user_id, phone=None, session_string=None):
    result = add_account_result(user_id, phone=phone, session_string=session_string)
    return result["id"]


def remove_duplicate_accounts(user_id=None):
    db = get_db()
    query = {}
    if user_id is not None:
        query["user_id"] = int(user_id)

    accounts = list(db["accounts"].find(query).sort("id", -1))
    seen = set()
    remove_ids = []
    for account in accounts:
        key = (account.get("user_id"), _account_unique_key(account))
        if key in seen:
            remove_ids.append(account["id"])
            continue
        seen.add(key)

    if remove_ids:
        db["accounts"].delete_many({"id": {"$in": remove_ids}})

    return len(remove_ids)


def get_accounts(user_id, status=None):
    db = get_db()
    query = {"user_id": int(user_id)}
    if status:
        query["status"] = status
    return unique_accounts(list(db["accounts"].find(query)))


def get_all_active_accounts(user_id):
    return get_accounts(user_id, 'active')


def get_global_active_accounts():
    db = get_db()
    return unique_accounts(list(db["accounts"].find({"status": "active"})))


def get_limited_global_active_accounts(user_id):
    limit = get_global_account_limit(user_id)
    if limit <= 0:
        return []
    return get_global_active_accounts()[:limit]


def mark_account_reaction_cooldown(session_string, minutes=180, reason=None):
    db = get_db()
    until = datetime.utcnow() + timedelta(minutes=int(minutes or 180))
    update = {
        "reaction_cooldown_until": until,
        "last_reaction_limit_at": datetime.utcnow(),
    }
    if reason:
        update["last_reaction_limit_reason"] = str(reason)[:240]
    db["accounts"].update_one({"session_string": session_string}, {"$set": update})
    return until


def clear_expired_reaction_cooldowns():
    db = get_db()
    db["accounts"].update_many(
        {"reaction_cooldown_until": {"$lte": datetime.utcnow()}},
        {"$unset": {"reaction_cooldown_until": "", "last_reaction_limit_reason": ""}},
    )


def split_reaction_ready_accounts(accounts):
    now = datetime.utcnow()
    ready = []
    cooldown = []
    for account in accounts:
        until = account.get("reaction_cooldown_until")
        if until and until > now:
            cooldown.append(account)
        else:
            ready.append(account)
    return ready, cooldown


def remove_account(account_id, user_id):
    db = get_db()
    db["accounts"].delete_one({"id": int(account_id), "user_id": int(user_id)})


def remove_all_accounts(user_id):
    db = get_db()
    db["accounts"].delete_many({"user_id": int(user_id)})


def count_accounts(user_id):
    db = get_db()
    uid = int(user_id)
    user_accounts = unique_accounts(list(db["accounts"].find({"user_id": uid})))
    total = len(user_accounts)
    live = len([a for a in user_accounts if a.get("status") == "active"])
    expired = len([a for a in user_accounts if a.get("status") == "expired"])
    return {'total': total, 'live': live, 'expired': expired}


def get_session_owner_stats():
    db = get_db()
    users_by_id = {u["user_id"]: u for u in db["users"].find({})}
    stats = []

    for user_id in db["accounts"].distinct("user_id"):
        accounts = list(db["accounts"].find({"user_id": int(user_id)}))
        unique = unique_accounts(accounts)
        user = users_by_id.get(int(user_id), {})
        stats.append({
            "user_id": int(user_id),
            "full_name": user.get("full_name") or "",
            "username": user.get("username") or "",
            "raw_total": len(accounts),
            "total": len(unique),
            "active": len([a for a in unique if a.get("status") == "active"]),
            "expired": len([a for a in unique if a.get("status") == "expired"]),
        })

    return sorted(stats, key=lambda row: (row["active"], row["total"], row["raw_total"]), reverse=True)


# ── CAMPAIGN FUNCTIONS ───────────────────────────────────────

def create_campaign(user_id, action, target, total_accounts, emoji=None, emoji_type=None, dm_text=None, option_index=None, scope="user", account_limit=None):
    db = get_db()
    camp_id = get_next_sequence("campaigns")
    doc = {
        "id": camp_id,
        "user_id": int(user_id),
        "action": action,
        "target": target,
        "total_accounts": total_accounts,
        "success": 0,
        "failed": 0,
        "status": "running",
        "control_status": "running",
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "end_time": "",
        "emoji": emoji,
        "emoji_type": emoji_type,
        "scope": scope,
        "account_limit": int(account_limit) if account_limit else None,
    }
    if dm_text is not None:
        doc["dm_text"] = dm_text
    if option_index is not None:
        doc["option_index"] = option_index
    db["campaigns"].insert_one(doc)
    db["users"].update_one({"user_id": int(user_id)}, {"$inc": {"total_campaigns": 1}})
    return camp_id


def finish_campaign(campaign_id, success, failed):
    db = get_db()
    campaign = db["campaigns"].find_one({"id": int(campaign_id)}) or {}
    final_status = "stopped" if campaign.get("control_status") == "stopped" else "done"
    db["campaigns"].update_one(
        {"id": int(campaign_id)},
        {"$set": {
            "success": success,
            "failed": failed,
            "status": final_status,
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M")
        }}
    )


def get_campaign(campaign_id):
    db = get_db()
    return db["campaigns"].find_one({"id": int(campaign_id)})


def set_campaign_control(campaign_id, control_status, actor_id=None):
    db = get_db()
    control_status = str(control_status or "").strip().lower()
    if control_status not in {"running", "paused", "stopped"}:
        raise ValueError("Invalid campaign control status")

    update = {
        "control_status": control_status,
        "control_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if actor_id is not None:
        update["control_actor_id"] = int(actor_id)
    if control_status in {"paused", "stopped"}:
        update["status"] = control_status
    elif control_status == "running":
        update["status"] = "running"

    db["campaigns"].update_one({"id": int(campaign_id)}, {"$set": update})
    return get_campaign(campaign_id)


def get_campaign_control_status(campaign_id):
    campaign = get_campaign(campaign_id) or {}
    return campaign.get("control_status") or campaign.get("status") or "running"


def get_campaigns(user_id):
    db = get_db()
    return list(db["campaigns"].find({"user_id": int(user_id)}).sort("id", -1).limit(20))


def get_all_campaigns():
    db = get_db()
    camps = list(db["campaigns"].find().sort("id", -1).limit(50))
    for c in camps:
        user = db["users"].find_one({"user_id": c["user_id"]})
        c["username"] = user.get("username", "") if user else ""
    return camps


# ── SCHEDULED FUNCTIONS ──────────────────────────────────────

def add_scheduled(user_id, action, target, scheduled_time, emoji=None, emoji_type=None, dm_text=None, option_index=None, scope="user", account_limit=None):
    db = get_db()
    sched_id = get_next_sequence("scheduled")
    doc = {
        "id": sched_id,
        "user_id": int(user_id),
        "action": action,
        "target": target,
        "scheduled_time": scheduled_time,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "emoji": emoji,
        "emoji_type": emoji_type,
        "scope": scope,
        "account_limit": int(account_limit) if account_limit else None,
    }
    if dm_text is not None:
        doc["dm_text"] = dm_text
    if option_index is not None:
        doc["option_index"] = option_index
    db["scheduled"].insert_one(doc)


def get_scheduled(user_id):
    db = get_db()
    return list(db["scheduled"].find({"user_id": int(user_id), "status": "pending"}).sort("scheduled_time", 1))


def cancel_scheduled(scheduled_id, user_id):
    db = get_db()
    db["scheduled"].update_one(
        {"id": int(scheduled_id), "user_id": int(user_id)},
        {"$set": {"status": "cancelled"}}
    )


def get_pending_scheduled():
    db = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return list(db["scheduled"].find({"status": "pending", "scheduled_time": {"$lte": now_str}}))


def mark_scheduled_done(scheduled_id):
    db = get_db()
    db["scheduled"].update_one({"id": int(scheduled_id)}, {"$set": {"status": "done"}})


def update_account_status_by_session(session_string, status, reason=None):
    db = get_db()
    update = {
        "status": status,
        "status_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if reason:
        update["last_error"] = str(reason)[:500]
    db["accounts"].update_one(
        {"session_string": session_string},
        {"$set": update}
    )


def update_account_session(account_id, session_string, status="active"):
    db = get_db()
    db["accounts"].update_one(
        {"id": int(account_id)},
        {"$set": {"session_string": session_string, "status": status}}
    )
