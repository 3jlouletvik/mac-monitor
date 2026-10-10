"""Mac Monitor 🖥 — a smart system monitor for the macOS menu bar.

Run as a script:  python mac_monitor.py
Build as an app:  bash build_app.sh   (see README)
"""

import copy
import fcntl
import json
import logging
import os
import plistlib
import subprocess
import sys
import time
from collections import deque

import psutil
import rumps

VERSION = "2.1.1"

# ---------- PATHS ----------
LABEL = "local.macmonitor"   # name of the autostart job
LAUNCH_AGENT = os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")
CONFIG_DIR = os.path.expanduser("~/Library/Application Support/MacMonitor")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.expanduser("~/Library/Logs/MacMonitor.log")

# ---------- INTERNAL TIMINGS (not in the config file) ----------
CHECK_EVERY = 3        # seconds between CPU / RAM / network updates
SLOW_EVERY = 10        # disk, swap and battery are checked 10x less often
PROCS_EVERY = 5        # the process list is refreshed 5x less often
HISTORY = 20           # how many last values the mini-graph shows
BARS = "▁▂▃▄▅▆▇█"      # "bars" for the mini-graph
SNOOZE_SECONDS = 3600  # "snooze" lasts one hour
ICONS = {"cpu": "🖥", "ram": "🧠", "disk": "💾"}

# Since macOS Catalina the system and your files live on two separate volumes.
# "/" is only the (small) system volume, so it would always show a tiny percent.
# Your files are on "/System/Volumes/Data".
DISK_PATH = "/System/Volumes/Data" if os.path.exists("/System/Volumes/Data") else "/"

# ---------- USER SETTINGS (defaults; the user can override them in config.json) ----------
DEFAULT_CONFIG = {
    "language": "auto",                                  # "auto", "en" or "ru"
    "limits": {"cpu": 85, "ram": 85, "disk": 90},        # % at which the load is "high"
    "battery_low": 20,                                   # warn at this battery % or below
    "checks_in_row": 4,                                  # high N checks in a row (N * 3 sec)
    "cooldown_minutes": {"cpu": 10, "ram": 10, "disk": 360, "battery": 10},
    "notifications": True,                               # notifications on at start
}

# ---------- TEXTS (interface languages) ----------
TEXTS = {
    "ru": {
        "swap": "🔁 Своп: {gb:.1f} ГБ",
        "disk": "💾 Диск: {emoji} {pct:.0f}% (свободно {free:.0f} ГБ)",
        "battery": "🔋 Батарея: {pct:.0f}%{plug}",
        "no_battery": "🔋 Батарея: нет данных",
        "network": "🌐 Сеть: ⬇️ {down}  ⬆️ {up}",
        "mb": "МБ/с",
        "kb": "КБ/с",
        "top_cpu": "🔥 Больше всего грузят процессор:",
        "top_ram": "🐘 Больше всего занимают память:",
        "notifications": "🔔 Уведомления",
        "snooze": "⏸ Не беспокоить 1 час",
        "autostart": "🚀 Запускать при входе в систему",
        "settings": "⚙️ Открыть настройки",
        "activity": "📊 Мониторинг системы",
        "quit": "🚪 Выйти",
        "cpu_name": "Процессор",
        "ram_name": "Память",
        "disk_name": "Диск",
        "hint_cpu": "🔥 Больше всех грузит: {name}. Если не нужна — закрой её.",
        "hint_ram": "🐘 Больше всех занимает: {name}. Закрой лишние вкладки и программы.",
        "hint_disk": "🧹 Почисти корзину и папку «Загрузки».",
        "battery_low_title": "🪫 Батарея садится",
        "battery_low_text": "Осталось {pct:.0f}%. Пора подключить зарядку.",
    },
    "en": {
        "swap": "🔁 Swap: {gb:.1f} GB",
        "disk": "💾 Disk: {emoji} {pct:.0f}% ({free:.0f} GB free)",
        "battery": "🔋 Battery: {pct:.0f}%{plug}",
        "no_battery": "🔋 Battery: n/a",
        "network": "🌐 Network: ⬇️ {down}  ⬆️ {up}",
        "mb": "MB/s",
        "kb": "KB/s",
        "top_cpu": "🔥 Top CPU usage:",
        "top_ram": "🐘 Top memory usage:",
        "notifications": "🔔 Notifications",
        "snooze": "⏸ Snooze for 1 hour",
        "autostart": "🚀 Launch at login",
        "settings": "⚙️ Open settings",
        "activity": "📊 Open Activity Monitor",
        "quit": "🚪 Quit",
        "cpu_name": "CPU",
        "ram_name": "Memory",
        "disk_name": "Disk",
        "hint_cpu": "🔥 Top CPU hog: {name}. Close it if you don't need it.",
        "hint_ram": "🐘 Using the most memory: {name}. Close extra tabs and apps.",
        "hint_disk": "🧹 Empty the Trash and clean up your Downloads folder.",
        "battery_low_title": "🪫 Battery is low",
        "battery_low_text": "{pct:.0f}% left. Time to plug in the charger.",
    },
}

