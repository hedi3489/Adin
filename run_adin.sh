#!/bin/bash

cd /home/pi/Desktop/Adin
source adin-env/bin/activate

# Variables
export XDG_RUNTIME_DIR="/run/user/1000"
export PULSE_SERVER="unix:/run/user/1000/pulse/native"

python3 Fetcher.py
