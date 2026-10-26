from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import cv2
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="AUTONOVA AI", version="0.1.1")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

lock = threading.RLock()
events = deque(maxlen=100)
settings: dict[str, Any] = {
    "esp_url": os.getenv("ESP_URL", "http://192.168.1.14").rstrip("/"),
    "camera_source": "0",
    "model_path": "yolov8n.pt",
    "confidence": 0.45,
    "ocr_enabled": False,
    "obstacle_demo": True,
}
last_command = "STOP"
follow_enabled = False
obstacle_enabled = False
obstacle_thread: threading.Thread | None = None
obstacle_stop_event = threading.Event()
camera: cv2.VideoCapture | None = None
camera_thread: threading.Thread | None = None
camera_running = False
latest_frame = None
camera_status = "Stopped"
camera_error = ""
camera_fps = 0.0
camera_source_label = "not selected"
ai_model = None
ai_device = "CPU"
ai_gpu_available = False
ai_error = ""
ai_inference_ms = None
ai_fps = None
latest_detections: dict[str, Any] = {"person": False, "person_box": None, "frame_size": None, "obstacles": [], "obstacle_warning": False}
last_ai_frame = None
last_ai_time = 0.0
follow_thread: threading.Thread | None = None
follow_stop_event = threading.Event()
follow_last_command = "STOP"
follow_last_command_at = 0.0
esp_connected = False
esp_last_check = ""
FOLLOW_LOOP_SECONDS = 0.35
FOLLOW_PERSON_LOST_SECONDS = 0.9


def log_event(kind: str, message: str, level: str = "INFO") -> None:
    events.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "kind": kind,
        "message": message,
        "level": level,
    })


def camera_source_value(value: str):
    value = str(value or "0").strip()
    if value.isdigit():
        return int(value)
    return value


def get_esp_url() -> str:
    return str(settings["esp_url"]).rstrip("/")


def send_esp_command(command: str) -> dict[str, Any]:
    global last_command
    command = command.upper().strip()
    if command not in {"FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"}:
        raise HTTPException(status_code=400, detail="INVALID_COMMAND: unsupported command")
    url = f"{get_esp_url()}/command"
    try:
        response = requests.get(url, params={"cmd": command}, timeout=2.5)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            payload = {"response": response.text}
        with lock:
            last_command = command
        log_event("COMMAND", f"{command} sent to ESP", "INFO")
        return {"ok": True, "command": command, "esp_response": payload}
    except requests.RequestException as exc:
        log_event("ESP", f"Command {command} failed: {exc}", "ERROR")
        raise HTTPException(status_code=502, detail=f"ESP request failed: {exc}") from exc


def camera_worker() -> None:
    global camera, camera_running, latest_frame, camera_status, camera_error, camera_fps, camera_source_label
    frame_count = 0
    fps_started = time.time()
    while camera_running:
        with lock:
            cap = camera
        if cap is None or not cap.isOpened():
            time.sleep(0.15)
            continue
        ok, frame = cap.read()
        if not ok:
            camera_error = "Camera frame unavailable; check the source or reconnect."
            camera_status = "Error"
            time.sleep(0.25)
            continue
        with lock:
            latest_frame = frame
            camera_status = "Connected"
            camera_error = ""
        frame_count += 1
        now = time.time()
        if now - fps_started >= 1.0:
            camera_fps = round(frame_count / (now - fps_started), 1)
            frame_count = 0
            fps_started = now
        time.sleep(0.001)
    with lock:
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass
        camera = None
        camera_status = "Stopped"


def start_camera() -> dict[str, Any]:
    global camera, camera_thread, camera_running, camera_status, camera_error, camera_source_label, latest_frame
    with lock:
        if camera_running:
            return {"ok": True, "status": camera_status, "message": "Camera already running"}
        source = camera_source_value(str(settings.get("camera_source", "0")))
        camera_source_label = str(source)
        try:
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                cap.release()
                camera_status = "Error"
                camera_error = f"Could not open camera source: {source}"
                log_event("CAMERA", camera_error, "ERROR")
                raise HTTPException(status_code=400, detail=camera_error)
            camera = cap
            latest_frame = None
            camera_running = True
            camera_status = "Connecting"
            camera_error = ""
            camera_thread = threading.Thread(target=camera_worker, daemon=True)
            camera_thread.start()
        except HTTPException:
            raise
        except Exception as exc:
            camera_status = "Error"
            camera_error = str(exc)
            log_event("CAMERA", camera_error, "ERROR")
            raise HTTPException(status_code=500, detail=camera_error) from exc
    log_event("CAMERA", f"Camera started: {source}")
    return {"ok": True, "status": camera_status, "source": str(source)}


