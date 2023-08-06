import json
import traceback

import telebot
from ninja import Router
from telebot import apihelper

from toolbox import views as toolbox
from toolbox.views import logger

# Create your views here.
router = Router(tags=['telebot'])

notify = toolbox.parse_toml("notify").get('telegram_push')
telegram_token = notify.get('telegram_token')
telegram_chat_id = notify.get('telegram_chat_id')
bot = telebot.TeleBot(telegram_token)
proxy = notify.get('proxy')
if proxy:
    apihelper.proxy = proxy


@router.post("/callback")
def get_telebot_operate(request):
    try:
        print('in webhook....')  # 測試一下可不可以連到，連到應可以印出資訊
        json_string = json.dumps(json.loads(request.body))
        print(json_string)
        update = telebot.types.Update.de_json(json_string)
        print(update)
        bot.process_new_updates([update])
        return 'webhook is ok'
    except Exception as e:
        msg = f'telebot链接失败：{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(5))
        return msg


@bot.message_handler(func=lambda message: True, content_types=['text'])
def echo(message):
    bot.send_message(message.chat.id, message.text)


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(message.chat.id,
                 ("Hi there, I am EchoBot.\n"
                  "I am here to echo your kind words back to you."))


# Handle all other messages
@bot.message_handler(func=lambda message: True, content_types=['text'])
def echo_message(message):
    bot.reply_to(message.chat.id, message.text)
