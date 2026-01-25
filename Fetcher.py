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
    lcd_obj.write("Adin...", "    Waiting...")  # Initial waiting message
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

    now = datetime.now()
    fetch_date = date.today()  # default

    # Temporary fetch to check if Isha passed
    temp_list = execute_fetch(URL, fetch_date.strftime("%d-%m-%Y"), PARAMS)
    if temp_list and now >= temp_list[-1]["time"]:
        fetch_date = date.today() + timedelta(days=1)
        day_str = "Tomorrow's"
    else:
        day_str = "Today's"

    logging.info("Initial fetch...")
    prayers_list = execute_fetch(URL, fetch_date.strftime("%d-%m-%Y"), PARAMS)
    logging.getLogger().success(f"{day_str} prayer times fetched successfully.")

    # Schedule prayers
    for prayer in prayers_list:
        schedule.every().day.at(prayer["time"].strftime("%H:%M")).do(play_adhan).tag('prayers')
        logging.info(f"Scheduled {prayer['name']} at {prayer['time'].strftime('%H:%M')}")

    # Schedule refresh safely
    schedule_refresh_time()

def execute_fetch(url, date_str, params):
    try:
        response = requests.get(url + date_str, params=params, timeout=10)
        response.raise_for_status()
        timings = response.json()["data"]["timings"]
        # Removed duplicate SUCCESS log here
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
    schedule.clear('refresh')  # clear old refresh jobs

    if not prayers_list:
        return

    isha_time = prayers_list[-1]["time"]
    now = datetime.now()

    if now < isha_time:
        # Schedule refresh at Isha + 3 minutes
        refresh_time_dt = isha_time + timedelta(minutes=3)
        schedule.every().day.at(refresh_time_dt.strftime("%H:%M")).do(fetch_prayer_times).tag('refresh')

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
    future_prayers = [p for p in prayers_list if p["time"] > now]
    next_prayer = future_prayers[0] if future_prayers else prayers_list[0] if prayers_list else None
    if next_prayer:
        lcd.write("Now: " + now.strftime("%H:%M"),
                  f"{next_prayer['name']} at {next_prayer['time'].strftime('%H:%M')}")

# =========================
# Cleanup
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