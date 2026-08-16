from aiogram.fsm.state import State, StatesGroup

class UserSetup(StatesGroup):
    waiting_for_reply_content = State()

class UserSocialLink(StatesGroup):
    waiting_for_platform = State()
    waiting_for_title = State()
    waiting_for_url = State()
