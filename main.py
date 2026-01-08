"""
🤖 TRADING BOT ULTRA SIMPLE - SIN PANDAS
100% compatible con Render
"""

import os
import time
import random
import json
import requests
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
        self.SL_PIPS = int(os.getenv('STOP_LOSS_PIPS', '7'))
        self.TP_PIPS = int(os.getenv('TAKE_PROFIT_PIPS', '14'))
        
        print("="*60)
        print("🤖 TRADING BOT - SIN PANDAS")
        print("="*60)
        print(f"Telegram: {'✅ CONFIGURADO' if self.TELEGRAM_TOKEN else '❌ NO'}")
        print(f"Símbolo: {self.SYMBOL}")
        print(f"Capital: ${self.CAPITAL:.2f}")
        print(f"Riesgo/op: ${self.RIESGO:.2f}")
        print(f"Stop Loss: {self.SL_PIPS} pips")
        print(f"Take Profit: {self.TP_PIPS} pips")
        print("="*60)

# ================= MERCADO SIMULADO =================
class MercadoSimulado:
    """Simula precios sin necesidad de pandas"""
    
    def __init__(self, simbolo="EURUSD"):
        self.simbolo = simbolo
        self.precio_base = 1.08500
        
    def obtener_precio(self):
        """Generar precio simulado"""
        cambio = random.uniform(-0.0005, 0.0005)  # +/- 5 pips
        self.precio_base += cambio
        
        # Mantener rango realista
        self.precio_base = max(1.05000, min(1.12000, self.precio_base))
        
        return {
            'bid': round(self.precio_base - 0.00002, 5),
            'ask': round(self.precio_base, 5),
            'time': datetime.now().isoformat(),
            'simbolo': self.simbolo
        }
    
    def calcular_rsi_simple(self, precio_actual, historial):
        """Calcular RSI simple sin pandas"""
        if len(historial) < 14:
            return 50.0
        
        ganancias = []
        perdidas = []
        
        for i in range(1, min(15, len(historial))):
            cambio = historial[-i] - historial[-i-1] if i < len(historial) else 0
            if cambio > 0:
                ganancias.append(cambio)
            else:
                perdidas.append(abs(cambio))
        
        avg_gain = sum(ganancias) / len(ganancias) if ganancias else 0
        avg_loss = sum(perdidas) / len(perdidas) if perdidas else 0.001  # Evitar división por 0
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)

