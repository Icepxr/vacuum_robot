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
import subprocess
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
LINK_STALE_S = 1.0                  # #T มา 10 Hz — เงียบเกิน 1 s = ลิงก์มีปัญหา
DRIVE_DEADMAN_S = 0.30              # ไฟล์ 19 §19.3 — browser เงียบเกินนี้ → ส่ง $S แล้วเลิกส่ง $V
DRIVE_REPEAT_S = 0.10               # ส่ง $V ซ้ำ 10 Hz ให้ G8 (300 ms) ผ่านด้วย margin 3×
V_MAX_MM_S = 150                    # ค่าเริ่มต้นของเพดานที่ผู้ใช้ตั้งได้ (C28 — เดิม G14 เป็นการห้าม)
W_MAX_MRAD_S = 1500
V_HW_MAX_MM_S = 716                 # เพดานฮาร์ดแวร์: 152 rpm [วัดจริง M1] × π × Ø90 mm (ไฟล์ 19 §19.7) — ขอเกินก็ไม่ได้อยู่แล้ว
W_HW_MAX_MRAD_S = 7950              # 716 / (180/2) mm ≈ 7.96 rad/s [คำนวณ] ต้องตรงกับ manual_core.h


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
        # ── โหมดขับเอง: Pi "ถือ" setpoint ล่าสุดแล้วส่งซ้ำเอง (ไฟล์ 19 §19.3 — ห้ามให้ browser ส่ง $V ตรง) ──
        self.drive_v = 0
        self.drive_w = 0
        self.drive_last_mono = None              # เวลาที่ได้ drive จาก browser ล่าสุด · None = ไม่ได้ขับ
        self.drive_tripped = 0                   # นับครั้งที่ deadman ฝั่ง Pi ทำงาน
        self.cleaning = {"suction": 0, "brush": 0}
        # C28: เพดานความเร็วเป็นของผู้ใช้ (ตั้งจากหน้าเว็บ → $L) · Pi แค่ clamp ตามค่าเดียวกันและจำไว้ให้ client ใหม่
        self.cam_fallback = False                # True = เปิดกล้องไม่ได้ ใช้ภาพนิ่งแทน → cam_ok False ให้หน้าเว็บบอกตรงๆ
        self.cam_args = None                     # args ของกล้อง (index/engine/run_id) ให้ camera_hotplug ลองเปิดใหม่
        self.limits = {"v_max": V_MAX_MM_S, "w_max": W_MAX_MRAD_S, "v_hw_max": V_HW_MAX_MM_S, "w_hw_max": W_HW_MAX_MRAD_S}

    # ── ขับเอง ──
    def drive(self, v, w):
        vm, wm = self.limits["v_max"], self.limits["w_max"]
        self.drive_v = max(-vm, min(vm, int(v)))
        self.drive_w = max(-wm, min(wm, int(w)))
        self.drive_last_mono = time.monotonic()

    def set_limits(self, v_max, w_max):
        """เพดานที่ผู้ใช้ตั้ง — clamp ที่ฮาร์ดแวร์ (716 mm/s [คำนวณจาก 152 rpm วัดจริง] · ไฟล์ 19 §19.7) แล้วส่ง $L"""
        self.limits["v_max"] = max(0, min(V_HW_MAX_MM_S, int(v_max)))
        self.limits["w_max"] = max(0, min(W_HW_MAX_MRAD_S, int(w_max)))
        if self.daemon: self.daemon.send_limits(self.limits["v_max"], self.limits["w_max"])
        return self.limits

    def drive_release(self):
        """ผู้ใช้ปล่อยจอย/กด stop: ส่ง $S แล้วหยุดส่งซ้ำ"""
        self.drive_v = self.drive_w = 0
        self.drive_last_mono = None
        if self.daemon: self.daemon.send_stop()

    async def drive_loop(self):
        """ทุก 100 ms: ถ้ายังได้ drive จาก browser ภายใน 300 ms → ส่ง $V ซ้ำ · ไม่งั้น $S ครั้งเดียว (deadman ชั้น Pi)"""
        while True:
            await asyncio.sleep(DRIVE_REPEAT_S)
            if self.drive_last_mono is None or self.daemon is None:
                continue
            if time.monotonic() - self.drive_last_mono > DRIVE_DEADMAN_S:
                self.drive_tripped += 1
                self.drive_v = self.drive_w = 0
                self.drive_last_mono = None
                self.daemon.send_stop()
                self.on_event({"t": "log", "level": "warn", "msg": "deadman ฝั่ง Pi: browser เงียบเกิน 300 ms → $S"})
                continue
            self.daemon.send_velocity(self.drive_v, self.drive_w)

    # ── ถูกเรียกจาก thread ของ daemon — ห้ามบล็อก ──
    def on_event(self, ev):
        ev = dict(ev, ts=time.time())
        self.events.append(ev)
        if ev.get("t") == "capture":
            self.last_capture = ev
        if ev.get("t") == "event" and ev.get("code") == "BOOT":
            # ESP32 เพิ่งบูต (เปิดเครื่อง / WDT / brownout) — ค่าเพดาน $L หายไปกับ RAM → ส่งซ้ำ · บอกคนขับถ้าไม่ใช่เปิดเครื่อง
            reason = ev.get("detail", "")
            if self.daemon: self.daemon.send_limits(self.limits["v_max"], self.limits["w_max"])
            self.events.append({"t": "log", "ts": time.time(),
                                "level": "info" if reason == "POWERON" else "warn",
                                "msg": f"ESP32 บูตใหม่ ({reason}) — ส่งเพดาน $L ซ้ำแล้ว" +
                                       (" · รีบูตจาก watchdog: loop ค้างเกิน 1 s" if "WDT" in reason else "")})
            if self.loop: asyncio.run_coroutine_threadsafe(self.broadcast(self.events[-1]), self.loop)
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
                    "age_s": age, "alive": age is not None and age < LINK_STALE_S}
        cam_ok = self.backend is not None and self.backend.latest() is not None and not self.cam_fallback
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
                "cam_ok": cam_ok, "cam_fallback": self.cam_fallback, "cpu_temp_c": temp, "disk_free_mb": du.free // 2**20,
                "pending_sync": pending, "link": link, "last_capture": self.last_capture,
                "esp32_supports": ["CAPTURE_REQ", "$K", "$V", "$S", "$E", "$C", "$P", "$L", "$X", "$M", "#T"],
                "tele": (self.daemon.tele if self.daemon else None),
                "drive": {"v": self.drive_v, "w": self.drive_w, "active": self.drive_last_mono is not None,
                          "tripped": self.drive_tripped, "deadman_ms": int(DRIVE_DEADMAN_S * 1000)},
                "cleaning": self.cleaning,
                "limits": self.limits,
                "ip": pi_ips(),
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


