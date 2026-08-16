from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import config
from core.loader import bot
from database.requests import (
    get_or_create_user, get_user_auto_reply, set_user_auto_reply, get_user_social_links,
    add_social_link, delete_social_link, check_and_sync_premium,
    get_active_tariffs, get_tariff, grant_trial, create_premium_request, get_setting
)
from keyboards.user_kb import get_user_main_kb, get_social_platforms_kb, get_manage_links_kb, get_premium_menu_kb, get_tariff_payment_kb
from keyboards.admin_kb import get_premium_request_kb
from states.user_states import UserSetup, UserSocialLink
from services.onboarding import ONBOARDING_TEXT

router = Router()

@router.message(CommandStart())
async def start_user(message: Message, session: AsyncSession):
    user = await get_or_create_user(session, message.from_user.id, message.from_user.full_name)
    text = (
        f"Salom, <b>{message.from_user.full_name}</b>!\n"
        "Men ko'p foydalanuvchili Telegram Business Avto-javob botiman.\n\n"
        f"Sizning ID raqamingiz: <code>{message.from_user.id}</code>\n"
        "<i>(Premium tarif so'rash uchun shu ID'ni administratorga yuboring)</i>\n\n"
        "Meni o'z hisobingizga ulash va avto-javoblarni sozlash uchun quyidagi menyudan foydalaning."
    )
    await message.answer(text, reply_markup=get_user_main_kb())

@router.callback_query(F.data == "user_tutorial")
async def show_tutorial(call: CallbackQuery):
    await call.message.edit_text(ONBOARDING_TEXT, reply_markup=get_user_main_kb())

