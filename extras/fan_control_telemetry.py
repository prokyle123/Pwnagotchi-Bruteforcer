import os
import json
import time
import logging
import pigpio
from pwnagotchi.plugins import Plugin
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
from threading import Thread

class FanControl(Plugin):
    __author__ = "Kyle Williams"
    __version__ = "1.2.0"  # Adds dashboard telemetry output
    __license__ = "GPL3"
    __description__ = "A PWM fan controller with speed, RPM, display, and BruteForcer dashboard telemetry."

    def __init__(self):
        self.running = True
        self.pi = None
        self.FAN_GPIO = 18
        self.TACH_GPIO = 23
        self.fan_speed = 0
        self.last_tick = 0
        self.tick_count = 0
        self.rpm = 0
        self.bar_symbols_count = 18  # Number of symbols in the bar
        self.last_rpm_update = time.time()  # Track the last RPM update time

        # Shared dashboard telemetry. BruteForcer reads this tiny JSON file
        # instead of reaching directly into this plugin's process state.
        self.status_path = "/var/tmp/pwnagotchi/fan_status.json"
        self.status_write_interval = 2.0
        self.last_status_write = 0.0

        logging.info("FanControl: Initialized")

    def on_loaded(self):
        logging.info("FanControl: Plugin loaded")
        try:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                raise Exception("Failed to connect to pigpio daemon")
            self.pi.set_mode(self.TACH_GPIO, pigpio.INPUT)
            self.pi.set_pull_up_down(self.TACH_GPIO, pigpio.PUD_UP)
            self.pi.callback(self.TACH_GPIO, pigpio.FALLING_EDGE, self.tach_callback)
            self.running = True
            self._thread = Thread(target=self.run, daemon=True)
            self._thread.start()
            logging.info("FanControl: Background thread started")
        except Exception as e:
            logging.error(f"FanControl: Error during initialization: {e}")

    def on_unload(self, ui):
        logging.info("FanControl: Unloading plugin")
        self.running = False
        if self.pi:
            self.pi.set_PWM_dutycycle(self.FAN_GPIO, 255)  # Turn fan to 100% on exit for precautionary reasons
            self.fan_speed = 255
            self._write_dashboard_status(shutting_down=True)
            self.pi.stop()
        with ui._lock:
            ui.remove_element("fan_speed")
            ui.remove_element("fan_rpm")
            ui.remove_element("fan_bar")  # Remove the bar display
        logging.info("FanControl: Plugin unloaded")

    def on_ui_setup(self, ui):
        logging.info("FanControl: Setting up UI elements")
        ui.add_element("fan_speed", LabeledValue(color=BLACK, label="Fan", value=" 0%", position=(1, 95)))
        ui.add_element("fan_rpm", LabeledValue(color=BLACK, label="Fan RPM ", value=" 0", position=(160, 95)))
        ui.add_element("fan_bar", LabeledValue(color=BLACK, label="", value="[            ]", position=(38, 95)))
        logging.info("FanControl: UI elements set up")

    def on_ui_update(self, ui):
        logging.info("FanControl: Updating UI")
        fan_percentage = self.fan_speed / 2.55
        bar = self.barString(self.bar_symbols_count, int(fan_percentage))
        with ui._lock:
            ui.set("fan_speed", f"{fan_percentage:.0f}% ")
            ui.set("fan_rpm", f"{self.rpm:.0f} ")
            ui.set("fan_bar", f"{bar}")
        logging.info("FanControl: UI updated")

    def run(self):
        logging.info("FanControl: Running background process")
        while self.running:
            try:
                cpu_temp_f = self.get_cpu_temp()
                logging.info(f"FanControl: CPU Temp: {cpu_temp_f:.1f}F")
                new_fan_speed = self.adjust_fan_speed(cpu_temp_f)
                if new_fan_speed != self.fan_speed:
                    self.set_fan_speed(new_fan_speed)
                    logging.info(f"FanControl: New fan speed set: {new_fan_speed}")
                logging.info(f"FanControl: Fan Speed: {self.fan_speed / 2.55:.0f}%, Fan RPM: {self.rpm:.0f}")
                self._write_dashboard_status(cpu_temp_f=cpu_temp_f)
                time.sleep(5)  # 10-second delay to reduce CPU load and console spam
            except Exception as e:
                logging.error(f"FanControl: Error in run loop: {e}")

    def _write_dashboard_status(self, cpu_temp_f=None, shutting_down=False):
        """
        Publish a small, atomic fan status record for the BruteForcer dashboard.
        A write is limited to every couple seconds so this remains negligible
        compared with normal Pwnagotchi work.
        """
        now = time.time()
        if not shutting_down and now - self.last_status_write < self.status_write_interval:
            return

        try:
            if cpu_temp_f is None:
                cpu_temp_f = self.get_cpu_temp()
            fan_percent = max(0.0, min(100.0, float(self.fan_speed) / 2.55))
            payload = {
                "timestamp": now,
                "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "fan_percent": round(fan_percent, 1),
                "fan_pwm": int(self.fan_speed),
                "fan_rpm": round(float(self.rpm or 0.0), 1),
                "cpu_temp_f": round(float(cpu_temp_f or 0.0), 1),
                "pwm_gpio": int(self.FAN_GPIO),
                "tach_gpio": int(self.TACH_GPIO),
                "shutting_down": bool(shutting_down),
            }
            parent = os.path.dirname(self.status_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            temp_path = self.status_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as status_file:
                json.dump(payload, status_file, separators=(",", ":"))
                status_file.write("\n")
            os.replace(temp_path, self.status_path)
            self.last_status_write = now
        except Exception as e:
            logging.debug(f"FanControl: Could not write dashboard telemetry: {e}")

    def get_cpu_temp(self):
        try:
            res = os.popen('vcgencmd measure_temp').readline()
            temp_c = float(res.replace("temp=", "").replace("'C\n", ""))
            temp_f = temp_c * 9.0 / 5.0 + 32.0  # Convert to Fahrenheit
            return temp_f
        except Exception as e:
            logging.error(f"FanControl: Error getting CPU temperature: {e}")
            return 0.0

    def set_fan_speed(self, speed):
        try:
            self.fan_speed = speed
            if self.pi:
                self.pi.set_PWM_dutycycle(self.FAN_GPIO, speed)
                logging.info(f"FanControl: PWM duty cycle set to {speed}")
        except Exception as e:
            logging.error(f"FanControl: Error setting fan speed: {e}")

    def tach_callback(self, gpio, level, tick):
        try:
            if level == 0:
                self.tick_count += 1
                if self.tick_count == 2:  # Two pulses per revolution
                    dt = pigpio.tickDiff(self.last_tick, tick)
                    new_rpm = 60000000 / dt
                    current_time = time.time()

                    # Update RPM only if 5 seconds has passed since the last update
                    if current_time - self.last_rpm_update >= 2:
                        self.rpm = new_rpm
                        self.last_rpm_update = current_time
                        logging.info(f"FanControl: RPM calculated: {self.rpm:.2f}")

                    self.tick_count = 0
                    self.last_tick = tick
        except Exception as e:
            logging.error(f"FanControl: Error in tach callback: {e}")

    def adjust_fan_speed(self, cpu_temp_f):
        if cpu_temp_f < 70:
            return 0
        elif cpu_temp_f >= 120:
            return 255  # Full speed at 120Â°F and above

        # Calculate fan speed in 50 increments between 70Â°F and 120Â°F
        max_temp = 120
        min_temp = 70
        range_temp = max_temp - min_temp
        steps = 50
        step_size = range_temp / steps

        for i in range(steps):
            if cpu_temp_f < min_temp + (i + 1) * step_size:
                return int(255 * (i + 1) / steps)

        return 255  # Default to full speed if temperature is above the range

    def barString(self, symbols_count, percent):
        length = symbols_count - 2  # Exclude the '|' characters at both ends
        filled_length = round(length * percent / 100)  # Use round() for better precision
        bar_char = '='  # Use '=' for filled portions
        blank_char = ' '  # Use space for unfilled portions
        bar = '|' + bar_char * filled_length + blank_char * (length - filled_length) + '|'
        return bar
