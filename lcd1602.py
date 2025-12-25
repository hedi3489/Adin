from RPLCD.gpio import CharLCD
import RPi.GPIO as GPIO

class LCD1602:
    def __init__(self):
        self.lcd = CharLCD(
            numbering_mode=GPIO.BCM,
            cols=16, 
            rows=2, 
            pin_rs=4, 
            pin_e=17, 
            pins_data=[13, 6, 5, 22],
            charmap="A02"
    )

    def clear(self):
        self.lcd.clear()

    def write(self, line1="", line2=""):
        self.lcd.clear()
        self.lcd.write_string(line1[:16].ljust(16))
        self.lcd.cursor_pos = (1,0)
        self.lcd.write_string(line2[:16].ljust(16))

    def cleanup():
        GPIO.cleanup()