@app.get("/drive")
def drive_page():
    return FileResponse(STATIC_DIR / "drive.html")


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


ROI_PATH = Path(__file__).resolve().parent / "roi_config.json"


@app.get("/api/roi")
def api_roi_get():
    """กรอบ crop ที่ OCR ใช้ (สัดส่วน 0..1) — จาก roi_config.json ของ meter_reader"""
    try:
        cfg = json.loads(ROI_PATH.read_text(encoding="utf-8"))
    except Exception:                        # noqa: BLE001
        cfg = {}
    return JSONResponse({"crop": cfg.get("crop", {"x": 0, "y": 0, "w": 1, "h": 1})})


@app.post("/api/roi")
async def api_roi_set(body: dict):
    """ตั้งกรอบ crop จากหน้าเว็บ (ลากบนภาพสด) → เขียน roi_config.json · มีผลกับการถ่ายครั้งถัดไป"""
    c = body.get("crop") or {}
    try:
        crop = {k: max(0.0, min(1.0, float(c[k]))) for k in ("x", "y", "w", "h")}
    except (KeyError, TypeError, ValueError):
        return JSONResponse({"ok": False, "reason": "crop ต้องมี x y w h (0..1)"}, status_code=400)
    if crop["w"] < 0.02 or crop["h"] < 0.02:
        return JSONResponse({"ok": False, "reason": "กรอบเล็กเกินไป"}, status_code=400)
    try:
        cfg = json.loads(ROI_PATH.read_text(encoding="utf-8"))
    except Exception:                        # noqa: BLE001
        cfg = {}
    cfg["crop"] = crop
    ROI_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    if hub.backend is not None and hasattr(hub.backend, "cfg"):
        hub.backend.cfg["crop"] = crop        # backend กล้องจริงถือ cfg ไว้ในหน่วยความจำ
    hub.on_event({"t": "log", "level": "good", "msg": f"ตั้งกรอบ OCR ใหม่ x={crop['x']:.2f} y={crop['y']:.2f} w={crop['w']:.2f} h={crop['h']:.2f}"})
    return JSONResponse({"ok": True, "crop": crop})


