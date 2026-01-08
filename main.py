"""
🤖 TRADING BOT SIMPLIFICADO - COMPATIBLE RENDER
"""

import os
import time
import random
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, jsonify
import threading

# ================= CONFIG =================
class Config:
    def __init__(self):
        self.TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
        self.SYMBOL = os.getenv('SYMBOL', 'EURUSD')
        self.CAPITAL = float(os.getenv('CAPITAL_INICIAL', '100.00'))
        self.RIESGO = float(os.getenv('RIESGO_POR_OPERACION', '0.20'))
        
        print("="*50)
        print("🤖 BOT CONFIGURADO")
        print(f"Telegram: {'✅' if self.TELEGRAM_TOKEN else '❌'}")
        print(f"Capital: ${self.CAPITAL:.2f}")
        print("="*50)

# ================= SIMPLE API =================
def get_market_data():
    """Obtener datos simulados del mercado"""
    try:
        # Simular precio EURUSD
        base = 1.08500
        change = random.uniform(-0.001, 0.001)
        price = base + change
        
        return {
            'price': round(price, 5),
            'change': round(change * 10000, 1),  # en pips
            'timestamp': datetime.now().isoformat(),
            'real': False,
            'note': 'Datos simulados para prueba'
        }
    except:
        return {'price': 1.08500, 'error': 'No data'}

# ================= TRADING BOT =================
class TradingBot:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.stats = {
            'capital': config.CAPITAL,
            'trades_today': 0,
            'profit_today': 0.0,
            'loss_today': 0.0,
            'last_update': datetime.now().isoformat()
        }
        print("Bot inicializado")
    
    def analyze(self):
        """Analizar mercado simple"""
        data = get_market_data()
        price = data['price']
        
        # Señal aleatoria para demo
        if random.random() > 0.7:  # 30% chance de señal
            signal_type = random.choice(['BUY', 'SELL'])
            confidence = random.randint(65, 85)
            
            return {
                'type': signal_type,
                'price': price,
                'confidence': confidence,
                'time': datetime.now().isoformat()
            }
        return None
    
    def execute_trade(self, signal):
        """Ejecutar operación simulada"""
        # 70% chance de ganar
        wins = random.random() < 0.7
        
        if wins:
            result = self.config.RIESGO * 2
            self.stats['profit_today'] += result
            status = "WIN"
        else:
            result = -self.config.RIESGO
            self.stats['loss_today'] += abs(result)
            status = "LOSS"
        
        self.stats['capital'] += result
        self.stats['trades_today'] += 1
        
        trade = {
            'id': datetime.now().strftime('%H%M%S'),
            'type': signal['type'],
            'price': signal['price'],
            'result': result,
            'status': status,
            'confidence': signal['confidence']
        }
        
        # Notificar Telegram si configurado
        if self.config.TELEGRAM_TOKEN:
            self.notify_telegram(trade)
        
        print(f"Trade {trade['status']}: ${trade['result']:.2f}")
        return trade
    
    def notify_telegram(self, trade):
        """Enviar notificación a Telegram"""
        try:
            emoji = "✅" if trade['result'] > 0 else "❌"
            msg = (
                f"{emoji} *Trade {trade['status']}*\n\n"
                f"Type: {trade['type']}\n"
                f"Price: {trade['price']:.5f}\n"
                f"Result: ${trade['result']:.2f}\n"
                f"Confidence: {trade['confidence']}%\n"
                f"Time: {datetime.now().strftime('%H:%M')}"
            )
            
            url = f"https://api.telegram.org/bot{self.config.TELEGRAM_TOKEN}/sendMessage"
            data = {
                'chat_id': self.config.TELEGRAM_CHAT_ID,
                'text': msg,
                'parse_mode': 'Markdown'
            }
            requests.post(url, json=data, timeout=10)
        except:
            pass
    
    def start(self):
        """Iniciar bot"""
        self.running = True
        
        # Thread para trading
        def trading_loop():
            while self.running and self.stats['trades_today'] < 5:
                signal = self.analyze()
                if signal:
                    self.execute_trade(signal)
                    time.sleep(30)  # Esperar 30s
                time.sleep(10)  # Revisar cada 10s
        
        thread = threading.Thread(target=trading_loop, daemon=True)
        thread.start()
        
        print("✅ Bot started")
        return True
    
    def stop(self):
        """Detener bot"""
        self.running = False
        print("🛑 Bot stopped")
    
    def get_status(self):
        """Obtener estado"""
        self.stats['last_update'] = datetime.now().isoformat()
        return self.stats

# ================= FLASK APP =================
app = Flask(__name__)
bot = None

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'Trading Bot',
        'version': '1.0',
        'endpoints': ['/', '/health', '/status', '/price']
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/status')
def status():
    if bot:
        return jsonify(bot.get_status())
    return jsonify({'error': 'Bot not initialized'})

@app.route('/price')
def price():
    return jsonify(get_market_data())

@app.route('/start', methods=['POST'])
def start():
    global bot
    if not bot:
        config = Config()
        bot = TradingBot(config)
    
    bot.start()
    return jsonify({'success': True, 'message': 'Bot started'})

@app.route('/stop', methods=['POST'])
def stop():
    global bot
    if bot:
        bot.stop()
        return jsonify({'success': True, 'message': 'Bot stopped'})
    return jsonify({'error': 'Bot not running'})

# ================= INICIALIZACIÓN =================
def init():
    global bot
    print("🚀 Initializing Trading Bot...")
    config = Config()
    bot = TradingBot(config)
    
    # Auto-start if Telegram configured
    if config.TELEGRAM_TOKEN:
        print("🤖 Telegram configured - Bot ready")
    else:
        print("⚠️  Telegram not configured - Use web endpoints")

# ================= EJECUCIÓN =================
if __name__ == '__main__':
    init()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
