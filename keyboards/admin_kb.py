from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import PremiumTariff

def get_admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
                InlineKeyboardButton(text="📢 Xabar yuborish (Broadcast)", callback_data="admin_broadcast")
            ],
            [
                InlineKeyboardButton(text="👑 Premium berish (ID orqali)", callback_data="admin_premium")
            ],
            [
                InlineKeyboardButton(text="💳 Tariflar va karta", callback_data="admin_tariffs_menu")
            ]
        ]
    )

def get_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
        ]
    )

def get_tariffs_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Yangi tarif qo'shish", callback_data="admin_add_tariff")],
            [InlineKeyboardButton(text="📋 Tariflar ro'yxati (o'chirish)", callback_data="admin_list_tariffs")],
            [InlineKeyboardButton(text="💳 Karta raqamini o'rnatish", callback_data="admin_set_card")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back_main")]
        ]
    )

def get_tariffs_list_kb(tariffs: list[PremiumTariff]) -> InlineKeyboardMarkup:
    kb = []
    for tariff in tariffs:
        kb.append([InlineKeyboardButton(
            text=f"❌ {tariff.name} — {tariff.price_text} ({tariff.days} kun)",
            callback_data=f"admin_delete_tariff_{tariff.id}"
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_tariffs_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_premium_request_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"premium_approve_{request_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"premium_reject_{request_id}")
            ]
        ]
    )