import requests
from datetime import datetime, timedelta, date
import schedule
import time
import subprocess
import logging
from lcd1602 import LCD1602
import signal
import sys

# =========================
# Configuration
# =========================
prayers = {}
counter = 0
ORDER = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

# Logging setup
logging.basicConfig(
    filename="/home/pi/Desktop/Adin/adin.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(message)s"
)

# API configuration
URL = "https://api.aladhan.com/v1/timings/"
PARAMS = {
    "latitude": "45.49829337659685",
    "longitude": "-73.5006225145062"
}

# =========================
# Custom Log Levels
# =========================
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")
def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)
logging.Logger.success = success

# =========================
# Initialization Helpers
# =========================
def init_lcd():
    lcd = LCD1602()
    time.sleep(0.5)
    lcd.clear()
    time.sleep(0.1)
    lcd.clear()
    lcd.write("Adin Awake", "Fetching times")
    time.sleep(3)
    return lcd

def log_startup():
    logging.info("")
    logging.info("==================================================")
    logging.info("===== Fetcher.py started =====")
    logging.info("==================================================")

# =========================
# Prayer Time Fetching
# =========================
def fetch_prayer_times():
    global prayers
    schedule.clear('prayers')

    date_str = date.today().strftime("%d-%m-%Y")

    if "Isha" in prayers:
        isha = datetime.strptime(prayers["Isha"], "%H:%M").time()
        if datetime.now().time() > isha:
            date_str = (date.today() + timedelta(days=1)).strftime("%d-%m-%Y")

    prayers = execute_fetch(URL, date_str, PARAMS)

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
        logging.getLogger().success("Prayer times fetched successfully.")
    except Exception as e:
        logging.error(f"Error fetching prayer times: {e}")
        timings = {}

    prayers_dict = {
        "Fajr": timings.get('Fajr', '00:00'),
        "Dhuhr": timings.get('Dhuhr', '00:00'),
        "Asr": timings.get('Asr', '00:00'),
        "Maghrib": timings.get('Maghrib', '00:00'),
        "Isha": timings.get('Isha', '00:00')
    }
    return prayers_dict

def schedule_refresh_time():
    isha_time = datetime.strptime(prayers["Isha"], "%H:%M")
    refresh_time_dt = isha_time + timedelta(minutes=5)
    refresh_time = refresh_time_dt.strftime("%H:%M")
    schedule.every().day.at(refresh_time).do(fetch_prayer_times).tag('refresh')

# =========================
# Prayer Actions
# =========================
def play_adhan():
    global counter
    now = datetime.now().strftime("%H:%M")
    logging.info(f"Playing Adhan at {now}")
    try:
        subprocess.Popen(["mpg123", "-o", "alsa", "/home/pi/Desktop/Adin/adhan.mp3"])
    except Exception as e:
        logging.error(f"Error playing audio: {e}")
    counter += 1

# =========================
# LCD Handling
# =========================
def update_lcd():
    global counter
    now = datetime.now().strftime("%H:%M")
    counter %= len(ORDER)
    lcd.write("Now: " + now, f"{ORDER[counter]} at {prayers[ORDER[counter]]}")

def reconcile_counter():
    global counter
    now = datetime.now().time()
    counter = 0
    for name in ORDER:
        prayer_time = datetime.strptime(prayers[name], "%H:%M").time()
        if now > prayer_time:
            counter += 1
        else:
            break

# =========================
# Shutdown / Cleanup
# =========================
def graceful_exit(signum, frame):
    lcd.clear()
    lcd.write("Adin...", "   Asleep...")
    lcd.cleanup()
    sys.exit(0)

# =========================
# Main Function
# =========================
def main():
    global lcd
    log_startup()
    lcd = init_lcd()

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

# =========================
# Entry Point
# =========================
if __name__ == "__main__":
    main()