@app.get("/stream.mjpg")
async def stream(frames: int = 0, fps: int = 0):
    """MJPEG multipart · frames>0 = จำกัดจำนวนเฟรมแล้วจบ (ใช้ในเทสต์) · fps = 2..15 (ค่าตั้งต้น PREVIEW_FPS)"""
    if hub.backend is None:
        return JSONResponse({"error": "no camera"}, status_code=503)
    rate = max(2, min(15, fps)) if fps else PREVIEW_FPS

    async def gen():
        period = 1.0 / rate
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
            d = hub.daemon
            if t == "capture" and d is not None:
                await asyncio.to_thread(d.capture_now)
            elif t == "status":
                await ws.send_text(json.dumps(hub.status(), ensure_ascii=False))
            elif t == "drive":                       # {"t":"drive","v":mm/s,"w":mrad/s} ส่งซ้ำ ≥ 5 Hz ขณะกด
                hub.drive(cmd.get("v", 0), cmd.get("w", 0))
            elif t == "release":                     # ปล่อยจอย
                hub.drive_release()
            elif t == "stop" and d is not None:
                hub.drive_release()
            elif t == "estop" and d is not None:     # ทำงานทุกโหมด ไม่ผ่านตัวกรอง
                hub.drive_v = hub.drive_w = 0; hub.drive_last_mono = None
                d.send_estop()
                hub.on_event({"t": "log", "level": "bad", "msg": "E-STOP จากหน้าเว็บ → $E"})
            elif t == "clean" and d is not None:     # {"t":"clean","suction":0-100,"brush":0-100} (C30: แปรง 6 V บนราง 5 V ไม่ต้องจำกัด)
                suc = int(cmd.get("suction", hub.cleaning["suction"])); br = int(cmd.get("brush", hub.cleaning["brush"]))
                hub.cleaning = {"suction": max(0, min(100, suc)), "brush": max(0, min(100, br))}
                d.send_clean(hub.cleaning["suction"], hub.cleaning["brush"])
            elif t == "ping" and d is not None:
                d.send_ping()
            elif t == "x" and d is not None:         # {"t":"x","us":500-2500|0} เซอร์โวแกน X ของกล้อง (C30) · ESP32 ตรวจช่วง/R1 เอง
                d.send_servo_x(int(cmd.get("us", 0)))
            elif t == "limits":                      # {"t":"limits","v_max":mm/s,"w_max":mrad/s} — C28 ผู้ใช้ตั้งเพดานเอง
                lim = hub.set_limits(cmd.get("v_max", hub.limits["v_max"]), cmd.get("w_max", hub.limits["w_max"]))
                hub.on_event({"t": "limits", **lim})
            elif t == "m" and d is not None:         # {"t":"m","us":500-2500|0} เสา scissor ไม่บล็อก (C30) · ESP32 ตรวจช่วง/R1/mission เอง
                d.send_mast(int(cmd.get("us", 0)))
            else:
                await ws.send_text(json.dumps({"t": "nack", "cmd": t, "reason": "ไม่รู้จักคำสั่ง"}, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)


async def sys_ticker():
    while True:
        await asyncio.sleep(1.0)
        if hub.clients:
            await hub.broadcast(hub.status())


CAMERA_RETRY_S = 5.0

async def camera_hotplug():
    """ไม่มีกล้องตอนสตาร์ท (cam_fallback) → ลองเปิดใหม่ทุก 5 s · เปิดได้ก็สลับ backend ให้ daemon/stream ทันที
    (เจอจริง 18 ก.ย.: เสียบ BRIO หลัง service ขึ้น → ไม่มีภาพจนกว่าจะ restart)"""
    while True:
        await asyncio.sleep(CAMERA_RETRY_S)
        if not hub.cam_fallback or hub.cam_args is None:
            continue
        try:
            cam = await asyncio.to_thread(D.UsbCameraBackend, hub.cam_args.camera,
                                          engine=hub.cam_args.engine, run_id=hub.cam_args.run_id)
        except RuntimeError:
            continue                          # ยังไม่เสียบ — เงียบ ไม่ spam log
        old = hub.backend
        hub.backend = cam
        if hub.daemon: hub.daemon.backend = cam
        hub.cam_fallback = False
        try: old.close()
        except Exception: pass               # noqa: BLE001
        D.log("กล้องเสียบแล้ว → สลับมาภาพสด")
        hub.on_event({"t": "log", "level": "good", "msg": "กล้องเสียบแล้ว — ภาพสดกลับมา"})


@app.on_event("startup")
async def _startup():
    hub.loop = asyncio.get_running_loop()
    asyncio.create_task(sys_ticker())
    asyncio.create_task(hub.drive_loop())
    asyncio.create_task(camera_hotplug())


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def start_daemon(port, backend, baud=115200):
    d = D.CaptureDaemon(port, backend, baud, on_event=hub.on_event)
    hub.daemon, hub.backend = d, backend
    th = threading.Thread(target=d.run, name="capture-daemon", daemon=True)
    th.start()
    return d


def pi_ips():
    """IPv4 ของ Pi ทุก interface (ไว้โชว์บนหน้าเว็บ/log — IP เปลี่ยนบ่อยบน Wi-Fi อาคาร/hotspot มือถือ)"""
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=2).stdout.split()
        return [a for a in out if "." in a]
    except Exception:                        # noqa: BLE001
        return []


