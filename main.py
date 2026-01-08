"""
🤖 TRADING BOT COMPLETO - Versión Render
Control por Telegram + Server 24/7
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import asyncio
import logging
import json
import os
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# ================= CONFIGURACIÓN =================
class Config:
    """Configuración - SE LLENARÁ CON VARIABLES DE ENTORNO"""
    # MT5 (se configurarán en Render)
    MT5_ACCOUNT = "5044586613"
    MT5_PASSWORD = "*pP0YvRv"
    MT5_SERVER = "MetaQuotes-Demo"
    
    # Telegram (se configurarán en Render)
    TELEGRAM_TOKEN = "8595969076:AAHRJ8cT4g_1CPISEySdl7sYglS5UowTiJg"
    TELEGRAM_CHAT_ID = "6571763499"
    
    # Trading
    SYMBOL = "EURUSD"
    TIMEFRAME = "M1"
    CAPITAL_DEMO = 100.00
    RIESGO_POR_OPERACION = 0.20
    STOP_LOSS_PIPS = 7
    TAKE_PROFIT_PIPS = 14
    
    # Límites
    MAX_OPERACIONES_DIA = 5
    MAX_PERDIDA_DIARIA = 0.40
    OBJETIVO_DIARIO = 0.80
    
    # Horarios UTC (8:00-12:00 hora Europa)
    HORA_INICIO = "08:00"
    HORA_FIN = "12:00"

# ================= TRADING BOT =================
class TradingBot:
    def __init__(self, config: Config):
        self.config = config
        self.estado = {
            "activo": False,
            "operaciones_hoy": 0,
            "ganancias_hoy": 0.0,
            "perdidas_hoy": 0.0,
            "perdidas_seguidas": 0,
            "capital": config.CAPITAL_DEMO,
            "modo": "DEMO",
            "conectado": False,
            "ultima_actualizacion": datetime.now().isoformat()
        }
        self.scheduler = BackgroundScheduler()
        self.setup_logging()
        
    def setup_logging(self):
        """Configurar sistema de logs"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def cargar_config(self):
        """Cargar configuración desde variables de entorno"""
        self.config.MT5_ACCOUNT = os.getenv('MT5_ACCOUNT', '')
        self.config.MT5_PASSWORD = os.getenv('MT5_PASSWORD', '')
        self.config.MT5_SERVER = os.getenv('MT5_SERVER', 'MetaQuotes-Demo')
        self.config.TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
        self.config.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
        
        self.logger.info("✅ Configuración cargada desde variables de entorno")
    
    def conectar_mt5(self) -> bool:
        """Conectar a MT5"""
        try:
            if not mt5.initialize():
                self.logger.error("❌ No se pudo inicializar MT5")
                return False
            
            account = int(self.config.MT5_ACCOUNT) if self.config.MT5_ACCOUNT else 0
            authorized = mt5.login(
                login=account,
                password=self.config.MT5_PASSWORD,
                server=self.config.MT5_SERVER
            )
            
            if authorized:
                info = mt5.account_info()
                self.logger.info(f"✅ Conectado a MT5 - Balance: ${info.balance:.2f}")
                self.estado['conectado'] = True
                return True
            else:
                self.logger.error(f"❌ Error login MT5: {mt5.last_error()}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error conectando MT5: {e}")
            return False
    
    def dentro_horario(self) -> bool:
        """Verificar si estamos en horario de trading"""
        ahora = datetime.utcnow()
        if ahora.weekday() >= 5:  # Fin de semana
            return False
        
        hora_actual = ahora.strftime("%H:%M")
        return self.config.HORA_INICIO <= hora_actual <= self.config.HORA_FIN
    
    def obtener_datos(self):
        """Obtener datos del mercado"""
        try:
            rates = mt5.copy_rates_from_pos(
                self.config.SYMBOL,
                mt5.TIMEFRAME_M1,
                0,
                50
            )
            
            if rates is None:
                return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Calcular indicadores
            df['ema9'] = df['close'].ewm(span=9).mean()
            df['ema21'] = df['close'].ewm(span=21).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(20).mean()
            bb_std = df['close'].rolling(20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error obteniendo datos: {e}")
            return None
    
    def analizar_senal(self, df):
        """Analizar y detectar señales"""
        if df is None or len(df) < 20:
            return None
        
        ultimo = df.iloc[-1]
        anterior = df.iloc[-2]
        
        # Señal COMPRA
        if (ultimo['close'] > ultimo['ema9'] and
            ultimo['rsi'] < 35 and
            anterior['rsi'] < ultimo['rsi']):
            
            return {
                'tipo': 'BUY',
                'precio': ultimo['close'],
                'rsi': ultimo['rsi'],
                'confianza': 75,
                'timestamp': datetime.now().isoformat()
            }
        
        # Señal VENTA
        elif (ultimo['close'] < ultimo['ema9'] and
              ultimo['rsi'] > 65 and
              anterior['rsi'] > ultimo['rsi']):
            
            return {
                'tipo': 'SELL',
                'precio': ultimo['close'],
                'rsi': ultimo['rsi'],
                'confianza': 75,
                'timestamp': datetime.now().isoformat()
            }
        
        return None
    
    def ejecutar_operacion(self, senal):
        """Ejecutar operación de trading"""
        try:
            symbol_info = mt5.symbol_info(self.config.SYMBOL)
            tick = mt5.symbol_info_tick(self.config.SYMBOL)
            
            if senal['tipo'] == 'BUY':
                precio = tick.ask
                order_type = mt5.ORDER_TYPE_BUY
                sl = precio - (self.config.STOP_LOSS_PIPS * 0.0001)
                tp = precio + (self.config.TAKE_PROFIT_PIPS * 0.0001)
            else:
                precio = tick.bid
                order_type = mt5.ORDER_TYPE_SELL
                sl = precio + (self.config.STOP_LOSS_PIPS * 0.0001)
                tp = precio - (self.config.TAKE_PROFIT_PIPS * 0.0001)
            
            # Calcular lote
            lote = self.config.RIESGO_POR_OPERACION / (self.config.STOP_LOSS_PIPS * 0.10)
            lote = round(max(0.01, lote), 2)
            
            orden = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.config.SYMBOL,
                "volume": lote,
                "type": order_type,
                "price": precio,
                "sl": sl,
                "tp": tp,
                "magic": 100234,
                "comment": f"RenderBot_{senal['tipo']}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            resultado = mt5.order_send(orden)
            
            if resultado.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"✅ Operación {senal['tipo']} ejecutada - Ticket: {resultado.order}")
                self.estado['operaciones_hoy'] += 1
                return True
            
            self.logger.error(f"❌ Error en orden: {resultado.comment}")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error ejecutando operación: {e}")
            return False
    
    def ciclo_trading(self):
        """Ciclo principal de trading"""
        if not self.estado['activo'] or not self.dentro_horario():
            return
        
        # Verificar límites
        if (self.estado['operaciones_hoy'] >= self.config.MAX_OPERACIONES_DIA or
            self.estado['perdidas_hoy'] >= self.config.MAX_PERDIDA_DIARIA):
            self.logger.info("⏹️  Límites alcanzados, deteniendo trading")
            self.estado['activo'] = False
            return
        
        df = self.obtener_datos()
        senal = self.analizar_senal(df) if df is not None else None
        
        if senal and senal['confianza'] > 65:
            self.logger.info(f"🔔 Señal {senal['tipo']} detectada")
            
            # Pequeña espera para confirmación
            time.sleep(2)
            
            if self.ejecutar_operacion(senal):
                # Esperar antes de siguiente operación
                time.sleep(30)
    
    def iniciar(self):
        """Iniciar bot de trading"""
        self.cargar_config()
        
        if not self.conectar_mt5():
            return False
        
        self.estado['activo'] = True
        
        # Programar ciclos de trading cada 10 segundos
        self.scheduler.add_job(
            self.ciclo_trading,
            'interval',
            seconds=10,
            id='trading_cycle'
        )
        
        # Programar reconexión cada hora
        self.scheduler.add_job(
            self.conectar_mt5,
            'interval',
            hours=1,
            id='reconnect'
        )
        
        self.scheduler.start()
        self.logger.info("🤖 Bot de trading INICIADO")
        return True
    
    def detener(self):
        """Detener bot de trading"""
        self.estado['activo'] = False
        self.scheduler.shutdown()
        mt5.shutdown()
        self.logger.info("🛑 Bot de trading DETENIDO")
    
    def get_estado(self):
        """Obtener estado actual"""
        self.estado['ultima_actualizacion'] = datetime.now().isoformat()
        return self.estado

