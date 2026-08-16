from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from database.models import User, AutoReply, SocialLink, RepliedCustomer, PremiumTariff, PremiumRequest, PremiumRequestStatus, BotSetting, BusinessChat, ScheduledStory, KeywordReply

async def get_or_create_user(session: AsyncSession, user_id: int, full_name: str = None) -> User:
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(user_id=user_id, full_name=full_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def get_user_by_connection(session: AsyncSession, connection_id: str) -> User | None:
    stmt = select(User).where(User.connection_id == connection_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def update_user_connection(session: AsyncSession, user_id: int, connection_id: str):
    stmt = update(User).where(User.user_id == user_id).values(connection_id=connection_id)
    await session.execute(stmt)
    await session.commit()

async def get_user_auto_reply(session: AsyncSession, user_id: int) -> AutoReply | None:
    stmt = select(AutoReply).where(AutoReply.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def set_user_auto_reply(session: AsyncSession, user_id: int, greeting_text: str = None, media_file_id: str = None, media_type: str = "text"):
    stmt = select(AutoReply).where(AutoReply.user_id == user_id)
    result = await session.execute(stmt)
    auto_reply = result.scalar_one_or_none()

    if not auto_reply:
        auto_reply = AutoReply(user_id=user_id, greeting_text=greeting_text, media_file_id=media_file_id, media_type=media_type)
        session.add(auto_reply)
    else:
        auto_reply.greeting_text = greeting_text
        auto_reply.media_file_id = media_file_id
        auto_reply.media_type = media_type
    
    await session.commit()

async def get_user_social_links(session: AsyncSession, user_id: int) -> list[SocialLink]:
    stmt = select(SocialLink).where(SocialLink.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def add_social_link(session: AsyncSession, user_id: int, platform_type: str, title: str, url_or_number: str):
    link = SocialLink(user_id=user_id, platform_type=platform_type, title=title, url_or_number=url_or_number)
    session.add(link)
    await session.commit()

async def delete_social_link(session: AsyncSession, link_id: int):
    stmt = select(SocialLink).where(SocialLink.id == link_id)
    result = await session.execute(stmt)
    link = result.scalar_one_or_none()
    if link:
        await session.delete(link)
        await session.commit()

async def has_replied_to_customer(session: AsyncSession, owner_id: int, customer_id: int) -> bool:
    stmt = select(RepliedCustomer).where(
        RepliedCustomer.owner_id == owner_id,
        RepliedCustomer.customer_id == customer_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None

async def mark_replied_to_customer(session: AsyncSession, owner_id: int, customer_id: int) -> bool:
    """Mijozni 'javob berilganlar' ro'yxatiga qo'shadi.
    True qaytarsa - bu birinchi marta yozilgani va yozish muvaffaqiyatli bo'lgani,
    False qaytarsa - poyga holati (race condition) tufayli boshqa so'rov allaqachon
    belgilab ulgurgani (masalan mijoz tez-tez xabar yuborgan bo'lsa)."""
    session.add(RepliedCustomer(owner_id=owner_id, customer_id=customer_id))
    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False

async def grant_premium(session: AsyncSession, user_id: int, days: int) -> User | None:
    """Foydalanuvchiga `days` kunlik premium beradi.
    Agar foydalanuvchida hali muddati tugamagan premium bo'lsa, muddatga
    qo'shib boradi (uzaytiradi), aks holda hozirgi vaqtdan boshlab hisoblaydi.
    Kelajakda to'lov tizimi (Click/Payme) integratsiya qilinganda ham
    shu funksiya webhook orqali chaqirilishi mumkin."""
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return None

    now = datetime.utcnow()
    base = user.premium_expires_at if (user.premium_expires_at and user.premium_expires_at > now) else now
    user.premium_expires_at = base + timedelta(days=days)
    user.is_premium = True
    await session.commit()
    await session.refresh(user)
    return user

async def check_and_sync_premium(session: AsyncSession, user_id: int) -> User | None:
    """Foydalanuvchi profilini ochganda/chaqirilganda muddati tugagan
    premiumni darhol Freemiumga tushiradi."""
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return None

    if user.is_premium and user.premium_expires_at and user.premium_expires_at <= datetime.utcnow():
        user.is_premium = False
        await session.commit()
        await session.refresh(user)
    return user

async def downgrade_expired_premiums(session: AsyncSession) -> int:
    """Fon rejimidagi (background) vazifa uchun: muddati tugagan barcha
    premiumlarni birdaniga Freemiumga tushiradi. Nechta foydalanuvchi
    tushirilganini qaytaradi."""
    stmt = select(User).where(User.is_premium == True, User.premium_expires_at <= datetime.utcnow())
    result = await session.execute(stmt)
    expired_users = list(result.scalars().all())

    for user in expired_users:
        user.is_premium = False

    if expired_users:
        await session.commit()
    return len(expired_users)

async def get_premium_users_count(session: AsyncSession) -> int:
    stmt = select(User).where(User.is_premium == True)
    result = await session.execute(stmt)
    return len(list(result.scalars().all()))

async def get_all_users_count(session: AsyncSession) -> int:
    stmt = select(User)
    result = await session.execute(stmt)
    return len(list(result.scalars().all()))

async def get_all_users(session: AsyncSession) -> list[User]:
    stmt = select(User)
    result = await session.execute(stmt)
    return list(result.scalars().all())

# --- Tariflar (Premium Tariffs) ---

async def add_tariff(session: AsyncSession, name: str, days: int, price_text: str) -> PremiumTariff:
    tariff = PremiumTariff(name=name, days=days, price_text=price_text, is_active=True)
    session.add(tariff)
    await session.commit()
    await session.refresh(tariff)
    return tariff

async def get_active_tariffs(session: AsyncSession) -> list[PremiumTariff]:
    stmt = select(PremiumTariff).where(PremiumTariff.is_active == True)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_all_tariffs(session: AsyncSession) -> list[PremiumTariff]:
    stmt = select(PremiumTariff)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_tariff(session: AsyncSession, tariff_id: int) -> PremiumTariff | None:
    stmt = select(PremiumTariff).where(PremiumTariff.id == tariff_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def delete_tariff(session: AsyncSession, tariff_id: int):
    tariff = await get_tariff(session, tariff_id)
    if tariff:
        await session.delete(tariff)
        await session.commit()

# --- Bepul sinov (Trial) ---

async def grant_trial(session: AsyncSession, user_id: int, trial_days: int = 3) -> User | None:
    """3 kunlik bepul sinovni beradi. Har bir foydalanuvchiga faqat bir marta beriladi.
    Agar allaqachon ishlatilgan bo'lsa None qaytaradi."""
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or user.trial_used:
        return None

    now = datetime.utcnow()
    base = user.premium_expires_at if (user.premium_expires_at and user.premium_expires_at > now) else now
    user.premium_expires_at = base + timedelta(days=trial_days)
    user.is_premium = True
    user.trial_used = True
    await session.commit()
    await session.refresh(user)
    return user

# --- Premium so'rovlar (to'lov arizalari) ---

async def create_premium_request(session: AsyncSession, user_id: int, tariff_id: int) -> PremiumRequest:
    req = PremiumRequest(user_id=user_id, tariff_id=tariff_id, status=PremiumRequestStatus.pending)
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req

async def get_premium_request(session: AsyncSession, request_id: int) -> PremiumRequest | None:
    stmt = select(PremiumRequest).where(PremiumRequest.id == request_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def resolve_premium_request(session: AsyncSession, request_id: int, approve: bool, admin_id: int) -> PremiumRequest | None:
    """So'rovni tasdiqlaydi yoki rad etadi. Faqat 'pending' holatdagi so'rovlar
    qayta ishlanadi - shu orqali bir nechta admin bir vaqtda bosib qolsa ham
    ikki marta premium berilib ketmaydi."""
    req = await get_premium_request(session, request_id)
    if not req or req.status != PremiumRequestStatus.pending:
        return None

    req.status = PremiumRequestStatus.approved if approve else PremiumRequestStatus.rejected
    req.resolved_by = admin_id
    await session.commit()
    await session.refresh(req)
    return req

# --- Bot sozlamalari (masalan: karta raqami) ---

# --- Bot ruxsatlari / biznes boshqaruvi ---

async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def toggle_auto_mark_read(session: AsyncSession, user_id: int) -> bool | None:
    """Xabarlarni avtomatik o'qilgan deb belgilashni yoqadi/o'chiradi.
    Yangi holatni (True/False) qaytaradi, foydalanuvchi topilmasa None."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    user.auto_mark_read = not user.auto_mark_read
    await session.commit()
    return user.auto_mark_read

async def upsert_business_chat(
    session: AsyncSession,
    owner_id: int,
    connection_id: str,
    chat_id: int,
    incoming_message_id: int | None = None,
    outgoing_message_id: int | None = None,
) -> BusinessChat:
    """Owner-ning shu mijoz bilan chatidagi so'nggi xabar ID'larini yangilaydi.
    'O'chirish' funksiyalari uchun eng so'nggi kirgan/chiqqan xabarni eslab qoladi."""
    stmt = select(BusinessChat).where(BusinessChat.owner_id == owner_id, BusinessChat.chat_id == chat_id)
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()

    if not chat:
        chat = BusinessChat(owner_id=owner_id, connection_id=connection_id, chat_id=chat_id)
        session.add(chat)

    chat.connection_id = connection_id
    if incoming_message_id is not None:
        chat.last_incoming_message_id = incoming_message_id
    if outgoing_message_id is not None:
        chat.last_outgoing_message_id = outgoing_message_id
    chat.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(chat)
    return chat

async def get_most_recent_business_chat(session: AsyncSession, owner_id: int) -> BusinessChat | None:
    stmt = select(BusinessChat).where(BusinessChat.owner_id == owner_id).order_by(BusinessChat.updated_at.desc())
    result = await session.execute(stmt)
    return result.scalars().first()

async def clear_incoming_message(session: AsyncSession, chat_pk_id: int):
    stmt = select(BusinessChat).where(BusinessChat.id == chat_pk_id)
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()
    if chat:
        chat.last_incoming_message_id = None
        await session.commit()

async def clear_outgoing_message(session: AsyncSession, chat_pk_id: int):
    stmt = select(BusinessChat).where(BusinessChat.id == chat_pk_id)
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()
    if chat:
        chat.last_outgoing_message_id = None
        await session.commit()


# --- Rejalashtirilgan hikoyalar (Scheduled stories) ---

async def create_scheduled_story(
    session: AsyncSession, owner_id: int, connection_id: str,
    media_file_id: str, media_type: str, caption: str | None,
    scheduled_at: datetime, active_period: int = 86400,
) -> ScheduledStory:
    story = ScheduledStory(
        owner_id=owner_id, connection_id=connection_id,
        media_file_id=media_file_id, media_type=media_type,
        caption=caption, scheduled_at=scheduled_at, active_period=active_period,
    )
    session.add(story)
    await session.commit()
    await session.refresh(story)
    return story

async def get_due_scheduled_stories(session: AsyncSession) -> list[ScheduledStory]:
    """Joylash vaqti kelib, hali joylanmagan barcha hikoyalarni qaytaradi."""
    stmt = select(ScheduledStory).where(
        ScheduledStory.is_posted == False,
        ScheduledStory.scheduled_at <= datetime.utcnow(),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_user_scheduled_stories(session: AsyncSession, owner_id: int) -> list[ScheduledStory]:
    stmt = select(ScheduledStory).where(
        ScheduledStory.owner_id == owner_id,
        ScheduledStory.is_posted == False,
    ).order_by(ScheduledStory.scheduled_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def mark_scheduled_story_posted(session: AsyncSession, story_id: int, failed_reason: str | None = None):
    stmt = select(ScheduledStory).where(ScheduledStory.id == story_id)
    result = await session.execute(stmt)
    story = result.scalar_one_or_none()
    if story:
        story.is_posted = True
        story.failed_reason = failed_reason
        await session.commit()

async def delete_scheduled_story(session: AsyncSession, story_id: int, owner_id: int) -> bool:
    stmt = select(ScheduledStory).where(ScheduledStory.id == story_id, ScheduledStory.owner_id == owner_id)
    result = await session.execute(stmt)
    story = result.scalar_one_or_none()
    if not story:
        return False
    await session.delete(story)
    await session.commit()
    return True


# --- Ish vaqti bo'yicha avtojavob ---

async def toggle_working_hours(session: AsyncSession, user_id: int) -> bool | None:
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    user.working_hours_enabled = not user.working_hours_enabled
    await session.commit()
    return user.working_hours_enabled

async def set_working_hours(session: AsyncSession, user_id: int, start_hour: int, end_hour: int) -> bool:
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    user.work_start_hour = start_hour
    user.work_end_hour = end_hour
    await session.commit()
    return True

async def set_out_of_hours_text(session: AsyncSession, user_id: int, text_value: str) -> bool:
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    user.out_of_hours_text = text_value
    await session.commit()
    return True

def is_within_working_hours(user: User, now_utc: datetime) -> bool:
    """UTC soatiga asoslanib, hozir ish vaqtimi yoki yo'qligini aniqlaydi.
    Kechqurundan tongga cho'zilgan intervallarni ham (masalan 22:00-06:00)
    to'g'ri hisoblaydi."""
    hour = now_utc.hour
    start, end = user.work_start_hour, user.work_end_hour
    if start == end:
        return True  # butun sutka ish vaqti deb hisoblanadi
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # kechadan tongga cho'zilgan interval


# --- Kalit so'zga asoslangan avtojavoblar ---

async def add_keyword_reply(session: AsyncSession, user_id: int, keyword: str, reply_text: str) -> KeywordReply:
    kr = KeywordReply(user_id=user_id, keyword=keyword.strip().lower(), reply_text=reply_text)
    session.add(kr)
    await session.commit()
    await session.refresh(kr)
    return kr

async def get_keyword_replies(session: AsyncSession, user_id: int) -> list[KeywordReply]:
    stmt = select(KeywordReply).where(KeywordReply.user_id == user_id).order_by(KeywordReply.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def find_matching_keyword_reply(session: AsyncSession, user_id: int, message_text: str) -> KeywordReply | None:
    if not message_text:
        return None
    text_lower = message_text.lower()
    replies = await get_keyword_replies(session, user_id)
    for kr in replies:
        if kr.keyword in text_lower:
            return kr
    return None

async def delete_keyword_reply(session: AsyncSession, kr_id: int, user_id: int) -> bool:
    stmt = select(KeywordReply).where(KeywordReply.id == kr_id, KeywordReply.user_id == user_id)
    result = await session.execute(stmt)
    kr = result.scalar_one_or_none()
    if not kr:
        return False
    await session.delete(kr)
    await session.commit()
    return True


# --- Statistika ---

async def increment_auto_reply_count(session: AsyncSession, user_id: int):
    user = await get_user_by_id(session, user_id)
    if user:
        user.total_auto_replies = (user.total_auto_replies or 0) + 1
        await session.commit()

async def get_unique_customers_count(session: AsyncSession, owner_id: int) -> int:
    stmt = select(func.count()).select_from(RepliedCustomer).where(RepliedCustomer.owner_id == owner_id)
    result = await session.execute(stmt)
    return result.scalar_one() or 0


# --- Avtojavob rejimi: bir marta yoki har safar ---

async def toggle_reply_every_time(session: AsyncSession, user_id: int) -> bool | None:
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    user.reply_every_time = not user.reply_every_time
    await session.commit()
    return user.reply_every_time


async def get_setting(session: AsyncSession, key: str) -> str | None:
    stmt = select(BotSetting).where(BotSetting.key == key)
    result = await session.execute(stmt)
    setting = result.scalar_one_or_none()
    return setting.value if setting else None

async def set_setting(session: AsyncSession, key: str, value: str):
    stmt = select(BotSetting).where(BotSetting.key == key)
    result = await session.execute(stmt)
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        setting = BotSetting(key=key, value=value)
        session.add(setting)
    await session.commit()