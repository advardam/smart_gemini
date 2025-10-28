import time
import statistics
from gpiozero import Device, Buzzer, Button, DistanceSensor

# I2C libraries
import board
import busio
import adafruit_tcs34725
import adafruit_circuitpython_mlx90640

# Luma OLED libraries
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

# --- ROBUSTNESS: Clean up any pins left open by a previous run ---
def cleanup_gpio_pins():
    try:
        if Device.pin_factory:
            Device.pin_factory.close()
            print("INFO: Cleaned up previously used GPIO pins.")
    except Exception:
        pass

cleanup_gpio_pins()

# --- HARDWARE PIN CONFIGURATION ---
ULTRASONIC_TRIG_PIN = 23
ULTRASONIC_ECHO_PIN = 24
BUZZER_PIN = 18
BUTTON_PIN = 17

# --- HARDWARE INITIALIZATION ---
try:
    i2c_bus = busio.I2C(board.SCL, board.SDA)
except Exception as e:
    print(f"FATAL: I2C bus could not be initialized. Error: {e}")
    i2c_bus = None

mlx_sensor = adafruit_circuitpython_mlx90640.MLX90640(i2c_bus) if i2c_bus else None
tcs_sensor = adafruit_tcs34725.TCS34725(i2c_bus) if i2c_bus else None

try:
    oled_serial = i2c(port=1, address=0x3C)
    oled_device = ssd1306(oled_serial)
except Exception as e:
    print(f"Warning: Could not initialize OLED Display. Error: {e}")
    oled_device = None

try:
    distance_sensor_obj = DistanceSensor(echo=ULTRASONIC_ECHO_PIN, trigger=ULTRASONIC_TRIG_PIN)
    buzzer_obj = Buzzer(BUZZER_PIN)
    button_obj = Button(BUTTON_PIN, pull_up=True)
except Exception as e:
    print(f"Warning: A GPIO device could not be initialized. Error: {e}")
    distance_sensor_obj = None
    buzzer_obj = None
    button_obj = None

# ... (The rest of the file is unchanged) ...
def get_color_name(rgb):
    r, g, b = rgb
    if r > 200 and g > 200 and b > 200: return "White"
    if r < 30 and g < 30 and b < 30: return "Black"
    if r > g and r > b: return "Red"
    if g > r and g > b: return "Green"
    if b > r and b > g: return "Blue"
    if r > 100 and g > 100 and b < 50: return "Yellow"
    return "Unknown"

def read_temperature():
    if mlx_sensor:
        try:
            # Note: MLX90640 provides an array of temperatures. We take an average.
            temps = [0] * 768
            mlx_sensor.getFrame(temps)
            ambient = round(mlx_sensor.temperature_ambient, 1)
            obj_temp = round(sum(temps) / 768, 1) # Average of all pixels
            return {"ambient": ambient, "object": obj_temp}
        except (OSError, IOError): return {"ambient": 0, "object": 0}
    return {"ambient": 25.0, "object": 25.0}

def read_color():
    if tcs_sensor:
        try: return {"color_name": get_color_name(tcs_sensor.color_rgb_bytes)}
        except Exception: return {"color_name": "Error"}
    return {"color_name": "N/A"}

def buzzer_beep(duration):
    if buzzer_obj:
        buzzer_obj.beep(on_time=duration, n=1)

def read_button():
    if button_obj:
        return not button_obj.is_pressed
    return True

def measure_distance(samples=10):
    if not distance_sensor_obj:
        print("Distance sensor is not available.")
        return 0, 0
    readings = [distance_sensor_obj.distance * 100 for _ in range(samples)]
    valid_readings = [r for r in readings if 2 < r < 400]
    if not valid_readings: return 0, 0
    avg = round(statistics.mean(valid_readings), 2)
    std_dev = round(statistics.stdev(valid_readings) if len(valid_readings) > 1 else 0, 2)
    return avg, std_dev

def analyze_absorption(sigma):
    if sigma > 1.2: return "High"
    elif sigma > 0.5: return "Medium"
    else: return "Low"

def update_physical_oled(distance, shape, material):
    if oled_device:
        try:
            with canvas(oled_device) as draw:
                draw.text((0, 0), f"Dist: {distance}", fill="white")
                draw.text((0, 12), f"Shape: {shape}", fill="white")
                draw.text((0, 24), f"Mat: {material}", fill="white")
        except Exception as e: print(f"Error writing to OLED: {e}")
    else:
        print(f"--- OLED Sim ---\nDist: {distance}\nShape: {shape}\nMat: {material}\n----------------")