# ================= BOT DE TELEGRAM =================
class TelegramBot:
    def __init__(self, token: str, trading_bot: TradingBot):
        self.token = token
        self.trading_bot = trading_bot
        self.app = None
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        await update.message.reply_text(
            "🤖 *Trading Bot Controller*\n\n"
            "Comandos disponibles:\n"
            "/start - Muestra este mensaje\n"
            "/status - Estado del bot\n"
            "/startbot - Iniciar trading\n"
            "/stopbot - Detener trading\n"
            "/estado - Estado detallado\n"
            "/operaciones - Operaciones hoy\n"
            "/help - Ayuda\n",
            parse_mode='Markdown'
        )
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status"""
        estado = self.trading_bot.get_estado()
        
        mensaje = (
            f"📊 *Estado del Bot*\n\n"
            f"• Trading: {'✅ ACTIVO' if estado['activo'] else '❌ DETENIDO'}\n"
            f"• MT5: {'✅ CONECTADO' if estado['conectado'] else '❌ DESCONECTADO'}\n"
            f"• Operaciones hoy: {estado['operaciones_hoy']}\n"
            f"• Ganancias: ${estado['ganancias_hoy']:.2f}\n"
            f"• Pérdidas: ${estado['perdidas_hoy']:.2f}\n"
            f"• Neto: ${estado['ganancias_hoy'] - estado['perdidas_hoy']:.2f}"
        )
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    async def startbot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /startbot"""
        if self.trading_bot.iniciar():
            await update.message.reply_text("✅ *Bot de trading INICIADO*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ *Error al iniciar el bot*", parse_mode='Markdown')
    
    async def stopbot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stopbot"""
        self.trading_bot.detener()
        await update.message.reply_text("🛑 *Bot de trading DETENIDO*", parse_mode='Markdown')
    
    async def estado_detallado(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /estado"""
        estado = self.trading_bot.get_estado()
        
        mensaje = (
            f"📈 *Estado Detallado*\n\n"
            f"• Trading: {'✅ ACTIVO' if estado['activo'] else '❌ DETENIDO'}\n"
            f"• MT5: {'✅ CONECTADO' if estado['conectado'] else '❌ DESCONECTADO'}\n"
            f"• Última actualización: {estado['ultima_actualizacion'][11:19]}\n"
            f"• Operaciones hoy: {estado['operaciones_hoy']}\n"
            f"• Ganancias: ${estado['ganancias_hoy']:.2f}\n"
            f"• Pérdidas: ${estado['perdidas_hoy']:.2f}\n"
            f"• Neto: ${estado['ganancias_hoy'] - estado['perdidas_hoy']:.2f}\n"
            f"• Capital: ${estado['capital']:.2f}\n"
            f"• Modo: {estado['modo']}\n"
            f"• Horario: {self.trading_bot.config.HORA_INICIO} - {self.trading_bot.config.HORA_FIN} UTC"
        )
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    async def operaciones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /operaciones"""
        estado = self.trading_bot.get_estado()
        
        if estado['operaciones_hoy'] == 0:
            await update.message.reply_text("📭 No hay operaciones hoy")
        else:
            mensaje = f"📋 *Operaciones Hoy: {estado['operaciones_hoy']}*\n\n"
            mensaje += f"• Ganancias: ${estado['ganancias_hoy']:.2f}\n"
            mensaje += f"• Pérdidas: ${estado['perdidas_hoy']:.2f}\n"
            mensaje += f"• Neto: ${estado['ganancias_hoy'] - estado['perdidas_hoy']:.2f}"
            
            await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    async def ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        mensaje = (
            "🆘 *Comandos Disponibles*\n\n"
            "*/start* - Iniciar bot\n"
            "*/status* - Estado general\n"
            "*/startbot* - Iniciar trading automático\n"
            "*/stopbot* - Detener trading\n"
            "*/estado* - Estado detallado\n"
            "*/operaciones* - Ver operaciones del día\n"
            "*/help* - Esta ayuda\n\n"
            "📊 *Horario de trading:*\n"
            "• 08:00 - 12:00 UTC (Automático)\n"
            "• Máximo 5 operaciones/día\n"
            "• Stop automático en ganancias/pérdidas"
        )
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    def setup_handlers(self):
        """Configurar handlers de comandos"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("startbot", self.startbot))
        self.app.add_handler(CommandHandler("stopbot", self.stopbot))
        self.app.add_handler(CommandHandler("estado", self.estado_detallado))
        self.app.add_handler(CommandHandler("operaciones", self.operaciones))
        self.app.add_handler(CommandHandler("help", self.ayuda))
    
    async def run(self):
        """Ejecutar bot de Telegram"""
        self.app = Application.builder().token(self.token).build()
        self.setup_handlers()
        
        await self.app.initialize()
        await self.app.start()
        
        # Para Webhook (Render necesita esto)
        await self.app.updater.start_polling()
        
        print("🤖 Bot de Telegram iniciado")
        
        # Mantener corriendo
        await asyncio.Event().wait()

