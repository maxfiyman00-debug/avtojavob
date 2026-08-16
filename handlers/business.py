"""
Skrinshotda ko'rsatilgan 'Bot ruxsatlari' funksiyalarini to'liq boshqarish:
- Xabarlarni boshqarish: avtomatik o'qilgan deb belgilash, yuborilgan/qabul
  qilingan xabarlarni o'chirish (auto-javob berish handlers/business.py da).
- Profilni boshqarish: ism, tarjimai hol, foydalanuvchi nomi, profil rasmi.
- Hikoyalarni boshqarish: hikoya (story) joylash.
- Sovg'a va yulduzlarni boshqarish: balansni ko'rish, sovg'ani yulduzga
  aylantirish.

Barcha amallar Telegram Business Bot API orqali, owner bergan connection_id
yordamida, owner nomidan bajariladi (aiogram 3.15+, Bot API 7.x+ talab qilinadi).
"""
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, Message, ContentType,
    InputStoryContentPhoto, InputStoryContentVideo,
)
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.requests import (
    get_user_by_id, toggle_auto_mark_read, get_most_recent_business_chat,
    clear_incoming_message, clear_outgoing_message,
    create_scheduled_story, get_user_scheduled_stories, delete_scheduled_story,
    toggle_working_hours, set_working_hours, set_out_of_hours_text,
    add_keyword_reply, get_keyword_replies, delete_keyword_reply,
    get_unique_customers_count, toggle_reply_every_time,
)
from services.media import download_as_input_file
from keyboards.user_kb import (
    get_user_main_kb, get_management_menu_kb, get_profile_menu_kb,
    get_back_to_management_kb, get_gifts_kb, get_story_timing_kb, get_scheduled_stories_kb,
    get_working_hours_kb, get_keywords_menu_kb,
)
from states.business_states import ProfileEdit, StoryPost, WorkingHours, KeywordReplySetup

router = Router()

# Sovg'alar ro'yxati callback_data uchun juda uzun bo'lishi mumkin (Telegram
# callback_data limiti 64 bayt), shu sabab har bir foydalanuvchi uchun
# so'nggi ko'rsatilgan sovg'alar ro'yxatini vaqtincha xotirada saqlaymiz.
_gifts_cache: dict[int, list[str]] = {}


async def _require_connection(call: CallbackQuery, session: AsyncSession):
    """Owner business ulanishga ega ekanini tekshiradi. Bo'lmasa ogohlantiradi."""
    user = await get_user_by_id(session, call.from_user.id)
    if not user or not user.connection_id:
        await call.answer(
            "❗️ Avval Telegram Business orqali botni hisobingizga ulang.",
            show_alert=True,
        )
        return None
    return user


# --- Asosiy boshqaruv menyusi ---

@router.callback_query(F.data == "biz_management_menu")
async def management_menu(call: CallbackQuery, session: AsyncSession):
    user = await _require_connection(call, session)
    if not user:
        return
    await call.message.edit_text(
        "<b>🛠 Biznes boshqaruvi</b>\n\n"
        "Bu yerdan ulangan Business hisobingizni to'liq boshqarishingiz mumkin: "
        "xabarlar, profil, hikoyalar, sovg'a va yulduzlar.",
        reply_markup=get_management_menu_kb(user.auto_mark_read, user.reply_every_time),
    )
    await call.answer()


# --- Xabarlarni boshqarish ---

@router.callback_query(F.data == "toggle_auto_read")
async def toggle_read(call: CallbackQuery, session: AsyncSession):
    new_state = await toggle_auto_mark_read(session, call.from_user.id)
    if new_state is None:
        return await call.answer("Xatolik yuz berdi.", show_alert=True)

    user = await get_user_by_id(session, call.from_user.id)
    await call.message.edit_reply_markup(reply_markup=get_management_menu_kb(user.auto_mark_read, user.reply_every_time))
    await call.answer("✅ Yoqildi" if new_state else "❌ O'chirildi")


