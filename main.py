import asyncio
import logging
from core.loader import bot, dp
from database.db import init_db, AsyncSessionLocal
from database.requests import downgrade_expired_premiums, get_due_scheduled_stories, mark_scheduled_story_posted
from middlewares.db_middleware import DbSessionMiddleware
from handlers import admin, user_setup, business, business_management
from aiogram.types import InputStoryContentPhoto, InputStoryContentVideo
from aiogram.exceptions import TelegramAPIError

PREMIUM_CHECK_INTERVAL_HOURS = 1
STORY_CHECK_INTERVAL_SECONDS = 60

async def premium_expiry_watcher():
    """Fon rejimida muntazam ishlaydi: muddati tugagan premium
    foydalanuvchilarni avtomatik ravishda Freemiumga tushiradi."""
    while True:
        try:
            async with AsyncSessionLocal() as session:
                downgraded = await downgrade_expired_premiums(session)
                if downgraded:
                    logging.info(f"Premium muddati tugagan {downgraded} ta foydalanuvchi Freemiumga tushirildi.")
        except Exception as e:
            logging.error(f"Premium expiry watcher xatoligi: {e}")
        await asyncio.sleep(PREMIUM_CHECK_INTERVAL_HOURS * 3600)

async def scheduled_story_watcher():
    """Fon rejimida muntazam ishlaydi: vaqti kelgan rejalashtirilgan
    hikoyalarni Telegram Business API orqali avtomatik joylaydi."""
    while True:
        try:
            async with AsyncSessionLocal() as session:
                due_stories = await get_due_scheduled_stories(session)
                for story in due_stories:
                    try:
                        content = (
                            InputStoryContentPhoto(photo=story.media_file_id) if story.media_type == "photo"
                            else InputStoryContentVideo(video=story.media_file_id)
                        )
                        await bot.post_story(
                            business_connection_id=story.connection_id,
                            content=content,
                            active_period=story.active_period,
                            caption=story.caption,
                        )
                        await mark_scheduled_story_posted(session, story.id)
                        logging.info(f"Scheduled story {story.id} posted for owner {story.owner_id}")
                    except TelegramAPIError as e:
                        logging.error(f"Failed to post scheduled story {story.id}: {e}")
                        await mark_scheduled_story_posted(session, story.id, failed_reason=str(e))
        except Exception as e:
            logging.error(f"Scheduled story watcher xatoligi: {e}")
        await asyncio.sleep(STORY_CHECK_INTERVAL_SECONDS)

async def main():
    logging.info("Starting database initialization...")
    await init_db()
    logging.info("Database initialized.")

    # Middlewares
    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))

    # Routers
    dp.include_router(admin.router)
    dp.include_router(user_setup.router)
    dp.include_router(business_management.router)
    dp.include_router(business.router)

    # Fon vazifalari: premium muddatlarini va rejalashtirilgan hikoyalarni tekshirish
    asyncio.create_task(premium_expiry_watcher())
    asyncio.create_task(scheduled_story_watcher())

    logging.info("Bot is polling...")
    # await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")