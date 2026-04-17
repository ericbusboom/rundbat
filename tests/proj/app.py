import os
from datetime import datetime

from flask import Flask, render_template

CONFIG_KEYS = ["FOO", "BAR", "FOO_SECRET", "BAR_SECRET"]

config = {k: os.environ.get(k, "") for k in CONFIG_KEYS}

app = Flask(__name__)


@app.route("/")
def index():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("index.html", config=config, now=now)
