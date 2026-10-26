# Autonomous Serving Cart — latest firmware package

This package provides firmware for the ESP8266 web server and Arduino UNO 4-motor controller, designed to work with the existing FastAPI website's `/status` and `/command?cmd=...` API expectations.

## Included
- `firmware/esp8266_webserver/esp8266_webserver.ino`: local Wi-Fi control page, `/status`, and `/command` endpoints.
- `firmware/arduino_4motor/arduino_4motor.ino`: four motor control and Arduino-side 1.2 second command watchdog.

## Important limitation: person following
The two firmware sketches do **not** perform AI person following by themselves. Person following needs the laptop backend to use the camera + YOLO `person` detections to select FORWARD/LEFT/RIGHT/STOP, and send those commands to the ESP only when following is explicitly enabled and hardware is verified. This package intentionally does not claim person-following is implemented or tested.

## Wi-Fi
SSID/password are set in the ESP sketch to the values provided in the chat. Keep this sketch private and change the password if it was shared outside your trusted environment. ESP8266 supports 2.4 GHz Wi-Fi; ensure `BROCODE_EXT` offers 2.4 GHz.

## Wiring
- ESP D6 (TX) -> Arduino D2 (RX)
- Arduino D3 (TX) -> ESP D5 (RX) **through a 5V-to-3.3V level shifter or resistor divider**
- ESP GND <-> Arduino GND
- Four motors -> M1, M2, M3, M4 of a classic L293D V1-compatible HW-130 shield
- Power the motors from a suitable motor supply, not the ESP/USB 3.3V pin.

Do not connect Arduino 5V TX directly to ESP8266 GPIO. Check the exact shield revision: the `AFMotor` code is only for the classic Adafruit V1-compatible L293D shield. Other HW-130 revisions may require different firmware/library.

## Upload and test
1. Test with cart wheels lifted and secured. Keep a hand on power switch.
2. Install `AFMotor` library compatible with the classic L293D V1 shield.
3. Upload Arduino sketch first, then ESP sketch. Select the correct board and COM port.
4. ESP Serial Monitor baud: 115200. Use the IP it prints.
5. Browse to `http://<ESP_IP>/status`; expect JSON with `device: ESP8266` and `wifi: connected`.
6. Browse to `http://<ESP_IP>/`; test STOP first. Then test each direction briefly with wheels lifted.
7. Arduino watchdog stops motors when commands stop arriving. Still test a physical emergency power cut before any driving.

## Current validation status
- Code was generated for the stated hardware assumption, but not compiled against your exact board/shield in this environment.
- No physical motor, obstacle sensor, or person-following test is claimed.


## Current AUTONOVA firmware wiring
- ESP8266 TX0/GPIO1 -> Arduino UNO D2 (SoftwareSerial RX), both command serials at 9600 baud.
- Arduino D3 is unused for ESP serial in this setup.
- HC-SR04 TRIG -> A0, ECHO -> A1, VCC -> 5V, GND -> GND.
- Share GND between ESP8266, Arduino, motor shield, and sensor. Power the ESP from a suitable regulated 3.3 V source; do not feed 5 V into ESP pins.
- Disconnect ESP TX0 from UNO D2 while uploading firmware to the ESP, then reconnect. ESP TX0 is used for commands, so Serial Monitor text from ESP is not a debug channel; find its IP from the router or /status after connecting.
- Arduino sketch expects a classic AFMotor/L293D V1-compatible shield.
