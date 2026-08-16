from aiogram.fsm.state import State, StatesGroup


class ProfileEdit(StatesGroup):
    """Biznes profilini tahrirlash (Bot API: set_business_account_*)."""
    waiting_for_name = State()
    waiting_for_bio = State()
    waiting_for_username = State()
    waiting_for_photo = State()


class StoryPost(StatesGroup):
    """Biznes hisobi nomidan hikoya (story) joylash."""
    waiting_for_media = State()
    waiting_for_datetime = State()  # "hozir emas, vaqt belgilash" tanlanganda


class WorkingHours(StatesGroup):
    """Ish vaqtini va ish vaqtidan tashqarida yuboriladigan xabarni sozlash."""
    waiting_for_hours = State()
    waiting_for_text = State()


class KeywordReplySetup(StatesGroup):
    """Kalit so'zga asoslangan avtojavob qo'shish."""
    waiting_for_keyword = State()
    waiting_for_reply_text = State()