# ================= TRADING BOT =================
class TradingBot:
    def __init__(self, config):
        self.config = config
        self.mercado = MercadoSimulado(config.SYMBOL)
        self.historial_precios = []
        
        self.estado = {
            'activo': False,
            'capital': config.CAPITAL,
            'operaciones_hoy': 0,
            'ganancias_hoy': 0.0,
            'perdidas_hoy': 0.0,
            'precio_actual': 0.0,
            'rsi_actual': 50.0,
            'ultima_actualizacion': datetime.now().isoformat(),
            'modo': 'SIMULADO SIN PANDAS'
        }
        
        print("✅ Bot inicializado sin pandas")
    
    def dentro_horario(self):
        """Verificar horario de trading"""
        ahora = datetime.utcnow()
        if ahora.weekday() >= 5:
            return False
        
        hora_actual = ahora.strftime("%H:%M")
        return "08:00" <= hora_actual <= "12:00"
    
    def analizar_mercado(self):
        """Analizar mercado sin pandas"""
        if not self.dentro_horario():
            return None
        
        # Obtener precio
        precio_data = self.mercado.obtener_precio()
        precio_actual = precio_data['ask']
        
        # Actualizar historial
        self.historial_precios.append(precio_actual)
        if len(self.historial_precios) > 100:
            self.historial_precios = self.historial_precios[-50:]  # Mantener últimos 50
        
        # Calcular RSI
        rsi = self.mercado.calcular_rsi_simple(precio_actual, self.historial_precios)
        self.estado['precio_actual'] = precio_actual
        self.estado['rsi_actual'] = rsi
        
        # Media móvil simple (reemplazo de EMA)
        if len(self.historial_precios) >= 9:
            sma_9 = sum(self.historial_precios[-9:]) / 9
        else:
            sma_9 = precio_actual
        
        # Detectar señales
        if precio_actual > sma_9 and rsi < 35:
            return {
                'tipo': 'BUY',
                'precio': precio_actual,
                'rsi': rsi,
                'sma': sma_9,
                'confianza': 75,
                'timestamp': datetime.now().isoformat()
            }
        elif precio_actual < sma_9 and rsi > 65:
            return {
                'tipo': 'SELL',
                'precio': precio_actual,
                'rsi': rsi,
                'sma': sma_9,
                'confianza': 75,
                'timestamp': datetime.now().isoformat()
            }
        
        return None
    
    def ejecutar_operacion(self, senal):
        """Ejecutar operación simulada"""
        # Probabilidad basada en confianza
        prob_exito = senal['confianza'] / 100 * 0.8
        
        if random.random() < prob_exito:
            resultado = self.config.RIESGO * 2  # Ratio 1:2
            estado = "✅ GANADA"
            self.estado['ganancias_hoy'] += resultado
        else:
            resultado = -self.config.RIESGO
            estado = "❌ PERDIDA"
            self.estado['perdidas_hoy'] += abs(resultado)
        
        self.estado['capital'] += resultado
        self.estado['operaciones_hoy'] += 1
        
        operacion = {
            'id': datetime.now().strftime('%H%M%S'),
            'tipo': senal['tipo'],
            'precio': senal['precio'],
            'resultado': resultado,
            'estado': estado,
            'confianza': senal['confianza'],
            'timestamp': senal['timestamp']
        }
        
        # Notificar Telegram
        self.notificar_telegram(operacion)
        
        print(f"\n📊 {operacion['estado']} {operacion['tipo']}")
        print(f"   Precio: {operacion['precio']:.5f}")
        print(f"   Resultado: ${operacion['resultado']:.2f}")
        print(f"   Capital: ${self.estado['capital']:.2f}")
        
        return operacion
    
    def notificar_telegram(self, operacion):
        """Enviar notificación a Telegram"""
        if not self.config.TELEGRAM_TOKEN:
            return
        
        try:
            mensaje = (
                f"{operacion['estado']} *Operación {operacion['tipo']}*\n\n"
                f"• Par: {self.config.SYMBOL}\n"
                f"• Precio: {operacion['precio']:.5f}\n"
                f"• Resultado: ${operacion['resultado']:.2f}\n"
                f"• Confianza: {operacion['confianza']}%\n"
                f"• Capital: ${self.estado['capital']:.2f}\n"
                f"• Hora: {operacion['timestamp'][11:19]}\n"
                f"• Modo: Simulación\n"
                f"• Ops hoy: {self.estado['operaciones_hoy']}/5"
            )
            
            url = f"https://api.telegram.org/bot{self.config.TELEGRAM_TOKEN}/sendMessage"
            data = {
                'chat_id': self.config.TELEGRAM_CHAT_ID,
                'text': mensaje,
                'parse_mode': 'Markdown'
            }
            
            requests.post(url, json=data, timeout=10)
            print("📱 Notificación enviada a Telegram")
            
        except Exception as e:
            print(f"❌ Error Telegram: {e}")
    
    def ciclo_trading(self):
        """Ciclo principal"""
        print("🔄 Iniciando ciclo de trading...")
        
        while self.estado['activo']:
            try:
                # Verificar límites
                if (self.estado['operaciones_hoy'] >= 5 or
                    self.estado['perdidas_hoy'] >= 0.40):
                    print("🎯 Límites alcanzados")
                    self.estado['activo'] = False
                    break
                
                # Analizar
                senal = self.analizar_mercado()
                
                if senal and senal['confianza'] >= 70:
                    print(f"\n🔔 Señal {senal['tipo']} detectada!")
                    print(f"   Precio: {senal['precio']:.5f}, RSI: {senal['rsi']:.1f}")
                    
                    # Esperar confirmación
                    time.sleep(2)
                    
                    # Ejecutar
                    self.ejecutar_operacion(senal)
                    
                    # Esperar antes de siguiente
                    time.sleep(30)
                
                # Mostrar estado
                hora = datetime.now().strftime("%H:%M:%S")
                precio = self.estado.get('precio_actual', 0)
                ops = self.estado['operaciones_hoy']
                pl = self.estado['ganancias_hoy'] - self.estado['perdidas_hoy']
                
                print(f"[{hora}] {self.config.SYMBOL}: {precio:.5f} | Ops: {ops}/5 | P/L: ${pl:.2f}", end='\r')
                
                # Actualizar timestamp
                self.estado['ultima_actualizacion'] = datetime.now().isoformat()
                
                # Esperar
                time.sleep(15)
                
            except Exception as e:
                print(f"\n❌ Error en ciclo: {e}")
                time.sleep(30)
    
    def iniciar(self):
        """Iniciar bot"""
        self.estado['activo'] = True
        
        # Thread para trading
        thread = threading.Thread(target=self.ciclo_trading, daemon=True)
        thread.start()
        
        print("✅ Bot INICIADO")
        
        # Notificar Telegram
        if self.config.TELEGRAM_TOKEN:
            self.enviar_mensaje_telegram(
                "🤖 *TRADING BOT INICIADO*\n\n"
                f"• Símbolo: {self.config.SYMBOL}\n"
                f"• Capital: ${self.estado['capital']:.2f}\n"
                f"• Riesgo/op: ${self.config.RIESGO:.2f}\n"
                f"• Horario: 08:00-12:00 UTC\n"
                f"• Modo: Simulación\n"
                f"• Estado: ACTIVO ✅"
            )
        
        return True
    
    def enviar_mensaje_telegram(self, mensaje):
        """Enviar mensaje simple"""
        try:
            url = f"https://api.telegram.org/bot{self.config.TELEGRAM_TOKEN}/sendMessage"
            data = {
                'chat_id': self.config.TELEGRAM_CHAT_ID,
                'text': mensaje,
                'parse_mode': 'Markdown'
            }
            requests.post(url, json=data, timeout=10)
        except:
            pass
    
    def detener(self):
        """Detener bot"""
        self.estado['activo'] = False
        
        # Resumen
        neto = self.estado['ganancias_hoy'] - self.estado['perdidas_hoy']
        
        print("\n" + "="*60)
        print("🛑 BOT DETENIDO - RESUMEN")
        print("="*60)
        print(f"Operaciones: {self.estado['operaciones_hoy']}")
        print(f"Ganancias: ${self.estado['ganancias_hoy']:.2f}")
        print(f"Pérdidas: ${self.estado['perdidas_hoy']:.2f}")
        print(f"Neto: ${neto:.2f}")
        print(f"Capital final: ${self.estado['capital']:.2f}")
        print("="*60)
        
        # Notificar Telegram
        if self.config.TELEGRAM_TOKEN:
            self.enviar_mensaje_telegram(
                "🛑 *BOT DETENIDO*\n\n"
                f"• Operaciones: {self.estado['operaciones_hoy']}\n"
                f"• Neto: ${neto:.2f}\n"
                f"• Capital: ${self.estado['capital']:.2f}\n"
                f"• Rendimiento: {(neto/self.config.CAPITAL*100):.1f}%"
            )
    
    def get_status(self):
        """Obtener estado"""
        self.estado['ultima_actualizacion'] = datetime.now().isoformat()
        return self.estado

