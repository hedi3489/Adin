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
# Globals / Configuration
# =========================
prayers_list = []  # List of dicts: {"name": str, "time": datetime}
lcd = None

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
    lcd_obj = LCD1602()
    time.sleep(0.5)
    lcd_obj.clear()
    time.sleep(0.1)
    lcd_obj.clear()
    lcd_obj.write("Adin Awake", "Fetching times")
    time.sleep(3)
    return lcd_obj

def log_startup():
    logging.info("")
    logging.info("==================================================")
    logging.info("===== Fetcher.py started =====")
    logging.info("==================================================")

# =========================
# Prayer Time Fetching
# =========================
def fetch_prayer_times():
    global prayers_list
    schedule.clear('prayers')

    # Determine which date to fetch (today or tomorrow if Isha passed)
    now = datetime.now()
    if prayers_list:
        isha_datetime = prayers_list[-1]["time"]
        if now >= isha_datetime:
            fetch_date = date.today() + timedelta(days=1)
        else:
            fetch_date = date.today()
    else:
        fetch_date = date.today()
    date_str = fetch_date.strftime("%d-%m-%Y")

    prayers_list = execute_fetch(URL, date_str, PARAMS)

    # Schedule prayers
    for prayer in prayers_list:
        schedule.every().day.at(prayer["time"].strftime("%H:%M")).do(play_adhan).tag('prayers')
        logging.info(f"Scheduled {prayer['name']} at {prayer['time'].strftime('%H:%M')}")

    schedule_refresh_time()

def execute_fetch(url, date_str, params):
    try:
        response = requests.get(url + date_str, params=params, timeout=10)
        response.raise_for_status()
        timings = response.json()["data"]["timings"]
        logging.getLogger().success("Prayer times fetched successfully.")
    except Exception as e:
        logging.error(f"Error fetching prayer times: {e}")
        timings = {}

    prayers = []
    for name in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
        time_str = timings.get(name, "00:00")
        prayer_time = datetime.strptime(time_str, "%H:%M")
        prayers.append({"name": name, "time": prayer_time})

    return prayers

# =========================
# Schedule Refresh
# =========================
def schedule_refresh_time():
    if not prayers_list:
        return
    # Schedule refresh 5 minutes after Isha
    isha_time = prayers_list[-1]["time"]
    refresh_time_dt = isha_time + timedelta(minutes=5)
    refresh_time = refresh_time_dt.time()
    schedule.every().day.at(refresh_time.strftime("%H:%M")).do(fetch_prayer_times).tag('refresh')

# =========================
# Prayer Actions
# =========================
def play_adhan():
    now_str = datetime.now().strftime("%H:%M")
    logging.info(f"Playing Adhan at {now_str}")
    try:
        subprocess.Popen(["mpg123", "-o", "alsa", "/home/pi/Desktop/Adin/adhan.mp3"])
    except Exception as e:
        logging.error(f"Error playing audio: {e}")

# =========================
# LCD Handling
# =========================
def update_lcd():
    now = datetime.now()
    next_prayer = next(
        (p for p in prayers_list if p["time"].time() > now.time()),
        prayers_list[0] if prayers_list else None
    )
    if next_prayer:
        lcd.write("Now: " + now.strftime("%H:%M"),
                  f"{next_prayer['name']} at {next_prayer['time'].strftime('%H:%M')}")

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
