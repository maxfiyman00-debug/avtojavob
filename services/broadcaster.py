import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

async def send_message(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except TelegramAPIError as e:
        logging.error(f"Target [ID:{user_id}]: failed to send message - {e}")
        return False
    else:
        logging.info(f"Target [ID:{user_id}]: message sent.")
        return True

async def broadcast(bot: Bot, users: list[int], text: str, delay: float = 0.05) -> int:
    count = 0
    try:
        for user_id in users:
            if await send_message(bot, user_id, text):
                count += 1
            await asyncio.sleep(delay)  # Limit API requests
    finally:
        logging.info(f"{count} messages successful sent.")
    return count
