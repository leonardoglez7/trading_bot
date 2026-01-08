"""
🤖 TRADING BOT COMPLETO + TELEGRAM CONTROL
Versión: 4.0 - Server + Telegram
Autor: Asistente Trading
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import asyncio
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from threading import Thread
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# ================= CONFIGURACIÓN =================
@dataclass
class Config:
    """Configuración del sistema"""
    # MT5 Credenciales (DEMO)
    MT5_ACCOUNT: int = 12345678
    MT5_PASSWORD: str = "tu_password_demo"
    MT5_SERVER: str = "MetaQuotes-Demo"
    
    # Telegram Bot Token (OBTÉN UNO GRATIS)
    TELEGRAM_TOKEN: str = "TU_TELEGRAM_BOT_TOKEN"  # Obtén de @BotFather
    TELEGRAM_CHAT_ID: str = "TU_CHAT_ID"  # Tu ID de chat
    
    # Trading
    SYMBOL: str = "EURUSD"
    TIMEFRAME: str = "M1"
    CAPITAL_DEMO: float = 100.00
    RIESGO_POR_OPERACION: float = 0.20
    STOP_LOSS_PIPS: int = 7
    TAKE_PROFIT_PIPS: int = 14
    
    # Límites
    MAX_OPERACIONES_DIA: int = 5
    MAX_PERDIDA_DIARIA: float = 0.40
    OBJETIVO_DIARIO: float = 0.80
    
    # Horarios (UTC)
    HORA_INICIO: str = "08:00"  # 8 AM Europa
    HORA_FIN: str = "12:00"
    
    # Server
    SERVER_URL: str = ""  # Para webhooks si necesitas

# ================= TRADING BOT =================
class TradingBot:
    def __init__(self, config: Config, telegram_bot=None):
        self.config = config
        self.telegram_bot = telegram_bot
        self.estado = {
            "activo": False,
            "operaciones_hoy": 0,
            "ganancias_hoy": 0.0,
            "perdidas_hoy": 0.0,
            "perdidas_seguidas": 0,
            "capital": config.CAPITAL_DEMO,
            "ultima_senal": None,
            "operaciones": [],
            "modo": "DEMO"
        }
        self.scheduler = BackgroundScheduler()
        self.setup_logging()
        
    def setup_logging(self):
        """Configurar logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    async def enviar_telegram(self, mensaje: str):
        """Enviar mensaje a Telegram"""
        if self.telegram_bot and self.config.TELEGRAM_CHAT_ID:
            try:
                await self.telegram_bot.send_message(
                    chat_id=self.config.TELEGRAM_CHAT_ID,
                    text=mensaje
                )
            except Exception as e:
                self.logger.error(f"Error enviando a Telegram: {e}")
    
    def conectar_mt5(self) -> bool:
        """Conectar a MT5"""
        try:
            if not mt5.initialize():
                self.logger.error("MT5 no pudo inicializarse")
                return False
            
            authorized = mt5.login(
                login=self.config.MT5_ACCOUNT,
                password=self.config.MT5_PASSWORD,
                server=self.config.MT5_SERVER
            )
            
            if authorized:
                self.logger.info("✅ Conectado a MT5")
                asyncio.run(self.enviar_telegram("✅ Bot conectado a MT5"))
                return True
            else:
                self.logger.error(f"Error login MT5: {mt5.last_error()}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error conectando MT5: {e}")
            return False
    
    def dentro_horario(self) -> bool:
        """Verificar horario de trading"""
        ahora = datetime.utcnow()
        if ahora.weekday() >= 5:
            return False
        
        hora_actual = ahora.strftime("%H:%M")
        return self.config.HORA_INICIO <= hora_actual <= self.config.HORA_FIN
    
    def obtener_datos(self) -> Optional[pd.DataFrame]:
        """Obtener datos del mercado"""
        try:
            rates = mt5.copy_rates_from_pos(
                self.config.SYMBOL,
                getattr(mt5, f"TIMEFRAME_{self.config.TIMEFRAME}"),
                0,
                100
            )
            
            if rates is None:
                return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Indicadores
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
    
    def analizar_senal(self, df: pd.DataFrame) -> Optional[Dict]:
        """Analizar y detectar señales"""
        if df is None or len(df) < 20:
            return None
        
        ultimo = df.iloc[-1]
        anterior = df.iloc[-2]
        
        # Señal COMPRA
        if (ultimo['close'] > ultimo['ema9'] and
            ultimo['rsi'] < 35 and
            anterior['rsi'] < ultimo['rsi'] and
            ultimo['close'] <= ultimo['bb_lower'] * 1.0002):
            
            return {
                'tipo': 'BUY',
                'precio': ultimo['close'],
                'rsi': ultimo['rsi'],
                'confianza': 75,
                'timestamp': datetime.now()
            }
        
        # Señal VENTA
        elif (ultimo['close'] < ultimo['ema9'] and
              ultimo['rsi'] > 65 and
              anterior['rsi'] > ultimo['rsi'] and
              ultimo['close'] >= ultimo['bb_upper'] * 0.9998):
            
            return {
                'tipo': 'SELL',
                'precio': ultimo['close'],
                'rsi': ultimo['rsi'],
                'confianza': 75,
                'timestamp': datetime.now()
            }
        
        return None
    
    def ejecutar_operacion(self, senal: Dict) -> bool:
        """Ejecutar operación"""
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
                "comment": f"AutoBot_{senal['tipo']}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            resultado = mt5.order_send(orden)
            
            if resultado.retcode == mt5.TRADE_RETCODE_DONE:
                # Enviar notificación a Telegram
                mensaje = f"""
✅ OPERACIÓN EJECUTADA
Tipo: {senal['tipo']}
Par: {self.config.SYMBOL}
Precio: {precio:.5f}
Lote: {lote}
SL: {sl:.5f}
TP: {tp:.5f}
Ticket: {resultado.order}
                """
                asyncio.run(self.enviar_telegram(mensaje))
                
                self.estado['operaciones_hoy'] += 1
                self.logger.info(f"Operación ejecutada: {senal['tipo']}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error ejecutando operación: {e}")
            return False
    
    def ciclo_trading(self):
        """Ciclo principal de trading"""
        if not self.estado['activo'] or not self.dentro_horario():
            return
        
        df = self.obtener_datos()
        if df is None:
            return
        
        senal = self.analizar_senal(df)
        
        if senal and senal['confianza'] > 65:
            self.logger.info(f"Señal detectada: {senal['tipo']}")
            
            # Enviar alerta a Telegram
            asyncio.run(self.enviar_telegram(
                f"🔔 Señal {senal['tipo']} detectada\n"
                f"Precio: {senal['precio']:.5f}\n"
                f"RSI: {senal['rsi']:.1f}\n"
                f"Confianza: {senal['confianza']}%"
            ))
            
            # Ejecutar después de 2 segundos
            time.sleep(2)
            if self.ejecutar_operacion(senal):
                time.sleep(30)  # Esperar antes de siguiente operación
    
    def iniciar(self):
        """Iniciar bot de trading"""
        if not self.conectar_mt5():
            return False
        
        self.estado['activo'] = True
        
        # Programar ciclos cada 10 segundos
        self.scheduler.add_job(
            self.ciclo_trading,
            'interval',
            seconds=10,
            id='trading_cycle'
        )
        self.scheduler.start()
        
        self.logger.info("🤖 Bot de trading iniciado")
        asyncio.run(self.enviar_telegram("🤖 Bot de trading INICIADO"))
        return True
    
    def detener(self):
        """Detener bot de trading"""
        self.estado['activo'] = False
        self.scheduler.shutdown()
        mt5.shutdown()
        
        self.logger.info("🛑 Bot de trading detenido")
        asyncio.run(self.enviar_telegram("🛑 Bot de trading DETENIDO"))
    
    def get_estado(self) -> Dict:
        """Obtener estado actual"""
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
            "/operaciones - Ver operaciones hoy\n"
            "/capital - Ver capital\n"
            "/help - Ayuda\n",
            parse_mode='Markdown'
        )
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status"""
        estado = self.trading_bot.get_estado()
        activo = "✅ ACTIVO" if estado['activo'] else "❌ DETENIDO"
        
        mensaje = (
            f"📊 *Estado del Bot*\n\n"
            f"• Bot: {activo}\n"
            f"• Operaciones hoy: {estado['operaciones_hoy']}\n"
            f"• Ganancias: ${estado['ganancias_hoy']:.2f}\n"
            f"• Pérdidas: ${estado['perdidas_hoy']:.2f}\n"
            f"• Neto: ${estado['ganancias_hoy'] - estado['perdidas_hoy']:.2f}\n"
            f"• Capital: ${estado['capital']:.2f}\n"
            f"• Modo: {estado['modo']}"
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
        
        # Verificar conexión MT5
        try:
            mt5.initialize()
            account = mt5.account_info()
            conexion = "✅ CONECTADO"
            balance = f"${account.balance:.2f}"
        except:
            conexion = "❌ DESCONECTADO"
            balance = "N/A"
        
        mensaje = (
            f"📈 *Estado Detallado*\n\n"
            f"• Trading: {'✅ ACTIVO' if estado['activo'] else '❌ DETENIDO'}\n"
            f"• MT5: {conexion}\n"
            f"• Balance MT5: {balance}\n"
            f"• Operaciones hoy: {estado['operaciones_hoy']}\n"
            f"• G/P Neto: ${estado['ganancias_hoy'] - estado['perdidas_hoy']:.2f}\n"
            f"• Horario: {self.trading_bot.config.HORA_INICIO} - {self.trading_bot.config.HORA_FIN} UTC\n"
            f"• Símbolo: {self.trading_bot.config.SYMBOL}\n"
            f"• Riesgo/op: ${self.trading_bot.config.RIESGO_POR_OPERACION:.2f}"
        )
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    async def operaciones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /operaciones"""
        estado = self.trading_bot.get_estado()
        
        if estado['operaciones_hoy'] == 0:
            await update.message.reply_text("📭 No hay operaciones hoy")
        else:
            mensaje = f"📋 *Operaciones Hoy: {estado['operaciones_hoy']}*\n\n"
            for i, op in enumerate(estado.get('operaciones', [])[-5:], 1):
                mensaje += f"{i}. {op['tipo']} - ${op['resultado']:.2f}\n"
            
            await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    async def capital(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /capital"""
        estado = self.trading_bot.get_estado()
        
        mensaje = (
            f"💰 *Gestión de Capital*\n\n"
            f"• Capital actual: ${estado['capital']:.2f}\n"
            f"• Riesgo por operación: ${self.trading_bot.config.RIESGO_POR_OPERACION:.2f}\n"
            f"• (% del capital: {(self.trading_bot.config.RIESGO_POR_OPERACION/estado['capital']*100):.1f}%)\n"
            f"• Stop Loss: {self.trading_bot.config.STOP_LOSS_PIPS} pips\n"
            f"• Take Profit: {self.trading_bot.config.TAKE_PROFIT_PIPS} pips\n"
            f"• Ratio R:R: 1:2\n"
            f"• Objetivo diario: ${self.trading_bot.config.OBJETIVO_DIARIO:.2f}"
        )
        
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
            "*/capital* - Gestión de capital\n"
            "*/help* - Esta ayuda\n\n"
            "📊 *Notas:*\n"
            "• El bot opera de 08:00 a 12:00 UTC\n"
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
        self.app.add_handler(CommandHandler("capital", self.capital))
        self.app.add_handler(CommandHandler("help", self.ayuda))
    
    async def run(self):
        """Ejecutar bot de Telegram"""
        self.app = Application.builder().token(self.token).build()
        self.setup_handlers()
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        print("🤖 Bot de Telegram iniciado")
        
        # Mantener corriendo
        await asyncio.Event().wait()

# ================= SERVER WEB (para Render) =================
from flask import Flask, jsonify, request
import threading

class WebServer:
    def __init__(self, trading_bot: TradingBot, port=5000):
        self.trading_bot = trading_bot
        self.port = port
        self.app = Flask(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """Configurar rutas web"""
        @self.app.route('/')
        def index():
            return jsonify({
                "status": "online",
                "service": "Trading Bot Server",
                "version": "4.0"
            })
        
        @self.app.route('/status')
        def status():
            estado = self.trading_bot.get_estado()
            return jsonify(estado)
        
        @self.app.route('/start', methods=['POST'])
        def start():
            if self.trading_bot.iniciar():
                return jsonify({"success": True, "message": "Bot iniciado"})
            return jsonify({"success": False, "message": "Error al iniciar"})
        
        @self.app.route('/stop', methods=['POST'])
        def stop():
            self.trading_bot.detener()
            return jsonify({"success": True, "message": "Bot detenido"})
        
        @self.app.route('/health')
        def health():
            return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})
    
    def run(self):
        """Ejecutar servidor web"""
        self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)

# ================= SISTEMA PRINCIPAL =================
class SistemaTradingCompleto:
    def __init__(self):
        self.config = Config()
        self.trading_bot = None
        self.telegram_bot = None
        self.web_server = None
        
    def cargar_configuracion(self):
        """Cargar configuración desde variables de entorno (para Render)"""
        # Para Render, usa variables de entorno
        self.config.MT5_ACCOUNT = int(os.getenv('MT5_ACCOUNT', self.config.MT5_ACCOUNT))
        self.config.MT5_PASSWORD = os.getenv('MT5_PASSWORD', self.config.MT5_PASSWORD)
        self.config.MT5_SERVER = os.getenv('MT5_SERVER', self.config.MT5_SERVER)
        self.config.TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', self.config.TELEGRAM_TOKEN)
        self.config.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', self.config.TELEGRAM_CHAT_ID)
        
        print("📋 Configuración cargada")
        print(f"   MT5 Account: {self.config.MT5_ACCOUNT}")
        print(f"   Telegram Token: {'✅ Configurado' if self.config.TELEGRAM_TOKEN != 'TU_TELEGRAM_BOT_TOKEN' else '❌ NO configurado'}")
    
    async def iniciar_sistema(self):
        """Iniciar todo el sistema"""
        print("🚀 Iniciando Sistema de Trading Completo...")
        
        # 1. Cargar configuración
        self.cargar_configuracion()
        
        # 2. Crear trading bot
        self.trading_bot = TradingBot(self.config)
        
        # 3. Crear bot de Telegram si hay token
        if self.config.TELEGRAM_TOKEN and self.config.TELEGRAM_TOKEN != "TU_TELEGRAM_BOT_TOKEN":
            self.telegram_bot = TelegramBot(self.config.TELEGRAM_TOKEN, self.trading_bot)
            
            # Iniciar Telegram en segundo plano
            telegram_thread = threading.Thread(
                target=asyncio.run,
                args=(self.telegram_bot.run(),),
                daemon=True
            )
            telegram_thread.start()
            print("🤖 Bot de Telegram iniciado")
        
        # 4. Iniciar servidor web (para Render)
        self.web_server = WebServer(self.trading_bot, port=int(os.getenv('PORT', 5000)))
        web_thread = threading.Thread(
            target=self.web_server.run,
            daemon=True
        )
        web_thread.start()
        print("🌐 Servidor web iniciado")
        
        # 5. Iniciar trading bot automáticamente si está en horario
        if self.trading_bot.dentro_horario():
            self.trading_bot.iniciar()
            print("⏰ Iniciando trading (dentro de horario)")
        
        # 6. Mantener el sistema corriendo
        print("✅ Sistema completamente operativo")
        print("📊 Accede a:")
        print("   • Telegram: Busca tu bot")
        print("   • Web: http://localhost:5000")
        print("   • Logs: trading_bot.log")
        
        # Mantener proceso activo
        while True:
            await asyncio.sleep(3600)  # Esperar 1 hora
    
    def ejecutar(self):
        """Punto de entrada principal"""
        asyncio.run(self.iniciar_sistema())

# ================= ARCHIVOS ADICIONALES NECESARIOS =================

# requirements.txt (guárdalo como archivo separado)
REQUIREMENTS = """MetaTrader5>=5.0.43
pandas>=1.5.0
numpy>=1.23.0
python-telegram-bot>=20.0
Flask>=2.3.0
APScheduler>=3.10.0
gunicorn>=20.1.0
"""

# runtime.txt (para Render)
RUNTIME = "python-3.9.0"

# Procfile (para Render)
PROCFILE = "web: gunicorn main:app"

# ================= INSTRUCCIONES PASO A PASO =================
def mostrar_instrucciones():
    print("\n" + "="*80)
    print("🚀 GUÍA PARA DESPLEGAR EN SERVER GRATUITO")
    print("="*80)
    
    print("\n📋 1. OBTENER BOT DE TELEGRAM:")
    print("   a. Busca @BotFather en Telegram")
    print("   b. Envía /newbot")
    print("   c. Nómbralo (ej: MiTradingBot)")
    print("   d. Copia el token (ej: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)")
    print("   e. Para obtener tu CHAT_ID:")
    print("      - Busca @userinfobot en Telegram")
    print("      - Envía /start")
    print("      - Copia tu ID (ej: 123456789)")
    
    print("\n🌐 2. CREAR CUENTA EN RENDER (GRATIS):")
    print("   a. Ve a https://render.com")
    print("   b. Regístrate con GitHub")
    print("   c. Click en 'New' → 'Web Service'")
    
    print("\n📦 3. PREPARAR ARCHIVOS EN GITHUB:")
    print("   Crea un repositorio con estos archivos:")
    print("   ├── main.py          (este código)")
    print("   ├── requirements.txt (dependencias)")
    print("   ├── runtime.txt      (python-3.9.0)")
    print("   └── Procfile         (web: gunicorn main:app)")
    
    print("\n⚙️  4. CONFIGURAR EN RENDER:")
    print("   En 'Environment Variables', añade:")
    print("   • MT5_ACCOUNT = tu_numero_cuenta_demo")
    print("   • MT5_PASSWORD = tu_password_demo")
    print("   • MT5_SERVER = MetaQuotes-Demo")
    print("   • TELEGRAM_TOKEN = token_de_tu_bot")
    print("   • TELEGRAM_CHAT_ID = tu_chat_id")
    
    print("\n🚀 5. DESPLEGAR:")
    print("   a. Conecta tu repositorio de GitHub")
    print("   b. Render detectará automáticamente los archivos")
    print("   c. Click en 'Create Web Service'")
    print("   d. Espera 5-10 minutos para el despliegue")
    
    print("\n📱 6. USAR EL SISTEMA:")
    print("   a. Busca tu bot en Telegram")
    print("   b. Envía /start para ver comandos")
    print("   c. Usa /startbot para iniciar trading")
    print("   d. El bot funcionará 24/7 en el server")
    
    print("\n📊 7. MONITOREAR:")
    print("   • Logs: En Render dashboard → 'Logs'")
    print("   • Estado: En Telegram con /status")
    print("   • Web: https://tudominio.onrender.com")
    
    print("\n" + "="*80)
    print("💰 COSTO: GRATIS (hasta 750 horas/mes en Render)")
    print("⏰ El bot se dormirá después de 15 min inactivo (gratis)")
    print("🔧 Para evitar sleep: Pings cada 10 min o upgrade a plan pago")
    print("="*80)

# ================= EJECUCIÓN LOCAL =================
if __name__ == "__main__":
    # Mostrar instrucciones
    mostrar_instrucciones()
    
    respuesta = input("\n¿Continuar con ejecución local? (s/n): ").lower().strip()
    
    if respuesta == 's':
        print("\nIniciando sistema localmente...")
        sistema = SistemaTradingCompleto()
        
        try:
            sistema.ejecutar()
        except KeyboardInterrupt:
            print("\n🛑 Sistema detenido por usuario")
    else:
        print("\nPara desplegar en Render:")
        print("1. Guarda este código como main.py")
        print("2. Crea los archivos requirements.txt, runtime.txt y Procfile")
        print("3. Sigue las instrucciones arriba")