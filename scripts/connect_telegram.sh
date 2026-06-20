#!/usr/bin/env bash
# connect_telegram.sh — בודק דרישות קדם ומכין את השרת לחיבור טלגרם
# ====================================================================
# מריצים את זה על השרת לפני שמתחילים. הוא בודק שהכל מוכן,
# מאמת את Claude אם צריך, ומכוון אותך לדרך הנכונה.
#
#   bash connect_telegram.sh
#
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CONNECT="$HERE/claude_connect.py"
CLAUDE="$HOME/.local/bin/claude"; command -v claude >/dev/null 2>&1 && CLAUDE="$(command -v claude)"

echo "════════════════════════════════════════════════════"
echo "  חיבור טלגרם — בדיקת מוכנות"
echo "════════════════════════════════════════════════════"
echo

# ── 1. Claude Code מותקן? ─────────────────────────────
if [ -x "$CLAUDE" ] || command -v claude >/dev/null 2>&1; then
  VER="$("$CLAUDE" --version 2>/dev/null | head -1)"
  echo "✅ Claude Code: $VER"
  # גרסה 2.1.80+ נדרשת לדרך ה-Channels
  MAJ_OK="$(printf '%s\n' "$VER" | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+' | awk -F. '{print ($1>2)||($1==2&&$2>1)||($1==2&&$2==1&&$3>=80)}')"
  [ "$MAJ_OK" = "1" ] && echo "   → תומך ב-Channels (הדרך הקלה) ✓" \
                      || echo "   → לדרך ה-Channels צריך 2.1.80+. עדכן, או לך על דרך הבוט (custom)."
else
  echo "❌ Claude Code לא מותקן. התקן קודם, ואז חזור הנה."
  exit 1
fi
echo

# ── 2. Bun מותקן? (נדרש ל-Channels) ───────────────────
if command -v bun >/dev/null 2>&1; then
  echo "✅ Bun: $(bun --version 2>/dev/null)"
else
  echo "⚠️  Bun לא מותקן (נדרש לדרך ה-Channels)."
  echo "    להתקנה:  curl -fsSL https://bun.sh/install | bash   ואז פתח טרמינל חדש."
fi
echo

# ── 3. האם Claude מאומת? (הנקודה הכי קריטית) ──────────
echo "── בדיקת אימות Claude ──"
python3 "$CONNECT" check
echo
echo "מריץ בדיקה חיה (זה הקובע)..."
if python3 "$CONNECT" test >/tmp/cl_test.out 2>&1; then
  echo "✅ Claude מאומת ועובד."
  AUTH_OK=1
else
  cat /tmp/cl_test.out
  echo
  echo "❌ Claude לא מאומת / הטוקן פג. צריך להתחבר:"
  echo "     python3 $CONNECT start      # פתח את הלינק ואשר"
  echo "     python3 $CONNECT finish '<הקוד>'"
  echo "     python3 $CONNECT test       # ודא שעובד"
  AUTH_OK=0
fi
rm -f /tmp/cl_test.out
echo

# ── 4. מה הלאה ─────────────────────────────────────────
echo "════════════════════════════════════════════════════"
if [ "${AUTH_OK:-0}" = "1" ]; then
  echo "  מוכן לחבר טלגרם! בחר דרך:"
  echo
  echo "  ▶ הקלה (מומלצת): Claude Code Channels"
  echo "     1. צור בוט אצל @BotFather בטלגרם (קבל TOKEN)"
  echo "     2. בתוך claude:  /plugin install telegram@claude-plugins-official"
  echo "     3. עקוב אחרי ההגדרה — מדביקים את ה-TOKEN, וזהו."
  echo
  echo "  ▶ למתקדמים: בוט Python משלך — ראה ערכת 12-telegram-bot"
else
  echo "  קודם תקן את האימות למעלה, ואז הרץ שוב את הסקריפט הזה."
fi
echo "════════════════════════════════════════════════════"
