import sys
import json
import math
import time
from decimal import Decimal, getcontext
from datetime import datetime
from PyQt5.QtNetwork import QNetworkCookie
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, 
                             QCheckBox, QSplitter, QFrame, QTableWidgetItem, 
                             QAbstractItemView, QTableWidget, QHeaderView, QProgressBar)
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis
from PyQt5.QtCore import QTimer, QUrl, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
from PyQt5.QtGui import QPainter, QPen, QColor

# Set precision
getcontext().prec = 20

# --- CONFIGURATION ---
URL = "https://just-dice.com"
STATE_FILE = "bot_state.json"

class BotEngine(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JustDice Native Bot (Infinite Flow)")
        self.resize(1024, 768)

        # --- INTERNAL STATE ---
        self.is_running = False
        self.last_balance = Decimal("0")
        self.initial_balance = Decimal("0")
        self.tracked_balance = Decimal("0")
        self.next_compound = Decimal("0")
        self.last_change_time = 0  # Watchdog timer
        
        # Strategy Vars
        self.cat = Decimal("0")
        self.felix = Decimal("0")
        self.orgy = Decimal("0")
        self.fart = 1
        self.tabby = Decimal("0")
        self.tens = Decimal("0")
        self.sevens = Decimal("0")
        self.eights = Decimal("0")

        # Wipe everything
        # --- UI SETUP ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # LEFT PANEL: Controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        # right PANEL: Controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Password")
        self.pass_input.setEchoMode(QLineEdit.Password)
        
        self.btn_login = QPushButton("1. Inject Login")
        self.btn_login.clicked.connect(self.inject_login)
        self.btn_start = QPushButton("2. Start Engine")
        self.btn_start.clicked.connect(self.toggle_engine)
        self.btn_start.setEnabled(False)
        
        self.lbl_balance = QLabel("Balance: 0.00000000")
        self.lbl_profit = QLabel("Life Profit: 0.00000000")
        self.lbl_bet = QLabel("Next Bet: 0.00000000")
        self.lbl_compound = QLabel("Compound Goal: 0.00000000")
        
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background: #111; color: #0f0; font-family: monospace; font-size: 11px;")

        left_layout.addWidget(QLabel("<b>Just-dice.com snowybot</b>"))
        left_layout.addWidget(QLabel("<b>Credentials</b>"))
        left_layout.addWidget(self.user_input)
        left_layout.addWidget(self.pass_input)
        left_layout.addWidget(self.btn_login)
        left_layout.addWidget(QFrame(frameShape=QFrame.HLine))
        left_layout.addWidget(self.lbl_balance)
        left_layout.addWidget(self.lbl_profit)
        left_layout.addWidget(self.lbl_bet)
        left_layout.addWidget(self.lbl_compound)
        left_layout.addWidget(QFrame(frameShape=QFrame.HLine))
        left_layout.addWidget(self.btn_start)
        left_layout.addWidget(self.log_box)
        
        # --- PROFIT CHART SETUP ---
        self.series = QLineSeries()
        
        # Style the line
        pen = QPen(QColor("#0f0"))
        pen.setWidth(2)
        self.series.setPen(pen)

        self.chart = QChart()
        self.chart.addSeries(self.series)
        self.chart.legend().hide()
        self.chart.setBackgroundVisible(False)
        self.chart.layout().setContentsMargins(0, 0, 0, 0)

        # Axis Setup
        self.axis_x = QValueAxis()
        self.axis_x.setLabelFormat("%d")
        self.axis_x.setTitleText("Bets")
        
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("Profit")

        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        self.series.attachAxis(self.axis_x)
        self.series.attachAxis(self.axis_y)

        # The actual Widget that displays the chart
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMinimumHeight(250)
        self.chart_view.setStyleSheet("background: transparent;")

        # Track data points
        self.bet_count = 0
        self.current_total_profit = 0

        # Add to layout
        right_layout.addWidget(QLabel("<b>Profit Performance</b>"))
        right_layout.addWidget(self.chart_view)

        # --- RESET BUTTON ---
        self.btn_reset_chart = QPushButton("Clear Chart Data")
        self.btn_reset_chart.clicked.connect(self.reset_chart)
        self.btn_reset_chart.setStyleSheet("""
            QPushButton { 
                background-color: #444; 
                color: white; 
                border-radius: 4px; 
                padding: 5px; 
            }
            QPushButton:hover { background-color: #555; }
        """)
        
        # Add to layout under the chart
        left_layout.addWidget(self.btn_reset_chart)

        # Darn: Browser
        self.browser_view = QWebEngineView()
        self.profile = QWebEngineProfile.defaultProfile()
        self.cookie_store = self.profile.cookieStore()

        # Wipe everything
        self.cookie_store.deleteAllCookies()
 
        self.last_activity_time = time.time()
        
        splitter = QSplitter()
        splitter.addWidget(left_panel) 
        splitter.addWidget(right_panel)      
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        # --- TIMERS ---
        self.heartbeat = QTimer()
        self.heartbeat.setInterval(150) # 150ms Tick
        self.heartbeat.timeout.connect(self.tick)
        self.reset_chart()

        self.log("System initialized. Loading Just-Dice...")
        self.browser_view.setUrl(QUrl(URL))
        self.browser_view.loadFinished.connect(self.on_load_finished)
    
    def reset_chart(self):
        # 1. Clear the actual data points
        self.series.clear()
        
        # 2. Reset the counters
        self.bet_count = 0
        self.current_total_profit = 0
        
        # 3. Reset the axes so they don't stay zoomed out
        self.axis_x.setRange(0, 100000)
        self.axis_y.setRange(-500000, 500000)
        
        self.log("📊 Chart data has been cleared.")

    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_box.append(f"[{ts}] {msg}")
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_load_finished(self):
        self.log("✅ Page Loaded removing popup if there.")
        try:
           self.browser_view.page().runJavaScript("document.querySelectorAll('.fancybox-overlay').forEach(e => e.remove());")
        except: pass

    def inject_login(self):
        u = self.user_input.text()
        p = self.pass_input.text()
        if not u or not p: return

        js = f"""
        (function() {{
            var u = document.getElementById('myuser');
            var p = document.getElementById('mypass');
            var btn = document.getElementById('myok');
            var links = document.getElementsByTagName('a');
            for(var i=0; i<links.length; i++) {{
                if(links[i].innerText.includes('Account')) {{
                    links[i].click();
                    break;
                }}
            }}
            setTimeout(() => {{
                if(u && p) {{
                    u.value = '{u}';
                    p.value = '{p}';
                    if(btn) btn.click();
                }}
            }}, 1500);
        }})();
        """
        self.browser_view.page().runJavaScript(js)
        self.log("⏳ Credentials injecting please wait...")
        QTimer.singleShot(15000, self.check_ready)

    def check_ready(self):
        self.browser_view.page().runJavaScript(
            "document.getElementById('pct_balance') ? document.getElementById('pct_balance').value : null;",
            self.verify_login
        )

    def verify_login(self, val):
        if val:
            self.log(f"✅ Logged in! Balance: {val}")
            self.btn_start.setEnabled(True)
            self.btn_start.setStyleSheet("background-color: #008000; color: white; font-weight: bold;")
            self.setup_state(Decimal(val))
            self.last_activity_time = time.time()
        else:
            self.log("❌ Login failed or slow load. Click Inject again.")

    # ---------------------------------------------------------------------------
    # STATE & MATH
    # ---------------------------------------------------------------------------
    def setup_state(self, real_bal):
        self.calculate_units(real_bal)
        self.state_data = self.load_state_file()
        
        if self.state_data:
            self.log("📂 Resuming from file...")
            self.cat = self.state_data.get("cat", self.tabby)
            self.felix = self.state_data.get("felix", Decimal(0))
            self.orgy = self.state_data.get("orgy", Decimal(0))
            self.fart = int(self.state_data.get("fart", 1))
            self.initial_balance = self.state_data.get("initial_balance", real_bal)
            self.next_compound = self.state_data.get("next_compound", real_bal * Decimal("2.4"))
            
            last_saved = self.state_data.get("last_balance", real_bal)
            drift = real_bal - last_saved
            self.tracked_balance = self.state_data.get("tracked_balance", real_bal) + drift
            self.log(f"⚖️ Drift Corrected: {drift:.8f}")
        else:
            self.log("🆕 Fresh Start.")
            self.cat = self.tabby
            self.fart = 1
            self.tracked_balance = self.initial_balance = real_bal
            self.next_compound = real_bal * Decimal("2.4")
            mighty = ((math.floor(real_bal / self.tens)) * self.tens)
            self.felix = self.orgy = mighty

        self.last_balance = real_bal
        self.update_ui_stats()
   
    def update_chart(self, delta):
        self.bet_count += 1
        self.current_total_profit += float(delta) # Use float for chart compatibility
        
        # Add new point (X = Bet Number, Y = Total Profit)
        self.series.append(self.bet_count, self.current_total_profit)

        # Auto-scale the axes so the line is always visible
        self.axis_x.setRange(max(0, self.bet_count - 5000000), self.bet_count + 5)
        
        # Dynamic Y-axis scaling
        points = self.series.pointsVector()
        if points:
            y_values = [p.y() for p in points[-5000000:]] # Look at last 50 bets
            margin = abs(max(y_values) - min(y_values)) * 0.1
            self.axis_y.setRange(min(y_values) - margin, max(y_values) + margin)

        # Keep memory clean: remove points older than 100 bets
        #if self.series.count() > 1000000:
        # self.series.remove(0)

    def load_state_file(self):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                keys = ["cat", "felix", "orgy", "tracked_balance", "initial_balance", "last_balance", "next_compound"]
                for k in keys:
                    if k in data: data[k] = Decimal(data[k])
                return data
        except: return None

    def save_state(self):
        try:
            data = {
                "cat": self.cat, "felix": self.felix, "orgy": self.orgy, "fart": self.fart,
                "tracked_balance": self.tracked_balance, "initial_balance": self.initial_balance,
                "last_balance": self.last_balance, "next_compound": self.next_compound
            }
            serializable = {k: str(v) if isinstance(v, Decimal) else v for k, v in data.items()}
            with open(STATE_FILE, "w") as f:
                json.dump(serializable, f)
        except: pass

    def calculate_units(self, balance):
        if balance == 0: return
        self.tabby = (balance / Decimal("144000")).quantize(Decimal("1.00000000"))
        self.tens = (self.tabby * Decimal("10.0"))
        self.sevens = (self.tabby * Decimal("6.9"))
        self.eights = (self.tabby * Decimal("7.9"))

    # ---------------------------------------------------------------------------
    # ENGINE CONTROL
    # ---------------------------------------------------------------------------
    def toggle_engine(self):
        if self.is_running:
            self.is_running = False
            self.heartbeat.stop()
            self.btn_start.setText("2. Start Engine")
            self.btn_start.setStyleSheet("background-color: #008000; color: white; font-weight: bold;")
            self.log("🛑 Engine STOPPED.")
            self.save_state()
        else:
            self.log("🔄 Syncing balance before start...")
            self.btn_start.setEnabled(False) 
            self.browser_view.page().runJavaScript(
                "document.getElementById('pct_balance').value", 
                self.engage_engine
            )

    def engage_engine(self, bal_str):
        self.btn_start.setEnabled(True)
        if not bal_str: return

        try:
            fresh_balance = Decimal(bal_str)
        except: return

        # FORCE SYNC
        if fresh_balance != self.last_balance:
            self.log(f"⚖️ Sync: {self.last_balance} -> {fresh_balance}")
            self.last_balance = fresh_balance
            if self.state_data:
                drift = fresh_balance - self.state_data.get("last_balance", fresh_balance)
                self.tracked_balance = self.state_data.get("tracked_balance", fresh_balance) + drift

        if self.cat == 0:
            self.calculate_units(fresh_balance)
            self.cat = self.tabby

        self.is_running = True
        self.btn_start.setText("STOP ENGINE")
        self.btn_start.setStyleSheet("background-color: #b30000; color: white; font-weight: bold;")
        self.log(f"🚀 STARTED. Base: {self.cat:.8f}")
        
        # Start Timer
        self.last_change_time = time.time()
        self.last_activity_time = time.time()
        self.fire_bet()
        self.heartbeat.start()

    # ---------------------------------------------------------------------------
    # CORE LOOP WITH KICKSTART
    # ---------------------------------------------------------------------------
    def tick(self):
        self.browser_view.page().runJavaScript(
            "document.getElementById('pct_balance').value", 
            self.process_tick
        )

    def kool_poop(self):
        self.log("please wait for reconnect stopping engine dont worry will reconnect...")
        self.toggle_engine()
        QTimer.singleShot(2000, self.lol_poop)
    
    def lol_poop(self):
        self.log("please wait for reconnect reloading browser dont worry will reconnect...")
        self.cookie_store.deleteAllCookies()
        self.browser_view.reload()
        QTimer.singleShot(5000, self.devils_pooped)
    
    def devils_pooped(self):
        self.log("please wait for reconnect injecting login as why your login stays there dont worry will reconnect...")
        self.inject_login()
        QTimer.singleShot(20000, self.angel_popped)

    def angel_popped(self):
        self.log("please wait for reconnect ...reconnecting...")
        self.toggle_engine()

    def process_tick(self, bal_str):
        if not bal_str or not self.is_running: return
        try:
            current_real = Decimal(bal_str)
        except: return

        if time.time() - self.last_activity_time > 10:
            self.last_activity_time = time.time()
            self.kool_poop()
            
        # CASE 1: BALANCE CHANGED (Bet Processed)
        if current_real != self.last_balance:
            self.last_change_time = time.time() # Reset Stuck Timer
            self.last_activity_time = time.time()
            
            delta = current_real - self.last_balance

            # CALL THE CHART HERE
            self.update_chart(delta)

            # Hacker Guard
            if abs(delta) > (self.cat * Decimal("1.01")):
                self.log(f"🚨 SECURITY: Delta {delta} > Bet {self.cat}")
                self.toggle_engine()
                return

            self.tracked_balance += delta
            self.last_balance = current_real
            
            # Compounding
            if self.tracked_balance >= self.next_compound:
                self.log("💎 COMPOUND MILESTONE!")
                self.calculate_units(self.tracked_balance)
                self.next_compound = self.tracked_balance * Decimal("2.4")
                self.cat = self.tabby

            # Strategy
            mighty = ((math.floor(self.tracked_balance / self.tens)) * self.tens)
            
            if self.tracked_balance >= (self.orgy + (self.tens * self.fart)):
                self.cat = self.tabby
                self.fart = 1
                self.felix = mighty
                self.orgy = mighty

            if self.tracked_balance > (mighty + self.sevens) and self.tracked_balance < (mighty + self.eights) and self.tracked_balance < self.felix:
                 self.fart = 0
                 self.cat *= 2
                 self.felix = self.tracked_balance

            if self.tracked_balance > (mighty + self.sevens) and self.tracked_balance < (mighty + self.eights) and self.tracked_balance > self.felix:
                 self.cat *= 2
                 self.felix = self.tracked_balance
            
            # LOG & UI
            sess = self.tracked_balance - self.initial_balance
            self.log(f"💰 {current_real:.8f} | D: {delta:+.8f} | Sess: {sess:+.8f}")
            self.update_ui_stats()
            self.save_state()
            
            # NEXT BET
            self.fire_bet()

        # CASE 2: STUCK CHECK
        else:
            # If 4 seconds pass with no balance change, Kickstart
            if time.time() - self.last_change_time > 0.01:
                self.fire_bet()
                self.last_change_time = time.time() 

                
    def fire_bet(self):
        js = f"""
        var chance = document.getElementById('pct_chance');
        var bet = document.getElementById('pct_bet');
        var btn = document.getElementById('a_lo');
        if(chance) chance.value = '49.5';
        if(bet) bet.value = '{self.cat:.8f}';
        if(btn) btn.click();
        """
        self.browser_view.page().runJavaScript(js)

    def update_ui_stats(self):
        self.lbl_balance.setText(f"Bal: {self.last_balance:.8f}")
        self.lbl_profit.setText(f"Life Profit: {(self.tracked_balance - self.initial_balance):.8f}")
        self.lbl_bet.setText(f"Next Bet: {self.cat:.8f}")
        self.lbl_compound.setText(f"Goal: {self.next_compound:.8f}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    bot = BotEngine()
    bot.show()
    sys.exit(app.exec_())