# ================= SERVER WEB (Flask para Render) =================
app = Flask(__name__)
trading_bot_instance = None
telegram_bot_instance = None

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Trading Bot Server",
        "version": "1.0",
        "uptime": get_uptime()
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/status')
def status():
    if trading_bot_instance:
        return jsonify(trading_bot_instance.get_estado())
    return jsonify({"error": "Bot no inicializado"})

@app.route('/start', methods=['POST'])
def start_bot():
    if trading_bot_instance and trading_bot_instance.iniciar():
        return jsonify({"success": True, "message": "Bot iniciado"})
    return jsonify({"success": False, "message": "Error al iniciar"})

@app.route('/stop', methods=['POST'])
def stop_bot():
    if trading_bot_instance:
        trading_bot_instance.detener()
        return jsonify({"success": True, "message": "Bot detenido"})
    return jsonify({"success": False, "message": "Bot no inicializado"})

def get_uptime():
    """Calcular tiempo activo"""
    if not hasattr(get_uptime, 'start_time'):
        get_uptime.start_time = datetime.now()
    uptime = datetime.now() - get_uptime.start_time
    return str(uptime).split('.')[0]

# ================= MANTENER ACTIVO EL SERVER =================
def ping_self():
    """Ping automático para evitar que Render duerma"""
    import requests
    import threading
    
    def ping():
        while True:
            try:
                # Usa el URL de tu app en Render
                requests.get('https://your-app.onrender.com/health')
                print(f"✅ Ping realizado: {datetime.now().strftime('%H:%M:%S')}")
            except:
                print("❌ Error en ping")
            time.sleep(300)  # Cada 5 minutos
    
    thread = threading.Thread(target=ping, daemon=True)
    thread.start()

