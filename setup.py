"""Build the macOS app:  python setup.py py2app   (or just:  bash build_app.sh)"""

from setuptools import setup

APP = ["mac_monitor.py"]

OPTIONS = {
    "packages": ["rumps", "psutil"],
    "plist": {
        "CFBundleName": "Mac Monitor",
        "CFBundleDisplayName": "Mac Monitor",
        "CFBundleIdentifier": "io.github.3jlouletvik.macmonitor",
        "CFBundleVersion": "2.1.0",
        "CFBundleShortVersionString": "2.1.0",
        "LSUIElement": True,   # menu bar only, no Dock icon
    },
}

setup(
    app=APP,
    name="Mac Monitor",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
