#!/usr/bin/env python3
"""
mrc_web.py — หลังบ้านแอปควบคุมหุ่นบน Pi 5 (ขั้น E ขั้นต่ำ · software_architecture.md §3–§4)

ครอบ capture_daemon.py ที่พิสูจน์แล้ว ไม่แทนที่: daemon ยังรันใน thread ของมันเอง คุย UART กับ ESP32
ตามเดิม · ไฟล์นี้แค่ (1) รับเหตุการณ์จาก daemon ส่งขึ้น WebSocket (2) เสิร์ฟภาพสด MJPEG
(3) รับคำสั่ง "ถ่ายเดี๋ยวนี้" จากหน้าเว็บ (4) เสิร์ฟหน้าเว็บ + รายการค่าที่อ่านได้ + รูป

ขอบเขตตอนนี้ (15 ก.ย. 2026): ESP32 รองรับแค่ CAPTURE_REQ/$K → หน้าเว็บ**ไม่มีปุ่มขับ/E-STOP ที่กดได้**
จนกว่า ESP32 จะรับ $V/$E (C19/C20 ขั้น E) — ไม่โชว์ปุ่มที่กดแล้วไม่เกิดอะไร เพราะจะหลงคิดว่าหยุดหุ่นได้

    python src/mrc_web.py                         # UART /dev/ttyAMA0 · BRIO index 0 · http://0.0.0.0:8000
    python src/mrc_web.py --image photo.jpg       # ไม่มีกล้อง
    python src/mrc_web.py --no-serial             # ไม่มี ESP32 (ดูภาพสด/ถ่ายจากเว็บอย่างเดียว)
"""
import argparse
import asyncio
import json
import os
import shutil
import sys
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_daemon as D          # noqa: E402
import mrc_protocol as P            # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = Path(os.environ.get("MRC_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
IMAGE_DIR = DATA_DIR / "images"
JSONL_PATH = DATA_DIR / "readings.jsonl"
PREVIEW_FPS = 10                    # ไฟล์ 19 §19.1 — 10 fps ≈ 3 Mbps บน hotspot
LINK_STALE_S = 2.0                  # ไม่ได้เฟรมถูกต้องจาก ESP32 นานกว่านี้ = แสดง "ไม่ตอบ" (ยังไม่มี #T ที่ 20 Hz)


class Hub:
    """ตัวกลางระหว่าง thread ของ daemon กับ event loop ของ FastAPI · เก็บ state ล่าสุด + broadcast"""

    def __init__(self):
        self.loop = None
        self.clients: set[WebSocket] = set()
        self.daemon = None
        self.backend = None
        self.events = deque(maxlen=200)          # log ล่าสุดให้ client ที่เพิ่งต่อเห็นย้อนหลัง
        self.last_capture = None
        self.started = time.time()

    # ── ถูกเรียกจาก thread ของ daemon — ห้ามบล็อก ──
    def on_event(self, ev):
        ev = dict(ev, ts=time.time())
        self.events.append(ev)
        if ev.get("t") == "capture":
            self.last_capture = ev
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.broadcast(ev), self.loop)

    async def broadcast(self, ev):
        dead = []
        msg = json.dumps(ev, ensure_ascii=False, default=str)
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:                    # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def status(self):
        d = self.daemon
        link = None
        if d is not None:
            age = None if d.last_rx_mono is None else round(time.monotonic() - d.last_rx_mono, 1)
            link = {"port": d.ser.port, "baud": d.ser.baudrate, "stats": d.stats,
                    "age_s": age, "alive": age is not None and age < LINK_STALE_S,
                    "note": "ESP32 ยังไม่ส่ง #T ต่อเนื่อง — alive จะจริงเฉพาะหลัง CAPTURE_REQ ล่าสุดไม่นาน"}
        cam_ok = self.backend is not None and self.backend.latest() is not None
        try:
            temp = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
        except Exception:                        # noqa: BLE001
            temp = None
        du = shutil.disk_usage(DATA_DIR if DATA_DIR.exists() else Path("/"))
        pending = 0
        if JSONL_PATH.exists():
            pending = sum(1 for l in JSONL_PATH.read_text(encoding="utf-8").splitlines()
                          if l.strip() and '"synced_at": null' in l)
        return {"t": "sys", "ts": time.time(), "uptime_s": round(time.time() - self.started),
                "cam_ok": cam_ok, "cpu_temp_c": temp, "disk_free_mb": du.free // 2**20,
                "pending_sync": pending, "link": link, "last_capture": self.last_capture,
                "esp32_supports": ["CAPTURE_REQ", "$K"],   # หน้าเว็บใช้ตัดสินว่าโชว์ปุ่มอะไร
                "clients": len(self.clients)}


hub = Hub()
app = FastAPI(title="MRC-001 control")