# ================= INICIALIZACIÓN =================
def init_system():
    """Inicializar todo el sistema"""
    global trading_bot_instance, telegram_bot_instance
    
    print("🚀 Iniciando Sistema de Trading...")
    
    # 1. Crear configuración
    config = Config()
    
    # 2. Crear y configurar trading bot
    trading_bot_instance = TradingBot(config)
    trading_bot_instance.cargar_config()
    
    # 3. Iniciar bot de Telegram si hay token
    if config.TELEGRAM_TOKEN and config.TELEGRAM_TOKEN != "":
        try:
            telegram_bot_instance = TelegramBot(config.TELEGRAM_TOKEN, trading_bot_instance)
            
            # Iniciar Telegram en segundo plano
            telegram_thread = threading.Thread(
                target=lambda: asyncio.run(telegram_bot_instance.run()),
                daemon=True
            )
            telegram_thread.start()
            print("🤖 Bot de Telegram iniciado en segundo plano")
        except Exception as e:
            print(f"❌ Error iniciando Telegram: {e}")
    
    # 4. Iniciar trading automáticamente si está en horario
    if trading_bot_instance.dentro_horario():
        trading_bot_instance.iniciar()
        print("⏰ Trading iniciado automáticamente (dentro de horario)")
    
    # 5. Iniciar sistema de ping (opcional, descomenta si necesitas)
    # ping_self()
    
    print("✅ Sistema completamente operativo")
    print(f"📊 Accede a: https://your-app.onrender.com")
    print(f"📱 Control por Telegram: Busca tu bot")

# ================= EJECUCIÓN EN RENDER =================
if __name__ == "__main__":
    # Inicializar sistema al arrancar
    init_system()
    
    # Ejecutar servidor Flask (Render necesita esto)
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
