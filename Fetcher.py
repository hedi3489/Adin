import requests
from datetime import datetime
import schedule
import time
import subprocess
import logging
from lcd1602 import LCD1602

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
    """Fetch new prayer times and reschedule Adhan jobs."""
    global prayers
    # Clear old jobs first
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

    next_prayer = list(prayers.items())[0]
    lcd.clear()
    lcd.write(
        "Next Prayer,",
        f"{next_prayer[0]} at {next_prayer[1]}"
    )

    for prayer, t in prayers.items():
        logging.info(f"Scheduled {prayer} at {t}")
        # lcd.write("Next prayer,", f"{prayer} as {t}")
        schedule.every().day.at(t).do(play_adhan).tag('prayers')

# Function to play audio
def play_adhan():
    now = datetime.now().strftime("%H:%M")
    logging.info(f"Playing Adhan at {now}")
    try:
        subprocess.Popen(["mpg123", "-o", "alsa", "/home/pi/Desktop/Adin/adhan.mp3"])
    except Exception as e:
        logging.error(f"Error playing audio: {e}")

# Initial fetch
fetch_prayer_times()

# Schedule daily refresh at 00:05
schedule.every().day.at("00:05").do(fetch_prayer_times).tag('refresh')

# Keep running
try:

    while True:
        schedule.run_pending()
        time.sleep(1)
except KeyboardInterrupt:
    lcd.cleanup()
