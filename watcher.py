#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, re, time, threading, logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Any, Dict, List
import requests
from dotenv import load_dotenv

# Load environment variables from a .env file (if present) before any os.getenv call.
load_dotenv()

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger("moltbook")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _fh = RotatingFileHandler(os.path.join(LOG_DIR, "watcher.log"),
                              maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_fh)

# Map the UI's log levels onto stdlib logging methods.
_LOG_LEVEL_MAP = {"info": "info", "success": "info", "warn": "warning",
                  "alert": "warning", "error": "error"}

MOLTBOOK_API = "https://www.moltbook.com/api/v1/posts"
SORT, LIMIT, INTERVAL = "new", 20, 60
KEYWORDS: List[str] = []
THRESH_NOTIFY, THRESH_DIGEST = 70, 40
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
AI_MIN_INTERVAL, AI_DOWN_COOLDOWN = 10, 300
STATE_FILE, TREND_LOG = "state.json", "trend_log.jsonl"
TREND_WINDOW_SEC = 86400            # entries older than this are ignored / rotated out
TREND_LOG_MAX_BYTES = 1_000_000     # rotate trend_log.jsonl once it grows past ~1MB
TREND_LOG_MAX_LINES = 20_000        # hard cap on retained lines after rotation

shared = {
    "running": False, "logs": [], "posts": [], "trend": [],
    "stats": {"total": 0, "notified": 0, "ai_used": 0},
}
_lock = threading.Lock()

def is_running():
    with _lock:
        return shared["running"]

def add_log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    with _lock:
        shared["logs"].append({"ts": ts, "msg": msg, "level": level})
        shared["logs"] = shared["logs"][-100:]
    getattr(logger, _LOG_LEVEL_MAP.get(level, "info"))(msg)

def redact_text(s):
    s = str(s or "")
    s = re.sub(r"https?://\S+", "[URL]", s)
    return re.sub(r"\b[A-Za-z0-9_\-]{24,}\b", "[TOKEN]", s).strip()

def passes_keyword_filter(title, content):
    if not KEYWORDS: return True
    text = (title + " " + content).lower()
    return any(kw.lower() in text for kw in KEYWORDS)

def rotate_trend_log():
    """Prune trend_log.jsonl when it grows too large.

    Drops entries older than the trend window (which build_trend_keywords ignores
    anyway) and, as a hard backstop, keeps only the most recent lines. The rewrite
    goes through a temp file + os.replace so a crash can't leave a truncated log.
    """
    try:
        if not os.path.exists(TREND_LOG) or os.path.getsize(TREND_LOG) <= TREND_LOG_MAX_BYTES:
            return
        cutoff = int(time.time()) - TREND_WINDOW_SEC
        kept = []
        with open(TREND_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    if int(json.loads(line).get("ts", 0)) > cutoff:
                        kept.append(line if line.endswith("\n") else line + "\n")
                except Exception:
                    continue
        if len(kept) > TREND_LOG_MAX_LINES:
            kept = kept[-TREND_LOG_MAX_LINES:]
        tmp = TREND_LOG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.writelines(kept)
        os.replace(tmp, TREND_LOG)
    except Exception:
        pass

def append_trend_log(text):
    try:
        rotate_trend_log()
        with open(TREND_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "text": redact_text(text)}, ensure_ascii=False) + "\n")
    except: pass

def build_trend_keywords(top_n=10):
    if not os.path.exists(TREND_LOG): return []
    freq = {}
    try:
        with open(TREND_LOG, "r", encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if int(e.get("ts", 0)) > int(time.time()) - TREND_WINDOW_SEC:
                    for t in re.findall(r"[ぁ-んァ-ン一-龥]{3,}|[a-z0-9]{3,}", e.get("text","").lower()):
                        freq[t] = freq.get(t, 0) + 1
    except: pass
    return [{"word": k, "count": v} for k, v in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]]

