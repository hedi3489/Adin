# Adin: RPi Adhan Player
Adin is a Raspberry Pi script that fetches daily prayer times from the `Aladhan API`, plays the Adhan at each prayer, and displays the current time and next prayer on an LCD. It handles midnight and post-Isha rollovers, and updates the display continuously.

### Hardware Requirements
- Raspberry Pi
- Speaker connected to the Pi
- LCD1602 display

### Software Requirements
- Python 3
- Virtual environment
- requests library (pip install requests)
- schedule library (pip install schedule)
- mpg123 for audio playback

### Features
- Daily fetching of prayer times
- Adhan playing for each prayer
- LCD display of current time and next prayer
- Re-fetching tomorrow's prayer times after Isha

## Usage
1. Place script, LCD library, and Adhan audio file at /Desktop/Adin/
2. Activate the virtual environment and set audio variables before running:
    ```
    cd /home/pi/Desktop/Adin
    source adin-env/bin/activate
    export XDG_RUNTIME_DIR="/run/user/1000"
    export PULSE_SERVER="unix:/run/user/1000/pulse/native"
    python3 Fetcher.py
    ```
3. You can also run via the provided shell script:
   ```
   ./run_adin.sh
   ```
