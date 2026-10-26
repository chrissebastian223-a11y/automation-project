# AUTONOVA AI — Windows 11 local dashboard

This is a local-first project bundle for the autonomous serving-cart project. It includes a FastAPI dashboard, camera preview, optional YOLO person/object detection, optional OCR, ESP8266 HTTP control, teacher/demo mode, and manual remote controls.

## Important validation status
- Python files are syntax-checked when this package is generated.
- Hardware, camera, GPU/CUDA, and motor behavior have **not** been physically tested on your computer/cart.
- Do not call this "fully tested" until you complete the hardware test checklist below.
- Camera-only obstacle avoidance is an estimate, not a safety-rated distance sensor. For real movement, use a tested distance sensor and retain a physical emergency power switch.
- Firmware from your supplied ZIP assumes a classic L293D V1-compatible AFMotor shield. Verify the actual shield before powering motors.

## Quick start (Windows 11)
1. Install Python 3.11 (64-bit) from python.org and check **Add Python to PATH**.
2. Extract this folder to a simple path, e.g. `C:\AUTONOVA_AI`.
3. Double-click `START_WINDOWS.bat`.
4. Open `http://127.0.0.1:8000` if it does not open automatically.
5. In **Settings**, enter the ESP8266 IP address shown in the ESP Serial Monitor. Click **Test ESP**.
6. Choose camera index `0` and click **Start Camera**.
7. AI detection is optional. Use **Install AI dependencies** in the terminal (see below) and select a compatible model. The default model `yolov8n.pt` may download on first run, so the first setup needs internet. To run completely offline, place a compatible `.pt` model in `models/` and set its path in Settings.

## GPU notes (NVIDIA RTX 3050)
The app reports the actual PyTorch CUDA availability and inference device. Merely having an RTX 3050 does not guarantee CUDA is installed/enabled.
- Install a current NVIDIA driver.
- In the activated project environment, install a CUDA-enabled PyTorch build following the official PyTorch selector: https://pytorch.org/get-started/locally/
- Install optional AI dependencies: `pip install ultralytics`
- Restart the app. The dashboard must report `GPU (CUDA)` before claiming GPU inference is active.
- If CUDA is unavailable, AI falls back to CPU and reports that status. No fake GPU status is shown.
- Actual FPS depends on camera, resolution, model, driver, and thermal/power limits.

## Camera options
- Laptop USB/webcam: camera index 0 or 1.
- Phone camera: use an IP camera app and enter its HTTP/stream URL if the app exposes a compatible MJPEG/HTTP stream. College Wi-Fi may isolate devices; laptop hotspot or USB camera may be more reliable. Do not expose the ESP or dashboard to the public internet.
- Recorded video: enter a local video file path in Settings.

## Obstacle avoidance and person following (updated)

- **Obstacle avoidance runs on the Arduino**, not just on the laptop: HC-SR04 TRIG is A0 and ECHO is A1. The firmware blocks forward motion when the sensor reports 18 cm or less, pivots right briefly, then stops before trying again. If the sensor returns no echo, forward movement is stopped. This is a basic single-sensor demo, not a safety-rated navigation system; it cannot see rear/side obstacles.
- **Person following runs on the laptop** using YOLO's largest person bounding box. It turns to center the person, moves forward only when the person appears small in the image, and stops if the person is close/uncertain or an object is detected in the lower center of the frame. Image size is only a rough distance proxy.
- Before enabling following: start camera, load the AI model, test ESP connection, lift wheels and test direction/STOP, then test in a clear area at low speed. Keep a physical motor power cutoff available.
- The Arduino firmware includes a 1.2-second command watchdog. The laptop refreshes moving follow commands; network/AI delays should cause the robot to stop rather than continue indefinitely.

## Robot connection
The dashboard sends these commands to ESP: `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`.
Default transport is HTTP to `http://<ESP-IP>/command?cmd=...`, matching the supplied firmware API. ESP HTTP success means the ESP accepted/sent the command over serial; it is not proof the Arduino physically executed it unless the firmware implements and returns an Arduino acknowledgement.
- ESP and laptop need reachable local network addresses for HTTP mode.
- If college Wi-Fi blocks device-to-device traffic, use a laptop hotspot or a supported USB serial setup. USB serial fallback is not included in this initial UI; do not select it as if it exists.
- Never paste Wi-Fi passwords into public code or share them in screenshots.

## Safety
- Test with wheels lifted and cart securely supported.
- Keep the physical power cut switch accessible.
- Use STOP before connecting/disconnecting.
- The dashboard has hold-to-move and STOP-on-release, but browser/network failures can still delay STOP. The Arduino-side watchdog in the supplied firmware is an additional safeguard, not a substitute for physical power cutoff.
- Camera AI does not guarantee obstacle distance or safe passage. If uncertain, stop.
- Don't run person-following until motor directions and stop behavior are verified.

## Included features
- Local dashboard and event log
- Manual remote control
- ESP connectivity test/status
- Camera preview from webcam, compatible URL, or local video file
- Optional YOLO detection for supported COCO classes
- Basic person-following command logic (disabled by default; requires camera + explicit enable)
- Camera obstacle demonstration mode (visual detections; conservative stop behavior)
- Optional OCR endpoint (requires optional OCR dependency)
- Teacher/demo mode and test checklist

## Hardware validation checklist
Mark each item PASS only after physically testing:
- [ ] ESP `/status` returns JSON and shows connected Wi-Fi
- [ ] ESP `/command?cmd=STOP` works
- [ ] Each direction verified briefly with wheels lifted
- [ ] Motor directions match labels
- [ ] Stop on button release works
- [ ] Stop when browser/client connection is lost tested
- [ ] Arduino command watchdog tested
- [ ] Camera disconnect/reconnect tested
- [ ] GPU inference verified in dashboard and Task Manager
- [ ] Person-following behavior tested in a clear, low-speed area
- [ ] HC-SR04 returns realistic distances in Arduino Serial Monitor
- [ ] Obstacle response tested with a safe dummy obstacle (wheels raised first)
- [ ] Physical emergency power cut tested


## Separate autonomous modes
- **Person Following Mode**: enable the camera, load the YOLO model, then turn on Person Following. It uses visual position/size as a rough cue and stops when detection is lost.
- **Obstacle Avoidance Mode**: turn on this mode without needing the camera or AI. The laptop repeatedly requests forward motion; the Arduino firmware must be uploaded and the HC-SR04 must be wired to TRIG=A0 and ECHO=A1. The Arduino stops/pivots when the distance is at or below 18 cm, then attempts forward movement again after a cooldown.
- The two modes are mutually exclusive. Manual movement commands turn off both modes.
- This is not safety-rated. Test with wheels lifted and a physical power cutoff ready; one front sensor cannot detect side/rear obstacles.