# ---------- LOG FILE (errors are written here, handy for bug reports) ----------
try:
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
except OSError:
    pass


# ---------- CONFIG ----------
def is_compatible(default, value):
    """Is the value from the file the same kind of thing as the default (number/text/yes-no)?"""
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


def merge(base, extra):
    """Copies values from `extra` into `base`: only known keys and only suitable values."""
    for key, value in extra.items():
        if key not in base:
            continue
        if isinstance(base[key], dict):
            if isinstance(value, dict):
                merge(base[key], value)      # go one level deeper
        elif is_compatible(base[key], value):
            base[key] = value


def load_config():
    """Reads config.json. No file yet? Creates it with defaults.
    A missing or broken value in the file just means "use the default"."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                user_config = json.load(f)
            if isinstance(user_config, dict):
                merge(config, user_config)
        else:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    except (OSError, ValueError):
        logging.exception("Could not read the config, using defaults")
    return config


def detect_system_language():
    """Looks at the macOS language: Russian -> "ru", anything else -> "en"."""
    try:
        out = subprocess.run(
            ["defaults", "read", "-g", "AppleLanguages"],
            capture_output=True, text=True, timeout=3,
        ).stdout
        for line in out.splitlines():
            line = line.strip().strip('(),"')
            if line:
                return "ru" if line.lower().startswith("ru") else "en"
    except (OSError, subprocess.SubprocessError):
        pass
    return "en"


def resolve_language(setting):
    return setting if setting in TEXTS else detect_system_language()


CONFIG = load_config()
LANG = resolve_language(CONFIG["language"])
LIMITS = CONFIG["limits"]
BATTERY_LOW = CONFIG["battery_low"]
CHECKS_IN_ROW = CONFIG["checks_in_row"]


def t(key, **values):
    """Returns the interface text in the chosen language and fills in the {placeholders}."""
    return TEXTS[LANG][key].format(**values)


# ---------- HELPERS ----------
def set_text(obj, text):
    """Change a label only if it really changed (less work for macOS)."""
    if obj.title != text:
        obj.title = text


def level_emoji(value, limit):
    """🟢 fine, 🟡 getting high, 🔴 too high."""
    if value >= limit:
        return "🔴"
    if value >= limit - 25:
        return "🟡"
    return "🟢"


def sparkline(values):
    """Turns a list of percents into a mini-graph: ▁▂▅▇."""
    text = ""
    for v in values:
        index = int(v / 100 * len(BARS))         # index = position of a symbol in BARS
        text += BARS[min(index, len(BARS) - 1)]   # min() keeps us inside the string
    return text


def format_speed(bytes_per_sec):
    if bytes_per_sec >= 1024 ** 2:
        return f"{bytes_per_sec / 1024 ** 2:.1f} {t('mb')}"
    return f"{bytes_per_sec / 1024:.0f} {t('kb')}"


def notify(title, text):
    """System notification. Popen does not wait, so the menu never freezes."""
    title = title.replace('"', "'").replace("\\", "")
    text = text.replace('"', "'").replace("\\", "")
    script = f'display notification "{text}" with title "{title}"'
    subprocess.Popen(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def all_processes():
    """Load per program. Processes with the same name are summed up
    (Chrome has dozens of them) so we see the whole program at once."""
    cores = psutil.cpu_count() or 1
    totals = {}
    for proc in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
        info = proc.info
        name = info["name"] or "?"
        cpu = (info["cpu_percent"] or 0) / cores   # % of the whole CPU
        ram = info["memory_percent"] or 0          # % of all memory
        old_cpu, old_ram = totals.get(name, (0, 0))
        totals[name] = (old_cpu + cpu, old_ram + ram)
    return [(name, cpu, ram) for name, (cpu, ram) in totals.items()]


def acquire_lock():
    """Makes sure only one copy of the app runs (e.g. autostart + manual launch).
    Returns an open lock file, or None if another copy is already running."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    lock = open(os.path.join(CONFIG_DIR, "app.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return None
    return lock


# ---------- AUTOSTART ----------
def app_command():
    """The command that launches us at login."""
    if ".app/" in sys.executable:               # running as a real .app
        app_path = sys.executable.split(".app/")[0] + ".app"
        return ["/usr/bin/open", "-a", app_path]
    return [sys.executable, os.path.abspath(__file__)]   # running as a plain script