def stop_camera() -> dict[str, Any]:
    global camera_running, camera, camera_status, latest_frame, follow_enabled, obstacle_enabled
    camera_running = False
    follow_enabled = False
    follow_stop_event.set()
    obstacle_enabled = False
    obstacle_stop_event.set()
    try:
        send_esp_command("STOP")
    except HTTPException:
        pass
    with lock:
        cap = camera
    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass
    with lock:
        camera = None
        latest_frame = None
        camera_status = "Stopped"
    log_event("CAMERA", "Camera stopped")
    return {"ok": True, "status": "Stopped"}


class SettingsBody(BaseModel):
    esp_url: str = Field(default="http://192.168.1.14")
    camera_source: str = Field(default="0")
    model_path: str = Field(default="yolov8n.pt")
    confidence: float = Field(default=0.45, ge=0.05, le=0.99)
    ocr_enabled: bool = False
    obstacle_demo: bool = True


class CommandBody(BaseModel):
    command: str


class FollowBody(BaseModel):
    enabled: bool


class ObstacleBody(BaseModel):
    enabled: bool


@app.get("/api/health")
def health():
    return {"ok": True, "service": "AUTONOVA AI"}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def status():
    with lock:
        cam = {
            "status": camera_status,
            "error": camera_error,
            "source": camera_source_label,
            "fps": camera_fps,
        }
        detections = dict(latest_detections)
        event_list = list(events)
    gpu_name = "NVIDIA GPU" if ai_gpu_available else ""
    return {
        "camera": cam,
        "ai": {
            "loaded": ai_model is not None,
            "error": ai_error,
            "gpu_available": ai_gpu_available,
            "gpu_name": gpu_name,
            "device": ai_device,
            "inference_ms": ai_inference_ms,
            "ai_fps": ai_fps,
        },
        "esp": {"connected": esp_connected, "message": ("ESP /status responded" if esp_connected else "Click Test ESP to check connection."), "last_check": esp_last_check},
        "last_command": last_command,
        "detection": detections,
        "settings": dict(settings),
        "events": event_list,
        "follow_enabled": follow_enabled,
        "obstacle_enabled": obstacle_enabled,
        "mode": "person_follow" if follow_enabled else ("obstacle_avoidance" if obstacle_enabled else "manual"),
        "safety": {"ultrasonic_obstacle_avoidance": "Arduino firmware required; test sensor before driving", "follow_mode": "conservative visual tracking; stop if target is lost"},
    }


@app.post("/api/settings")
def save_settings(body: SettingsBody):
    esp = body.esp_url.strip().rstrip("/")
    if not esp.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="ESP URL must start with http:// or https://")
    settings.update({
        "esp_url": esp,
        "camera_source": body.camera_source.strip() or "0",
        "model_path": body.model_path.strip() or "yolov8n.pt",
        "confidence": body.confidence,
        "ocr_enabled": body.ocr_enabled,
        "obstacle_demo": body.obstacle_demo,
    })
    log_event("SETTINGS", "Configuration saved")
    return {"ok": True, "settings": dict(settings)}


@app.post("/api/command")
def command(body: CommandBody):
    global follow_enabled, obstacle_enabled
    # Any manual command takes exclusive control away from autonomous modes.
    follow_enabled = False
    follow_stop_event.set()
    obstacle_enabled = False
    obstacle_stop_event.set()
    return send_esp_command(body.command)


@app.get("/api/esp/test")
def test_esp():
    global esp_connected, esp_last_check
    try:
        response = requests.get(f"{get_esp_url()}/status", timeout=2.5)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError:
            data = {"response": response.text}
        esp_connected = True
        esp_last_check = datetime.now().strftime("%H:%M:%S")
        log_event("ESP", "ESP status request succeeded")
        return {"ok": True, "status": data}
    except requests.RequestException as exc:
        esp_connected = False
        esp_last_check = datetime.now().strftime("%H:%M:%S")
        log_event("ESP", f"ESP test failed: {exc}", "ERROR")
        raise HTTPException(status_code=502, detail=f"Could not reach ESP at {get_esp_url()}: {exc}") from exc


@app.post("/api/camera/start")
def api_camera_start():
    return start_camera()


@app.post("/api/camera/stop")
def api_camera_stop():
    stop_camera()
    try:
        send_esp_command("STOP")
    except HTTPException:
        pass
    return {"ok": True, "status": "Stopped"}


@app.get("/video.mjpg")
def video_mjpeg():
    def frames():
        while True:
            with lock:
                frame = None if latest_frame is None else latest_frame.copy()
            if frame is None:
                time.sleep(0.1)
                continue
            ok, encoded = cv2.imencode(".jpg", frame)
            if ok:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n")
            time.sleep(0.03)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/ai/load")
