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
# Configuration / State
# =========================
prayers_list = []  # [{"name": str, "time": datetime}]
lcd = None

URL = "https://api.aladhan.com/v1/timings/"
PARAMS = {
    "latitude": "45.49829337659685",
    "longitude": "-73.5006225145062"
}

# =========================
# Logging setup
# =========================
logging.basicConfig(
    filename="/home/pi/Desktop/Adin/adin.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(message)s"
)

# Custom SUCCESS level
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")

def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)

logging.Logger.success = success

# =========================
# Startup helpers
# =========================
def log_startup():
    logging.info("")
    logging.info("==================================================")
    logging.info("===== Fetcher.py started =====")
    logging.info("==================================================")

def init_lcd():
    lcd_obj = LCD1602()
    time.sleep(0.5)
    lcd_obj.clear()
    time.sleep(0.1)
    lcd_obj.clear()
    lcd_obj.write("Adin...", "    Waiting...")
    return lcd_obj

# =========================
# Fetching logic
# =========================
def execute_fetch(url, date_str, params):
    try:
        response = requests.get(url + date_str, params=params, timeout=10)
        response.raise_for_status()
        timings = response.json()["data"]["timings"]
    except Exception as e:
        logging.error(f"Error fetching prayer times: {e}")
        timings = {}

    fetch_date = datetime.strptime(date_str, "%d-%m-%Y").date()
    prayers = []

    for name in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
        time_str = timings.get(name, "00:00")
        prayer_time = datetime.combine(
            fetch_date,
            datetime.strptime(time_str, "%H:%M").time()
        )
        prayers.append({"name": name, "time": prayer_time})

    return prayers

def prune_past_prayers():
    global prayers_list
    now = datetime.now()
    before = len(prayers_list)

    prayers_list = [p for p in prayers_list if p["time"] > now]

    pruned = before - len(prayers_list)
    if pruned > 0:
        logging.info(f"Pruned {pruned} past prayer(s)")

def fetch_prayer_times():
    global prayers_list

    schedule.clear('prayers')

    now = datetime.now()
    fetch_date = date.today()

    # Temporary fetch to decide today vs tomorrow
    temp_list = execute_fetch(URL, fetch_date.strftime("%d-%m-%Y"), PARAMS)

    if temp_list and now >= temp_list[-1]["time"]:
        fetch_date += timedelta(days=1)
        day_str = "Tomorrow's"
    else:
        day_str = "Today's"

    logging.info("Initial fetch...")
    prayers_list = execute_fetch(URL, fetch_date.strftime("%d-%m-%Y"), PARAMS)

    prune_past_prayers()

    logging.getLogger().success(f"{day_str} prayer times fetched successfully.")

    for prayer in prayers_list:
        schedule.every().day.at(
            prayer["time"].strftime("%H:%M")
        ).do(
            play_adhan,
            prayer_name=prayer["name"]
        ).tag('prayers')

        logging.info(
            f"Scheduled {prayer['name']} at {prayer['time'].strftime('%H:%M')}"
        )

    schedule_refresh_time()

# =========================
# Refresh scheduling
# =========================
def schedule_refresh_time():
    schedule.clear('refresh')

    if not prayers_list:
        return

    refresh_time = prayers_list[-1]["time"] + timedelta(minutes=3)

    schedule.every().day.at(
        refresh_time.strftime("%H:%M")
    ).do(fetch_prayer_times).tag('refresh')

# =========================
# Prayer action
# =========================
def play_adhan(prayer_name):
    global prayers_list

    now_str = datetime.now().strftime("%H:%M")
    logging.info(f"Playing Adhan for {prayer_name} at {now_str}")

    try:
        subprocess.Popen(
            ["mpg123", "-o", "alsa", "/home/pi/Desktop/Adin/adhan.mp3"]
        )
    except Exception as e:
        logging.error(f"Error playing audio: {e}")

    prayers_list = [
        p for p in prayers_list if p["name"] != prayer_name
    ]

# =========================
# LCD handling
# =========================
def update_lcd():
    now_str = datetime.now().strftime("%H:%M")

    if not prayers_list:
        lcd.write("Fetching prayers", "   in a bit...")
        return

    next_prayer = prayers_list[0]
    lcd.write(
        f"Now: {now_str}",
        f"{next_prayer['name']} at {next_prayer['time'].strftime('%H:%M')}"
    )

# =========================
# Cleanup
# =========================
def graceful_exit(signum, frame):
    if lcd:
        lcd.clear()
        lcd.write("Adin...", "   Asleep...")
        lcd.cleanup()
    sys.exit(0)

# =========================
# Main loop
# =========================
def main():
    global lcd

    log_startup()
    lcd = init_lcd()

    fetch_prayer_times()
    schedule.every(5).seconds.do(update_lcd)

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, graceful_exit)

    while True:
        schedule.run_pending()
        time.sleep(1)

# =========================
# Entry point
# =========================
if __name__ == "__main__":
    main()
