import json
import math
import os
import random
import sys
import threading
import time
import uuid
import requests
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Metadata Upgrade Pasif dari game.js
UPGRADES_META = {
    "seeds":   {"name": "Seeds",         "base": 200,     "ph": 12},
    "wheel":   {"name": "Wheel",         "base": 1000,    "ph": 50},
    "house":   {"name": "House",         "base": 5000,    "ph": 220},
    "friends": {"name": "Friends",       "base": 20000,   "ph": 800},
    "farm":    {"name": "Farm",          "base": 80000,   "ph": 2800},
    "factory": {"name": "Factory",       "base": 350000,  "ph": 11000},
    "rocket":  {"name": "Rocket",        "base": 1500000, "ph": 42000},
}

# Metadata Upgrade Status dari game.js
LEVELS_META = {
    "regenLvl": {"name": "Regen Speed",  "base": 800, "mult": 1.8},
    "tapLvl":   {"name": "Tap Power",    "base": 200, "mult": 1.6},
    "enLvl":    {"name": "Max Energy",   "base": 500, "mult": 1.7},
}

log_lock = threading.Lock()

def log(tag, message, account_name=None):
    now = datetime.now().strftime("%H:%M:%S")
    acc_tag = f"[{account_name}] " if account_name else ""
    with log_lock:
        print(f"[{now}] {acc_tag}[{tag:<8}] {message}")

