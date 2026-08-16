from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import SocialLink, PremiumTariff, BusinessChat

def get_user_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📖 Botni ulash qo'llanmasi", callback_data="user_tutorial")
            ],
            [
                InlineKeyboardButton(text="⚙️ Avto-javobni sozlash", callback_data="user_setup_reply"),
                InlineKeyboardButton(text="🔗 Tugmalar qo'shish", callback_data="user_setup_links")
            ],
            [
                InlineKeyboardButton(text="🛠 Biznes boshqaruvi", callback_data="biz_management_menu")
            ],
            [
                InlineKeyboardButton(text="💎 Premium olish", callback_data="user_premium_menu")
            ],
            [
                InlineKeyboardButton(text="👤 Profil va Holat", callback_data="user_profile")
            ]
        ]
    )

<<<<<<< HEAD
def get_management_menu_kb(auto_mark_read: bool, reply_every_time: bool = False) -> InlineKeyboardMarkup:
    read_toggle_text = "👁 Avto-o'qish: ✅ Yoqilgan" if auto_mark_read else "👁 Avto-o'qish: ❌ O'chirilgan"
    reply_mode_text = (
        "🔁 Javob rejimi: Har safar" if reply_every_time
        else "🔁 Javob rejimi: Faqat birinchi murojaatga"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=read_toggle_text, callback_data="toggle_auto_read")],
            [InlineKeyboardButton(text=reply_mode_text, callback_data="toggle_reply_mode")],
=======
def get_management_menu_kb(auto_mark_read: bool) -> InlineKeyboardMarkup:
    read_toggle_text = "👁 Avto-o'qish: ✅ Yoqilgan" if auto_mark_read else "👁 Avto-o'qish: ❌ O'chirilgan"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=read_toggle_text, callback_data="toggle_auto_read")],
>>>>>>> 996f2e5fc4d650bd0bd5cb316b85a3dad8b21cfa
            [
                InlineKeyboardButton(text="🗑 Oxirgi qabul qilinganni o'chirish", callback_data="delete_last_received"),
            ],
            [
                InlineKeyboardButton(text="🗑 Oxirgi yuborilganni o'chirish", callback_data="delete_last_sent"),
            ],
            [InlineKeyboardButton(text="👤 Profilni boshqarish", callback_data="biz_profile_menu")],
            [InlineKeyboardButton(text="📖 Hikoya joylash", callback_data="biz_post_story")],
            [InlineKeyboardButton(text="🕒 Rejalashtirilgan hikoyalar", callback_data="biz_scheduled_stories")],
            [InlineKeyboardButton(text="🎁 Sovg'a va Yulduzlar", callback_data="biz_gifts_menu")],
            [InlineKeyboardButton(text="🕐 Ish vaqti", callback_data="biz_working_hours")],
            [InlineKeyboardButton(text="🔑 Kalit so'z javoblari", callback_data="biz_keywords_menu")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="biz_stats")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main")],
        ]
    )

def get_working_hours_kb(enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "🕐 Ish vaqti: ✅ Yoqilgan" if enabled else "🕐 Ish vaqti: ❌ O'chirilgan"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="toggle_working_hours")],
            [InlineKeyboardButton(text="⏰ Soatlarni belgilash", callback_data="set_work_hours")],
            [InlineKeyboardButton(text="✍️ Ish vaqtidan tashqari xabar", callback_data="set_out_of_hours_text")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="biz_management_menu")],
        ]
    )

def get_keywords_menu_kb(keywords: list) -> InlineKeyboardMarkup:
    kb = []
    for kr in keywords:
        kb.append([InlineKeyboardButton(text=f"🗑 {kr.keyword}", callback_data=f"delete_keyword_{kr.id}")])
    kb.append([InlineKeyboardButton(text="➕ Yangi qo'shish", callback_data="add_keyword")])
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="biz_management_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_profile_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ismni tahrirlash", callback_data="edit_name")],
            [InlineKeyboardButton(text="📝 Tarjimai holni tahrirlash", callback_data="edit_bio")],
            [InlineKeyboardButton(text="🔗 Foydalanuvchi nomini tahrirlash", callback_data="edit_username")],
            [InlineKeyboardButton(text="🖼 Profil rasmini tahrirlash", callback_data="edit_photo")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="biz_management_menu")],
        ]
    )