def autostart_enabled():
    return os.path.exists(LAUNCH_AGENT)


def set_autostart(enable):
    """Creates or removes a file in ~/Library/LaunchAgents."""
    if enable:
        data = {"Label": LABEL, "ProgramArguments": app_command(), "RunAtLoad": True}
        os.makedirs(os.path.dirname(LAUNCH_AGENT), exist_ok=True)
        with open(LAUNCH_AGENT, "wb") as f:
            plistlib.dump(data, f)
    elif os.path.exists(LAUNCH_AGENT):
        os.remove(LAUNCH_AGENT)


# ---------- THE APP ----------
class MacMonitor(rumps.App):
    def __init__(self):
        super().__init__("🖥 …", quit_button=t("quit"))

        # menu rows
        self.cpu_item = rumps.MenuItem("🖥 CPU: …")
        self.ram_item = rumps.MenuItem("🧠 RAM: …")
        self.swap_item = rumps.MenuItem("🔁 …")
        self.disk_item = rumps.MenuItem("💾 …")
        self.battery_item = rumps.MenuItem("🔋 …")
        self.net_item = rumps.MenuItem("🌐 …")
        self.cpu_trend = rumps.MenuItem("📈 CPU: …")
        self.ram_trend = rumps.MenuItem("📈 RAM: …")
        self.cpu_items = [rumps.MenuItem("—") for _ in range(3)]
        self.ram_items = [rumps.MenuItem("—") for _ in range(3)]

        # clickable rows
        self.activity_item = rumps.MenuItem(t("activity"), callback=self.open_activity_monitor)
        self.notify_item = rumps.MenuItem(t("notifications"), callback=self.toggle_notify)
        self.notify_item.state = int(CONFIG["notifications"])   # 1 = checkmark
        self.snooze_item = rumps.MenuItem(t("snooze"), callback=self.toggle_snooze)
        self.autostart_item = rumps.MenuItem(t("autostart"), callback=self.toggle_autostart)
        self.autostart_item.state = int(autostart_enabled())
        self.settings_item = rumps.MenuItem(t("settings"), callback=self.open_settings)
        self.version_item = rumps.MenuItem(f"Mac Monitor v{VERSION}")

        self.menu = [
            self.cpu_item,
            self.ram_item,
            self.swap_item,
            self.disk_item,
            self.battery_item,
            self.net_item,
            None,   # separator line
            self.cpu_trend,
            self.ram_trend,
            None,
            rumps.MenuItem(t("top_cpu")),
            *self.cpu_items,
            rumps.MenuItem(t("top_ram")),
            *self.ram_items,
            None,
            self.activity_item,
            None,
            self.notify_item,
            self.snooze_item,
            self.autostart_item,
            self.settings_item,
            None,
            self.version_item,
        ]

        # the assistant's "memory"
        self.tick = 0                                       # how many checks have happened
        self.high_count = {"cpu": 0, "ram": 0, "disk": 0}   # how many checks in a row were high
        self.last_alert = {}                                # when we last warned about each thing
        self.snooze_until = 0
        self.error_logged = False
        self.cpu_history = deque(maxlen=HISTORY)            # deque drops the oldest value itself
        self.ram_history = deque(maxlen=HISTORY)
        self.cpu_top = [("?", 0, 0)]
        self.ram_top = [("?", 0, 0)]
        self.disk_percent = 0
        self.last_net = psutil.net_io_counters()
        self.last_net_time = time.time()

        psutil.cpu_percent(None)   # the first call only sets the starting point
        self.refresh_processes()
        self.update_slow()

    # --- menu clicks ---
    def toggle_notify(self, sender):
        sender.state = not sender.state

    def toggle_snooze(self, sender):
        if time.time() < self.snooze_until:
            self.snooze_until = 0
        else:
            self.snooze_until = time.time() + SNOOZE_SECONDS
        sender.state = int(time.time() < self.snooze_until)

    def toggle_autostart(self, sender):
        sender.state = not sender.state
        set_autostart(bool(sender.state))

    def open_settings(self, _):
        subprocess.Popen(["open", "-t", CONFIG_PATH])

    def open_activity_monitor(self, _):
        subprocess.Popen(["open", "-a", "Activity Monitor"])

    # --- alerts ---
    def can_alert(self, key):
        if not self.notify_item.state:
            return False
        if time.time() < self.snooze_until:
            return False
        cooldown = CONFIG["cooldown_minutes"][key] * 60
        return time.time() - self.last_alert.get(key, 0) >= cooldown

    def send_alert(self, key, title, text):
        self.last_alert[key] = time.time()
        notify(title, text)

    def hint_for(self, key):
        if key == "cpu":
            return t("hint_cpu", name=self.cpu_top[0][0])
        if key == "ram":
            return t("hint_ram", name=self.ram_top[0][0])
        return t("hint_disk")

    # --- data updates ---
    def refresh_processes(self):
        procs = all_processes()
        self.cpu_top = sorted(procs, key=lambda p: p[1], reverse=True)[:3]
        self.ram_top = sorted(procs, key=lambda p: p[2], reverse=True)[:3]
        for item, (name, cpu, ram) in zip(self.cpu_items, self.cpu_top):
            set_text(item, f"{name} — {cpu:.0f}%")
        for item, (name, cpu, ram) in zip(self.ram_items, self.ram_top):
            set_text(item, f"{name} — {ram:.1f}%")

    def update_slow(self):
        """Things that change slowly: disk, swap, battery."""
        disk = psutil.disk_usage(DISK_PATH)
        self.disk_percent = disk.percent
        emoji = level_emoji(disk.percent, LIMITS["disk"])
        set_text(self.disk_item, t("disk", emoji=emoji, pct=disk.percent, free=disk.free / 1024 ** 3))

        set_text(self.swap_item, t("swap", gb=psutil.swap_memory().used / 1024 ** 3))

        battery = psutil.sensors_battery()
        if battery is None:   # e.g. a desktop Mac
            set_text(self.battery_item, t("no_battery"))
            return
        plug = " ⚡" if battery.power_plugged else ""
        set_text(self.battery_item, t("battery", pct=battery.percent, plug=plug))
        if (
            battery.percent <= BATTERY_LOW
            and not battery.power_plugged
            and self.can_alert("battery")
        ):
            self.send_alert(
                "battery",
                t("battery_low_title"),
                t("battery_low_text", pct=battery.percent),
            )

    @rumps.timer(CHECK_EVERY)
    def update(self, _):
        """Called automatically every CHECK_EVERY seconds.
        If something goes wrong, the error goes to the log file instead of killing the app."""
        try:
            self.do_update()
        except Exception:
            if not self.error_logged:   # log only the first error, do not flood the file
                logging.exception("Update failed")
                self.error_logged = True

    def do_update(self):
        self.tick += 1

        # snooze is over -> remove the checkmark
        if self.snooze_item.state and time.time() >= self.snooze_until:
            self.snooze_item.state = 0

        cpu = psutil.cpu_percent(None)
        ram = psutil.virtual_memory().percent
        self.cpu_history.append(cpu)
        self.ram_history.append(ram)

        set_text(self.cpu_item, f"🖥 CPU: {level_emoji(cpu, LIMITS['cpu'])} {cpu:.0f}%")
        set_text(self.ram_item, f"🧠 RAM: {level_emoji(ram, LIMITS['ram'])} {ram:.0f}%")
        set_text(self.cpu_trend, f"📈 CPU: {sparkline(self.cpu_history)}")
        set_text(self.ram_trend, f"📈 RAM: {sparkline(self.ram_history)}")

        # network speed = how many bytes were added / how many seconds passed
        net = psutil.net_io_counters()
        now = time.time()
        seconds = max(now - self.last_net_time, 0.001)
        down = (net.bytes_recv - self.last_net.bytes_recv) / seconds
        up = (net.bytes_sent - self.last_net.bytes_sent) / seconds
        self.last_net, self.last_net_time = net, now
        set_text(self.net_item, t("network", down=format_speed(down), up=format_speed(up)))

        # rare checks
        if self.tick % SLOW_EVERY == 0:
            self.update_slow()
        if self.tick % PROCS_EVERY == 1:
            self.refresh_processes()

        # how many checks in a row was the load above the limit?
        values = {"cpu": cpu, "ram": ram, "disk": self.disk_percent}
        for key, value in values.items():
            if value >= LIMITS[key]:
                self.high_count[key] += 1
            else:
                self.high_count[key] = 0
        alarms = [key for key in values if self.high_count[key] >= CHECKS_IN_ROW]

        for key in alarms:
            if self.can_alert(key):
                self.refresh_processes()   # fresh data, so we can name the culprit
                title = f"{ICONS[key]} {t(key + '_name')}: {values[key]:.0f}%"
                self.send_alert(key, title, self.hint_for(key))

        warning = "⚠️ " if alarms else ""
        set_text(self, f"{warning}🖥 {cpu:.0f}% 🧠 {ram:.0f}%")


if __name__ == "__main__":
    lock = acquire_lock()
    if lock is None:
        sys.exit(0)   # another copy is already running
    try:
        os.nice(10)   # ask macOS for a lower priority: the monitor must not slow you down
    except OSError:
        pass
    MacMonitor().run()
