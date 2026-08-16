from aiogram.fsm.state import State, StatesGroup

class AdminBroadcast(StatesGroup):
    waiting_for_message = State()

class AdminPremium(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_days = State()

class AdminTariff(StatesGroup):
    waiting_for_name = State()
    waiting_for_days = State()
    waiting_for_price = State()

class AdminCard(StatesGroup):
    waiting_for_card_number = State()