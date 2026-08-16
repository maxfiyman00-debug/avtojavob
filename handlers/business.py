from aiogram import Router, F, Bot
from aiogram.types import Message, BusinessConnection
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime

from database.requests import (
    update_user_connection, get_user_by_connection, get_user_auto_reply, get_user_social_links,
    get_or_create_user, has_replied_to_customer, mark_replied_to_customer, upsert_business_chat,
    find_matching_keyword_reply, is_within_working_hours, increment_auto_reply_count,
)
from keyboards.user_kb import build_business_links_kb

router = Router()

@router.business_connection()
async def handle_business_connection(connection: BusinessConnection, session: AsyncSession):
    user_id = connection.user_chat_id
    # Foydalanuvchi bazada mavjud emasligi mumkin (agar u botga /start bosmasdan
    # to'g'ridan-to'g'ri Telegram Business orqali ulagan bo'lsa). Shu sabab
    # avval qatorni yaratib olamiz, aks holda keyingi UPDATE hech narsaga
    # ta'sir qilmay, connection_id saqlanmay qolardi.
    full_name = connection.user.full_name if connection.user else None
    await get_or_create_user(session, user_id, full_name)

    if connection.is_enabled:
        logging.info(f"User {user_id} enabled business connection: {connection.id}")
        await update_user_connection(session, user_id, connection.id)
    else:
        logging.info(f"User {user_id} disabled business connection")
        await update_user_connection(session, user_id, None)

@router.business_message()
async def handle_business_message(message: Message, session: AsyncSession, bot: Bot):
    logging.info(f"Received business_message from {message.from_user.id} in chat {message.chat.id}")
    connection_id = message.business_connection_id
    if not connection_id:
        return
        
    owner = await get_user_by_connection(session, connection_id)
    if not owner:
        logging.warning(f"Owner not found for connection {connection_id}")
        return

    if message.from_user.id == owner.user_id:
        # Owner o'zi yozgan xabar - "yuborilgan xabarni o'chirish" funksiyasi
        # uchun uni so'nggi chiqgan xabar sifatida eslab qolamiz, lekin
        # avto-javob berilmaydi.
        await upsert_business_chat(
            session, owner.user_id, connection_id, message.chat.id,
            outgoing_message_id=message.message_id,
        )
        return

    # Mijozdan kelgan xabarni "so'nggi kirgan xabar" sifatida eslab qolamiz
    await upsert_business_chat(
        session, owner.user_id, connection_id, message.chat.id,
        incoming_message_id=message.message_id,
    )

    # "Xabarlarni avtomatik o'qilgan deb belgilash" yoqilgan bo'lsa
    if owner.auto_mark_read:
        try:
            await bot.read_business_message(
                business_connection_id=connection_id,
                chat_id=message.chat.id,
                message_id=message.message_id,
            )
        except TelegramAPIError as e:
            logging.error(f"Error marking business message as read: {e}")

    # --- Kalit so'zga asoslangan avtojavob ---
    # Bu umumiy "faqat birinchi murojaatga javob" cheklovidan mustasno:
    # mijoz har safar shu kalit so'zni yozganda mos javob yuboriladi.
    keyword_reply = await find_matching_keyword_reply(session, owner.user_id, message.text or message.caption)
    if keyword_reply:
        try:
            sent = await bot.send_message(
                chat_id=message.chat.id,
                text=keyword_reply.reply_text,
                business_connection_id=connection_id,
            )
            await upsert_business_chat(
                session, owner.user_id, connection_id, message.chat.id,
                outgoing_message_id=sent.message_id,
            )
            await increment_auto_reply_count(session, owner.user_id)
        except TelegramAPIError as e:
            logging.error(f"Error sending keyword reply: {e}")
        return

    auto_reply = await get_user_auto_reply(session, owner.user_id)
    if not auto_reply:
        logging.info(f"Owner {owner.user_id} has no auto-reply set")
        return

    # Shu mijozga (message.from_user.id) shu owner nomidan avval javob
<<<<<<< HEAD
    # berilgan bo'lsa, odatda qayta yubormaymiz - faqat birinchi murojaatga
    # javob beramiz. Lekin owner "reply_every_time" rejimini yoqqan bo'lsa,
    # bu cheklov chetlab o'tiladi va har safar javob beriladi.
    if not owner.reply_every_time:
        already_replied = await has_replied_to_customer(session, owner.user_id, message.from_user.id)
        if already_replied:
            logging.info(f"Customer {message.from_user.id} already got the auto-reply for owner {owner.user_id}")
            return

        # Yozib qo'yishni xabar yuborishdan oldin qilamiz - shunda mijoz tez-tez
        # xabar yozib yuborsa ham (masalan bir necha xabarni ketma-ket), ikkinchi
        # marta yuborilib yubormaydi.
        is_first_time = await mark_replied_to_customer(session, owner.user_id, message.from_user.id)
        if not is_first_time:
            return
    else:
        # Statistika ("noyob mijozlar soni") uchun baribir eslab qolamiz,
        # lekin bu javob berish-bermaslikka ta'sir qilmaydi.
        await mark_replied_to_customer(session, owner.user_id, message.from_user.id)
