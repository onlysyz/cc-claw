"""CC-Claw Telegram Bot - with Onboarding Flow"""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

from ..config import config
from ..services.storage import init_storage
from ..services.simple_storage import simple_storage


logger = logging.getLogger(__name__)

# Onboarding states
ONBOARDING_STEPS = [
    ("profession", "🏠 What is your profession?\n\n(e.g. Software Engineer, Student, Designer, Writer...)"),
    ("situation", "📍 What is your current situation?\n\n(e.g. Working on a project, Learning to code, Looking for a job...)"),
    ("goal", "🎯 What is your short-term goal?\n\n(e.g. Finish my portfolio, Learn React, Launch my startup...)"),
    ("better", "✨ What does 'better' look like for you?\n\n(e.g. More productive, Better organized, More confident in coding...)"),
]

STEP_NEXT = {
    "pending": "profession",
    "profession": "situation",
    "situation": "goal",
    "goal": "better",
    "better": "complete",
}


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
        dp.add_handler(CommandHandler("onboarding", self.cmd_onboarding))
        dp.add_handler(CommandHandler("progress", self.cmd_progress))
        dp.add_handler(CommandHandler("pause", self.cmd_pause))
        dp.add_handler(CommandHandler("resume", self.cmd_resume))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_message))

        logger.info("Starting Telegram bot...")
        self.updater.start_polling(drop_pending_updates=True)
        self._running = True

        import time
        while self._running:
            time.sleep(1)
        logger.info("Telegram bot stopped")

    # --- Commands ---

    def cmd_start(self, update: Update, context: CallbackContext):
        """Handle /start command"""
        user = update.effective_user
        from ..services.storage import storage

        db_user = storage.get_user(user.id)
        if not db_user:
            db_user = storage.create_user(
                user.id,
                username=user.username,
                first_name=user.first_name,
            )

        # Check if onboarding complete
        state = db_user.get("onboarding_state", "pending")
        if state != "complete":
            # Start onboarding
            return self._start_onboarding(update, db_user)

        update.message.reply_text(
            f"👋 Hello {user.first_name}!\n\n"
            "Welcome back to CC-Claw!\n"
            "Your AI partner is always working for you.\n\n"
            "Commands:\n"
            "/progress - View goal progress\n"
            "/pause - Pause autonomous mode\n"
            "/resume - Resume autonomous mode\n"
            "/tasks - List current tasks\n"
            "/status - Check connection\n"
            "/onboarding - Redo onboarding\n"
            "/help - Show all commands"
        )

    def cmd_help(self, update: Update, context: CallbackContext):
        """Handle /help command"""
        update.message.reply_text(
            "📖 CC-Claw Commands:\n\n"
            "/start - Welcome + onboarding\n"
            "/progress - View progress & token stats\n"
            "/pause - Pause autonomous execution\n"
            "/resume - Resume autonomous execution\n"
            "/tasks - List task queue\n"
            "/goals - Manage goals\n"
            "/status - Connection status\n"
            "/onboarding - Redo onboarding\n"
            "/help - Show this help"
        )

    def cmd_onboarding(self, update: Update, context: CallbackContext):
        """Handle /onboarding - restart onboarding"""
        from ..services.storage import storage
        user = update.effective_user
        db_user = storage.get_user(user.id)
        if not db_user:
            db_user = storage.create_user(user.id, username=user.username, first_name=user.first_name)

        return self._start_onboarding(update, db_user)

    def cmd_progress(self, update: Update, context: CallbackContext):
        """Handle /progress command"""
        user = update.effective_user
        from ..services.storage import storage

        db_user = storage.get_user(user.id)
        if not db_user or not db_user.get("device_ids"):
            update.message.reply_text("❌ No device paired. Use /pair first.")
            return

        device = storage.get_user_device(db_user["id"])
        if not device:
            update.message.reply_text("❌ No device paired.")
            return

        # Check if device is online
        status_val = simple_storage.get_device_status(device["id"])
        if status_val != "online":
            update.message.reply_text("🔴 Device is offline. CC-Claw is not running.")
            return

        # Forward request to device
        message_data = {
            "chat_id": update.message.chat_id,
            "user_id": user.id,
            "content": "/progress",
            "message_id": str(update.message.message_id),
        }
        simple_storage.publish_message(device["id"], message_data)
        update.message.reply_text("⏳ Fetching your progress report...")

    def cmd_pause(self, update: Update, context: CallbackContext):
        """Handle /pause command"""
        user = update.effective_user
        from ..services.storage import storage

        db_user = storage.get_user(user.id)
        if not db_user or not db_user.get("device_ids"):
            update.message.reply_text("❌ No device paired.")
            return

        device = storage.get_user_device(db_user["id"])
        if not device:
            update.message.reply_text("❌ No device paired.")
            return

        status_val = simple_storage.get_device_status(device["id"])
        if status_val != "online":
            update.message.reply_text("🔴 Device is offline.")
            return

        message_data = {
            "chat_id": update.message.chat_id,
            "user_id": user.id,
            "content": "/pause",
            "message_id": str(update.message.message_id),
        }
        simple_storage.publish_message(device["id"], message_data)
        update.message.reply_text("⏸️ Pause signal sent...")

    def cmd_resume(self, update: Update, context: CallbackContext):
        """Handle /resume command"""
        user = update.effective_user
        from ..services.storage import storage

        db_user = storage.get_user(user.id)
        if not db_user or not db_user.get("device_ids"):
            update.message.reply_text("❌ No device paired.")
            return

        device = storage.get_user_device(db_user["id"])
        if not device:
            update.message.reply_text("❌ No device paired.")
            return

        status_val = simple_storage.get_device_status(device["id"])
        if status_val != "online":
            update.message.reply_text("🔴 Device is offline.")
            return

        message_data = {
            "chat_id": update.message.chat_id,
            "user_id": user.id,
            "content": "/resume",
            "message_id": str(update.message.message_id),
        }
        simple_storage.publish_message(device["id"], message_data)
        update.message.reply_text("▶️ Resume signal sent...")

    def cmd_pair(self, update: Update, context: CallbackContext):
        """Handle /pair command"""
        user = update.effective_user
        telegram_id = user.id

        from ..services.storage import storage

        db_user = storage.get_user(telegram_id)
        if db_user and db_user.get("device_ids"):
            update.message.reply_text(
                "⚠️ You already have a device paired.\n"
                "Use /unpair first to pair a new device."
            )
            return

        if not db_user:
            db_user = storage.create_user(
                telegram_id,
                username=user.username,
                first_name=user.first_name,
            )

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
        """Handle /pairwith command"""
        user = update.effective_user
        telegram_id = user.id

        from ..services.storage import storage

        db_user = storage.get_user(telegram_id)
        if db_user and db_user.get("device_ids"):
            update.message.reply_text(
                "⚠️ You already have a device paired.\n"
                "Use /unpair first to pair a new device."
            )
            return

        if not db_user:
            db_user = storage.create_user(
                telegram_id,
                username=user.username,
                first_name=user.first_name,
            )

        args = context.args
        if len(args) < 2:
            update.message.reply_text(
                "Usage: /pairwith <device_id> <token>\n\n"
                "Run 'cc-claw pair' on your device first to get these values."
            )
            return

        device_id = args[0]
        device_token = args[1]

        device = storage.get_device(device_id)
        if not device:
            update.message.reply_text("❌ Device not found. Run 'cc-claw pair' first.")
            return

        from ..services.storage import FileStorage
        token_data = FileStorage().verify_token(device_token)
        if not token_data or token_data.get("device_id") != device_id:
            update.message.reply_text("❌ Invalid token. Run 'cc-claw pair' again on your device.")
            return

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
            status_val = simple_storage.get_device_status(device["id"])
            is_online = status_val == "online"
            state = db_user.get("onboarding_state", "pending")

            update.message.reply_text(
                f"📱 Device Status\n\n"
                f"Name: {device['name']}\n"
                f"Platform: {device['platform']}\n"
                f"Status: {'🟢 Online' if is_online else '🔴 Offline'}\n"
                f"Onboarding: {'✅ Complete' if state == 'complete' else '⏳ Incomplete'}"
            )
        else:
            update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )

    def cmd_stop(self, update: Update, context: CallbackContext):
        """Handle /stop command"""
        update.message.reply_text("🛑 Stop command sent to device...")

    def cmd_tasks(self, update: Update, context: CallbackContext):
        """Handle /tasks command"""
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

        status_val = simple_storage.get_device_status(device["id"])
        if status_val != "online":
            update.message.reply_text(
                "🔴 Device is offline.\n"
                "Please make sure cc-claw is running on your device."
            )
            return

        message_data = {
            "chat_id": update.message.chat_id,
            "user_id": user.id,
            "content": "/tasks",
            "message_id": str(update.message.message_id),
        }
        simple_storage.publish_message(device["id"], message_data)
        update.message.reply_text("⏳ Fetching tasks...")

    # --- Onboarding Flow ---

    def _start_onboarding(self, update: Update, db_user: dict):
        """Start the onboarding flow"""
        from ..services.storage import storage

        storage.set_onboarding_state(db_user["id"], "profession", {})
        first_question = ONBOARDING_STEPS[0][1]
        update.message.reply_text(
            f"👋 Let's get to know you!\n\n"
            f"{first_question}\n\n"
            "Just type your answer — I'll guide you through the rest."
        )

    def handle_message(self, update: Update, context: CallbackContext):
        """Handle incoming messages — routes to onboarding or normal flow"""
        user = update.effective_user
        message_text = update.message.text

        from ..services.storage import storage
        db_user = storage.get_user(user.id)

        if not db_user:
            db_user = storage.create_user(
                user.id,
                username=user.username,
                first_name=user.first_name,
            )

        # Check onboarding state
        state = db_user.get("onboarding_state", "pending")
        if state != "complete":
            return self._handle_onboarding_message(update, db_user, message_text)

        # Normal flow — forward to device
        return self._handle_normal_message(update, db_user, message_text)

    def _handle_onboarding_message(self, update: Update, db_user: dict, message_text: str):
        """Handle messages during onboarding"""
        from ..services.storage import storage

        state = db_user.get("onboarding_state", "pending")
        onboarding_data = db_user.get("onboarding_data", {})

        # Map current state to step index
        step_map = {k: i for i, (k, _) in enumerate(ONBOARDING_STEPS)}
        next_state = STEP_NEXT.get(state, "complete")

        if state in step_map:
            # Save answer for current step
            step_key = state
            onboarding_data[step_key] = message_text.strip()

        if next_state == "complete":
            # Onboarding complete — save profile to device
            storage.set_onboarding_state(db_user["id"], "complete", onboarding_data)
            logger.info(f"Onboarding complete for user {db_user['id']}: {onboarding_data}")

            # Forward profile to paired device if exists
            if db_user.get("device_ids"):
                device = storage.get_user_device(db_user["id"])
                if device:
                    profile_msg = {
                        "type": "profile",
                        "action": "save_profile",
                        "data": {
                            "profession": onboarding_data.get("profession", ""),
                            "situation": onboarding_data.get("situation", ""),
                            "short_term_goal": onboarding_data.get("goal", ""),
                            "what_better_means": onboarding_data.get("better", ""),
                        },
                        "chat_id": update.message.chat_id,
                        "user_id": db_user["telegram_id"],
                    }
                    simple_storage.publish_message(device["id"], profile_msg)

            update.message.reply_text(
                "✅ Onboarding complete!\n\n"
                f"📋 Summary:\n"
                f"• Profession: {onboarding_data.get('profession', 'N/A')}\n"
                f"• Situation: {onboarding_data.get('situation', 'N/A')}\n"
                f"• Goal: {onboarding_data.get('goal', 'N/A')}\n"
                f"• Better: {onboarding_data.get('better', 'N/A')}\n\n"
                "🎯 Your AI partner is now working for you.\n"
                "Type /progress anytime to check your status."
            )

        else:
            # Move to next step
            storage.set_onboarding_state(db_user["id"], next_state, onboarding_data)

            # Find the question for next step
            step_idx = step_map.get(next_state, 0)
            if step_idx < len(ONBOARDING_STEPS):
                _, question = ONBOARDING_STEPS[step_idx]
                update.message.reply_text(question)
            else:
                update.message.reply_text("Something went wrong. Try /onboarding again.")

    def _handle_normal_message(self, update: Update, db_user: dict, message_text: str):
        """Handle regular messages — forward to device"""
        from ..services.storage import storage

        device = storage.get_user_device(db_user["id"])

        if not device:
            update.message.reply_text(
                "❌ No device paired.\n"
                "Use /pair to connect your device."
            )
            return

        status_val = simple_storage.get_device_status(device["id"])
        if status_val != "online":
            update.message.reply_text(
                "🔴 Device is offline.\n"
                "Please make sure cc-claw is running on your device."
            )
            return

        message_data = {
            "chat_id": update.message.chat_id,
            "user_id": db_user["telegram_id"],
            "content": message_text,
            "message_id": str(update.message.message_id),
            "priority": True,  # user message — high priority
        }
        simple_storage.publish_message(device["id"], message_data)
        update.message.reply_text("⏳ Processing...")

    # --- Bot control ---

    def stop(self):
        """Stop the bot"""
        self._running = False
        if self.updater:
            self.updater.stop()
        logger.info("Telegram bot stopping...")

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