@router.callback_query(F.data == "toggle_reply_mode")
async def toggle_reply_mode(call: CallbackQuery, session: AsyncSession):
    new_state = await toggle_reply_every_time(session, call.from_user.id)
    if new_state is None:
        return await call.answer("Xatolik yuz berdi.", show_alert=True)

    user = await get_user_by_id(session, call.from_user.id)
    await call.message.edit_reply_markup(reply_markup=get_management_menu_kb(user.auto_mark_read, user.reply_every_time))
    await call.answer(
        "🔁 Endi mijoz har xabar yozganda javob olinadi." if new_state
        else "🔁 Endi mijozga faqat birinchi murojaatida javob beriladi.",
        show_alert=True,
    )


@router.callback_query(F.data == "delete_last_received")
async def delete_last_received(call: CallbackQuery, session: AsyncSession, bot: Bot):
    user = await _require_connection(call, session)
    if not user:
        return

    chat = await get_most_recent_business_chat(session, user.user_id)
    if not chat or not chat.last_incoming_message_id:
        return await call.answer("O'chirish uchun xabar topilmadi.", show_alert=True)

    try:
        await bot.delete_business_messages(
            business_connection_id=user.connection_id,
            message_ids=[chat.last_incoming_message_id],
        )
        await clear_incoming_message(session, chat.id)
        await call.answer("🗑 Mijozdan kelgan oxirgi xabar o'chirildi.", show_alert=True)
    except TelegramAPIError as e:
        logging.error(f"delete_last_received error: {e}")
        await call.answer("Xabarni o'chirib bo'lmadi (juda eski bo'lishi mumkin).", show_alert=True)


@router.callback_query(F.data == "delete_last_sent")
async def delete_last_sent(call: CallbackQuery, session: AsyncSession, bot: Bot):
    user = await _require_connection(call, session)
    if not user:
        return

    chat = await get_most_recent_business_chat(session, user.user_id)
    if not chat or not chat.last_outgoing_message_id:
        return await call.answer("O'chirish uchun xabar topilmadi.", show_alert=True)

    try:
        await bot.delete_business_messages(
            business_connection_id=user.connection_id,
            message_ids=[chat.last_outgoing_message_id],
        )
        await clear_outgoing_message(session, chat.id)
        await call.answer("🗑 Yuborilgan oxirgi xabar o'chirildi.", show_alert=True)
    except TelegramAPIError as e:
        logging.error(f"delete_last_sent error: {e}")
        await call.answer("Xabarni o'chirib bo'lmadi (juda eski bo'lishi mumkin).", show_alert=True)


# --- Profilni boshqarish ---

@router.callback_query(F.data == "biz_profile_menu")
async def profile_menu(call: CallbackQuery, session: AsyncSession):
    user = await _require_connection(call, session)
    if not user:
        return
    await call.message.edit_text(
        "<b>👤 Profilni boshqarish</b>\n\nQaysi ma'lumotni tahrirlamoqchisiz?",
        reply_markup=get_profile_menu_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "edit_name")
async def edit_name_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Yangi ism(lar)ni yuboring.\n"
        "Format: <code>Ism | Familiya</code> (familiya ixtiyoriy, bo'lmasa faqat ism yozing).",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(ProfileEdit.waiting_for_name)
    await call.answer()


