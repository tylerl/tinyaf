#!/bin/bash
set -e
cd /workspaces/tinyaf
virtualenv .venv
.venv/bin/pip3 install -r requirements/dev.txt