class HomkaAccount:
    def __init__(self, acc_config, settings, stop_event=None):
        self.acc_config = acc_config
        self.settings = settings
        self.stop_event = stop_event or threading.Event()
        self.name = acc_config.get("name", "Akun")
        self.base_url = "https://apptg.biz/api"
        
        self.init_data = acc_config.get("init_data", "").strip()
        self.client_id = acc_config.get("client_id")
        if not self.client_id:
            self.client_id = str(uuid.uuid4())
            acc_config["client_id"] = self.client_id

        self.ref_code = acc_config.get("ref_code", "ref_6311855705")
        self.proxy = acc_config.get("proxy")

        self.session = requests.Session()
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0",
            "Origin": "https://apptg.biz",
            "Referer": "https://apptg.biz/?tgWebAppStartParam=" + self.ref_code,
            "Content-Type": "application/json",
            "X-Telegram-Init-Data": self.init_data,
            "X-Client-Id": self.client_id,
            "Accept": "*/*"
        }

        # Game state
        self.user_id = 0
        self.tg_name = ""
        self.balance = 0.0
        self.earned = 0.0
        self.energy = 0
        self.tap_lvl = 1
        self.en_lvl = 1
        self.regen_lvl = 1
        self.upgrades = {}
        self.daily_streak = 0
        self.daily_claimed = False
        self.boost_available_at = 0

    def post(self, endpoint, data=None):
        url = f"{self.base_url}/{endpoint}.php"
        data = data or {}
        try:
            resp = self.session.post(url, headers=self.headers, json=data, timeout=15)
            if resp.status_code != 200:
                log("ERR", f"HTTP {resp.status_code} pada {endpoint}: {resp.text[:100]}", self.name)
                return None
            res_json = resp.json()
            if not res_json.get("ok"):
                log("ERR", f"API Error ({endpoint}): {res_json.get('error', 'Unknown')}", self.name)
                return None
            return res_json.get("data")
        except requests.exceptions.RequestException as e:
            log("NET", f"Koneksi terganggu ({endpoint}): {e}", self.name)
            return None

    def auth(self):
        log("AUTH", "Menghubungkan ke server...", self.name)
        payload = {"ref": self.ref_code, "tz": 420}
        data = self.post("auth", payload)
        if not data:
            log("FAIL", "Gagal otentikasi! Periksa init_data.", self.name)
            return False

        self._update_state(data)
        offline = data.get("offlineIncome", 0)
        log("SUCCESS", f"Login OK: {self.tg_name} (ID: {self.user_id}) | Saldo: {self.balance:,.2f} Koin", self.name)
        if offline > 0:
            log("CLAIM", f"Offline Income: +{offline:,.2f} koin", self.name)
        return True

    def _update_state(self, d):
        if not d: return
        if "userId" in d: self.user_id = d["userId"]
        if "name" in d: self.tg_name = d["name"]
        if "balance" in d: self.balance = float(d["balance"])
        if "earned" in d: self.earned = float(d["earned"])
        if "energy" in d: self.energy = int(d["energy"])
        if "tapLvl" in d: self.tap_lvl = int(d["tapLvl"])
        if "enLvl" in d: self.en_lvl = int(d["enLvl"])
        if "regenLvl" in d: self.regen_lvl = int(d["regenLvl"])
        if "upgrades" in d and isinstance(d["upgrades"], dict):
            self.upgrades = d["upgrades"]
        if "dailyStreak" in d: self.daily_streak = int(d["dailyStreak"])
        if "dailyClaimedToday" in d: self.daily_claimed = bool(d["dailyClaimedToday"])
        if "boostAvailableAt" in d: self.boost_available_at = int(d["boostAvailableAt"])

    @property
    def max_energy(self):
        return 1000 + (self.en_lvl - 1) * 500

    @property
    def regen_per_sec(self):
        return 2 + (self.regen_lvl - 1)

    @property
    def profit_per_hour(self):
        total = 0
        for uid, meta in UPGRADES_META.items():
            lvl = self.upgrades.get(uid, 0)
            total += lvl * meta["ph"]
        return total

    def claim_daily(self):
        if self.daily_claimed: return
        log("DAILY", f"Klaim Daily Streak Hari ke-{self.daily_streak + 1}...", self.name)
        data = self.post("daily")
        if data:
            self._update_state(data)
            self.daily_claimed = True
            log("DAILY", f"Berhasil klaim harian! Saldo: {self.balance:,.2f}", self.name)

    def claim_boost(self):
        log("BOOST", "Mencoba klaim Full Energy Boost...", self.name)
        data = self.post("boost")
        if data:
            self._update_state(data)
            log("BOOST", f"Boost sukses! Energi penuh: {self.energy}/{self.max_energy}", self.name)
            return True
        return False

    def send_taps(self, tap_count):
        ts = int(time.time() * 1000)
        data = self.post("tap", {"taps": tap_count, "ts": ts})
        if data:
            self.balance = float(data.get("balance", self.balance))
            self.energy = int(data.get("energy", self.energy))
            self.earned = float(data.get("earned", self.earned))
            accepted = data.get("accepted", tap_count)
            log("TAP", f"+{accepted * self.tap_lvl} koin ({accepted} tap) | Energi: {self.energy}/{self.max_energy} | Saldo: {self.balance:,.2f}", self.name)
            return True
        return False

    def get_upgrade_cost(self, upg_type, upg_id=None):
        if upg_type in LEVELS_META:
            curr_lvl = getattr(self, "tap_lvl" if upg_type == "tapLvl" else ("en_lvl" if upg_type == "enLvl" else "regen_lvl"))
            meta = LEVELS_META[upg_type]
            return math.floor(meta["base"] * (meta["mult"] ** (curr_lvl - 1)))
        elif upg_type == "upgrade" and upg_id in UPGRADES_META:
            curr_lvl = self.upgrades.get(upg_id, 0)
            meta = UPGRADES_META[upg_id]
            return math.floor(meta["base"] * (1.4 ** curr_lvl))
        return float("inf")

    def check_and_buy_smart_upgrades(self):
        level_caps = self.settings.get("level_caps", {})
        reserve = self.settings.get("min_reserve_coins", 1000)
        max_cost = self.settings.get("max_upgrade_cost", 15000)

        candidates = []

        # 1. Regen Speed
        cap_regen = level_caps.get("regenLvl", 5)
        if self.regen_lvl < cap_regen:
            cost = self.get_upgrade_cost("regenLvl")
            candidates.append({"type": "regenLvl", "id": None, "name": "Regen Speed", "cost": cost, "payback": cost / 3600.0, "target_lvl": self.regen_lvl + 1})

        # 2. Pasif
        for uid, meta in UPGRADES_META.items():
            cap = level_caps.get(uid, 0)
            curr_lvl = self.upgrades.get(uid, 0)
            if curr_lvl < cap:
                cost = self.get_upgrade_cost("upgrade", uid)
                candidates.append({"type": "upgrade", "id": uid, "name": meta["name"], "cost": cost, "payback": cost / meta["ph"], "target_lvl": curr_lvl + 1})

        # 3. Tap & Energy Lvl
        cap_tap = level_caps.get("tapLvl", 3)
        if self.tap_lvl < cap_tap:
            cost = self.get_upgrade_cost("tapLvl")
            candidates.append({"type": "tapLvl", "id": None, "name": "Tap Power", "cost": cost, "payback": 50.0, "target_lvl": self.tap_lvl + 1})

        cap_en = level_caps.get("enLvl", 3)
        if self.en_lvl < cap_en:
            cost = self.get_upgrade_cost("enLvl")
            candidates.append({"type": "enLvl", "id": None, "name": "Max Energy", "cost": cost, "payback": 60.0, "target_lvl": self.en_lvl + 1})

        candidates.sort(key=lambda x: x["payback"])

        for c in candidates:
            if c["cost"] <= max_cost and (self.balance - reserve) >= c["cost"]:
                log("SMART-UPG", f"Membeli '{c['name']}' ke Lv {c['target_lvl']} ({c['cost']:,} koin, balik modal ~{c['payback']:.1f} jam)...", self.name)
                res = self.post("buy", {"type": c["type"], "id": c["id"]})
                if res:
                    self._update_state(res)
                    log("SUCCESS", f"Upgrade '{c['name']}' berhasil! Sisa saldo: {self.balance:,.2f}", self.name)
                    break

    def run_loop(self):
        """Metode untuk mode concurrent (thread mandiri)"""
        if not self.auth():
            return

        if self.settings.get("auto_daily", True):
            self.claim_daily()

        min_batch = self.settings.get("min_taps_batch", 5)
        max_batch = self.settings.get("max_taps_batch", 12)
        min_del = self.settings.get("min_delay_sec", 1.5)
        max_del = self.settings.get("max_delay_sec", 3.0)

        while not self.stop_event.is_set():
            if self.settings.get("auto_upgrade", True):
                self.check_and_buy_smart_upgrades()

            req_energy = self.tap_lvl * min_batch
            if self.energy >= req_energy:
                possible_taps = self.energy // self.tap_lvl
                taps = random.randint(min_batch, min(max_batch, possible_taps))
                self.send_taps(taps)
                self.stop_event.wait(random.uniform(min_del, max_del))
            else:
                log("INFO", f"Energi rendah ({self.energy}/{self.max_energy})", self.name)
                boosted = False
                if self.settings.get("auto_boost", True):
                    boosted = self.claim_boost()

                if not boosted:
                    target_energy = int(self.max_energy * 0.8)
                    needed_energy = target_energy - self.energy
                    wait_sec = max(25, int(needed_energy / self.regen_per_sec))
                    log("WAIT", f"Menunggu regenerasi energi (~{wait_sec} dtk)...", self.name)
                    
                    for _ in range(0, wait_sec, 10):
                        if self.stop_event.is_set(): break
                        self.stop_event.wait(10)
                        data = self.post("sync")
                        if data:
                            self._update_state(data)
                            if self.energy >= target_energy:
                                break
                    log("RESUME", f"Energi siap ({self.energy}/{self.max_energy}). Lanjut tap!", self.name)

    def drain_energy_once(self):
        """Metode untuk mode sequential (habiskan energi saat giliran akun ini)"""
        if not self.user_id:
            if not self.auth():
                return
        else:
            data = self.post("sync")
            if data: self._update_state(data)

        if self.settings.get("auto_daily", True):
            self.claim_daily()

        if self.settings.get("auto_upgrade", True):
            self.check_and_buy_smart_upgrades()

        min_batch = self.settings.get("min_taps_batch", 5)
        max_batch = self.settings.get("max_taps_batch", 12)
        min_del = self.settings.get("min_delay_sec", 1.2)
        max_del = self.settings.get("max_delay_sec", 2.2)

        while not self.stop_event.is_set():
            req_energy = self.tap_lvl * min_batch
            if self.energy >= req_energy:
                possible_taps = self.energy // self.tap_lvl
                taps = random.randint(min_batch, min(max_batch, possible_taps))
                self.send_taps(taps)
                self.stop_event.wait(random.uniform(min_del, max_del))
            else:
                if self.settings.get("auto_boost", True) and self.claim_boost():
                    continue
                break

