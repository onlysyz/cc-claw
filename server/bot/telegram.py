"""CC-Claw Telegram Bot"""

import asyncio
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

from ..config import config
from ..models.db import SessionLocal
from ..services.pairing import PairingService
from ..services.redis import redis_service


logger = logging.getLogger(__name__)


class CCClawBot:
    """Telegram Bot for CC-Claw"""

    def __init__(self):
        self.app: Optional[Application] = None

    async def start(self):
        """Start the bot"""
        if not config.telegram_bot_token:
            logger.error("Telegram bot token not configured")
            return

        self.app = Application.builder().token(config.telegram_bot_token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("pair", self.cmd_pair))
        self.app.add_handler(CommandHandler("unpair", self.cmd_unpair))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Starting Telegram bot...")
        await self.app.run_polling()

    async def cmd_start(self, update: Update, context: CallbackContext):
        """Handle /start command"""
        user = update.effective_user
        await update.message.reply_text(
            f"👋 Hello {user.first_name}!\n\n"
            "Welcome to CC-Claw!\n\n"
            "I help you control Claude Code CLI remotely through Telegram.\n\n"
            "Commands:\n"
            "/pair - Connect your device\n"
            "/unpair - Disconnect your device\n"
            "/status - Check connection status\n"
            "/stop - Stop current session\n"
            "/help - Show this help"
        )

    async def cmd_help(self, update: Update, context: CallbackContext):
        """Handle /help command"""
        await update.message.reply_text(
            "📖 CC-Claw Commands:\n\n"
            "/start - Welcome message\n"
            "/pair - Start pairing process\n"
            "/unpair - Disconnect your device\n"
            "/status - Check connection status\n"
            "/stop - Stop current session\n"
            "/help - Show this help"
        )

    async def cmd_pair(self, update: Update, context: CallbackContext):
        """Handle /pair command"""
        user = update.effective_user

        # Check if already paired
        db = SessionLocal()
        try:
            pairing_service = PairingService(db)
            existing_device = pairing_service.get_user_device(user.id)

            if existing_device:
                await update.message.reply_text(
                    "⚠️ You already have a device paired.\n"
                    "Use /unpair first to pair a new device."
                )
                return

            # Generate pairing code
            code = pairing_service.create_pairing(
                user.id,
                username=user.username,
                first_name=user.first_name,
            )

            await update.message.reply_text(
                f"🔗 Pairing Code: `{code}`\n\n"
                "Enter this code on your device to complete pairing.\n\n"
                "The code expires in 5 minutes.",
                parse_mode="Markdown"
            )
        finally:
            db.close()

    async def cmd_unpair(self, update: Update, context: CallbackContext):
        """Handle /unpair command"""
        user = update.effective_user

        db = SessionLocal()
        try:
            pairing_service = PairingService(db)
            success = pairing_service.unpair_device(user.id)

            if success:
                await update.message.reply_text("✅ Device unpaired successfully!")
            else:
                await update.message.reply_text("❌ No device paired.")
        finally:
            db.close()

    async def cmd_status(self, update: Update, context: CallbackContext):
        """Handle /status command"""
        user = update.effective_user

        db = SessionLocal()
        try:
            pairing_service = PairingService(db)
            device = pairing_service.get_user_device(user.id)

            if device:
                status = redis_service.get_device_status(str(device.id))
                is_online = status == "online"

                await update.message.reply_text(
                    f"📱 Device Status\n\n"
                    f"Name: {device.name}\n"
                    f"Platform: {device.platform}\n"
                    f"Status: {'🟢 Online' if is_online else '🔴 Offline'}"
                )
            else:
                await update.message.reply_text(
                    "❌ No device paired.\n"
                    "Use /pair to connect your device."
                )
        finally:
            db.close()

    async def cmd_stop(self, update: Update, context: CallbackContext):
        """Handle /stop command"""
        # TODO: Send stop signal to device
        await update.message.reply_text("🛑 Stop command sent to device...")

    async def handle_message(self, update: Update, context: CallbackContext):
        """Handle incoming messages"""
        user = update.effective_user
        message_text = update.message.text

        db = SessionLocal()
        try:
            pairing_service = PairingService(db)
            device = pairing_service.get_user_device(user.id)

            if not device:
                await update.message.reply_text(
                    "❌ No device paired.\n"
                    "Use /pair to connect your device."
                )
                return

            # Check if device is online
            status = redis_service.get_device_status(str(device.id))
            if status != "online":
                await update.message.reply_text(
                    "🔴 Your device is offline.\n"
                    "Please make sure cc-claw is running on your device."
                )
                return

            # Forward message to device via Redis pub/sub
            message_data = {
                "chat_id": update.message.chat_id,
                "user_id": user.id,
                "content": message_text,
                "message_id": str(update.message.message_id),
            }

            redis_service.publish_message(str(device.id), message_data)

            # Send "processing" message
            await update.message.reply_text("⏳ Processing...")

        finally:
            db.close()

    async def send_message_to_user(self, telegram_id: int, text: str):
        """Send message to a user"""
        if not self.app:
            return

        await self.app.bot.send_message(chat_id=telegram_id, text=text)

    async def send_photo_to_user(self, telegram_id: int, photo_path: str, caption: str = None):
        """Send photo to a user"""
        if not self.app:
            return

        with open(photo_path, "rb") as photo:
            await self.app.bot.send_photo(chat_id=telegram_id, photo=photo, caption=caption)


# Global bot instance
bot = CCClawBot()


async def send_message(telegram_id: int, text: str):
    """Helper function to send message"""
    await bot.send_message_to_user(telegram_id, text)
