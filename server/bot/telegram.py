"""CC-Claw Telegram Bot"""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

from ..config import config
from ..services.storage import init_storage
from ..services.simple_storage import simple_storage


logger = logging.getLogger(__name__)


class CCClawBot:
    """Telegram Bot for CC-Claw"""

    def __init__(self):
        self.updater: Optional[Updater] = None
        self._running = False

    def start(self):
        """Start the bot"""
        if not config.telegram_bot_token:
            logger.error("Telegram bot token not configured")
            return

        # Initialize storage
        init_storage()

        self.updater = Updater(token=config.telegram_bot_token)

        # Register handlers
        dp = self.updater.dispatcher
        dp.add_handler(CommandHandler("start", self.cmd_start))
        dp.add_handler(CommandHandler("help", self.cmd_help))
        dp.add_handler(CommandHandler("pair", self.cmd_pair))
        dp.add_handler(CommandHandler("pairwith", self.cmd_pairwith))
        dp.add_handler(CommandHandler("unpair", self.cmd_unpair))
        dp.add_handler(CommandHandler("status", self.cmd_status))
        dp.add_handler(CommandHandler("stop", self.cmd_stop))
        dp.add_handler(CommandHandler("tasks", self.cmd_tasks))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_message))

        logger.info("Starting Telegram bot...")
        self.updater.start_polling(drop_pending_updates=True)
        self._running = True

        # Instead of idle(), just keep the bot running
        # The main thread will handle signals
        import time
        while self._running:
            time.sleep(1)
        logger.info("Telegram bot stopped")

    def cmd_start(self, update: Update, context: CallbackContext):
        """Handle /start command"""
        user = update.effective_user
        update.message.reply_text(
            f"👋 Hello {user.first_name}!\n\n"
            "Welcome to CC-Claw!\n\n"
            "I help you control Claude Code CLI remotely through Telegram.\n\n"
            "Commands:\n"
            "/pair - Connect your device\n"
            "/unpair - Disconnect your device\n"
            "/status - Check connection status\n"
            "/stop - Stop current session\n"
            "/tasks - List scheduled tasks\n"
            "/delay <min> <cmd> - Schedule a command\n"
            "/help - Show this help"
        )

    def cmd_help(self, update: Update, context: CallbackContext):
        """Handle /help command"""
        update.message.reply_text(
            "📖 CC-Claw Commands:\n\n"
            "/start - Welcome message\n"
            "/pair - Start pairing process\n"
            "/unpair - Disconnect your device\n"
            "/status - Check connection status\n"
            "/stop - Stop current session\n"
            "/tasks - List scheduled tasks\n"
            "/delay <min> <cmd> - Schedule a command\n"
            "/help - Show this help"
        )

    def cmd_pair(self, update: Update, context: CallbackContext):
        """Handle /pair command"""
        user = update.effective_user
        telegram_id = user.id

        # Initialize storage
        from ..services.storage import storage

        # Check if already paired
        db_user = storage.get_user(telegram_id)
        if db_user and db_user.get("device_ids"):
            update.message.reply_text(
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

        update.message.reply_text(
            f"🔗 Pairing Code: `{code}`\n\n"
            "Enter this code on your device to complete pairing.\n\n"
            "OR - if you want to use device_id/token directly:\n"
            "1. Run 'cc-claw pair' on your device\n"
            "2. Send me: /pairwith <device_id> <token>\n\n"
            "The code expires in 5 minutes.",
            parse_mode="Markdown"
        )

    def cmd_pairwith(self, update: Update, context: CallbackContext):
        """Handle /pairwith command - pair with device_id and token directly"""
        user = update.effective_user
        telegram_id = user.id

        # Initialize storage
        from ..services.storage import storage

        # Check if already paired
        db_user = storage.get_user(telegram_id)
        if db_user and db_user.get("device_ids"):
            update.message.reply_text(
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

        # Parse device_id and token from command args
        args = context.args
        if len(args) < 2:
            update.message.reply_text(
                "Usage: /pairwith <device_id> <token>\n\n"
                "Run 'cc-claw pair' on your device first to get these values."
            )
            return

        device_id = args[0]
        device_token = args[1]

        # Verify the device exists and token is valid
        device = storage.get_device(device_id)
        if not device:
            update.message.reply_text("❌ Device not found. Run 'cc-claw pair' first.")
            return

        # Verify token
        from ..services.storage import FileStorage
        token_data = FileStorage().verify_token(device_token)
        if not token_data or token_data.get("device_id") != device_id:
            update.message.reply_text("❌ Invalid token. Run 'cc-claw pair' again on your device.")
            return

        # Link device to user
        storage.update_user(db_user["id"], device_ids=[device_id])

        update.message.reply_text(
            f"✅ Paired successfully!\n\n"
            f"Device: {device.get('name', device_id)}\n"
            f"Platform: {device.get('platform', 'unknown')}"
        )

    def cmd_unpair(self, update: Update, context: CallbackContext):
        """Handle /unpair command"""
        user = update.effective_user
        telegram_id = user.id

        from ..services.storage import storage
        db_user = storage.get_user(telegram_id)

        if not db_user:
            update.message.reply_text("❌ No device paired.")
            return

        device = storage.get_user_device(db_user["id"])

        if device:
            # Delete device and tokens
            storage.delete_device(device["id"])
            simple_storage.delete_user_device(telegram_id)
            update.message.reply_text("✅ Device unpaired successfully!")
        else:
            update.message.reply_text("❌ No device paired.")

    def cmd_status(self, update: Update, context: CallbackContext):
        """Handle /status command"""
        user = update.effective_user
        telegram_id = user.id

        from ..services.storage import storage
        db_user = storage.get_user(telegram_id)

        if not db_user:
            update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        device = storage.get_user_device(db_user["id"])

        if device:
            status = simple_storage.get_device_status(device["id"])
            is_online = status == "online"

            update.message.reply_text(
                f"📱 Device Status\n\n"
                f"Name: {device['name']}\n"
                f"Platform: {device['platform']}\n"
                f"Status: {'🟢 Online' if is_online else '🔴 Offline'}"
            )
        else:
            update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )

    def cmd_stop(self, update: Update, context: CallbackContext):
        """Handle /stop command"""
        # TODO: Send stop signal to device
        update.message.reply_text("🛑 Stop command sent to device...")

    def cmd_tasks(self, update: Update, context: CallbackContext):
        """Handle /tasks command - list scheduled tasks"""
        user = update.effective_user
        telegram_id = user.id

        from ..services.storage import storage
        db_user = storage.get_user(telegram_id)

        if not db_user:
            update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        device = storage.get_user_device(db_user["id"])

        if not device:
            update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        # Check if device is online
        status = simple_storage.get_device_status(device["id"])
        if status != "online":
            update.message.reply_text(
                "🔴 Your device is offline.\n"
                "Please make sure cc-claw is running on your device."
            )
            return

        # Forward request to device
        message_data = {
            "chat_id": update.message.chat_id,
            "user_id": user.id,
            "content": "/tasks",
            "message_id": str(update.message.message_id),
        }
        simple_storage.publish_message(device["id"], message_data)

        # Send "processing" message
        update.message.reply_text("⏳ Fetching tasks...")

    def stop(self):
        """Stop the bot"""
        self._running = False
        if self.updater:
            self.updater.stop()
        logger.info("Telegram bot stopping...")

    def handle_message(self, update: Update, context: CallbackContext):
        """Handle incoming messages"""
        user = update.effective_user
        message_text = update.message.text

        from ..services.storage import storage
        db_user = storage.get_user(user.id)

        if not db_user:
            update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        device = storage.get_user_device(db_user["id"])

        if not device:
            update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        # Check if device is online
        status = simple_storage.get_device_status(device["id"])
        if status != "online":
            update.message.reply_text(
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
        update.message.reply_text("⏳ Processing...")

    def send_message_to_user(self, telegram_id: int, text: str):
        """Send message to a user"""
        if not self.updater:
            return
        self.updater.bot.send_message(chat_id=telegram_id, text=text)

    def send_photo_to_user(self, telegram_id: int, photo_path: str, caption: str = None):
        """Send photo to a user"""
        if not self.updater:
            return
        with open(photo_path, "rb") as photo:
            self.updater.bot.send_photo(chat_id=telegram_id, photo=photo, caption=caption)


# Global bot instance
bot = CCClawBot()


def send_message(telegram_id: int, text: str):
    """Helper function to send message"""
    bot.send_message_to_user(telegram_id, text)


def send_photo(telegram_id: int, photo_path: str, caption: str = None):
    """Helper function to send photo"""
    bot.send_photo_to_user(telegram_id, photo_path, caption)
