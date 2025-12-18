import requests
from datetime import datetime
import schedule
import time
import subprocess
import logging

# Setup logging 
logging.basicConfig(
    filename="/home/pi/Desktop/Adin/adin.log",   
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("=== Fetcher.py started ===")

# API endpoint and parameters
url = "https://api.aladhan.com/v1/timingsByCity"
params = {
    "city": "Montreal",
    "country": "Canada",
    "method": 2
}

# Send GET request
try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    timings = data["data"]["timings"]
    logging.info("Prayer times fetched successfully.")
except Exception as e:
    logging.error(f"Error fetching prayer times: {e}")
    timings = {}

# Store times in array
prayers = { 
   "Fajr": timings.get('Fajr', '00:00'),
   "Dhuhr": timings.get('Dhuhr', '00:00'),
   "Asr": timings.get('Asr', '00:00'),
   "Maghreb": timings.get('Maghrib', '00:00'),
   "Isha": timings.get('Isha', '00:00')
}

for prayer, t in prayers.items():
    logging.info(f"Scheduled {prayer} at {t}")

# Function to play audio
def play_adhan():
    now = datetime.now().strftime("%H:%M")
    logging.info(f"Playing Adhan at {now}")
    try:
        subprocess.Popen(["mpg123", "/home/pi/Desktop/Adin/adhan.mp3"])
    except Exception as e:
        logging.error(f"Error playing audio: {e}")

# Schedule each prayer
for prayer, t in prayers.items():
    schedule.every().day.at(t).do(play_adhan)

# Keep running
while True:
    schedule.run_pending()
    time.sleep(1)
