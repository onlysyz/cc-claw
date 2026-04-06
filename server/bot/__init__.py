"""CC-Claw Bot Package"""

from .telegram import CCClawBot, bot as telegram_bot, send_message as tg_send_message, send_photo as tg_send_photo
from .lark import LarkBot, lark_bot, send_lark_message

__all__ = [
    "CCClawBot",
    "telegram_bot",
    "tg_send_message",
    "tg_send_photo",
    "LarkBot",
    "lark_bot",
    "send_lark_message",
]
