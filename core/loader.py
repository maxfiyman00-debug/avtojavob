from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from core.config import config
import logging

logging.basicConfig(level=logging.INFO)

if not config.bot_token:
    logging.warning("BOT_TOKEN is not set!")

bot = Bot(token=config.bot_token or "PLACEHOLDER", default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
