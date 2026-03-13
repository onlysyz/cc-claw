"""CC-Claw Telegram Bot"""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

from ..config import config
from ..services.storage import init_storage
from ..services.redis import simple_storage


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

        # Initialize storage
        init_storage()

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
        telegram_id = user.id

        # Initialize storage
        from ..services.storage import storage

        # Check if already paired
        db_user = storage.get_user(telegram_id)
        if db_user and db_user.get("device_ids"):
            await update.message.reply_text(
                "⚠️ You already have a device paired.\n"
                "Use /unpair first to pair a new device."
            )
            return

        # Get or create user
        if not db_user:
            db_user = storage.create_user(
                telegram_id,
                username=user.username,
                first_name=user.first_name,
            )

        # Generate pairing code
        code, expires_at = storage.create_pairing(db_user["id"])

        await update.message.reply_text(
            f"🔗 Pairing Code: `{code}`\n\n"
            "Enter this code on your device to complete pairing.\n\n"
            "The code expires in 5 minutes.",
            parse_mode="Markdown"
        )

    async def cmd_unpair(self, update: Update, context: CallbackContext):
        """Handle /unpair command"""
        user = update.effective_user
        telegram_id = user.id

        from ..services.storage import storage
        db_user = storage.get_user(telegram_id)

        if not db_user:
            await update.message.reply_text("❌ No device paired.")
            return

        device = storage.get_user_device(db_user["id"])

        if device:
            # Delete device and tokens
            storage.delete_device(device["id"])
            simple_storage.delete_user_device(telegram_id)
            await update.message.reply_text("✅ Device unpaired successfully!")
        else:
            await update.message.reply_text("❌ No device paired.")

    async def cmd_status(self, update: Update, context: CallbackContext):
        """Handle /status command"""
        user = update.effective_user
        telegram_id = user.id

        from ..services.storage import storage
        db_user = storage.get_user(telegram_id)

        if not db_user:
            await update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        device = storage.get_user_device(db_user["id"])

        if device:
            status = simple_storage.get_device_status(device["id"])
            is_online = status == "online"

            await update.message.reply_text(
                f"📱 Device Status\n\n"
                f"Name: {device['name']}\n"
                f"Platform: {device['platform']}\n"
                f"Status: {'🟢 Online' if is_online else '🔴 Offline'}"
            )
        else:
            await update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )

    async def cmd_stop(self, update: Update, context: CallbackContext):
        """Handle /stop command"""
        # TODO: Send stop signal to device
        await update.message.reply_text("🛑 Stop command sent to device...")

    async def handle_message(self, update: Update, context: CallbackContext):
        """Handle incoming messages"""
        user = update.effective_user
        message_text = update.message.text

        from ..services.storage import storage
        db_user = storage.get_user(user.id)

        if not db_user:
            await update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        device = storage.get_user_device(db_user["id"])

        if not device:
            await update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        # Check if device is online
        status = simple_storage.get_device_status(device["id"])
        if status != "online":
            await update.message.reply_text(
                "🔴 Your device is offline.\n"
                "Please make sure cc-claw is running on your device."
            )
            return

        # Store message for device to poll
        message_data = {
            "chat_id": update.message.chat_id,
            "user_id": user.id,
            "content": message_text,
            "message_id": str(update.message.message_id),
        }
        simple_storage.publish_message(device["id"], message_data)

        # Send "processing" message
        await update.message.reply_text("⏳ Processing...")

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