def read_readings(limit=50):
    if not JSONL_PATH.exists():
        return []
    lines = [l for l in JSONL_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for l in reversed(lines[-limit:]):
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    return out


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def api_status():
    return JSONResponse(hub.status())


@app.get("/api/readings")
def api_readings(limit: int = 50):
    return JSONResponse(read_readings(max(1, min(limit, 500))))


@app.get("/images/{name}")
def image(name: str):
    p = (IMAGE_DIR / Path(name).name)
    if not p.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(p)


@app.post("/api/capture")
def api_capture():
    """ถ่ายจากเว็บ — ไม่ผ่าน ESP32 · ผลจริงมาทาง WebSocket (capture แล้ว reading)"""
    if hub.daemon is None:
        return JSONResponse({"ok": False, "reason": "no daemon"}, status_code=503)
    ok = hub.daemon.capture_now()
    return JSONResponse({"ok": ok})


@app.get("/stream.mjpg")
async def stream(frames: int = 0):
    """MJPEG multipart · frames>0 = จำกัดจำนวนเฟรมแล้วจบ (ใช้ในเทสต์) · 0 = ไม่รู้จบ"""
    if hub.backend is None:
        return JSONResponse({"error": "no camera"}, status_code=503)

    async def gen():
        period = 1.0 / PREVIEW_FPS
        sent = 0
        while frames <= 0 or sent < frames:
            sent += 1
            t0 = time.monotonic()
            jpg = await asyncio.to_thread(hub.backend.preview_jpeg)   # resize+encode 6 ms — ออกจาก event loop
            if jpg:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    hub.clients.add(ws)
    try:
        await ws.send_text(json.dumps({"t": "hello", "proto": 1, "events": list(hub.events)[-50:]},
                                      ensure_ascii=False, default=str))
        await ws.send_text(json.dumps(hub.status(), ensure_ascii=False))
        while True:
            raw = await ws.receive_text()
            try:
                cmd = json.loads(raw)
            except json.JSONDecodeError:
                continue
            t = cmd.get("t")
            if t == "capture" and hub.daemon is not None:
                await asyncio.to_thread(hub.daemon.capture_now)
            elif t == "status":
                await ws.send_text(json.dumps(hub.status(), ensure_ascii=False))
            else:
                # คำสั่งขับ/E-STOP/ยกเสา ยังไม่รองรับฝั่ง ESP32 (C19/C20) — ตอบตรงๆ ไม่แกล้งส่ง
                await ws.send_text(json.dumps({"t": "nack", "cmd": t,
                                               "reason": "ESP32 ยังรองรับแค่ CAPTURE_REQ/$K (ขั้น E)"},
                                              ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)


async def sys_ticker():
    while True:
        await asyncio.sleep(1.0)
        if hub.clients:
            await hub.broadcast(hub.status())


@app.on_event("startup")
async def _startup():
    hub.loop = asyncio.get_running_loop()
    asyncio.create_task(sys_ticker())


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def start_daemon(port, backend, baud=115200):
    d = D.CaptureDaemon(port, backend, baud, on_event=hub.on_event)
    hub.daemon, hub.backend = d, backend
    th = threading.Thread(target=d.run, name="capture-daemon", daemon=True)
    th.start()
    return d


def main():
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--serial", default="/dev/ttyAMA0")
    ap.add_argument("--no-serial", action="store_true", help="ไม่มี ESP32 — ภาพสด/ถ่ายจากเว็บอย่างเดียว")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--image", help="ใช้รูปนี้แทนกล้อง")
    ap.add_argument("--engine", choices=["tesseract", "ssocr"], default="tesseract")
    ap.add_argument("--run-id", default=time.strftime("run_%Y%m%d_%H%M%S"))
    args = ap.parse_args()

    backend = (D.StillImageBackend(args.image) if args.image
               else D.UsbCameraBackend(args.camera, engine=args.engine, run_id=args.run_id))
    if args.no_serial:
        hub.backend = backend
        # daemon ที่ไม่มี serial: ใช้ capture_now ได้ แต่ไม่ฟัง ESP32
        import pty
        master, slave = pty.openpty()          # พอร์ตปลอมให้ daemon เปิดได้ — ไม่มีใครส่งอะไรมา
        hub.daemon = D.CaptureDaemon(os.ttyname(slave), backend, on_event=hub.on_event)
        D.log("โหมด --no-serial: ไม่ฟัง ESP32")
    else:
        start_daemon(args.serial, backend)
    D.log(f"เว็บ http://{args.host}:{args.port}  (ภาพสด {PREVIEW_FPS} fps)")
    # timeout_graceful_shutdown: ไม่งั้น SIGTERM จะรอ /stream.mjpg ที่ browser เปิดค้างไว้ตลอดกาล
    # → process เก่าไม่ตาย ถือ /dev/ttyAMA0 ซ้อนกับตัวใหม่ แล้วแย่งอ่าน byte จนไม่มีใครได้เฟรมครบ (เจอจริง 16 ก.ย.)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning", timeout_graceful_shutdown=2)


if __name__ == "__main__":
    main()