def get_back_to_management_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="biz_management_menu")]]
    )

def get_story_timing_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Hozir joylash", callback_data="story_post_now")],
            [InlineKeyboardButton(text="🕒 Vaqt belgilash", callback_data="story_schedule")],
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="biz_management_menu")],
        ]
    )

def get_scheduled_stories_kb(stories: list) -> InlineKeyboardMarkup:
    kb = []
    for s in stories:
        label = f"🗑 {s.scheduled_at.strftime('%Y-%m-%d %H:%M')} UTC"
        kb.append([InlineKeyboardButton(text=label, callback_data=f"cancel_story_{s.id}")])
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="biz_management_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_gifts_kb(owned_gifts: list) -> InlineKeyboardMarkup:
    """owned_gifts - (index, OwnedGift) juftliklari ro'yxati. Callback_data uzunligi
    64 baytdan oshmasligi uchun to'liq owned_gift_id o'rniga indeks ishlatiladi
    (haqiqiy ID handler ichidagi vaqtinchalik keshdan olinadi)."""
    kb = []
    for idx, g in owned_gifts:
        kb.append([InlineKeyboardButton(
            text=f"⭐️ #{idx + 1} sovg'ani yulduzga aylantirish",
            callback_data=f"gift_to_stars_{idx}"
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="biz_gifts_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_premium_menu_kb(tariffs: list[PremiumTariff], trial_available: bool) -> InlineKeyboardMarkup:
    kb = []
    if trial_available:
        kb.append([InlineKeyboardButton(text="🎁 3 kunlik bepul sinov", callback_data="premium_trial")])
    for tariff in tariffs:
        kb.append([InlineKeyboardButton(text=f"{tariff.name} — {tariff.price_text}", callback_data=f"premium_tariff_{tariff.id}")])
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_tariff_payment_kb(tariff_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ To'ladim", callback_data=f"premium_pay_{tariff_id}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="user_premium_menu")]
        ]
    )

def get_social_platforms_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📸 Instagram", callback_data="platform_instagram"),
                InlineKeyboardButton(text="✈️ Telegram", callback_data="platform_telegram")
            ],
            [
                InlineKeyboardButton(text="📞 Telefon", callback_data="platform_phone"),
                InlineKeyboardButton(text="🌐 Boshqa", callback_data="platform_other")
            ],
            [
                InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main")
            ]
        ]
    )

def get_manage_links_kb(links: list[SocialLink]) -> InlineKeyboardMarkup:
    kb = []
    for link in links:
        kb.append([InlineKeyboardButton(text=f"❌ {link.title}", callback_data=f"delete_link_{link.id}")])
    kb.append([InlineKeyboardButton(text="➕ Yangi qo'shish", callback_data="add_new_link")])
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def build_business_links_kb(links: list[SocialLink]) -> InlineKeyboardMarkup:
    kb = []
    for link in links:
        # url_or_number bo'lishi mumkin. Agar raqam bo'lsa uni tekshirish kerak
        url = link.url_or_number
        if not url.startswith("http") and not url.startswith("tg://"):
            if any(char.isdigit() for char in url):
                 url = "https://t.me/" + "".join(filter(lambda x: x.isdigit() or x == '+', url))
            else:
                 url = f"https://{url}" # Fallback
        kb.append([InlineKeyboardButton(text=link.title, url=url)])
    
    if len(kb) == 0:
        return None
    return InlineKeyboardMarkup(inline_keyboard=kb)