def open_camera_or_fallback(args):
    """เปิดกล้อง USB · ถ้าไม่มี (ยังไม่เสียบ / ถอดไป) ให้รันต่อด้วยภาพนิ่งแทนที่จะตาย —
    ไม่งั้น systemd Restart=always จะวนเปิดใหม่ทุก 2 s และหน้าเว็บ/ลิงก์ ESP32 ไม่ขึ้นเลยทั้งที่ขับได้โดยไม่มีภาพ
    cam_ok ใน /api/status จะเป็น False → หน้าเว็บโชว์ "ไม่มีภาพ" (เสียบกล้องแล้วต้องรีสตาร์ท service — ยังไม่ทำ hot-plug)"""
    try:
        return D.UsbCameraBackend(args.camera, engine=args.engine, run_id=args.run_id)
    except RuntimeError as e:
        D.log(f"⚠ {e} — รันต่อโดยไม่มีกล้อง")
    hub.cam_fallback = True
    hub.cam_args = args
    imgs = sorted(IMAGE_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime) if IMAGE_DIR.exists() else []
    if imgs:
        D.log(f"ใช้รูปล่าสุดแทนภาพสด: {imgs[-1].name}")
        return D.StillImageBackend(imgs[-1])
    import cv2, numpy as np
    ph = DATA_DIR / "no_camera.jpg"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame = np.full((480, 640, 3), 24, np.uint8)
    cv2.putText(frame, "NO CAMERA", (170, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (90, 90, 200), 3)
    cv2.imwrite(str(ph), frame)
    return D.StillImageBackend(ph)


def main():
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--serial", default="/dev/ttyAMA0")
    ap.add_argument("--no-serial", action="store_true", help="ไม่มี ESP32 — ภาพสด/ถ่ายจากเว็บอย่างเดียว")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--image", help="ใช้รูปนี้แทนกล้อง")
    ap.add_argument("--engine", choices=["sevenseg", "tesseract", "ssocr"], default="sevenseg")   # C30: 7-seg ก่อน (18 ก.ย.)
    ap.add_argument("--run-id", default=time.strftime("run_%Y%m%d_%H%M%S"))
    args = ap.parse_args()

    backend = D.StillImageBackend(args.image) if args.image else open_camera_or_fallback(args)
    if args.no_serial:
        hub.backend = backend
        # daemon ที่ไม่มี serial: ใช้ capture_now ได้ แต่ไม่ฟัง ESP32
        import pty
        master, slave = pty.openpty()          # พอร์ตปลอมให้ daemon เปิดได้ — ไม่มีใครส่งอะไรมา
        hub.daemon = D.CaptureDaemon(os.ttyname(slave), backend, on_event=hub.on_event)
        D.log("โหมด --no-serial: ไม่ฟัง ESP32")
    else:
        start_daemon(args.serial, backend)
    D.log(f"เว็บ http://{args.host}:{args.port}  (ภาพสด {PREVIEW_FPS} fps) · IP ของ Pi: {' '.join(pi_ips()) or 'ยังไม่มี'}")
    # timeout_graceful_shutdown: ไม่งั้น SIGTERM จะรอ /stream.mjpg ที่ browser เปิดค้างไว้ตลอดกาล
    # → process เก่าไม่ตาย ถือ /dev/ttyAMA0 ซ้อนกับตัวใหม่ แล้วแย่งอ่าน byte จนไม่มีใครได้เฟรมครบ (เจอจริง 16 ก.ย.)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning", timeout_graceful_shutdown=2)


if __name__ == "__main__":
    main()
