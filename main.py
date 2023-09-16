import json
import os
import threading

import aiogram
import asyncio
import time
import requests
from dotenv import load_dotenv
load_dotenv()
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram import Bot, Dispatcher, executor
from aiogram.types import InlineQuery, \
    InputTextMessageContent, InlineQueryResultArticle
from aiogram.dispatcher.filters.builtin import CommandStart
from datetime import datetime
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup

bot = Bot(os.getenv('TOKEN'))
dp = Dispatcher(bot, storage=MemoryStorage())

global started
started = False


class Website(StatesGroup):
    add = State()
    remove = State()


class Admin(StatesGroup):
    timer = State()


def _get(val):
    with open('./websites.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        try: return data[str(val)]
        except Exception as e: return e


def _sign(dic):
    with open('./websites.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    try:
        usr = data[dic]
    except KeyError:
        data[dic] = {}
        with open('./websites.json', 'w', encoding='utf-8') as f:
            json.dump(data, f)


def _edit(dic, val, new):
    with open('./websites.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    try:
        data[dic][val] = new
        with open('./websites.json', 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e: return e


def _delete(dic, val=None):
    with open('./websites.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    try:
        if val is not None: data[dic].append(val)
        else: data.pop(str(dic))
        with open('./websites.json', 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return data[dic]
    except Exception as e: return e


def my_commands():
    return[types.bot_command.BotCommand(command='add', description=f'Add new link to ping every {_get("timer")} mins.')]


def ping_markup(user, website):
    user = _get(user)
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text='✅ YES' if user[str(website)] == 'True' else "YES", callback_data=f'{website}?yes'))
    markup.add(InlineKeyboardButton(text='✅ NO' if user[str(website)] == 'False' else "NO", callback_data=f'{website}?no'))
    return markup


async def ping():
    while 1:
        with open('./websites.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        for user in data:
            if user != 'timer':
                for website in data[user]:
                    try:
                        request = requests.request('get', website)
                    except Exception as e: request = e
                    if data[user][website] == 'True':
                        await notify(user, request, website)
        await asyncio.sleep(int(_get("timer"))*60)


async def notify(user, request, website):
    await bot.send_message(int(user), f'`{website}`: {request}'.replace('.', '\.').replace('>', "\>").replace('<', '\<'), parse_mode='MarkdownV2')


@dp.message_handler(commands=['start'])
async def start(message: types.Message, state: FSMContext):
    _sign(f'{message.from_user.id}')
    await bot.set_my_commands(commands=my_commands())
    await message.reply(f'{_get("timer")}')


@dp.message_handler(commands=['add'])
async def add(message: types.Message, state: FSMContext):
    _sign(f'{message.from_user.id}')
    msg = await message.reply(f'Alright, a new website to ping. Send me a link...')
    await Website.add.set()
    await state.update_data(msg=msg)


@dp.message_handler(state=Website.add)
async def add_website(message: types.Message, state: FSMContext):
    user = _get(f'{message.from_user.id}')
    msg = (await state.get_data())['msg']
    if message.text.startswith('https://') is False: return await msg.edit_text('Link should start with https://')
    if len(message.text) >= 25: return await msg.edit_text('Link is too long...')
    if type(user) is Exception:
        return await msg.edit_text(f'{user}')
    else:
        with open('./websites.json', 'r', encoding='utf') as f:
            data = json.load(f)
        try:
            data[str(message.from_user.id)][message.text] = 'True'
            with open('./websites.json', 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            await message.delete()
            return await msg.edit_text(f'{e}')
        await message.delete()
        await msg.edit_text(f'Alright. I added new website `{message.text}`, should i send you message when i will ping it?'.replace(".", "\."), parse_mode='MarkdownV2', reply_markup=ping_markup(str(message.from_user.id), website=message.text))



@dp.callback_query_handler(state='*')
async def callback(call: CallbackQuery, state: FSMContext):
    await call.answer('⌛...')
    if call.data == 'cancel':
        await state.finish()
        await call.message.delete()
    if '?' in call.data:
        _edit(str(call.from_user.id), call.data.split('?')[0], 'True' if call.data.split('?')[1] == 'yes' else 'False')
        await call.message.edit_reply_markup(reply_markup=ping_markup(str(call.from_user.id), website=call.data.split('?')[0]))


@dp.message_handler(state=Admin.timer)
async def timer(message: types.Message, state: FSMContext):
    msg = (await state.get_data())['msg']
    if message.text.isdigit() is False: await msg.edit_text(text='Message you sent is not a number!'); return await message.delete()
    with open('./websites.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['timer'] = message.text
    with open('./websites.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)
    await message.delete()
    await msg.edit_text(text=f'Successfully set timer time to {_get("timer")} mins.')
    await state.finish()


@dp.message_handler(commands=['timer'])
async def timer(message: types.Message, state: FSMContext):
    if message.from_user.id == int(os.getenv('ADMIN')):
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text='Cancel', callback_data='cancel'))
        msg = await message.reply(f'Current timer: {_get("timer")} mins. Write new one', reply_markup=markup)
        await Admin.timer.set()
        await state.update_data(msg=msg)


async def on_startup(dp):
    asyncio.create_task(ping())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

