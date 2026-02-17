import requests
from datetime import datetime, timedelta, date
import schedule
import time
import subprocess
import logging
from lcd1602 import LCD1602
import signal
import sys
from pathlib import Path
import hashlib

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

# ---- Quran playback settings ----
QURAN_PRE_MAGHRIB_MINUTES = 15

# Quran.com API: chapter recitations endpoint:
# https://api.quran.com/api/v4/chapter_recitations/{reciter_id}/{chapter_number}
QURAN_API_BASE = "https://api.quran.com/api/v4"
QURAN_RECITER_ID = 2  # <-- CHANGE THIS to your preferred reciter id

# A reasonable rotating list (edit as you like)
QURAN_DAILY_SURAH_ROTATION = [
    36, 55, 67, 18, 56, 50, 32, 76, 78, 87, 92, 93, 94, 97, 112, 113, 114
]

QURAN_CACHE_DIR = Path("/home/pi/Desktop/Adin/quran_cache")
QURAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Runtime state for currently playing Quran
quran_proc = None
last_quran_started_for_date = None  # date object, prevents double-starting if schedule reloaded

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
# Quran helpers
# =========================
def stop_quran_if_playing():
    global quran_proc
    if quran_proc is not None and quran_proc.poll() is None:
        try:
            quran_proc.terminate()
        except Exception as e:
            logging.error(f"Error stopping Quran playback: {e}")
    quran_proc = None

def choose_daily_surah(for_date: date) -> int:
    """
    Deterministic daily selection so it's different each day and repeatable.
    Uses a hash of the date to pick from the rotation list.
    """
    key = for_date.isoformat().encode("utf-8")
    h = hashlib.sha256(key).digest()
    idx = int.from_bytes(h[:2], "big") % len(QURAN_DAILY_SURAH_ROTATION)
    return QURAN_DAILY_SURAH_ROTATION[idx]

def get_chapter_audio_url(reciter_id: int, chapter_number: int) -> str | None:
    """
    Calls Quran.com API v4:
      GET /chapter_recitations/{reciter_id}/{chapter_number}
    Expected response includes: audio_file.audio_url
    """
    endpoint = f"{QURAN_API_BASE}/chapter_recitations/{reciter_id}/{chapter_number}"
    try:
        r = requests.get(endpoint, timeout=10)
        r.raise_for_status()
        data = r.json()
        audio_file = data.get("audio_file") or {}
        return audio_file.get("audio_url")
    except Exception as e:
        logging.error(f"Error fetching Quran audio URL (reciter={reciter_id}, surah={chapter_number}): {e}")
        return None

def download_if_needed(url: str, out_path: Path) -> bool:
    try:
        if out_path.exists() and out_path.stat().st_size > 0:
            return True
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            tmp_path = out_path.with_suffix(out_path.suffix + ".part")
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        f.write(chunk)
            tmp_path.replace(out_path)
        return True
    except Exception as e:
        logging.error(f"Error downloading Quran audio: {e}")
        return False

def play_quran_before_maghrib(fetch_date: date):
    """
    Scheduled job: starts Quran playback 15 minutes before Maghrib.
    Uses cached MP3 to avoid network dependency at Iftar time.
    """
    global quran_proc, last_quran_started_for_date

    # Prevent double-starting if schedule refreshes
    if last_quran_started_for_date == fetch_date:
        return

    # If something is already playing, stop it before starting a new one
    stop_quran_if_playing()

    surah = choose_daily_surah(fetch_date)
    audio_url = get_chapter_audio_url(QURAN_RECITER_ID, surah)
    if not audio_url:
        logging.error("Quran playback skipped: no audio_url returned.")
        return

    cached_path = QURAN_CACHE_DIR / f"reciter_{QURAN_RECITER_ID}_surah_{surah}.mp3"
    if not download_if_needed(audio_url, cached_path):
        logging.error("Quran playback skipped: failed to cache audio.")
        return

    now_str = datetime.now().strftime("%H:%M")
    logging.info(f"Starting Quran (Surah {surah}) at {now_str} (before Maghrib)")

    try:
        quran_proc = subprocess.Popen(["mpg123", "-o", "alsa", str(cached_path)])
        last_quran_started_for_date = fetch_date
    except Exception as e:
        logging.error(f"Error playing Quran audio: {e}")
        quran_proc = None

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
    global prayers_list, last_quran_started_for_date

    schedule.clear('prayers')
    schedule.clear('quran')

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

    # Schedule Adhan for each prayer
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

    # Schedule Quran 15 minutes before Maghrib (if Maghrib is in the future)
    maghrib = next((p for p in prayers_list if p["name"] == "Maghrib"), None)
    if maghrib:
        start_dt = maghrib["time"] - timedelta(minutes=QURAN_PRE_MAGHRIB_MINUTES)
        if start_dt > datetime.now():
            schedule.every().day.at(
                start_dt.strftime("%H:%M")
            ).do(
                play_quran_before_maghrib,
                fetch_date=fetch_date
            ).tag('quran')

            logging.info(
                f"Scheduled Quran at {start_dt.strftime('%H:%M')} (Surah rotates daily)"
            )
        else:
            # If we're already past the start time, don't start late
            logging.info("Quran pre-Maghrib start time already passed; not scheduling today.")
            last_quran_started_for_date = None

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

    # Ensure Quran is not playing when Adhan starts (especially for Maghrib)
    stop_quran_if_playing()

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
    stop_quran_if_playing()
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
