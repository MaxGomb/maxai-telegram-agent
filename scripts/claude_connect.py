#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
claude_connect.py — חיבור Claude לשרת (מנוי Max/Pro) בלי כאב ראש
================================================================
הכלי הזה פותר את החלק הכי מבלבל בהתקנת סוכן על שרת: לאמת את Claude.

למה צריך אותו?
  מסך ההתחברות של claude (`claude auth login`) דורש מסך-מגע אמיתי (TTY),
  ועל שרת מרוחק זה מסתבך — וגם נשבר כל כמה חודשים כשהטוקן פג ("401").
  הכלי הזה עוקף את המסך הזה: מייצר לינק, אתה מאשר בדפדפן, מדביק קוד — וזהו.

שימוש:
  python3 claude_connect.py check       # בדיקת דרישות קדם + מצב התחברות
  python3 claude_connect.py start       # מדפיס לינק התחברות (פתח בדפדפן ואשר)
  python3 claude_connect.py finish CODE # מדביק את הקוד שקיבלת ומסיים
  python3 claude_connect.py test        # בדיקה חיה ש-Claude עונה

הערה: עובד עם מנוי Claude (Max/Pro). אין צורך ב-API key בתשלום.
"""

import sys, os, json, time, secrets, hashlib, base64, subprocess, shutil
import urllib.request, urllib.error
from urllib.parse import urlencode

# --- קבועים של זרימת ה-OAuth של Claude Code (ציבוריים) ---
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
REDIRECT  = "https://platform.claude.com/oauth/code/callback"
SCOPES    = "org:create_api_key user:profile user:inference user:sessions:claude_code user:mcp_servers"
AUTH_URL  = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"   # אומת מתוך ה-CLI עצמו

PKCE_FILE = os.path.expanduser("~/.cache/claude_connect_pkce.json")
CRED      = os.path.expanduser("~/.claude/.credentials.json")
CLAUDE    = os.path.expanduser("~/.local/bin/claude")
if not os.path.exists(CLAUDE):
    CLAUDE = shutil.which("claude") or CLAUDE


def b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _say(msg):
    print(msg, flush=True)


# ============================================================
# check — דרישות קדם + מצב נוכחי
# ============================================================
def check():
    ok = True
    # claude מותקן?
    if os.path.exists(CLAUDE) or shutil.which("claude"):
        try:
            v = subprocess.run([CLAUDE, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
            _say(f"✅ Claude Code מותקן: {v}")
        except Exception:
            _say("⚠️  Claude קיים אבל לא הגיב ל---version")
    else:
        _say("❌ Claude Code לא מותקן. התקן קודם: https://claude.ai/download")
        ok = False
    # מצב התחברות
    try:
        st = subprocess.run([CLAUDE, "auth", "status"], capture_output=True, text=True, timeout=15).stdout
        data = json.loads(st) if st.strip().startswith("{") else {}
        if data.get("loggedIn"):
            _say(f"ℹ️  סטטוס: מחובר (לפי הקובץ). מנוי: {data.get('subscriptionType','?')}")
            _say("    ⚠️  שים לב: 'מחובר' לא תמיד אומר שהטוקן תקף. הרץ `test` לבדיקה אמיתית.")
        else:
            _say("ℹ️  סטטוס: לא מחובר. הרץ `start` כדי להתחבר.")
    except Exception as e:
        _say(f"⚠️  לא הצלחתי לקרוא auth status: {e}")
    # קובץ טוקן + תוקף
    if os.path.exists(CRED):
        try:
            o = json.load(open(CRED))["claudeAiOauth"]
            exp = o.get("expiresAt", 0) / 1000
            human = time.strftime("%Y-%m-%d %H:%M", time.localtime(exp))
            left = (exp - time.time()) / 3600
            _say(f"🔑 טוקן קיים, פג: {human} ({left:.1f} שעות מעכשיו) | יש refresh: {bool(o.get('refreshToken'))}")
        except Exception:
            _say("⚠️  קובץ טוקן קיים אבל לא קריא.")
    else:
        _say("🔑 אין קובץ טוקן עדיין.")
    return ok


# ============================================================
# start — מייצר לינק התחברות
# ============================================================
def start():
    verifier  = b64url(secrets.token_bytes(32))
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    state     = b64url(secrets.token_bytes(24))
    os.makedirs(os.path.dirname(PKCE_FILE), exist_ok=True)
    json.dump({"verifier": verifier, "state": state}, open(PKCE_FILE, "w"))
    q = urlencode({
        "code": "true", "client_id": CLIENT_ID, "response_type": "code",
        "redirect_uri": REDIRECT, "scope": SCOPES,
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
    })
    _say("")
    _say("1) פתח את הלינק הבא בדפדפן והתחבר עם החשבון שלך:")
    _say("")
    _say("   " + AUTH_URL + "?" + q)
    _say("")
    _say("2) אחרי האישור תקבל קוד (בסגנון  xxxx#yyyy). העתק אותו.")
    _say("3) הרץ:  python3 claude_connect.py finish '<הקוד-שהעתקת>'")
    _say("")


# ============================================================
# finish — חילופי הטוקן + כתיבת קובץ ההזדהות
# ============================================================
def finish(raw):
    raw = raw.strip().strip("'\"")
    if not os.path.exists(PKCE_FILE):
        _say("❌ לא נמצאה התחלה. הרץ קודם: python3 claude_connect.py start"); return 1
    p = json.load(open(PKCE_FILE))
    code = raw.split("#", 1)[0]
    st   = raw.split("#", 1)[1] if "#" in raw else ""
    if st and st != p["state"]:
        _say("❌ הקוד לא תואם לבקשה הזו (state שונה). הרץ `start` שוב וקח קוד טרי."); return 1
    body = {
        "grant_type": "authorization_code", "code": code, "state": st,
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT, "code_verifier": p["verifier"],
    }
    req = urllib.request.Request(
        TOKEN_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "claude-cli"},
        method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30); status = resp.status; text = resp.read().decode()
    except urllib.error.HTTPError as e:
        status = e.code; text = e.read().decode()
    except Exception as e:
        _say(f"❌ הבקשה נכשלה (אינטרנט?): {e}"); return 1
    if status != 200:
        _say(f"❌ החילופין נכשלו (HTTP {status}). כנראה הקוד פג — הרץ `start` שוב.")
        _say("   פרטים: " + text[:300]); return 1
    d = json.loads(text)
    scopes = d.get("scope", "").split() if d.get("scope") else SCOPES.split()
    expires_at = int(time.time() * 1000) + int(d.get("expires_in", 28800)) * 1000
    cred = {"claudeAiOauth": {
        "accessToken":  d.get("access_token", ""),
        "refreshToken": d.get("refresh_token", ""),
        "expiresAt":    expires_at,
        "scopes":       scopes,
        "subscriptionType": d.get("subscription_type") or "max",
    }}
    os.makedirs(os.path.dirname(CRED), exist_ok=True)
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CRED))
    with os.fdopen(fd, "w") as f:
        json.dump(cred, f)
    os.chmod(tmp, 0o600); os.replace(tmp, CRED); os.chmod(CRED, 0o600)
    try:
        os.remove(PKCE_FILE)
    except OSError:
        pass
    _say("✅ התחברת! הטוקן נשמר.")
    _say("   עכשיו הרץ בדיקה חיה:  python3 claude_connect.py test")
    return 0


# ============================================================
# test — בדיקת inference חיה (המבחן האמיתי)
# ============================================================
def test():
    _say("בודק ש-Claude עונה באמת (לא 401)... רגע.")
    try:
        r = subprocess.run(
            [CLAUDE, "--print", "--dangerously-skip-permissions", "Reply with exactly one word: PONG"],
            capture_output=True, text=True, timeout=120)
        out = (r.stdout or "").strip()
        if "PONG" in out.upper():
            _say("✅ עובד! Claude מאומת ומגיב. אפשר להמשיך לחבר טלגרם.")
            return 0
        _say("❌ לא קיבלתי תשובה תקינה.")
        _say("   פלט: " + (out[:300] or "(ריק)"))
        if "401" in out or "authentication" in out.lower():
            _say("   זו שגיאת 401 — הטוקן לא תקף. הרץ שוב: start → finish.")
        return 1
    except subprocess.TimeoutExpired:
        _say("⚠️  לקח יותר מדי זמן. נסה שוב."); return 1
    except Exception as e:
        _say(f"❌ שגיאה: {e}"); return 1


USAGE = "שימוש: python3 claude_connect.py [check|start|finish '<code>'|test]"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        _say(USAGE); sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "check":   sys.exit(0 if check() else 1)
    elif cmd == "start": start()
    elif cmd == "finish":
        if len(sys.argv) < 3: _say("חסר קוד. " + USAGE); sys.exit(2)
        sys.exit(finish(sys.argv[2]))
    elif cmd == "test":  sys.exit(test())
    else:
        _say(USAGE); sys.exit(2)
