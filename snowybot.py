import sys
import math
import os
import json
import time
import getpass

from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
from PyQt5.QtCore import QUrl, QTimer

# -------------------------------
# LOGIN
USERNAME = input("Enter username: ")
PASSWORD = getpass.getpass("Enter password: ")

URL = "https://just-dice.com"
STATE_FILE = "bot_state.json"

# -------------------------------
# QUIET + HEADLESS FLAGS
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu"
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false"

# -------------------------------
def save_state(data):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return None

# -------------------------------
class RunBot:
    def __init__(self):
        self.app = QApplication(sys.argv)

        self.view = QWebEngineView()

        # 🔥 PyQt5 correct profile setup
        self.profile = QWebEngineProfile()
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)

        self.page = QWebEnginePage(self.profile, self.view)
        self.view.setPage(self.page)

        layout = QVBoxLayout()
        layout.addWidget(self.view)

        container = QWidget()
        container.setLayout(layout)
        container.hide()

        self.view.load(QUrl(URL))
        self.view.hide()

        print("✅ Page loading...")
        print("⏳ Waiting 35 seconds (initial load)...")
        QTimer.singleShot(35000, self.after_load)

        self.app.exec()

    # -------------------------------
    def after_load(self):
        print("⏳ Initial load complete → starting bot")
        self.handle_popup()

    # -------------------------------
    def handle_popup(self):
        print("🔧 Checking for popup...")

        script = """
        (function() {
            var p = document.querySelector(".fancybox-close");
            if (p) { p.click(); return true; }
            return false;
        })();
        """

        self.view.page().runJavaScript(script, self.after_popup)

    def after_popup(self, found):
        print("✅ Popup found and closed" if found else "ℹ️ No popup found")
        self.open_login()

    # -------------------------------
    def open_login(self):
        print("🔓 Opening login panel...")

        script = """
        (function() {
            let links = document.querySelectorAll("a");
            for (let i=0;i<links.length;i++){
                if(links[i].innerText.trim()==="Account"){
                    links[i].click(); return true;
                }
            }
            return false;
        })();
        """

        self.view.page().runJavaScript(script)
        QTimer.singleShot(1500, self.wait_login_panel)

    def wait_login_panel(self):
        script = "(function(){return !!document.querySelector('#myuser');})();"
        self.view.page().runJavaScript(script, self.login_panel_ready)

    def login_panel_ready(self, ready):
        if ready:
            print("⏳ Waiting 10s before login...")
            QTimer.singleShot(10000, self.do_login)
        else:
            QTimer.singleShot(1500, self.wait_login_panel)

    # -------------------------------
    def do_login(self):
        print("🔐 Logging in...")

        u = json.dumps(USERNAME)
        p = json.dumps(PASSWORD)

        self.view.page().runJavaScript(f'''
        (function(){{
            let el = document.querySelector("#myuser");
            if(el) el.value={u};
        }})();
        ''')

        QTimer.singleShot(1000, lambda: self.view.page().runJavaScript(f'''
        (function(){{
            let el = document.querySelector("#mypass");
            if(el) el.value={p};
        }})();
        '''))

        QTimer.singleShot(2000, lambda: self.run_js_click("#myok"))

        print("⏳ Waiting 35s after login for balance...")
        QTimer.singleShot(35000, self.wait_balance)

    # -------------------------------
    def wait_balance(self):
        self.get_value("#pct_balance", self.balance_ready)

    def balance_ready(self, val):
        if val is not None:
            print(f"✅ Balance: {val}")
            self.state = load_state()
            self.init_betting(float(val))
        else:
            QTimer.singleShot(2000, self.wait_balance)

    # -------------------------------
    def init_betting(self, whiskers):
        if self.state and "last_balance" in self.state:
            print(f"🔄 Last diff: {whiskers - self.state['last_balance']:.8f}")

        self.whiskers = whiskers
        self.tabby = round(whiskers / 144000, 8)

        if self.tabby == 0:
            QTimer.singleShot(2000, self.wait_balance)
            return

        self.purr = 49.5
        self.tens = self.tabby * 10
        self.sevens = self.tabby * 6.9
        self.eights = self.tabby * 7.9
        self.mighty = math.floor(whiskers / self.tens) * self.tens

        self.last_balance = whiskers
        self.last_change = time.time()

        if self.state:
            self.cat = self.state["cat"]
            self.felix = self.state["felix"]
            self.orgy = self.state["orgy"]
            self.shadow = self.state["shadow"]
            self.smokey = self.state["smokey"]
            self.fart = self.state["fart"]
        else:
            self.cat = self.tabby
            self.fart = 1
            self.shadow = whiskers
            self.smokey = whiskers
            self.felix = self.mighty
            self.orgy = self.mighty

        print(f"🐾 Balance: {whiskers:.8f}| Bet: {self.cat:.8f}")

        self.run_js_click("#b_min")

        self.timer = QTimer()
        self.timer.timeout.connect(self.bet_step)
        self.timer.start(200)

    # -------------------------------
    def bet_step(self):
        self.get_value("#pct_balance", self.process_bet)

    def process_bet(self, bal):
        if bal is None:
            return

        if bal != self.last_balance:
            self.last_balance = bal
            self.last_change = time.time()

        if time.time() - self.last_change > 120:
            print("⚠️ Stuck → reload")

            save_state({
                "cat": self.cat,
                "felix": self.felix,
                "orgy": self.orgy,
                "shadow": self.shadow,
                "smokey": self.smokey,
                "fart": self.fart,
                "last_balance": self.last_balance
            })

            self.reload_page()
            return


        current = bal
        self.mighty = ((math.floor(current / self.tens)) * self.tens)

        if current >= (self.orgy + (self.tens * self.fart)):
                self.cat = self.tabby
                self.fart = 1
                self.felix = self.mighty
                self.orgy = self.mighty

        if (current > (self.mighty + self.sevens)) and (current < (self.mighty + self.eights)) and current > self.felix:
                self.cat *= 2
                self.felix = current

        if (current > (self.mighty + self.sevens)) and (current < (self.mighty + self.eights)) and current < self.felix:
                self.cat *= 2
                self.fart = 0
                self.felix = current

        print(f"📈 Bal: {bal:.8f}| Profit: {(bal - self.whiskers):.8f} | Bet: {self.cat:.8f}")

        self.set_value("#pct_chance", self.purr)
        self.set_value("#pct_bet", f"{self.cat:.8f}")


        save_state({
                "cat": self.cat,
                "felix": self.felix,
                "orgy": self.orgy,
                "shadow": self.shadow,
                "smokey": self.smokey,
                "fart": self.fart,
                "last_balance": self.last_balance
        })

        self.run_js_click("#a_lo")

    # -------------------------------
    def reload_page(self):
        print("🧹 FULL reset (new profile)...")

        try:
            self.timer.stop()
        except:
            pass

        # 🔥 recreate clean profile (PyQt5 way)
        self.profile = QWebEngineProfile()
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)

        self.page = QWebEnginePage(self.profile, self.view)
        self.view.setPage(self.page)

        print("🔄 Reloading (35s)...")
        self.view.load(QUrl(URL))

        QTimer.singleShot(35000, self.after_load)

    # -------------------------------
    def get_value(self, selector, cb):
        script = f"""
        (function(){{
            let el = document.querySelector("{selector}");
            if(!el) return null;
            let v = Number(el.value);
            return isNaN(v) ? null : v;
        }})();
        """
        self.view.page().runJavaScript(script, cb)

    def set_value(self, selector, val):
        self.view.page().runJavaScript(
            f'document.querySelector("{selector}").value="{val}";'
        )

    def run_js_click(self, selector):
        self.view.page().runJavaScript(
            f'document.querySelector("{selector}")?.click();'
        )

# -------------------------------
if __name__ == "__main__":
    RunBot()
