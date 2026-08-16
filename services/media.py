"""
Telegram Business API'ning bir nechta metodlari (setBusinessAccountProfilePhoto,
postStory) ODDIY file_id'ni qabul qilmaydi - Telegram bu funksiyalar uchun
faylni albatta YANGIDAN yuklashni talab qiladi ("Profile photos can't be
reused and can only be uploaded as a new file").

Shu sabab, botimiz avval qandaydir file_id orqali olingan faylni (masalan
foydalanuvchi bizga yuborgan rasm/video) yuklab olib, keyin uni qayta,
yangi fayl sifatida Telegram'ga jo'natishi kerak.
"""
from aiogram import Bot
from aiogram.types import BufferedInputFile


async def download_as_input_file(bot: Bot, file_id: str, filename: str) -> BufferedInputFile:
    buffer = await bot.download(file_id)
    return BufferedInputFile(buffer.read(), filename=filename)
