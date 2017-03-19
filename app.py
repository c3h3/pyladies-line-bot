# encoding: utf-8

import os
APP_ID  = os.environ.get("APP_ID", "pyladies-201705-group4-demo")

try:
    from local_settings import *
except:
    pass

from flask import Flask, request, abort

app = Flask(__name__)

@app.route('/')
def index():
    return "<p>Hello! This is {app_id}!</p>".format(app_id=APP_ID)

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=os.environ['PORT'])
