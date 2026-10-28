#!/bin/bash
# 出勤一覧の自動更新（macOS launchd）を登録／解除する
#   ./autoupdate.sh install [分]   … 指定分ごとに更新（既定 30分）
#   ./autoupdate.sh uninstall      … 自動更新を止める
#   ./autoupdate.sh status         … 登録状態と最新ログを表示
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.harekei.schedule"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$DIR/autoupdate.log"

case "${1:-}" in
install)
  MIN="${2:-30}"
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/python3</string><string>$DIR/build_schedule.py</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>StartInterval</key><integer>$((MIN * 60))</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  echo "登録しました: ${MIN}分ごとに更新（ログ: $LOG）"
  ;;
uninstall)
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "自動更新を停止しました"
  ;;
status)
  launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -E "state|last exit" || echo "未登録"
  [ -f "$LOG" ] && tail -3 "$LOG"
  ;;
*)
  sed -n '2,5p' "$0"
  ;;
esac