=======
    # berilgan bo'lsa, qayta yubormaymiz - faqat birinchi murojaatga javob beramiz.
    already_replied = await has_replied_to_customer(session, owner.user_id, message.from_user.id)
    if already_replied:
        logging.info(f"Customer {message.from_user.id} already got the auto-reply for owner {owner.user_id}")
        return

    # Yozib qo'yishni xabar yuborishdan oldin qilamiz - shunda mijoz tez-tez
    # xabar yozib yuborsa ham (masalan bir necha xabarni ketma-ket), ikkinchi
    # marta yuborilib yubormaydi.
    is_first_time = await mark_replied_to_customer(session, owner.user_id, message.from_user.id)
    if not is_first_time:
        return
>>>>>>> 996f2e5fc4d650bd0bd5cb316b85a3dad8b21cfa

    social_links = await get_user_social_links(session, owner.user_id)
    
    # Telefon raqamlarni ajratib olamiz (ularni tugma qilib bo'lmaydi)
    phone_links = []
    button_links = []
    for link in social_links:
        url = link.url_or_number
        if not url.startswith("http") and not url.startswith("tg://") and any(c.isdigit() for c in url):
            phone_links.append(link)
        else:
            button_links.append(link)
            
    reply_markup = build_business_links_kb(button_links)

    # --- Ish vaqti bo'yicha avtojavob ---
    # Agar owner ish vaqtini yoqqan bo'lsa va hozir shu vaqt oralig'idan
    # tashqarida bo'lsa, o'ziga xos "band emasmiz" xabari yuboriladi
    # (agar u sozlangan bo'lsa), aks holda oddiy avtojavob davom etadi.
    if owner.working_hours_enabled and owner.out_of_hours_text and not is_within_working_hours(owner, datetime.utcnow()):
        text_to_send = owner.out_of_hours_text
        auto_reply_media_type = "text"
        auto_reply_media_file_id = None
    else:
        text_to_send = auto_reply.greeting_text or ""
        auto_reply_media_type = auto_reply.media_type
        auto_reply_media_file_id = auto_reply.media_file_id

    if phone_links:
        text_to_send += "\n\n📞 <b>Aloqa uchun:</b>\n"
        for p in phone_links:
            text_to_send += f"• {p.title}: <code>{p.url_or_number}</code>\n"

    sent = None
    try:
        if auto_reply_media_type == "text":
            sent = await bot.send_message(
                chat_id=message.chat.id, 
                text=text_to_send, 
                reply_markup=reply_markup,
                business_connection_id=connection_id
            )
        elif auto_reply_media_type == "photo":
            sent = await bot.send_photo(
                chat_id=message.chat.id,
                photo=auto_reply_media_file_id,
                caption=text_to_send,
                reply_markup=reply_markup,
                business_connection_id=connection_id
            )
        elif auto_reply_media_type == "video":
            sent = await bot.send_video(
                chat_id=message.chat.id,
                video=auto_reply_media_file_id,
                caption=text_to_send,
                reply_markup=reply_markup,
                business_connection_id=connection_id
            )
        elif auto_reply_media_type == "video_note":
            sent = await bot.send_video_note(
                chat_id=message.chat.id,
                video_note=auto_reply_media_file_id,
                reply_markup=reply_markup,
                business_connection_id=connection_id
            )
            if text_to_send:
                sent = await bot.send_message(
                    chat_id=message.chat.id,
                    text=text_to_send,
                    business_connection_id=connection_id
                )
        elif auto_reply_media_type == "voice":
            sent = await bot.send_voice(
                chat_id=message.chat.id,
                voice=auto_reply_media_file_id,
                caption=text_to_send,
                reply_markup=reply_markup,
                business_connection_id=connection_id
            )
        elif auto_reply_media_type == "document":
            sent = await bot.send_document(
                chat_id=message.chat.id,
                document=auto_reply_media_file_id,
                caption=text_to_send,
                reply_markup=reply_markup,
                business_connection_id=connection_id
            )

        if sent is not None:
            # Bot yuborgan javobni "so'nggi chiqqan xabar" sifatida eslab qolamiz,
            # shunda owner uni keyinroq "Oxirgi xabarni o'chirish" orqali o'chira oladi.
            await upsert_business_chat(
                session, owner.user_id, connection_id, message.chat.id,
                outgoing_message_id=sent.message_id,
            )
            await increment_auto_reply_count(session, owner.user_id)
    except TelegramAPIError as e:
        logging.error(f"Error sending business message: {e}")