@router.message(ProfileEdit.waiting_for_name)
async def edit_name_process(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    user = await get_user_by_id(session, message.from_user.id)
    if not user or not user.connection_id:
        await state.clear()
        return await message.answer("❗️ Business ulanish topilmadi.", reply_markup=get_user_main_kb())

    parts = [p.strip() for p in message.text.split("|")]
    first_name = parts[0][:64] if parts else message.text[:64]
    last_name = parts[1][:64] if len(parts) > 1 else None

    try:
        await bot.set_business_account_name(
            business_connection_id=user.connection_id,
            first_name=first_name,
            last_name=last_name,
        )
        await message.answer("✅ Ism muvaffaqiyatli yangilandi!", reply_markup=get_profile_menu_kb())
    except TelegramAPIError as e:
        logging.error(f"set_business_account_name error: {e}")
        await message.answer(f"❌ Xatolik: ismni yangilab bo'lmadi.\n<code>{e}</code>", reply_markup=get_profile_menu_kb())
    await state.clear()


@router.callback_query(F.data == "edit_bio")
async def edit_bio_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Yangi tarjimai hol (bio) matnini yuboring (bo'shatish uchun <code>-</code> yuboring):",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(ProfileEdit.waiting_for_bio)
    await call.answer()


@router.message(ProfileEdit.waiting_for_bio)
async def edit_bio_process(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    user = await get_user_by_id(session, message.from_user.id)
    if not user or not user.connection_id:
        await state.clear()
        return await message.answer("❗️ Business ulanish topilmadi.", reply_markup=get_user_main_kb())

    bio = "" if message.text.strip() == "-" else message.text[:140]
    try:
        await bot.set_business_account_bio(business_connection_id=user.connection_id, bio=bio)
        await message.answer("✅ Tarjimai hol yangilandi!", reply_markup=get_profile_menu_kb())
    except TelegramAPIError as e:
        logging.error(f"set_business_account_bio error: {e}")
        await message.answer(f"❌ Xatolik: bio yangilanmadi.\n<code>{e}</code>", reply_markup=get_profile_menu_kb())
    await state.clear()


@router.callback_query(F.data == "edit_username")
async def edit_username_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Yangi foydalanuvchi nomini (@ belgisisiz) yuboring.\n"
        "<i>Eslatma: bu username sizning barcha bog'langan public username'laringiz orasidan bo'lishi kerak.</i>",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(ProfileEdit.waiting_for_username)
    await call.answer()


@router.message(ProfileEdit.waiting_for_username)
async def edit_username_process(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    user = await get_user_by_id(session, message.from_user.id)
    if not user or not user.connection_id:
        await state.clear()
        return await message.answer("❗️ Business ulanish topilmadi.", reply_markup=get_user_main_kb())

    username = message.text.strip().lstrip("@")
    try:
        await bot.set_business_account_username(business_connection_id=user.connection_id, username=username or None)
        await message.answer("✅ Foydalanuvchi nomi yangilandi!", reply_markup=get_profile_menu_kb())
    except TelegramAPIError as e:
        logging.error(f"set_business_account_username error: {e}")
        await message.answer(f"❌ Xatolik: username yangilanmadi.\n<code>{e}</code>", reply_markup=get_profile_menu_kb())
    await state.clear()


@router.callback_query(F.data == "edit_photo")
async def edit_photo_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Yangi profil rasmini (kvadrat rasm tavsiya etiladi) yuboring:",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(ProfileEdit.waiting_for_photo)
    await call.answer()


@router.message(ProfileEdit.waiting_for_photo, F.content_type == ContentType.PHOTO)
async def edit_photo_process(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    from aiogram.types import InputProfilePhotoStatic

    user = await get_user_by_id(session, message.from_user.id)
    if not user or not user.connection_id:
        await state.clear()
        return await message.answer("❗️ Business ulanish topilmadi.", reply_markup=get_user_main_kb())

    try:
        photo_file_id = message.photo[-1].file_id
        # MUHIM: Telegram profil rasmlari uchun eski file_id'ni qabul qilmaydi -
        # fayl albatta YANGIDAN yuklanishi kerak, shu sabab avval yuklab olamiz.
        input_photo = await download_as_input_file(bot, photo_file_id, "profile.jpg")
        await bot.set_business_account_profile_photo(
            business_connection_id=user.connection_id,
            photo=InputProfilePhotoStatic(photo=input_photo),
        )
        await message.answer("✅ Profil rasmi yangilandi!", reply_markup=get_profile_menu_kb())
    except TelegramAPIError as e:
        logging.error(f"set_business_account_profile_photo error: {e}")
        await message.answer(f"❌ Xatolik: rasm yangilanmadi.\n<code>{e}</code>", reply_markup=get_profile_menu_kb())
    await state.clear()


# --- Hikoyalarni boshqarish ---

@router.callback_query(F.data == "biz_post_story")
async def post_story_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    user = await _require_connection(call, session)
    if not user:
        return
    await call.message.edit_text(
        "Hikoya sifatida joylash uchun rasm yoki video yuboring.\n"
        "<i>Izoh matnini rasm/video bilan birga caption sifatida yuborishingiz mumkin.</i>",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(StoryPost.waiting_for_media)
    await call.answer()


@router.message(StoryPost.waiting_for_media, F.content_type.in_([ContentType.PHOTO, ContentType.VIDEO]))
async def post_story_media_received(message: Message, state: FSMContext):
    # Media va caption'ni saqlab, "hozir joylash" yoki "vaqt belgilash"ni so'raymiz
    if message.content_type == ContentType.PHOTO:
        media_file_id = message.photo[-1].file_id
        media_type = "photo"
    else:
        media_file_id = message.video.file_id
        media_type = "video"

    await state.update_data(media_file_id=media_file_id, media_type=media_type, caption=message.caption)
    await message.answer(
        "Hikoyani qachon joylashni xohlaysiz?",
        reply_markup=get_story_timing_kb(),
    )
    # State hali StoryPost.waiting_for_media'da qoladi - keyingi qadam callback orqali davom etadi


@router.callback_query(F.data == "story_post_now")
async def post_story_now(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    media_file_id = data.get("media_file_id")
    media_type = data.get("media_type")
    caption = data.get("caption")

    user = await _require_connection(call, session)
    if not user or not media_file_id:
        await state.clear()
        return

    try:
        # MUHIM: hikoya uchun ham file_id qayta ishlatib bo'lmaydi - fayl
        # albatta yangidan yuklanishi shart. Bundan tashqari, aiogram'ning
        # InputStoryContentPhoto/Video klasslari "photo"/"video" maydonini
        # oddiy validatsiya orqali faqat 'str' deb qabul qiladi (hozirgi
        # aiogram versiyasidagi cheklov), shu sabab validatsiyani chetlab
        # o'tish uchun `model_construct` ishlatamiz - bu xavfsiz, chunki
        # qiymatni o'zimiz to'g'ri turda (BufferedInputFile) beryapmiz.
        if media_type == "photo":
            input_media = await download_as_input_file(bot, media_file_id, "story.jpg")
            content = InputStoryContentPhoto.model_construct(photo=input_media)
        else:
            input_media = await download_as_input_file(bot, media_file_id, "story.mp4")
            content = InputStoryContentVideo.model_construct(video=input_media)
        await bot.post_story(
            business_connection_id=user.connection_id,
            content=content,
            active_period=86400,  # 24 soat (minimal ruxsat etilgan davr)
            caption=caption,
        )
        await call.message.edit_text("✅ Hikoya muvaffaqiyatli joylandi!", reply_markup=get_management_menu_kb(user.auto_mark_read, user.reply_every_time))
    except TelegramAPIError as e:
        logging.error(f"post_story error: {e}")
        await call.message.edit_text(
            f"❌ Xatolik: hikoyani joylab bo'lmadi. Buning uchun Telegram Premium talab qilinishi mumkin.\n<code>{e}</code>",
            reply_markup=get_management_menu_kb(user.auto_mark_read, user.reply_every_time),
        )
    await state.clear()
    await call.answer()


@router.callback_query(F.data == "story_schedule")
async def post_story_schedule_ask_time(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Hikoya joylanadigan sana va vaqtni <b>UTC (Coordinated Universal Time)</b> bo'yicha kiriting.\n"
        "Format: <code>YYYY-MM-DD HH:MM</code>\n"
        "Masalan: <code>2026-08-20 09:00</code>",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(StoryPost.waiting_for_datetime)
    await call.answer()


@router.message(StoryPost.waiting_for_datetime)
async def post_story_schedule_save(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    media_file_id = data.get("media_file_id")
    media_type = data.get("media_type")
    caption = data.get("caption")

    user = await get_user_by_id(session, message.from_user.id)
    if not user or not user.connection_id or not media_file_id:
        await state.clear()
        return await message.answer("❗️ Business ulanish topilmadi.", reply_markup=get_user_main_kb())

    try:
        scheduled_at = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return await message.answer(
            "❌ Format noto'g'ri. Iltimos <code>YYYY-MM-DD HH:MM</code> formatida qayta yuboring.\n"
            "Masalan: <code>2026-08-20 09:00</code>"
        )

    if scheduled_at <= datetime.utcnow():
        return await message.answer("❌ Bu vaqt allaqachon o'tib ketgan. Kelajakdagi vaqtni kiriting.")

    await create_scheduled_story(
        session, user.user_id, user.connection_id,
        media_file_id, media_type, caption, scheduled_at,
    )
    await state.clear()
    await message.answer(
        f"✅ Hikoya <b>{scheduled_at.strftime('%Y-%m-%d %H:%M')} UTC</b> vaqtiga rejalashtirildi!\n"
        "Belgilangan vaqtda avtomatik joylanadi.",
        reply_markup=get_management_menu_kb(user.auto_mark_read, user.reply_every_time),
    )


@router.callback_query(F.data == "biz_scheduled_stories")
async def scheduled_stories_list(call: CallbackQuery, session: AsyncSession):
    user = await _require_connection(call, session)
    if not user:
        return
    stories = await get_user_scheduled_stories(session, user.user_id)
    if not stories:
        await call.message.edit_text(
            "Hozircha rejalashtirilgan hikoyalar yo'q.",
            reply_markup=get_back_to_management_kb(),
        )
    else:
        await call.message.edit_text(
            "<b>🕒 Rejalashtirilgan hikoyalar</b>\n\nBekor qilish uchun bosing:",
            reply_markup=get_scheduled_stories_kb(stories),
        )
    await call.answer()


@router.callback_query(F.data.startswith("cancel_story_"))
async def cancel_scheduled_story(call: CallbackQuery, session: AsyncSession):
    story_id = int(call.data.replace("cancel_story_", ""))
    ok = await delete_scheduled_story(session, story_id, call.from_user.id)
    await call.answer("🗑 Bekor qilindi." if ok else "Topilmadi.", show_alert=True)
    await scheduled_stories_list(call, session)


# --- Sovg'a va yulduzlarni boshqarish ---

@router.callback_query(F.data == "biz_gifts_menu")
async def gifts_menu(call: CallbackQuery, session: AsyncSession, bot: Bot):
    user = await _require_connection(call, session)
    if not user:
        return

    try:
        star_balance = await bot.get_business_account_star_balance(business_connection_id=user.connection_id)
        owned = await bot.get_business_account_gifts(business_connection_id=user.connection_id)
    except TelegramAPIError as e:
        logging.error(f"gifts_menu fetch error: {e}")
        return await call.answer("Sovg'a/yulduz ma'lumotlarini olib bo'lmadi.", show_alert=True)

    gifts_list = list(owned.gifts) if owned and owned.gifts else []
    # Callback_data cheklovi tufayli owned_gift_id'larni vaqtincha keshda saqlaymiz
    _gifts_cache[call.from_user.id] = [g.owned_gift_id for g in gifts_list if getattr(g, "owned_gift_id", None)]

    balance_amount = star_balance.amount if star_balance else 0
    text = (
        f"<b>🎁 Sovg'a va Yulduzlar</b>\n\n"
        f"⭐️ Yulduz balansi: <b>{balance_amount}</b>\n"
        f"🎁 Sovg'alar soni: <b>{len(gifts_list)}</b>\n\n"
        "Sovg'ani yulduzga aylantirish uchun quyidan tanlang:"
    )
    indexed = [(i, g) for i, g in enumerate(gifts_list) if getattr(g, "owned_gift_id", None)]
    await call.message.edit_text(text, reply_markup=get_gifts_kb(indexed))
    await call.answer()


@router.callback_query(F.data.startswith("gift_to_stars_"))
async def convert_gift(call: CallbackQuery, session: AsyncSession, bot: Bot):
    user = await _require_connection(call, session)
    if not user:
        return

    idx_str = call.data.replace("gift_to_stars_", "")
    cached = _gifts_cache.get(call.from_user.id, [])
    if not idx_str.isdigit() or int(idx_str) >= len(cached):
        return await call.answer("Bu sovg'a topilmadi, ro'yxatni qayta oching.", show_alert=True)

    owned_gift_id = cached[int(idx_str)]
    try:
        await bot.convert_gift_to_stars(business_connection_id=user.connection_id, owned_gift_id=owned_gift_id)
        await call.answer("✅ Sovg'a yulduzlarga aylantirildi!", show_alert=True)
        await gifts_menu(call, session, bot)
    except TelegramAPIError as e:
        logging.error(f"convert_gift_to_stars error: {e}")
        await call.answer("Sovg'ani aylantirib bo'lmadi.", show_alert=True)


# --- Ish vaqti bo'yicha avtojavob ---

@router.callback_query(F.data == "biz_working_hours")
async def working_hours_menu(call: CallbackQuery, session: AsyncSession):
    user = await _require_connection(call, session)
    if not user:
        return
    await call.message.edit_text(
        f"<b>🕐 Ish vaqti</b>\n\n"
        f"Joriy soatlar (UTC): <b>{user.work_start_hour:02d}:00 - {user.work_end_hour:02d}:00</b>\n\n"
        "Yoqilgan bo'lsa, shu vaqtdan tashqarida mijozga alohida "
        "\"hozir band emasmiz\" xabari yuboriladi.",
        reply_markup=get_working_hours_kb(user.working_hours_enabled),
    )
    await call.answer()


@router.callback_query(F.data == "toggle_working_hours")
async def toggle_hours(call: CallbackQuery, session: AsyncSession):
    new_state = await toggle_working_hours(session, call.from_user.id)
    if new_state is None:
        return await call.answer("Xatolik yuz berdi.", show_alert=True)
    user = await get_user_by_id(session, call.from_user.id)
    await call.message.edit_reply_markup(reply_markup=get_working_hours_kb(user.working_hours_enabled))
    await call.answer("✅ Yoqildi" if new_state else "❌ O'chirildi")


@router.callback_query(F.data == "set_work_hours")
async def set_hours_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Ish vaqtini <b>UTC</b> bo'yicha kiriting.\nFormat: <code>boshlanish-tugash</code> (0-23 oralig'ida)\n"
        "Masalan: <code>4-13</code> (agar mahalliy vaqtingiz UTC+5 bo'lsa va 09:00-18:00 ishlasangiz)",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(WorkingHours.waiting_for_hours)
    await call.answer()


@router.message(WorkingHours.waiting_for_hours)
async def set_hours_process(message: Message, state: FSMContext, session: AsyncSession):
    try:
        start_str, end_str = message.text.strip().split("-")
        start, end = int(start_str), int(end_str)
        if not (0 <= start <= 23 and 0 <= end <= 23):
            raise ValueError
    except (ValueError, AttributeError):
        return await message.answer("❌ Format noto'g'ri. Masalan: <code>9-18</code>")

    await set_working_hours(session, message.from_user.id, start, end)
    user = await get_user_by_id(session, message.from_user.id)
    await state.clear()
    await message.answer(
        f"✅ Ish vaqti <b>{start:02d}:00 - {end:02d}:00 UTC</b> qilib belgilandi.",
        reply_markup=get_working_hours_kb(user.working_hours_enabled),
    )


@router.callback_query(F.data == "set_out_of_hours_text")
async def set_out_of_hours_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Ish vaqtidan tashqarida mijozga yuboriladigan xabar matnini kiriting:",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(WorkingHours.waiting_for_text)
    await call.answer()


@router.message(WorkingHours.waiting_for_text)
async def set_out_of_hours_process(message: Message, state: FSMContext, session: AsyncSession):
    await set_out_of_hours_text(session, message.from_user.id, message.text)
    user = await get_user_by_id(session, message.from_user.id)
    await state.clear()
    await message.answer("✅ Xabar saqlandi!", reply_markup=get_working_hours_kb(user.working_hours_enabled))


# --- Kalit so'zga asoslangan avtojavoblar ---

@router.callback_query(F.data == "biz_keywords_menu")
async def keywords_menu(call: CallbackQuery, session: AsyncSession):
    user = await _require_connection(call, session)
    if not user:
        return
    keywords = await get_keyword_replies(session, user.user_id)
    text = "<b>🔑 Kalit so'zga asoslangan avtojavoblar</b>\n\n"
    if keywords:
        text += "Mijoz xabarida quyidagi so'zlardan biri bo'lsa, mos javob yuboriladi:\n"
        text += "\n".join(f"• <code>{kr.keyword}</code>" for kr in keywords)
        text += "\n\nO'chirish uchun bosing:"
    else:
        text += "Hozircha kalit so'zlar qo'shilmagan."
    await call.message.edit_text(text, reply_markup=get_keywords_menu_kb(keywords))
    await call.answer()


@router.callback_query(F.data == "add_keyword")
async def add_keyword_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Kalit so'zni kiriting (masalan: <code>narx</code>):",
        reply_markup=get_back_to_management_kb(),
    )
    await state.set_state(KeywordReplySetup.waiting_for_keyword)
    await call.answer()


@router.message(KeywordReplySetup.waiting_for_keyword)
async def add_keyword_word(message: Message, state: FSMContext):
    await state.update_data(keyword=message.text.strip())
    await message.answer("Endi shu kalit so'zga mos javob matnini kiriting:")
    await state.set_state(KeywordReplySetup.waiting_for_reply_text)


@router.message(KeywordReplySetup.waiting_for_reply_text)
async def add_keyword_reply_text(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    keyword = data.get("keyword")
    if not keyword:
        await state.clear()
        return await message.answer("Xatolik yuz berdi, qaytadan urinib ko'ring.", reply_markup=get_user_main_kb())

    await add_keyword_reply(session, message.from_user.id, keyword, message.text)
    user = await get_user_by_id(session, message.from_user.id)
    keywords = await get_keyword_replies(session, user.user_id)
    await state.clear()
    await message.answer(
        f"✅ <code>{keyword}</code> kalit so'zi qo'shildi!",
        reply_markup=get_keywords_menu_kb(keywords),
    )


@router.callback_query(F.data.startswith("delete_keyword_"))
async def delete_keyword(call: CallbackQuery, session: AsyncSession):
    kr_id = int(call.data.replace("delete_keyword_", ""))
    ok = await delete_keyword_reply(session, kr_id, call.from_user.id)
    await call.answer("🗑 O'chirildi." if ok else "Topilmadi.", show_alert=True)
    await keywords_menu(call, session)


# --- Statistika ---

@router.callback_query(F.data == "biz_stats")
async def show_stats(call: CallbackQuery, session: AsyncSession):
    user = await _require_connection(call, session)
    if not user:
        return
    unique_customers = await get_unique_customers_count(session, user.user_id)
    await call.message.edit_text(
        "<b>📊 Statistika</b>\n\n"
        f"💬 Jami yuborilgan avtojavoblar: <b>{user.total_auto_replies}</b>\n"
        f"👥 Noyob mijozlar soni: <b>{unique_customers}</b>",
        reply_markup=get_back_to_management_kb(),
    )
    await call.answer()