def load_ai():
    global ai_model, ai_device, ai_gpu_available, ai_error
    try:
        import torch
        from ultralytics import YOLO
        model_path = str(settings["model_path"])
        model = YOLO(model_path)
        ai_gpu_available = bool(torch.cuda.is_available())
        ai_device = "GPU (CUDA)" if ai_gpu_available else "CPU"
        ai_model = model
        ai_error = ""
        log_event("AI", f"AI model loaded on {ai_device}")
        return {"ok": True, "device": ai_device}
    except Exception as exc:
        ai_model = None
        ai_gpu_available = False
        ai_device = "CPU"
        ai_error = str(exc)
        log_event("AI", f"Could not load AI model: {exc}", "ERROR")
        raise HTTPException(status_code=500, detail=f"AI model load failed. Install optional AI dependencies and check model path: {exc}") from exc


def infer_frame(frame):
    """Run YOLO and retain the person box for conservative person following."""
    global latest_detections, ai_inference_ms, ai_fps, last_ai_frame, last_ai_time, ai_error
    if ai_model is None:
        return frame
    started = time.time()
    try:
        result = ai_model.predict(frame, conf=float(settings["confidence"]), device=0 if ai_gpu_available else "cpu", verbose=False)[0]
        names = result.names
        person_candidate = None
        obstacles = []
        height, width = frame.shape[:2]
        for box in result.boxes:
            cls_id = int(box.cls[0].item())
            name = str(names.get(cls_id, cls_id))
            xyxy = [int(v) for v in box.xyxy[0].tolist()]
            if name == "person":
                area = max(0, xyxy[2] - xyxy[0]) * max(0, xyxy[3] - xyxy[1])
                if person_candidate is None or area > person_candidate["area"]:
                    person_candidate = {"box": xyxy, "area": area}
            else:
                obstacles.append({"name": name, "box": xyxy})
        person_box = person_candidate["box"] if person_candidate else None
        # Informational camera warning only. Real obstacle protection is done on Arduino by HC-SR04.
        obstacle_warning = False
        for obj in obstacles:
            x1, y1, x2, y2 = obj["box"]
            cx = (x1 + x2) / 2 / max(width, 1)
            bottom = y2 / max(height, 1)
            if 0.2 <= cx <= 0.8 and bottom >= 0.75:
                obstacle_warning = True
                break
        latest_detections = {"person": person_box is not None, "person_box": person_box,
                             "frame_size": [width, height], "obstacles": obstacles,
                             "obstacle_warning": obstacle_warning, "error": ""}
        ai_error = ""
        ai_inference_ms = round((time.time() - started) * 1000, 1)
        ai_fps = round(1000 / ai_inference_ms, 1) if ai_inference_ms else None
        last_ai_frame = result.plot()
        last_ai_time = time.time()
        return last_ai_frame
    except Exception as exc:
        latest_detections = {"person": False, "person_box": None, "frame_size": None,
                             "obstacles": [], "obstacle_warning": False, "error": str(exc)}
        ai_error = str(exc)
        return frame


def follow_decision(detections: dict[str, Any]) -> str:
    """Use person position and apparent size as a rough proxy; never move forward if uncertain."""
    if not detections.get("person") or not detections.get("person_box") or not detections.get("frame_size"):
        return "STOP"
    x1, y1, x2, y2 = detections["person_box"]
    width, height = detections["frame_size"]
    if width <= 0 or height <= 0 or detections.get("obstacle_warning"):
        return "STOP"
    center_x = ((x1 + x2) / 2) / width
    height_ratio = max(0, y2 - y1) / height
    # Turn first to center the person. Move forward only when they are small/far in the image.
    if center_x < 0.38:
        return "LEFT"
    if center_x > 0.62:
        return "RIGHT"
    if height_ratio < 0.24:
        return "FORWARD"
    return "STOP"


def follow_worker_loop() -> None:
    global follow_last_command, follow_last_command_at
    while not follow_stop_event.wait(FOLLOW_LOOP_SECONDS):
        if not follow_enabled:
            break
        with lock:
            frame = None if latest_frame is None else latest_frame.copy()
        if frame is None or ai_model is None:
            decision = "STOP"
        else:
            infer_frame(frame)
            with lock:
                detections = dict(latest_detections)
            decision = follow_decision(detections)
        now = time.time()
        # Refresh moving commands to satisfy the Arduino command watchdog.
        if decision != follow_last_command or (decision != "STOP" and now - follow_last_command_at >= 0.55):
            try:
                send_esp_command(decision)
                follow_last_command = decision
                follow_last_command_at = now
                log_event("FOLLOW", f"Tracking decision: {decision}")
            except HTTPException as exc:
                log_event("FOLLOW", f"Command failed; stopping follow mode: {exc.detail}", "ERROR")
                follow_stop_event.set()
                break
    try:
        send_esp_command("STOP")
    except HTTPException:
        pass
    follow_last_command = "STOP"


