#!/bin/bash
# ═══════════════════════════════════════════════════════
# SolGuard — Telegram Bot Setup
# ═══════════════════════════════════════════════════════
#
# This script helps you configure Telegram alerts for SolGuard.
#
# Prerequisites:
#   1. A Telegram account
#   2. Your SolGuard .env file
#
# Steps (do these BEFORE running this script):
#   1. Open Telegram and search for @BotFather
#   2. Send: /newbot
#   3. Name it: SolGuard Alerts
#   4. Username: solguard_alerts_bot (or your choice)
#   5. Copy the bot token BotFather gives you
#   6. Start a chat with your new bot (send /start)
#   7. Get your chat ID by visiting:
#      https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
#      Look for "chat":{"id": YOUR_CHAT_ID}
#
# Then run this script with your token and chat ID.
# ═══════════════════════════════════════════════════════

echo "🛡️  SolGuard Telegram Setup"
echo "═══════════════════════════"

if [ -z "$1" ] || [ -z "$2" ]; then
    echo ""
    echo "Usage: ./setup_telegram.sh <BOT_TOKEN> <CHAT_ID>"
    echo ""
    echo "Example:"
    echo "  ./setup_telegram.sh 8680556168:AAEyr5qK3bN... 10508540"
    echo ""
    echo "See the comments at the top of this script for how to get these."
    exit 1
fi

BOT_TOKEN=$1
CHAT_ID=$2

# Test the bot
echo ""
echo "Testing bot connection..."
RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    -d "text=🛡️ SolGuard connected! You'll receive real-time alerts here." \
    -d "parse_mode=Markdown")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "✅ Bot connected! Check your Telegram."
    echo ""
    echo "Add these to your .env file:"
    echo "  TELEGRAM_BOT_TOKEN=${BOT_TOKEN}"
    echo "  TELEGRAM_CHAT_ID=${CHAT_ID}"
else
    echo "❌ Failed to connect. Check your token and chat ID."
    echo "Response: $RESPONSE"
    exit 1
fi
