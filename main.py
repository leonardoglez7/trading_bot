import os
from flask import Flask, request
import requests
from datetime import datetime
import pytz

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

# ===== TELEGRAM =====
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=data)

# ===== SESIÓN CUBA =====
def valid_session():
    cuba = pytz.timezone("America/Havana")
    hour = datetime.now(cuba).hour
    return (3 <= hour <= 6) or (9 <= hour <= 11)

# ===== WEBHOOK =====
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    # Filtro horario
    if not valid_session():
        return {"status": "ignored (out of session)"}

    side = data.get("side")

    # Checklist común (todas deben ser TRUE)
    base_conditions = [
        data.get("pullback") is True,
        data.get("rejection") is True,
        data.get("break_structure") is True
    ]

    if not all(base_conditions):
        return {"status": "ignored (conditions not met)"}

    # ===== SELL =====
    if side == "sell":
        if data["price"] < data["vwap"] and data["ema9_slope"] == "down":
            msg = (
                "📉 SEÑAL SELL – EURUSD\n\n"
                f"Precio: {data['price']}\n"
                "Sistema: VWAP + EMA9\n"
                "Riesgo: 20 pips\n"
                "RR mínimo: 1:2\n\n"
                "✔ Tendencia bajista\n"
                "✔ Pullback confirmado\n"
                "✔ Rechazo + ruptura"
            )
            send_telegram(msg)

    # ===== BUY =====
    elif side == "buy":
        if data["price"] > data["vwap"] and data["ema9_slope"] == "up":
            msg = (
                "📈 SEÑAL BUY – EURUSD\n\n"
                f"Precio: {data['price']}\n"
                "Sistema: VWAP + EMA9\n"
                "Riesgo: 20 pips\n"
                "RR mínimo: 1:2\n\n"
                "✔ Tendencia alcista\n"
                "✔ Pullback confirmado\n"
                "✔ Rechazo + ruptura"
            )
            send_telegram(msg)

    return {"status": "ok"}