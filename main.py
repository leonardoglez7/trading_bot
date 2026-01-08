"""
🤖 TRADING BOT ULTRA SIMPLE - 100% compatible
Sin pandas, sin numpy, sin compilación
"""

import os
import time
import random
from datetime import datetime
from flask import Flask, jsonify, request
import threading
import requests

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# ================= BOT STATE =================
bot_state = {
    'running': False,
    'capital': 100.00,
    'trades_today': 0,
    'profit': 0.0,
    'loss': 0.0,
    'last_price': 1.08500,
    'last_update': datetime.now().isoformat()
}

# ================= TELEGRAM =================
def send_telegram(message):
    """Enviar mensaje a Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except:
        return False

# ================= TRADING LOGIC =================
def generate_price():
    """Generar precio simulado"""
    change = random.uniform(-0.0003, 0.0003)  # +/- 3 pips
    bot_state['last_price'] += change
    bot_state['last_price'] = max(1.07000, min(1.10000, bot_state['last_price']))
    return round(bot_state['last_price'], 5)

def analyze_market():
    """Analizar mercado simple"""
    price = generate_price()
    
    # RSI simulado
    rsi = random.uniform(20, 80)
    
    # Señales simples
    if rsi < 35 and price > 1.08000:
        return {
            'signal': 'BUY',
            'price': price,
            'rsi': round(rsi, 1),
            'confidence': random.randint(70, 85)
        }
    elif rsi > 65 and price < 1.09000:
        return {
            'signal': 'SELL',
            'price': price,
            'rsi': round(rsi, 1),
            'confidence': random.randint(70, 85)
        }
    
    return None

def execute_trade(signal):
    """Ejecutar operación"""
    risk = 0.20  # $0.20 por operación
    wins = random.random() < 0.7  # 70% win rate
    
    if wins:
        result = risk * 2  # 1:2 ratio
        bot_state['profit'] += result
        status = "WIN"
    else:
        result = -risk
        bot_state['loss'] += abs(result)
        status = "LOSS"
    
    bot_state['capital'] += result
    bot_state['trades_today'] += 1
    
    trade = {
        'id': datetime.now().strftime('%H%M%S'),
        'signal': signal['signal'],
        'price': signal['price'],
        'result': round(result, 2),
        'status': status,
        'confidence': signal['confidence'],
        'time': datetime.now().strftime('%H:%M:%S')
    }
    
    # Notificar Telegram
    message = (
        f"{'✅' if wins else '❌'} *Trade {status}*\n\n"
        f"Signal: {trade['signal']}\n"
        f"Price: {trade['price']:.5f}\n"
        f"Result: ${trade['result']:.2f}\n"
        f"Confidence: {trade['confidence']}%\n"
        f"Time: {trade['time']}\n"
        f"Capital: ${bot_state['capital']:.2f}"
    )
    
    send_telegram(message)
    
    return trade

def trading_loop():
    """Loop principal de trading"""
    print("🔄 Trading loop started")
    
    while bot_state['running'] and bot_state['trades_today'] < 5:
        try:
            # Analizar mercado
            signal = analyze_market()
            
            if signal and signal['confidence'] > 70:
                print(f"🔔 Signal: {signal['signal']} at {signal['price']:.5f}")
                
                # Ejecutar trade
                trade = execute_trade(signal)
                print(f"📊 Trade {trade['status']}: ${trade['result']:.2f}")
                
                # Esperar entre trades
                time.sleep(30)
            
            # Actualizar estado
            bot_state['last_update'] = datetime.now().isoformat()
            
            # Mostrar status
            now = datetime.now().strftime('%H:%M:%S')
            price = bot_state['last_price']
            trades = bot_state['trades_today']
            pnl = bot_state['profit'] - bot_state['loss']
            
            print(f"[{now}] EURUSD: {price:.5f} | Trades: {trades}/5 | PnL: ${pnl:.2f}", end='\r')
            
            # Esperar entre análisis
            time.sleep(15)
            
        except Exception as e:
            print(f"❌ Error in trading loop: {e}")
            time.sleep(30)
    
    print("\n🛑 Trading loop stopped")

# ================= FLASK APP =================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'Ultra Simple Trading Bot',
        'version': '1.0',
        'endpoints': {
            '/': 'This page',
            '/health': 'Health check',
            '/status': 'Bot status',
            '/price': 'Current price',
            '/start': 'POST - Start bot',
            '/stop': 'POST - Stop bot'
        }
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'python_version': '3.9.18'
    })

@app.route('/status')
def status():
    return jsonify(bot_state)

@app.route('/price')
def price():
    price = generate_price()
    return jsonify({
        'symbol': 'EURUSD',
        'price': price,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/start', methods=['POST'])
def start_bot():
    if bot_state['running']:
        return jsonify({'error': 'Bot already running'})
    
    bot_state['running'] = True
    
    # Iniciar thread de trading
    thread = threading.Thread(target=trading_loop, daemon=True)
    thread.start()
    
    # Enviar notificación a Telegram
    send_telegram("🤖 *TRADING BOT STARTED*\n\nBot is now running and looking for signals!")
    
    return jsonify({
        'success': True,
        'message': 'Bot started successfully',
        'start_time': datetime.now().isoformat()
    })

@app.route('/stop', methods=['POST'])
def stop_bot():
    bot_state['running'] = False
    
    # Calcular resumen
    net_profit = bot_state['profit'] - bot_state['loss']
    
    # Enviar resumen a Telegram
    summary = (
        "🛑 *TRADING BOT STOPPED*\n\n"
        f"Trades today: {bot_state['trades_today']}\n"
        f"Profit: ${bot_state['profit']:.2f}\n"
        f"Loss: ${bot_state['loss']:.2f}\n"
        f"Net: ${net_profit:.2f}\n"
        f"Final capital: ${bot_state['capital']:.2f}"
    )
    
    send_telegram(summary)
    
    return jsonify({
        'success': True,
        'message': 'Bot stopped successfully',
        'summary': {
            'trades': bot_state['trades_today'],
            'profit': bot_state['profit'],
            'loss': bot_state['loss'],
            'net': net_profit,
            'capital': bot_state['capital']
        }
    })

# ================= KEEP ALIVE =================
def keep_server_alive():
    """Ping automático para evitar que Render duerma"""
    def ping():
        while True:
            try:
                # Usar la URL de Render si está disponible
                render_url = os.getenv('RENDER_EXTERNAL_URL', '')
                if render_url:
                    requests.get(f'{render_url}/health', timeout=5)
                    print(f"🏓 Ping successful: {datetime.now().strftime('%H:%M:%S')}")
                else:
                    # Si no hay URL, solo mantener activo
                    print(f"⏰ Server alive: {datetime.now().strftime('%H:%M:%S')}")
            except:
                print("⚠️  Ping failed")
            
            # Esperar 5 minutos
            time.sleep(300)
    
    # Iniciar en thread separado
    thread = threading.Thread(target=ping, daemon=True)
    thread.start()

# ================= INITIALIZATION =================
@app.before_first_request
def initialize():
    """Inicializar la aplicación"""
    print("\n" + "="*60)
    print("🚀 ULTRA SIMPLE TRADING BOT")
    print("="*60)
    print(f"Python: 3.9.18")
    print(f"Telegram: {'✅ Configured' if TELEGRAM_TOKEN else '❌ Not configured'}")
    print(f"Initial capital: ${bot_state['capital']:.2f}")
    print("\n📊 Endpoints available:")
    print("   http://your-app.onrender.com/")
    print("   http://your-app.onrender.com/health")
    print("   http://your-app.onrender.com/status")
    print("   http://your-app.onrender.com/price")
    print("="*60)
    
    # Iniciar sistema de keep-alive
    keep_server_alive()
    
    # Auto-start si Telegram está configurado
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        current_hour = datetime.utcnow().hour
        if 8 <= current_hour < 12:  # 08:00-12:00 UTC
            print("⏰ Market hours - Auto-starting bot...")
            bot_state['running'] = True
            thread = threading.Thread(target=trading_loop, daemon=True)
            thread.start()
        else:
            print(f"⏰ Outside market hours ({current_hour}:00 UTC) - Bot ready")

# ================= MAIN =================
if __name__ == '__main__':
    # Obtener puerto de Render
    port = int(os.getenv('PORT', 5000))
    
    # Inicializar
    @app.before_first_request
    def init():
        initialize()
    
    # Ejecutar servidor
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
