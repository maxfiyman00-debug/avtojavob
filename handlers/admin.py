from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import config
from core.loader import bot
from database.requests import (
    get_all_users_count, get_all_users, get_premium_users_count, grant_premium,
    add_tariff, get_all_tariffs, delete_tariff, get_tariff, set_setting, get_setting,
    get_premium_request, resolve_premium_request
)
from keyboards.admin_kb import get_admin_main_kb, get_cancel_kb, get_tariffs_menu_kb, get_tariffs_list_kb
from states.admin_states import AdminBroadcast, AdminPremium, AdminTariff, AdminCard
from services.broadcaster import broadcast

router = Router()

# Middleware orqali faqat adminlar kirishini ta'minlash ham mumkin, 
# lekin bu yerda oddiy filter ishlatamiz.
def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids_list

@router.message(Command("admin"))
async def admin_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("👑 Super Admin paneliga xush kelibsiz!", reply_markup=get_admin_main_kb())

@router.callback_query(F.data == "admin_stats")
async def show_stats(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return
    count = await get_all_users_count(session)
    premium_count = await get_premium_users_count(session)
    await call.message.edit_text(
        f"📊 Umumiy foydalanuvchilar soni: {count}\n👑 Faol premium foydalanuvchilar: {premium_count}",
        reply_markup=get_admin_main_kb()
    )

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("Barcha foydalanuvchilarga yuboriladigan xabarni kiriting (yoki bekor qiling):", reply_markup=get_cancel_kb())
    await state.set_state(AdminBroadcast.waiting_for_message)

@router.callback_query(F.data == "admin_cancel")
async def cancel_admin_flow(call: CallbackQuery, state: FSMContext):
    # Broadcast, premium yoki boshqa istalgan admin FSM oqimini bekor qiladi.
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text("Bekor qilindi.", reply_markup=get_admin_main_kb())

@router.message(AdminBroadcast.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    users = await get_all_users(session)
    user_ids = [u.user_id for u in users]
    
    msg = await message.answer(f"Ommaviy xabar yuborish boshlandi. Jami: {len(user_ids)} ta foydalanuvchi.")
    
    # Text orqali jo'natamiz. Media fayllarni copy_message qilib jo'natish qismi murakkabroq bo'lishi mumkin.
    count = await broadcast(bot, user_ids, message.html_text)
    
    await msg.reply(f"Xabar yuborish yakunlandi.\nMuvaffaqiyatli: {count} ta")

@router.callback_query(F.data == "admin_premium")
async def admin_premium(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        "👑 <b>Premium berish</b>\n\n"
        "Premium beriladigan foydalanuvchining Telegram ID raqamini yuboring.\n"
        "<i>(Foydalanuvchi ID'sini bilish uchun u avval botga /start bosgan bo'lishi kerak)</i>",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(AdminPremium.waiting_for_user_id)

@router.message(AdminPremium.waiting_for_user_id)
async def admin_premium_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        return await message.answer("❗️ Iltimos, faqat raqamlardan iborat Telegram ID yuboring.", reply_markup=get_cancel_kb())

    await state.update_data(target_user_id=int(raw))
    await message.answer("Necha kunlik premium berilsin? (masalan: 30)", reply_markup=get_cancel_kb())
    await state.set_state(AdminPremium.waiting_for_days)

@router.message(AdminPremium.waiting_for_days)
async def admin_premium_days(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        return await message.answer("❗️ Iltimos, musbat butun son kiriting (masalan: 30).", reply_markup=get_cancel_kb())

    data = await state.get_data()
    target_user_id = data["target_user_id"]
    days = int(raw)
    await state.clear()

    user = await grant_premium(session, target_user_id, days)
    if not user:
        return await message.answer(
            f"❌ <code>{target_user_id}</code> ID'li foydalanuvchi topilmadi.\n"
            "U botga hech bo'lmaganda bir marta /start bosgan bo'lishi kerak.",
            reply_markup=get_admin_main_kb()
        )

    expiry_str = user.premium_expires_at.strftime("%Y-%m-%d %H:%M")
    await message.answer(
        f"✅ Premium berildi!\n\n"
        f"Foydalanuvchi: <code>{target_user_id}</code>\n"
        f"Amal qilish muddati: <b>{expiry_str}</b> gacha",
        reply_markup=get_admin_main_kb()
    )

    try:
        await bot.send_message(
            target_user_id,
            f"🎉 Tabriklaymiz! Sizga <b>{days} kunlik Premium</b> tarif faollashtirildi.\n"
            f"Amal qilish muddati: <b>{expiry_str}</b> gacha."
        )
    except Exception:
        # Foydalanuvchi botni bloklagan yoki boshqa sabab bo'lishi mumkin - buni admin oqimini to'xtatmaymiz.
        pass

# --- Tariflar va karta boshqaruvi ---

@router.callback_query(F.data == "admin_tariffs_menu")
async def admin_tariffs_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("💳 <b>Tariflar va to'lov sozlamalari</b>", reply_markup=get_tariffs_menu_kb())

@router.callback_query(F.data == "admin_back_main")
async def admin_back_main(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("👑 Super Admin paneli", reply_markup=get_admin_main_kb())

@router.callback_query(F.data == "admin_add_tariff")
async def admin_add_tariff_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        "Yangi tarif nomini kiriting (masalan: <b>1 oylik</b>):",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(AdminTariff.waiting_for_name)

@router.message(AdminTariff.waiting_for_name)
async def admin_add_tariff_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        return await message.answer("❗️ Iltimos, matn ko'rinishida nom kiriting.", reply_markup=get_cancel_kb())
    await state.update_data(tariff_name=message.text.strip())
    await message.answer("Bu tarif necha kunlik? (masalan: 30)", reply_markup=get_cancel_kb())
    await state.set_state(AdminTariff.waiting_for_days)

@router.message(AdminTariff.waiting_for_days)
async def admin_add_tariff_days(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        return await message.answer("❗️ Iltimos, musbat butun son kiriting (masalan: 30).", reply_markup=get_cancel_kb())
    await state.update_data(tariff_days=int(raw))
    await message.answer("Narxini kiriting (masalan: 50 000 so'm):", reply_markup=get_cancel_kb())
    await state.set_state(AdminTariff.waiting_for_price)

@router.message(AdminTariff.waiting_for_price)
async def admin_add_tariff_price(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        return await message.answer("❗️ Iltimos, matn ko'rinishida narx kiriting.", reply_markup=get_cancel_kb())

    data = await state.get_data()
    await state.clear()
    tariff = await add_tariff(session, data["tariff_name"], data["tariff_days"], message.text.strip())

    await message.answer(
        f"✅ Yangi tarif qo'shildi!\n\n"
        f"Nomi: <b>{tariff.name}</b>\n"
        f"Muddati: {tariff.days} kun\n"
        f"Narxi: {tariff.price_text}",
        reply_markup=get_tariffs_menu_kb()
    )

@router.callback_query(F.data == "admin_list_tariffs")
async def admin_list_tariffs(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return
    tariffs = await get_all_tariffs(session)
    if not tariffs:
        return await call.message.edit_text("Hozircha hech qanday tarif qo'shilmagan.", reply_markup=get_tariffs_menu_kb())
    await call.message.edit_text(
        "📋 Mavjud tariflar. O'chirish uchun tarifni bosing:",
        reply_markup=get_tariffs_list_kb(tariffs)
    )

@router.callback_query(F.data.startswith("admin_delete_tariff_"))
async def admin_delete_tariff(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return
    tariff_id = int(call.data.split("_")[3])
    await delete_tariff(session, tariff_id)
    tariffs = await get_all_tariffs(session)
    if not tariffs:
        return await call.message.edit_text("Tarif o'chirildi. Boshqa tarif qolmadi.", reply_markup=get_tariffs_menu_kb())
    await call.message.edit_text("Tarif o'chirildi. Qolgan tariflar:", reply_markup=get_tariffs_list_kb(tariffs))

@router.callback_query(F.data == "admin_set_card")
async def admin_set_card_start(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return
    current = await get_setting(session, "card_number")
    current_line = f"\n\nJoriy karta: <code>{current}</code>" if current else ""
    await call.message.edit_text(
        f"Yangi karta raqamini yuboring (foydalanuvchilarga shu raqam ko'rsatiladi):{current_line}",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(AdminCard.waiting_for_card_number)

@router.message(AdminCard.waiting_for_card_number)
async def admin_set_card_save(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        return await message.answer("❗️ Iltimos, matn ko'rinishida karta raqamini yuboring.", reply_markup=get_cancel_kb())

    await set_setting(session, "card_number", message.text.strip())
    await state.clear()
    await message.answer("✅ Karta raqami saqlandi.", reply_markup=get_tariffs_menu_kb())

# --- Premium so'rovlarini tasdiqlash / rad etish ---

@router.callback_query(F.data.startswith("premium_approve_"))
async def premium_approve(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return
    request_id = int(call.data.split("_")[2])
    req = await resolve_premium_request(session, request_id, approve=True, admin_id=call.from_user.id)
    if not req:
        return await call.answer("❗️ Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)

    tariff = await get_tariff(session, req.tariff_id)
    user = await grant_premium(session, req.user_id, tariff.days)

    await call.answer("Tasdiqlandi ✅")
    await call.message.edit_text(
        call.message.html_text + f"\n\n✅ <b>Tasdiqlandi</b> (admin: {call.from_user.full_name})",
        reply_markup=None
    )

    try:
        await bot.send_message(
            req.user_id,
            f"🎉 Tabriklaymiz! To'lovingiz tasdiqlandi.\n"
            f"Sizga <b>{tariff.name}</b> ({tariff.days} kun) premium faollashtirildi.\n"
            f"Muddati: <b>{user.premium_expires_at.strftime('%Y-%m-%d')}</b> gacha."
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("premium_reject_"))
async def premium_reject(call: CallbackQuery, session: AsyncSession):
    if not is_admin(call.from_user.id):
        return
    request_id = int(call.data.split("_")[2])
    req = await resolve_premium_request(session, request_id, approve=False, admin_id=call.from_user.id)
    if not req:
        return await call.answer("❗️ Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)

    await call.answer("Rad etildi ❌")
    await call.message.edit_text(
        call.message.html_text + f"\n\n❌ <b>Rad etildi</b> (admin: {call.from_user.full_name})",
        reply_markup=None
    )

    try:
        await bot.send_message(
            req.user_id,
            "❌ Afsuski, to'lov so'rovingiz tasdiqlanmadi. Iltimos, administrator bilan bog'laning."
        )
    except Exception:
        pass