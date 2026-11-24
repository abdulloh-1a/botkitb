"""Ariza topshirish va admin operatsiyalari FSM holatlari."""

from aiogram.fsm.state import State, StatesGroup


class ApplicationStates(StatesGroup):
    first_name = State()
    last_name = State()
    age = State()
    grade = State()
    gender = State()
    phone = State()
    confirm = State()
    change_phone = State()


class AdminStates(StatesGroup):
    reject_reason = State()
    search = State()
    add_admin_id = State()
    add_admin_username = State()
    remove_admin = State()
    set_date = State()
    set_time = State()
    set_place = State()
    broadcast = State()