class MultiAccountManager:
    def __init__(self, config_data):
        self.config_data = config_data
        self.settings = config_data.get("settings", {})
        
        # Dukungan format lama (single account) & format baru (accounts list)
        raw_accounts = config_data.get("accounts")
        if not raw_accounts:
            raw_accounts = [{
                "name": "Akun 1",
                "enabled": True,
                "init_data": config_data.get("init_data", ""),
                "client_id": config_data.get("client_id"),
                "ref_code": config_data.get("ref_code", "ref_6311855705"),
                "proxy": None
            }]

        self.accounts_config = [a for a in raw_accounts if a.get("enabled", True) and a.get("init_data", "").strip() and not a.get("init_data", "").startswith("PASTE_")]
        self.stop_event = threading.Event()

    def run(self):
        if not self.accounts_config:
            print("\n[ERROR] Tidak ada akun aktif dengan init_data valid di config.json!")
            print("Silakan masukkan init_data untuk akun Anda di config.json terlebih dahulu.\n")
            return

        mode = self.settings.get("mode", "concurrent").lower()

        print("=" * 70)
        print(f" HOMKA / APPTG MULTI-ACCOUNT BOT")
        print(f" Total Akun Aktif : {len(self.accounts_config)}")
        print(f" Mode Eksekusi    : {mode.upper()} ({'Thread Bersamaan' if mode == 'concurrent' else 'Bergantian / Round-Robin'})")
        print(f" Smart Upgrade    : {'AKTIF' if self.settings.get('auto_upgrade', True) else 'NONAKTIF'}")
        print("=" * 70)

        accounts = [HomkaAccount(cfg, self.settings, self.stop_event) for cfg in self.accounts_config]

        # Simpan kembali config jika ada auto-generated client_id baru
        save_needed = any(cfg.get("client_id") != orig.get("client_id") for cfg, orig in zip(self.accounts_config, self.config_data.get("accounts", [])))
        if save_needed:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2)

        try:
            if mode == "concurrent":
                threads = []
                for acc in accounts:
                    t = threading.Thread(target=acc.run_loop, name=acc.name, daemon=True)
                    threads.append(t)
                    t.start()
                    time.sleep(1.0) # Jeda stagger agar tidak request serentak di milidetik yang sama

                while any(t.is_alive() for t in threads):
                    time.sleep(0.5)

            else: # sequential / round-robin
                round_num = 1
                while not self.stop_event.is_set():
                    log("ROUND", f"=== Memulai Putaran #{round_num} ===")
                    for acc in accounts:
                        if self.stop_event.is_set(): break
                        log("TURN", f"Giliran {acc.name}...", acc.name)
                        acc.drain_energy_once()
                        time.sleep(2.0)

                    log("SUMMARY", f"Putaran #{round_num} selesai untuk semua akun.")
                    print("\n--- RINGKASAN SALDO ---")
                    for acc in accounts:
                        print(f"  • {acc.name:<15} ({acc.tg_name}): {acc.balance:,.2f} Koin (~{acc.balance/1000000:.4f} USDT) | Pasif: +{acc.profit_per_hour}/jam")
                    print("-----------------------\n")

                    wait_round = 300 # 5 menit istirahat per putaran
                    log("WAIT", f"Semua akun istirahat {wait_round} detik menunggu pemulihan energi...")
                    for _ in range(0, wait_round, 10):
                        if self.stop_event.is_set(): break
                        time.sleep(10)

                    round_num += 1

        except KeyboardInterrupt:
            print("\n")
            log("STOP", "Menghentikan semua thread akun (Ctrl+C)...")
            self.stop_event.set()
            time.sleep(1.0)
            print("Bot berhasil dihentikan. Sampai jumpa!")

def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"[ERROR] File konfigurasi '{CONFIG_PATH}' tidak ditemukan.")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    manager = MultiAccountManager(config_data)
    manager.run()

if __name__ == "__main__":
    main()
