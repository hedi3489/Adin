import requests
from datetime import datetime, timedelta, date
import schedule
import time
import subprocess
import logging
from lcd1602 import LCD1602
import signal
import sys

# Variables
prayers = {}
remaining_prayers = []
counter = 0
toggle_state = True
lcd = LCD1602()
ORDER = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

# Logging setup
logging.basicConfig(
    filename="/home/pi/Desktop/Adin/adin.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.info("===== Fetcher.py started =====")

# API endpoint
url = "https://api.aladhan.com/v1/timings/"
params = {
    "latitude": "45.49829337659685",
    "longitude": "-73.5006225145062"
}



# Logic functions
def initial_fetch():

    global prayers
    schedule.clear('prayers')

    tdy_str = date.today().strftime("%d-%m-%Y")
    execute_fetch(url, tdy_str, params)

def execute_fetch(url, date_str, params):
    global prayers
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

def get_remaining_prayers(prayers):
    now = datetime.now().time()
    remaining = []

    for name in ORDER:
        prayer_time = datetime.strptime(prayers[name], "%H:%M").time()
        if prayer_time > now:
            remaining.append((name, prayers[name]))

    if not remaining_prayers:
        refresh_for_next_day()
        remaining_prayers = get_remaining_prayers(prayers)

    return remaining

def schedule_play_adhan(remaining_prayers):
    for prayer, t in remaining_prayers:
        logging.info(f"Scheduled {prayer} at {t}")
        schedule.every().day.at(t).do(play_adhan).tag("adhan")

def schedule_next_fetch():
    isha_str = prayers["Isha"]
    schedule.every().day.at(isha_str).do(refresh_for_next_day).tag("refresh")

def refresh_for_next_day():
    global remaining_prayers

    schedule.clear("adhan")
    schedule.clear("refresh")

    tmr_str = (date.today() + timedelta(days=1)).strftime("%d-%m-%Y")
    execute_fetch(url, tmr_str, params)

    remaining_prayers = get_remaining_prayers(prayers)
    schedule_play_adhan(remaining_prayers)
    schedule_next_fetch()


# Audio functions
def play_adhan():
    global counter
    now = datetime.now().strftime("%H:%M")
    logging.info(f"Playing Adhan at {now}")
    try:
        subprocess.Popen(["mpg123", "-o", "alsa", "/home/pi/Desktop/Adin/adhan.mp3"])
    except Exception as e:
        logging.error(f"Error playing audio: {e}")
    counter += 1 


# LCD functions
def screen_cleaning():
    time.sleep(0.5)
    lcd.clear()
    time.sleep(0.1)
    lcd.clear() 
    lcd.write(
        "Adin Awake",
        "Fetching times"
    )
    time.sleep(3)

def update_lcd():
    now = datetime.now().strftime("%H:%M")
    if remaining_prayers:
        prayer, t = remaining_prayers[0]
        lcd.write("Now: " + now, f"{prayer} at {t}")
    else:
        lcd.write("Now: " + now, "No prayers left")

def graceful_exit(signum, frame):
    lcd.clear()
    lcd.write("Adin...", "   Asleep...")
    lcd.cleanup()
    sys.exit(0)


# 1. Initialize
screen_cleaning()

# 2. Get prayers
initial_fetch() # sets the prayers list from F-I
time.sleep(5)

# 3. What time is it? which prayers are left?
remaining_prayers = get_remaining_prayers(prayers)

# 4. Schedule adhan
schedule_play_adhan(remaining_prayers)

# 5. Schedule fetching tomorrow's prayers
schedule_next_fetch()
  
# 4. schedule lcd updates
schedule.every(5).seconds.do(update_lcd)


# Catch Ctrl+C & termination signal
signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

while True:
    schedule.run_pending()
    time.sleep(1)
