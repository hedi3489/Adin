# Adin: RPi Adhan Player
Adin is a RPi script that fetches daily prayer times from the `Aladhan API` and plays the Adhan automatically at each one. 
It also automatically refreshes prayer times at midnight.

### Hardware Requirements
- Raspberry Pi
- Speaker connected to the Pi

### Software Requirements
- mpg123 for audio playback

# Usage
1. Configure your city, country, and method in the script:
  params = {
      "city": "Montreal",
      "country": "Canada",
      "method": 2
  }
  for more details on Aladhan API, see https://aladhan.com/prayer-times-api

2. Place your Fetcher.py and your Adhan audio file at the specified path:
  /home/pi/Desktop/Adin/adhan.mp3

3. Run script
   python Fetcher.py
