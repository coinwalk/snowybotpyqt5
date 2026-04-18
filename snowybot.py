import sys
import json
import math
import time
from decimal import Decimal, getcontext
from datetime import datetime

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, 
                             QCheckBox, QSplitter, QFrame)
from PyQt5.QtCore import QTimer, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile

# Set precision
getcontext().prec = 20

# --- CONFIGURATION ---
URL = "https://just-dice.com"
STATE_FILE = "bot_state.json"

class BotEngine(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JustDice Native Bot (Infinite Flow)")
        self.resize(1100, 700)

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

        # --- UI SETUP ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # LEFT PANEL: Controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
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

        # RIGHT PANEL: Browser
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.browser_view = QWebEngineView()
        profile = QWebEngineProfile("secure_profile", self.browser_view)
        page = QWebEnginePage(profile, self.browser_view)
        self.browser_view.setPage(page)
        
        self.chk_visible = QCheckBox("Show Browser (Uncheck for Headless Mode)")
        self.chk_visible.setChecked(True)
        self.chk_visible.toggled.connect(lambda x: self.browser_view.setVisible(x))

        right_layout.addWidget(self.chk_visible)
        right_layout.addWidget(self.browser_view)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)

        # --- TIMERS ---
        self.heartbeat = QTimer()
        self.heartbeat.setInterval(150) # 150ms Tick
        self.heartbeat.timeout.connect(self.tick)

        self.log("System initialized. Loading Just-Dice...")
        self.browser_view.setUrl(QUrl(URL))
        self.browser_view.loadFinished.connect(self.on_load_finished)

    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_box.append(f"[{ts}] {msg}")
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_load_finished(self):
        self.log("✅ Page Loaded. Please Login.")
        self.browser_view.page().runJavaScript("document.querySelectorAll('.fancybox-overlay').forEach(e => e.remove());")

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
        self.log("⏳ Credentials injected...")
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
            mighty = (math.floor(real_bal / self.tens)) * self.tens
            self.felix = self.orgy = mighty

        self.last_balance = real_bal
        self.update_ui_stats()

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
        self.tens = self.tabby * 10
        self.sevens = self.tabby * Decimal("6.9")
        self.eights = self.tabby * Decimal("7.9")

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

    def process_tick(self, bal_str):
        if not bal_str or not self.is_running: return
        try:
            current_real = Decimal(bal_str)
        except: return

        # CASE 1: BALANCE CHANGED (Bet Processed)
        if current_real != self.last_balance:
            self.last_change_time = time.time() # Reset Stuck Timer
            
            delta = current_real - self.last_balance
            
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
            mighty = (math.floor(self.tracked_balance / self.tens)) * self.tens
            
            if self.tracked_balance >= (self.orgy + (self.tens * self.fart)):
                self.cat = self.tabby
                self.fart = 1
                self.felix = self.orgy = mighty

            in_zone = (mighty + self.sevens) < self.tracked_balance < (mighty + self.eights)
            if in_zone:
                try:
                    if self.tracked_balance < self.felix:
                        self.fart = 0
                        self.cat *= 2
                        self.felix = self.tracked_balance
                    elif self.tracked_balance > self.felix:
                        self.cat *= 2
                        self.felix = self.tracked_balance
                except: pass
            
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
