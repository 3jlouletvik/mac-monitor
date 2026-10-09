#!/usr/bin/env bash
# Builds "Mac Monitor.app" and packs it into dist/MacMonitor.zip
# Usage:  bash build_app.sh
set -e                       # stop at the first error
cd "$(dirname "$0")"         # work from the folder where this file lives

python3 -m venv .venv-build
source .venv-build/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements-dev.txt

rm -rf build dist
python setup.py py2app

# ditto is the macOS way to zip an .app without breaking it
ditto -c -k --keepParent "dist/Mac Monitor.app" dist/MacMonitor.zip

echo "Done: dist/Mac Monitor.app and dist/MacMonitor.zip"
