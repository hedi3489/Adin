import requests
from datetime import datetime, timedelta, date
import schedule
import time
import subprocess
import logging
from lcd1602 import LCD1602
import signal
import sys

prayers = {}
counter = 0
toggle_state = True
ORDER = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

# Logging setup
logging.basicConfig(
    filename="/home/pi/Desktop/Adin/adin.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("===== Fetcher.py started =====")
lcd = LCD1602()

# Ensure LCD clears
time.sleep(0.5)
lcd.clear()
time.sleep(0.1)
lcd.clear() 

lcd.write(
    "Adin Awake",
    "Fetching times"
)
time.sleep(3)

# API endpoint and parameters

url = "https://api.aladhan.com/v1/timings/"
params = {
    "latitude": "45.49829337659685",
    "longitude": "-73.5006225145062"
}

def fetch_prayer_times():
    global prayers
    schedule.clear('prayers')

    date_str = date.today().strftime("%d-%m-%Y")

    if "Isha" in prayers:
        isha = datetime.strptime(prayers["Isha"], "%H:%M").time()
        if datetime.now().time() > isha:
            date_str = (date.today() + timedelta(days=1)).strftime("%d-%m-%Y")

    prayers = execute_fetch(url, date_str, params)

    for prayer, t in prayers.items():
        logging.info(f"Scheduled {prayer} at {t}")
        schedule.every().day.at(t).do(play_adhan).tag('prayers')

    schedule_refresh_time()

def execute_fetch(url, date_str, params):
    try:
        response = requests.get(url+date_str, params=params, timeout=10)
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
        "Maghrib": timings.get('Maghrib', '00:00'),
        "Isha": timings.get('Isha', '00:00')
    }
    return prayers


def play_adhan():
    global counter
    now = datetime.now().strftime("%H:%M")
    logging.info(f"Playing Adhan at {now}")
    try:
        subprocess.Popen(["mpg123", "-o", "alsa", "/home/pi/Desktop/Adin/adhan.mp3"])
    except Exception as e:
        logging.error(f"Error playing audio: {e}")
    counter += 1 

def update_lcd():
    global counter
    global ORDER
    now = datetime.now().strftime("%H:%M")
    counter %= len(ORDER)
    lcd.write("Now: " + now, f"{ORDER[counter]} at {prayers[ORDER[counter]]}")

def reconcile_counter():
    global counter
    global ORDER

    counter = 0
    now = datetime.now().time()
    for name in ORDER:
        prayer_time = datetime.strptime(prayers[name], "%H:%M").time()
        if now > prayer_time:
            counter += 1
        else:
            break

def schedule_refresh_time():
    isha_time = datetime.strptime(prayers["Isha"], "%H:%M")
    refresh_time_dt = isha_time + timedelta(minutes=5)
    refresh_time = refresh_time_dt.strftime("%H:%M")
    schedule.every().day.at(refresh_time).do(fetch_prayer_times).tag('refresh')

def graceful_exit(signum, frame):
    lcd.clear()
    lcd.write("Adin...", "   Asleep...")
    lcd.cleanup()
    sys.exit(0)

fetch_prayer_times()
time.sleep(5)
reconcile_counter()
schedule.every(5).seconds.do(update_lcd)

# Catch Ctrl+C & termination signal
signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

while True:
    schedule.run_pending()
    time.sleep(1)
