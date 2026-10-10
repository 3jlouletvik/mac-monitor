# 🖥 Mac Monitor

A tiny menu bar system monitor for macOS with **smart alerts**. It shows CPU and RAM right in the menu bar and warns you when something really eats your Mac's resources, and it tells you *which app* is to blame.

🇷🇺 [Читать по-русски](README.ru.md)

<p align="center"><img src="docs/screenshot.png" width="320" alt="Mac Monitor menu"></p>
<p align="center"><i>The menu (Russian interface; English is picked automatically on an English macOS)</i></p>

## ✨ Features

- 🖥 🧠 Live CPU and RAM in the menu bar with a 🟢🟡🔴 traffic light
- Dropdown menu: swap 🔁, disk 💾, battery 🔋, network speed 🌐, mini-graphs 📈
- 🔥 Top-3 apps by CPU and 🐘 by memory (all processes of one app are summed up, e.g. Chrome)
- 🔔 Smart alerts: only when the load stays high for ~12 seconds, names the culprit, no spam (cooldown)
- ⏸ Snooze notifications for 1 hour
- 🚀 "Launch at login" switch right in the menu
- 🪶 Lightweight: low priority, slow-changing things are checked less often
- 🌍 English and Russian interface (picked automatically)
- ⚙️ Settings in a simple JSON file
- One copy at a time, errors go to a log file

## 📦 Install

Two ways, the same program:

### Option A: the app (no Python needed)

1. Download the zip for **your** Mac from the [Releases](../../releases) page and unzip it:
   - `MacMonitor-apple-silicon.zip`: Macs with an Apple chip (M1, M2, M3 and newer)
   - `MacMonitor-intel.zip`: Macs with an Intel processor

   Not sure which one you have? Click  → *About This Mac*: it says **Chip** (Apple) or **Processor** (Intel).
2. Drag **Mac Monitor.app** to your **Applications** folder and open it.

The app is not signed with a paid Apple Developer certificate, so macOS blocks it on the first launch:

- **macOS 15 and newer:** try to open it, then go to *System Settings → Privacy & Security* and click **Open Anyway**.
- **Older macOS:** right-click the app → **Open**.
- **Or in Terminal:** `xattr -dr com.apple.quarantine "/Applications/Mac Monitor.app"`

### Option B: the script

You need Python 3.9+.

```bash
git clone https://github.com/3jlouletvik/mac-monitor.git
cd mac-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python mac_monitor.py
```

## 🔨 Build the app yourself

```bash
bash build_app.sh
```

The app is built for the processor of the Mac you run this on. The result is `dist/Mac Monitor.app` and `dist/MacMonitor-apple-silicon.zip` (or `dist/MacMonitor-intel.zip`). The same build runs on GitHub Actions for both processor types: push a tag like `v2.1.1` and both zips are attached to a Release automatically.

## ⚙️ Settings

Click **⚙️ Open settings** in the menu. The file lives at `~/Library/Application Support/MacMonitor/config.json`. **Restart the app** after editing.

| Key | Default | Meaning |
| --- | --- | --- |
| `language` | `"auto"` | `"auto"`, `"en"` or `"ru"` |
| `limits.cpu` / `limits.ram` / `limits.disk` | `85` / `85` / `90` | % at which the load counts as high |
| `battery_low` | `20` | warn at this battery % or below |
| `checks_in_row` | `4` | how many checks in a row (3 s each) must be high before warning |
| `cooldown_minutes` | cpu 10, ram 10, disk 360, battery 10 | minimum pause between repeated warnings |
| `notifications` | `true` | notifications on at start |

A wrong or missing value is simply ignored and the default is used.

## 🩺 Troubleshooting

- **"Launch error" when opening the app:** you downloaded the zip for the other processor type. Download the other one (see Install → Option A).
- **No notifications:** open *System Settings → Notifications* and allow them for **Script Editor** (macOS sends them through it).
- **Something is wrong:** look at `~/Library/Logs/MacMonitor.log` and attach it to your issue.
- **No temperature or fan speed:** macOS does not give this to regular apps without admin rights or extra tools.

## 📄 License

[MIT](LICENSE)

Made by [s(l)izzy](https://github.com/3jlouletvik).