@router.callback_query(F.data == "user_setup_reply")
async def setup_reply_start(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    auto_reply = await get_user_auto_reply(session, call.from_user.id)
    current_reply = "O'rnatilmagan"
    if auto_reply:
        if auto_reply.media_type == "text":
            current_reply = auto_reply.greeting_text[:50] + "..." if len(auto_reply.greeting_text) > 50 else auto_reply.greeting_text
        else:
            current_reply = f"{auto_reply.media_type} formati"
            
    await call.message.answer(
        f"Joriy avto-javob: <b>{current_reply}</b>\n\n"
        "Menga yangi avto-javob uchun matn, rasm, video yoki ovozli xabar yuboring."
    )
    await state.set_state(UserSetup.waiting_for_reply_content)
    await call.answer()

@router.message(UserSetup.waiting_for_reply_content, F.content_type.in_([
    ContentType.TEXT, ContentType.PHOTO, ContentType.VIDEO, 
    ContentType.VIDEO_NOTE, ContentType.VOICE, ContentType.DOCUMENT
]))
async def setup_reply_content(message: Message, state: FSMContext, session: AsyncSession):
    media_type = message.content_type
    greeting_text = message.html_text if message.text else message.caption
    media_file_id = None
    
    if media_type == ContentType.TEXT:
        media_type_str = "text"
    elif media_type == ContentType.PHOTO:
        media_type_str = "photo"
        media_file_id = message.photo[-1].file_id
    elif media_type == ContentType.VIDEO:
        media_type_str = "video"
        media_file_id = message.video.file_id
    elif media_type == ContentType.VIDEO_NOTE:
        media_type_str = "video_note"
        media_file_id = message.video_note.file_id
    elif media_type == ContentType.VOICE:
        media_type_str = "voice"
        media_file_id = message.voice.file_id
    elif media_type == ContentType.DOCUMENT:
        media_type_str = "document"
        media_file_id = message.document.file_id
    else:
        return await message.answer("Qo'llab-quvvatlanmaydigan format.")

    await set_user_auto_reply(session, message.from_user.id, greeting_text, media_file_id, media_type_str)
    await state.clear()
    await message.answer("✅ Avto-javob muvaffaqiyatli saqlandi!", reply_markup=get_user_main_kb())

@router.callback_query(F.data == "user_setup_links")
async def setup_links_main(call: CallbackQuery, session: AsyncSession):
    links = await get_user_social_links(session, call.from_user.id)
    await call.message.edit_text(
        "Ijtimoiy tarmoq va havola tugmalarini boshqarish:", 
        reply_markup=get_manage_links_kb(links)
    )

@router.callback_query(F.data == "back_to_main")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_text("Asosiy menyu:", reply_markup=get_user_main_kb())

@router.callback_query(F.data.startswith("delete_link_"))
async def delete_link_callback(call: CallbackQuery, session: AsyncSession):
    link_id = int(call.data.split("_")[2])
    await delete_social_link(session, link_id)
    links = await get_user_social_links(session, call.from_user.id)
    await call.message.edit_text("Tugma o'chirildi. Qolgan havolalar:", reply_markup=get_manage_links_kb(links))

@router.callback_query(F.data == "add_new_link")
async def add_new_link_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Qaysi tarmoqqa havola qo'shmoqchisiz?", reply_markup=get_social_platforms_kb())
    await state.set_state(UserSocialLink.waiting_for_platform)

@router.callback_query(F.data.startswith("platform_"), UserSocialLink.waiting_for_platform)
async def process_platform(call: CallbackQuery, state: FSMContext):
    platform = call.data.split("_")[1]
    await state.update_data(platform=platform)
    await call.message.edit_text(f"Siz {platform} ni tanladingiz.\nEndi tugmada qanday nom yozilishini kiriting:\n(Masalan: 📸 Mening Instagramim)")
    await state.set_state(UserSocialLink.waiting_for_title)

@router.message(UserSocialLink.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Juda yaxshi! Endi havola (URL) yoki telefon raqamini kiriting:\n(Masalan: https://instagram.com/uzbek yoki +998901234567)")
    await state.set_state(UserSocialLink.waiting_for_url)

@router.message(UserSocialLink.waiting_for_url)
async def process_url(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    platform = data['platform']
    title = data['title']
    url = message.text
    
    await add_social_link(session, message.from_user.id, platform, title, url)
    await state.clear()
    
    await message.answer("✅ Yangi havola tugmasi qo'shildi!", reply_markup=get_user_main_kb())

@router.callback_query(F.data == "user_profile")
async def user_profile(call: CallbackQuery, session: AsyncSession):
    # Profil ochilganda muddati tugagan premiumni darhol Freemiumga tushiramiz.
    user = await check_and_sync_premium(session, call.from_user.id)
    if not user:
        user = await get_or_create_user(session, call.from_user.id, call.from_user.full_name)

    status = "👑 Premium" if user.is_premium else "🆓 Freemium"
    expiry_line = ""
    if user.is_premium and user.premium_expires_at:
        expiry_line = f"\nMuddati: <b>{user.premium_expires_at.strftime('%Y-%m-%d')}</b> gacha"

    text = (
        f"<b>👤 Profil ma'lumotlari:</b>\n\n"
        f"ID: <code>{user.user_id}</code>\n"
        f"Tarif: <b>{status}</b>{expiry_line}\n"
        f"Business ulanish: {'✅ Faol' if user.connection_id else '❌ Ulanmagan'}"
    )
    await call.message.edit_text(text, reply_markup=get_user_main_kb())

# --- Premium olish oqimi ---

@router.callback_query(F.data == "user_premium_menu")
async def premium_menu(call: CallbackQuery, session: AsyncSession):
    user = await check_and_sync_premium(session, call.from_user.id)
    if not user:
        user = await get_or_create_user(session, call.from_user.id, call.from_user.full_name)

    tariffs = await get_active_tariffs(session)
    trial_available = not user.trial_used

    lines = ["<b>💎 Premium tariflar</b>\n"]
    if user.is_premium and user.premium_expires_at:
        lines.append(f"Joriy holat: 👑 Premium ({user.premium_expires_at.strftime('%Y-%m-%d')} gacha)\n")
    if trial_available:
        lines.append("🎁 Hali sinov muddatidan foydalanmagansiz - bepul 3 kunlik sinovni faollashtiring!")
    if not tariffs:
        lines.append("\nHozircha tariflar qo'shilmagan. Keyinroq qayta urinib ko'ring.")

    await call.message.edit_text("\n".join(lines), reply_markup=get_premium_menu_kb(tariffs, trial_available))

@router.callback_query(F.data == "premium_trial")
async def premium_trial(call: CallbackQuery, session: AsyncSession):
    user = await grant_trial(session, call.from_user.id, trial_days=3)
    if not user:
        return await call.answer("❗️ Siz sinov muddatidan avval foydalanib bo'lgansiz.", show_alert=True)

    await call.answer()
    await call.message.edit_text(
        f"🎉 Tabriklaymiz! Sizga <b>3 kunlik bepul Premium</b> faollashtirildi.\n"
        f"Muddati: <b>{user.premium_expires_at.strftime('%Y-%m-%d')}</b> gacha.",
        reply_markup=get_user_main_kb()
    )

@router.callback_query(F.data.startswith("premium_tariff_"))
async def premium_tariff_details(call: CallbackQuery, session: AsyncSession):
    tariff_id = int(call.data.split("_")[2])
    tariff = await get_tariff(session, tariff_id)
    if not tariff:
        return await call.answer("Bu tarif topilmadi.", show_alert=True)

    card_number = await get_setting(session, "card_number")
    card_line = f"<code>{card_number}</code>" if card_number else "Karta raqami hali kiritilmagan, admin bilan bog'laning."

    text = (
        f"<b>{tariff.name}</b>\n"
        f"Muddati: {tariff.days} kun\n"
        f"Narxi: <b>{tariff.price_text}</b>\n\n"
        f"💳 To'lov uchun karta raqami:\n{card_line}\n\n"
        "To'lovni amalga oshirgach, pastdagi \"✅ To'ladim\" tugmasini bosing. "
        "So'rovingiz administratorga yuboriladi va tasdiqlangach premium avtomatik faollashadi."
    )
    await call.message.edit_text(text, reply_markup=get_tariff_payment_kb(tariff.id))

@router.callback_query(F.data.startswith("premium_pay_"))
async def premium_pay(call: CallbackQuery, session: AsyncSession):
    tariff_id = int(call.data.split("_")[2])
    tariff = await get_tariff(session, tariff_id)
    if not tariff:
        return await call.answer("Bu tarif topilmadi.", show_alert=True)

    req = await create_premium_request(session, call.from_user.id, tariff.id)

    await call.answer()
    await call.message.edit_text(
        "✅ So'rovingiz qabul qilindi!\nAdministrator to'lovni tekshirib, tez orada premiumingizni faollashtiradi.",
        reply_markup=get_user_main_kb()
    )

    admin_text = (
        "💰 <b>Yangi premium so'rovi!</b>\n\n"
        f"Foydalanuvchi: {call.from_user.full_name} (@{call.from_user.username or '—'})\n"
        f"ID: <code>{call.from_user.id}</code>\n"
        f"Tarif: <b>{tariff.name}</b> — {tariff.price_text} ({tariff.days} kun)\n\n"
        "To'lov tushganini tekshirib, quyidagi tugmalardan birini tanlang:"
    )
    for admin_id in config.admin_ids_list:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=get_premium_request_kb(req.id))
        except Exception:
            # Admin botni bloklagan yoki chat topilmadi - qolgan adminlarga yuborishni davom ettiramiz.
            pass