import requests
from datetime import datetime, timedelta
import schedule
import time
import subprocess
import logging
from lcd1602 import LCD1602
import signal
import sys

toggle_state = True

# Logging setup
logging.basicConfig(
    filename="/home/pi/Desktop/Adin/adin.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("===== Fetcher.py started =====")
lcd = LCD1602()
lcd.write(
    "Adin Awake",
    "Fetching times"
)
time.sleep(3)

# API endpoint and parameters
url = "https://api.aladhan.com/v1/timingsByCity"
params = {
    "city": "Brossard",
    "country": "Canada",
    "method": 2
}

def fetch_prayer_times():
    global prayers
    schedule.clear('prayers')

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        timings = data["data"]["timings"]
        logging.info("Prayer times fetched successfully.")

    except Exception as e:
        logging.error(f"Error fetching prayer times: {e}")
        timings = {}

    prayers = {
        "Fajr": timings.get('Fajr', '00:00'),
        "Dhuhr": timings.get('Dhuhr', '00:00'),
        "Asr": timings.get('Asr', '00:00'),
        "Maghreb": timings.get('Maghrib', '00:00'),
        "Isha": timings.get('Isha', '00:00')
    }

    for prayer, t in prayers.items():
        logging.info(f"Scheduled {prayer} at {t}")
        # lcd.write("Next prayer,", f"{prayer} as {t}")
        schedule.every().day.at(t).do(play_adhan).tag('prayers')

    return prayers

def update_next_prayer_display(prayers):
    global toggle_state
    now = datetime.now().time()
    current_time = datetime.now().strftime("%H:%M")
    next_prayer = None

    for prayer, t in prayers.items():
        prayer_time = datetime.strptime(t, "%H:%M").time()
        if prayer_time > now:
            next_prayer = (prayer, t)
            break
    lcd.clear()
    if toggle_state:
        if next_prayer:
            lcd.write("Next Prayer,",f"{next_prayer[0]} at {next_prayer[1]}")
        else:
            lcd.write("Fetching prayers", "in a bit...")
    else:
        lcd.write("Currently,", f"it's {current_time}")
    
    toggle_state = not toggle_state


def play_adhan():
    now = datetime.now().strftime("%H:%M")
    logging.info(f"Playing Adhan at {now}")
    try:
        subprocess.Popen(["mpg123", "-o", "alsa", "/home/pi/Desktop/Adin/adhan.mp3"])
    except Exception as e:
        logging.error(f"Error playing audio: {e}")

def schedule_refresh_time():
    isha_time = datetime.strptime(prayers["Isha"], "%H:%M")
    refresh_time_dt = isha_time + timedelta(minutes=3)
    refresh_time = refresh_time_dt.strftime("%H:%M")
    schedule.every().day.at(refresh_time).do(fetch_prayer_times).tag('refresh')

def graceful_exit(signum, frame):
    lcd.clear()
    lcd.write("Adin...", "   Asleep...")
    lcd.cleanup()
    sys.exit(0)

prayers = {}
fetch_prayer_times()
time.sleep(5)
schedule_refresh_time()
schedule.every(5).seconds.do(update_next_prayer_display, prayers)

# Catch Ctrl+C & termination signal
signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

while True:
    schedule.run_pending()
    time.sleep(1)