# ================= FLASK APP =================
app = Flask(__name__)
bot = None

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'Trading Bot (sin pandas)',
        'version': '2.0',
        'features': [
            'Bot de trading simple',
            'Notificaciones Telegram',
            'Gestión de riesgo',
            'Simulación de mercado',
            '100% compatible Render'
        ]
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'python_version': '3.10.0'
    })

@app.route('/status')
def status():
    if bot:
        return jsonify(bot.get_status())
    return jsonify({'error': 'Bot no inicializado'})

@app.route('/precio')
def precio():
    """Obtener precio simulado"""
    if bot:
        precio_data = bot.mercado.obtener_precio()
        return jsonify(precio_data)
    return jsonify({'price': 1.08500, 'note': 'Bot no activo'})

@app.route('/start', methods=['POST'])
def start():
    global bot
    if not bot:
        config = Config()
        bot = TradingBot(config)
    
    bot.iniciar()
    return jsonify({'success': True, 'message': 'Bot iniciado'})

@app.route('/stop', methods=['POST'])
def stop():
    global bot
    if bot:
        bot.detener()
        return jsonify({'success': True, 'message': 'Bot detenido'})
    return jsonify({'error': 'Bot no inicializado'})

# ================= PING AUTOMÁTICO =================
def keep_alive():
    """Mantener activo el servidor"""
    def ping():
        while True:
            try:
                url = os.getenv('RENDER_EXTERNAL_URL', '')
                if url:
                    requests.get(f'{url}/health', timeout=10)
                    print(f"🏓 Ping: {datetime.now().strftime('%H:%M:%S')}")
            except:
                print("⚠️  Error en ping")
            time.sleep(300)
    
    thread = threading.Thread(target=ping, daemon=True)
    thread.start()

# ================= INICIALIZACIÓN =================
def init():
    global bot
    
    print("\n" + "="*60)
    print("🚀 TRADING BOT - SIN PANDAS")
    print("="*60)
    
    config = Config()
    bot = TradingBot(config)
    
    # Iniciar sistema de ping
    keep_alive()
    
    # Iniciar automáticamente si Telegram configurado
    if config.TELEGRAM_TOKEN:
        hora_actual = datetime.utcnow().strftime("%H:%M")
        if "08:00" <= hora_actual <= "12:00":
            print("⏰ Horario activo - Iniciando bot...")
            bot.iniciar()
        else:
            print(f"⏰ Fuera de horario ({hora_actual}) - Bot listo")
    else:
        print("⚠️  Telegram no configurado - Use endpoints web")
    
    print("\n✅ Sistema listo")
    print("📊 Endpoints:")
    print("   • /        - Información")
    print("   • /health  - Health check")
    print("   • /status  - Estado del bot")
    print("   • /precio  - Precio simulado")
    print("   • /start   - POST iniciar bot")
    print("   • /stop    - POST detener bot")
    print("="*60)

# ================= EJECUCIÓN =================
if __name__ == '__main__':
    init()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