def analyze_with_openai(title, content, url):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        import random
        return {"importance": random.randint(30,90), "category": random.choice(["Tech","News","Discussion","Other"]),
                "summary_ja": f"【デモ】{title[:30]}...", "should_notify": random.random()>0.7,
                "keywords": (title.split()+["demo"])[:3], "_demo": True}
    snippet = (content or "").strip()[:100]
    user_prompt = f"TITLE: {title}\nURL: {url}\nCONTENT: {snippet}\n以下のJSONのみ返せ: {{importance(0-100), category, summary_ja, should_notify(bool), keywords(list)}}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"model": OPENAI_MODEL, "input": [{"role":"system","content":"JSONのみ返せ。"},{"role":"user","content":user_prompt}]}
    r = requests.post(OPENAI_URL, headers=headers, json=body, timeout=20)
    r.raise_for_status()
    return json.loads(r.json()["output"][0]["content"][0]["text"])

def watcher_loop():
    seen = set()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: seen = set(json.load(f).get("seen", []))
        except: pass
    last_ai_ts = ai_down_until = 0.0
    add_log("👁️ Watcher started", "success")
    while is_running():
        loop_start = time.time()
        try:
            resp = requests.get(MOLTBOOK_API, params={"sort": SORT, "limit": LIMIT}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            posts = data if isinstance(data, list) else data.get("data", [])
            add_log(f"📡 Fetched {len(posts)} posts")
            new_count = 0
            for post in posts:
                pid = str(post.get("id", ""))
                title = post.get("title", "（タイトルなし）")
                content = post.get("content", "")
                url = f"https://www.moltbook.com/post/{pid}"
                if pid in seen: continue
                if not passes_keyword_filter(title, content):
                    seen.add(pid); continue
                append_trend_log(content)
                ai_result = None
                now = time.time()
                if now > ai_down_until and (now - last_ai_ts) > AI_MIN_INTERVAL:
                    try:
                        ai_result = analyze_with_openai(title, content, url)
                        last_ai_ts = now
                        with _lock: shared["stats"]["ai_used"] += 1
                        demo_tag = " [DEMO]" if ai_result.get("_demo") else ""
                        add_log(f"🤖 AI{demo_tag}: {title[:30]}… → 重要度{ai_result.get('importance')}", "info")
                    except Exception as e:
                        ai_down_until = now + AI_DOWN_COOLDOWN
                        add_log(f"⚠️ AI error: {e}", "warn")
                imp = ai_result.get("importance", 0) if ai_result else None
                card = {"id": pid, "title": title, "url": url, "ts": datetime.now().strftime("%H:%M:%S"),
                        "importance": imp, "category": ai_result.get("category") if ai_result else None,
                        "summary_ja": ai_result.get("summary_ja") if ai_result else None,
                        "keywords": ai_result.get("keywords") if ai_result else [],
                        "flagged": bool(ai_result and ai_result.get("should_notify") and imp >= THRESH_NOTIFY)}
                with _lock:
                    shared["posts"].insert(0, card)
                    shared["posts"] = shared["posts"][:50]
                    shared["stats"]["total"] += 1
                    if card["flagged"]: shared["stats"]["notified"] += 1
                if card["flagged"]: add_log(f"🔔 重要: {title[:40]}", "alert")
                seen.add(pid); new_count += 1
            if new_count: add_log(f"✅ {new_count} new posts processed", "success")
            trend = build_trend_keywords()
            with _lock: shared["trend"] = trend
            with open(STATE_FILE, "w") as f: json.dump({"seen": list(seen)[-5000:]}, f)
        except Exception as e: add_log(f"❌ Loop error: {e}", "error")
        elapsed = time.time() - loop_start
        for _ in range(int(max(1, INTERVAL - elapsed))):
            if not is_running(): break
            time.sleep(1)
    add_log("🛑 Watcher stopped", "warn")

def start_watcher():
    with _lock:
        if shared["running"]: return
        shared["running"] = True
    threading.Thread(target=watcher_loop, daemon=True).start()

def stop_watcher():
    with _lock:
        shared["running"] = False
