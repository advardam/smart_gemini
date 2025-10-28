"""
hw_layer.py — Hardware Abstraction Layer for Raspberry Pi 5
Supports:
- HC-SR04 Ultrasonic Sensor
- MLX90614 IR Temperature Sensor
- TCS34725 Color Sensor
- SSD1306 OLED Display (128x64)
- Button (GPIO17)
- Buzzer (GPIO18)

Features:
- Auto GPIO recovery
- Graceful sensor unavailability handling
- Safe cleanup with atexit
- Raspberry Pi 5 compatible (lgpio-based)
"""

import time
import sys
import atexit
import traceback

import lgpio
from smbus2 import SMBus
from board import SCL, SDA
import busio

# --- Optional Modules ---
try:
    from adafruit_tcs34725 import TCS34725
except ImportError:
    TCS34725 = None

try:
    from mlx90614 import MLX90614
except ImportError:
    MLX90614 = None

try:
    import Adafruit_SSD1306
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Adafruit_SSD1306 = None

# ---------------------------- #
#       GPIO Pin Mapping       #
# ---------------------------- #
TRIG = 23
ECHO = 24
BUZZER = 18
BUTTON = 17

gpio_handle = None

# ---------------------------- #
#   GPIO Initialization        #
# ---------------------------- #
def init_gpio():
    """Initialize GPIO safely and handle 'GPIO busy' errors."""
    global gpio_handle
    try:
        if gpio_handle is not None:
            lgpio.gpiochip_close(gpio_handle)

        gpio_handle = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(gpio_handle, TRIG)
        lgpio.gpio_claim_input(gpio_handle, ECHO)
        lgpio.gpio_claim_output(gpio_handle, BUZZER)
        lgpio.gpio_claim_input(gpio_handle, BUTTON)

        print("[INFO] GPIO initialized successfully.")
    except Exception as e:
        print(f"[WARN] GPIO init failed: {e}")
        cleanup_gpio()
        time.sleep(0.5)
        try:
            gpio_handle = lgpio.gpiochip_open(0)
            print("[INFO] GPIO recovered after error.")
        except Exception as e2:
            print(f"[ERROR] Unable to recover GPIO: {e2}")
            gpio_handle = None


def cleanup_gpio():
    """Safely release GPIO handle."""
    global gpio_handle
    try:
        if gpio_handle is not None:
            lgpio.gpiochip_close(gpio_handle)
            gpio_handle = None
            print("[INFO] GPIO cleaned up.")
    except Exception as e:
        print(f"[WARN] GPIO cleanup error: {e}")


atexit.register(cleanup_gpio)

# ---------------------------- #
#    Ultrasonic Measurement    #
# ---------------------------- #
def measure_distance():
    """Measure distance using HC-SR04."""
    global gpio_handle

    if gpio_handle is None:
        print("[ERROR] Distance sensor not available.")
        return None

    try:
        # Send 10µs trigger pulse
        lgpio.gpio_write(gpio_handle, TRIG, 1)
        time.sleep(0.00001)
        lgpio.gpio_write(gpio_handle, TRIG, 0)

        start_time = time.time()
        while lgpio.gpio_read(gpio_handle, ECHO) == 0:
            start_time = time.time()

        stop_time = time.time()
        while lgpio.gpio_read(gpio_handle, ECHO) == 1:
            stop_time = time.time()

        time_elapsed = stop_time - start_time
        distance = (time_elapsed * 34300) / 2

        if distance <= 2 or distance >= 400:
            return None
        return round(distance, 2)
    except Exception as e:
        print(f"[ERROR] Ultrasonic read failed: {e}")
        return None


# ---------------------------- #
#   Button and Buzzer Control  #
# ---------------------------- #
def wait_for_button_press():
    """Wait for button press (GPIO17)."""
    global gpio_handle
    if gpio_handle is None:
        print("[WARN] Button not available.")
        return False

    print("[INFO] Waiting for button press...")
    try:
        while lgpio.gpio_read(gpio_handle, BUTTON) == 1:
            time.sleep(0.05)
        print("[INFO] Button pressed.")
        return True
    except Exception as e:
        print(f"[WARN] Button read error: {e}")
        return False


def beep(duration=0.1):
    """Sound buzzer briefly."""
    global gpio_handle
    if gpio_handle is None:
        print("[WARN] Buzzer not available.")
        return

    try:
        lgpio.gpio_write(gpio_handle, BUZZER, 1)
        time.sleep(duration)
        lgpio.gpio_write(gpio_handle, BUZZER, 0)
    except Exception as e:
        print(f"[WARN] Buzzer failed: {e}")


# ---------------------------- #
#       MLX90614 Sensor        #
# ---------------------------- #
def read_temperature():
    """Read object and ambient temperature from MLX90614."""
    try:
        with SMBus(1) as bus:
            sensor = MLX90614(bus, address=0x5A)
            ambient = round(sensor.get_ambient(), 2)
            object_temp = round(sensor.get_object_1(), 2)
            return ambient, object_temp
    except Exception as e:
        print(f"[WARN] MLX90614 read failed: {e}")
        return None, None


# ---------------------------- #
#       TCS34725 Sensor        #
# ---------------------------- #
def read_color():
    """Read RGB and Lux data from TCS34725."""
    try:
        i2c = busio.I2C(SCL, SDA)
        sensor = TCS34725(i2c)
        r, g, b, c = sensor.color_raw
        color_temp = sensor.color_temperature
        lux = sensor.lux
        return {
            "r": r,
            "g": g,
            "b": b,
            "clear": c,
            "color_temp": color_temp,
            "lux": lux,
        }
    except Exception as e:
        print(f"[WARN] TCS34725 read failed: {e}")
        return None


# ---------------------------- #
#        OLED Display          #
# ---------------------------- #
def init_oled():
    """Initialize OLED display."""
    if Adafruit_SSD1306 is None:
        print("[WARN] OLED libraries not available.")
        return None

    try:
        disp = Adafruit_SSD1306.SSD1306_128_64(rst=None)
        disp.begin()
        disp.clear()
        disp.display()
        return disp
    except Exception as e:
        print(f"[WARN] OLED init failed: {e}")
        return None


def oled_display_message(disp, lines):
    """Display up to 4 lines of text on OLED."""
    if disp is None:
        return

    try:
        disp.clear()
        disp.display()
        width = disp.width
        height = disp.height
        image = Image.new("1", (width, height))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        for i, text in enumerate(lines[:4]):
            draw.text((0, i * 15), text, font=font, fill=255)

        disp.image(image)
        disp.display()
    except Exception as e:
        print(f"[WARN] OLED draw failed: {e}")


# ---------------------------- #
#       Module Auto Init       #
# ---------------------------- #
init_gpio()

# ---------------------------- #
#           Testing             #
# ---------------------------- #
if __name__ == "__main__":
    try:
        print("[TEST] Waiting for button to measure distance...")
        wait_for_button_press()
        dist = measure_distance()
        print(f"Distance: {dist} cm")

        amb, obj = read_temperature()
        print(f"Ambient: {amb}°C, Object: {obj}°C")

        color_data = read_color()
        print(f"Color Data: {color_data}")

        oled = init_oled()
        oled_display_message(oled, [
            f"Dist: {dist} cm",
            f"Obj: {obj} C",
            f"Lux: {color_data['lux'] if color_data else 'N/A'}"
        ])

        beep(0.2)

    except KeyboardInterrupt:
        cleanup_gpio()
