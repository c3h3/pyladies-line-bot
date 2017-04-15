# encoding: utf-8

import os
APP_ID  = os.environ.get("APP_ID", "pyladies-201705-group4-demo")

# Variables about linebot
CHANNEL_SECRET  = os.environ.get("CHANNEL_SECRET", "")
ChHANNEL_ACCESS_TOKEN = os.environ.get("ChHANNEL_ACCESS_TOKEN", "")

# Variables about mongodb
MONGODB_HOST = os.environ.get("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", 27017))
MONGODB_USER = os.environ.get("MONGODB_USER", "")
MONGODB_PWD = os.environ.get("MONGODB_PWD", "")
DB = os.environ.get("DB", "pyladies-linebots")


try:
    from local_settings import *
except:
    pass


from linebot import (
    LineBotApi, WebhookHandler
)

from linebot.exceptions import (
    InvalidSignatureError
)

from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage
)

handler = WebhookHandler(CHANNEL_SECRET)
line_bot_api = LineBotApi(ChHANNEL_ACCESS_TOKEN)


from pymongo import MongoClient

mcli = MongoClient(host=MONGODB_HOST, port=MONGODB_PORT)
db = mcli[DB]

if MONGODB_USER!="":
    db.authenticate(MONGODB_USER,MONGODB_PWD)



from todos_hello_mongodb import (
    save_event, save_message
)

from flask import Flask, request, abort

app = Flask(__name__)

@app.route('/')
def index():
    return "<p>Hello! This is {app_id}!</p>".format(app_id=APP_ID)


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)  # default
def handle_text_message(event):  # default

    my_line_id = event.source.sender_id

    # TODO: save the event data into mongodb
    save_event(db, APP_ID, my_line_id, event)

    if event.type == "message":

        # TODO: save the message data into mongodb
        save_message(db, APP_ID, my_line_id, event.message)

        msg = event.message.text  # message from user
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="Your line id is {line_id}. Your message is: {msg}".format(line_id=my_line_id,msg=msg)))


if __name__ == "__main__":
    app.run(host='0.0.0.0',port=os.environ['PORT'])
