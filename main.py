import os
from flask import Flask, request
import requests
from datetime import datetime
import pytz

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=data)

def valid_session():
    cuba = pytz.timezone("America/Havana")
    hour = datetime.now(cuba).hour
    return (3 <= hour <= 6) or (9 <= hour <= 11)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if not valid_session():
        return {"status": "ignored (out of session)"}

    conditions = [
        data["price"] < data["vwap"],
        data["ema9_slope"] == "down",
        data["pullback"] is True,
        data["rejection"] is True,
        data["break_structure"] is True
    ]

    if all(conditions):
        msg = (
            "📉 SEÑAL SELL EURUSD\n\n"
            f"Precio: {data['price']}\n"
            "Sistema: VWAP–EMA9\n"
            "Riesgo: 20 pips\n"
            "RR: 1:2 mínimo\n\n"
            "✔ Todas las condiciones cumplidas"
        )
        send_telegram(msg)

    return {"status": "ok"}