@app.get("/api/ai/frame.jpg")
def ai_frame():
    with lock:
        frame = None if latest_frame is None else latest_frame.copy()
    if frame is None:
        raise HTTPException(status_code=409, detail="Start the camera first")
    if ai_model is None:
        raise HTTPException(status_code=409, detail="Load the AI model first")
    annotated = infer_frame(frame)
    ok, encoded = cv2.imencode(".jpg", annotated)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not encode AI frame")
    from fastapi.responses import Response
    return Response(content=encoded.tobytes(), media_type="image/jpeg")


@app.post("/api/follow")
def follow(body: FollowBody):
    global follow_enabled, follow_thread, obstacle_enabled
    if body.enabled:
        obstacle_enabled = False
        obstacle_stop_event.set()
        if ai_model is None:
            raise HTTPException(status_code=409, detail="Load the AI model before enabling person following")
        if not camera_running or latest_frame is None:
            raise HTTPException(status_code=409, detail="Start the camera and wait until it is Connected before following")
        try:
            response = requests.get(f"{get_esp_url()}/status", timeout=2.0)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"ESP is not reachable; following was not enabled: {exc}") from exc
        follow_stop_event.clear()
        follow_enabled = True
        follow_thread = threading.Thread(target=follow_worker_loop, daemon=True, name="person-follow")
        follow_thread.start()
        log_event("FOLLOW", "Person following enabled; conservative visual tracking active")
    else:
        follow_enabled = False
        follow_stop_event.set()
        try:
            send_esp_command("STOP")
        except HTTPException:
            pass
        log_event("FOLLOW", "Person following disabled; STOP requested")
    return {"ok": True, "follow_enabled": follow_enabled,
            "warning": "Image size is only a rough distance proxy. Test slowly in a clear area; HC-SR04 obstacle guard and physical power cutoff are required."}

def obstacle_worker_loop() -> None:
    """Request forward travel repeatedly; Arduino HC-SR04 firmware guards and pivots at obstacles."""
    global obstacle_enabled
    while not obstacle_stop_event.wait(0.45):
        if not obstacle_enabled:
            break
        try:
            send_esp_command("FORWARD")
        except HTTPException as exc:
            log_event("OBSTACLE", f"Command failed; stopping obstacle mode: {exc.detail}", "ERROR")
            obstacle_enabled = False
            break
    try:
        send_esp_command("STOP")
    except HTTPException:
        pass


@app.post("/api/obstacle")
def obstacle_mode(body: ObstacleBody):
    global obstacle_enabled, follow_enabled, obstacle_thread, obstacle_stop_event
    if body.enabled:
        # Modes are mutually exclusive.
        follow_enabled = False
        follow_stop_event.set()
        if ai_model is None:
            log_event("OBSTACLE", "Obstacle avoidance mode requested; camera AI is not required")
        try:
            response = requests.get(f"{get_esp_url()}/status", timeout=2.0)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"ESP is not reachable; obstacle mode was not enabled: {exc}") from exc
        obstacle_stop_event.set()
        obstacle_stop_event = threading.Event()
        obstacle_enabled = True
        obstacle_thread = threading.Thread(target=obstacle_worker_loop, daemon=True, name="obstacle-avoidance")
        obstacle_thread.start()
        log_event("MODE", "Obstacle avoidance mode enabled; Arduino HC-SR04 firmware controls obstacle stop/pivot")
    else:
        obstacle_enabled = False
        obstacle_stop_event.set()
        try:
            send_esp_command("STOP")
        except HTTPException:
            pass
        log_event("MODE", "Obstacle avoidance mode disabled; STOP requested")
    return {"ok": True, "obstacle_enabled": obstacle_enabled,
            "warning": "Requires uploaded Arduino firmware, a working HC-SR04, and correct motor directions. One forward sensor cannot detect side/rear hazards."}


@app.get("/api/ocr")
def run_ocr():
    if not settings.get("ocr_enabled"):
        raise HTTPException(status_code=400, detail="Enable OCR in Settings first")
    with lock:
        frame = None if latest_frame is None else latest_frame.copy()
    if frame is None:
        raise HTTPException(status_code=409, detail="Start the camera first")
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=ai_gpu_available)
        results = reader.readtext(frame)
        out = [{"text": text, "confidence": round(float(conf), 3)} for _, text, conf in results]
        log_event("OCR", f"OCR completed: {len(out)} text items")
        return {"ok": True, "results": out}
    except Exception as exc:
        log_event("OCR", f"OCR failed: {exc}", "ERROR")
        raise HTTPException(status_code=500, detail=f"OCR failed; install easyocr: {exc}") from exc


@app.on_event("shutdown")
def shutdown():
    try:
        send_esp_command("STOP")
    except Exception:
        pass
    stop_camera()
