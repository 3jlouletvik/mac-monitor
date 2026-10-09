# Changelog

## 2.1.0
- Settings file `config.json` (thresholds, cooldowns, language)
- English and Russian interface (picked automatically)
- "Snooze for 1 hour" and "Open Activity Monitor" menu items
- Only one copy of the app can run at a time
- Errors are written to `~/Library/Logs/MacMonitor.log`
- GitHub Actions workflow that builds the app and attaches it to a Release
- Fixed the disk percentage: it now measures the volume with your files (`/System/Volumes/Data`)

## 2.0.0
- Emojis, 🟢🟡🔴 traffic light, mini-graphs, network speed, swap
- "Launch at login" switch
- Can be built as a `.app`
- Lower CPU usage: slow things are checked less often

## 1.0.0
- CPU / RAM / disk / battery in the menu bar and alerts about high load
