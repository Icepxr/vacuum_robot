"""8 ต.ค.: Pi ดึงทะเบียนห้อง+มิเตอร์จาก ARIA เอง (GET /ingest/registry) แทน export meters.json แล้ว scp
POST /readings แนบ registry_sha → ดึงเฉพาะตอนเปลี่ยน · ห้องที่ยังไม่มีมิเตอร์เลือกได้ · ไม่ยอมให้ทะเบียนว่างทับของเดิม"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import aria_store as S       # noqa: E402
import sync_supabase as Y    # noqa: E402

TOKEN = "t" * 43
REG = {"rooms": [{"room_id": "A10", "floor": "1"}, {"room_id": "A2", "floor": "1"}, {"room_id": "B1", "floor": None}],
       "meters": [{"meter_id": "W-A2-01", "room": "A2", "type": "water", "digits": 5, "decimals": 0, "waypoint": None, "lift_mm": None}]}


class FakeARIA(BaseHTTPRequestHandler):
    reg, sha, version, gets = REG, "s1", 7, []

    def log_message(self, *a): pass

    def _reply(self, code, body):
        b = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self._reply(200, {"accepted": [], "rejected": [], "registry_sha": FakeARIA.sha})

    def do_GET(self):
        if self.headers.get("x-device-token") != TOKEN:
            return self._reply(401, {"error": "unknown or revoked device token"})
        FakeARIA.gets.append(self.path)
        if self.path.endswith(f"have_sha={FakeARIA.sha}"):
            return self._reply(200, {"unchanged": True, "sha": FakeARIA.sha})
        self._reply(200, {"registry_version": FakeARIA.version, "exported_at": "2026-10-08T03:00:00Z", "sha": FakeARIA.sha, **FakeARIA.reg})


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "DATA_DIR", tmp_path)
    FakeARIA.reg, FakeARIA.sha, FakeARIA.version, FakeARIA.gets = REG, "s1", 7, []
    srv = HTTPServer(("127.0.0.1", 0), FakeARIA)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(Y, "INGEST_URL", f"http://127.0.0.1:{srv.server_port}/ingest")
    monkeypatch.setattr(Y, "LOCAL_STATUS_URL", "http://127.0.0.1:9/none")
    monkeypatch.setenv("ARIA_DEVICE_TOKEN", TOKEN)
    monkeypatch.setattr(sys, "argv", ["sync_supabase.py"])
    yield tmp_path
    srv.shutdown()


def test_pull_writes_registry_and_rooms_without_meters(env):
    ok, msg = Y.pull_registry(TOKEN)
    assert ok and "v7" in msg
    reg = S.load_registry()
    assert reg["registry_version"] == 7 and reg["sha"] == "s1" and reg["pulled_at"]
    assert S.room_ids(reg) == ["A2", "A10", "B1"]          # B1 ไม่มีมิเตอร์ก็เลือกได้ · เรียงแบบตัวเลข
    assert S.resolve_meter(reg, "A2", "water") == "W-A2-01" and S.resolve_meter(reg, "B1", "water") is None


def test_sync_pulls_only_when_sha_changes(env):
    assert Y.main() == 0 and len(FakeARIA.gets) == 1        # ยังไม่มีทะเบียน → ดึง
    assert Y.main() == 0 and len(FakeARIA.gets) == 1        # sha เท่าเดิม → ไม่เรียก GET เลย
    FakeARIA.sha, FakeARIA.version = "s2", 8
    FakeARIA.reg = {**REG, "rooms": REG["rooms"] + [{"room_id": "C3", "floor": None}]}
    assert Y.main() == 0 and len(FakeARIA.gets) == 2
    assert S.load_registry()["registry_version"] == 8 and "C3" in S.room_ids(S.load_registry())
    assert json.loads((env / "meters.json.prev").read_text())["registry_version"] == 7   # เก็บรุ่นก่อนไว้


def test_force_pull_unchanged_keeps_file(env):
    Y.pull_registry(TOKEN)
    before = (env / "meters.json").read_bytes()
    ok, msg = Y.pull_registry(TOKEN)                         # ปุ่มบนป๊อปอัพ: ส่ง have_sha → คลาวด์ตอบ unchanged
    assert ok and "ล่าสุด" in msg and FakeARIA.gets[-1].endswith("have_sha=s1")
    assert (env / "meters.json").read_bytes() == before


def test_empty_registry_never_wipes_existing(env):
    Y.pull_registry(TOKEN)
    FakeARIA.sha, FakeARIA.version, FakeARIA.reg = "s3", 9, {"rooms": [], "meters": []}
    ok, msg = Y.pull_registry(TOKEN)
    assert not ok and "empty_refused" in msg
    assert S.load_registry()["registry_version"] == 7


def test_bad_payload_rejected(env):
    assert S.save_registry({"registry_version": "x", "rooms": [], "meters": []}) == (False, "bad_version")
    assert S.save_registry({"registry_version": 1, "rooms": [{"room_id": "../x"}], "meters": []}) == (False, "bad_room")
    assert S.save_registry({"registry_version": 1, "rooms": [], "meters": [{"meter_id": "W", "room": "1", "type": "gas"}]}) == (False, "bad_meter")
    assert not (env / "meters.json").exists()


def test_network_down_keeps_old_registry(env, monkeypatch):
    Y.pull_registry(TOKEN)
    monkeypatch.setattr(Y, "INGEST_URL", "http://127.0.0.1:9/ingest")
    ok, msg = Y.pull_registry(TOKEN)
    assert not ok and S.load_registry()["registry_version"] == 7


def test_old_web_export_still_readable(env):
    (env / "meters.json").write_text(json.dumps({"registry_version": 3, "meters": [
        {"meter_id": "W-204-01", "room": "204", "type": "water"}]}))
    reg = S.load_registry()
    assert reg["rooms"] == [] and S.room_ids(reg) == ["204"]


def test_cli_registry_flag(env, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync_supabase.py", "--registry"])
    assert Y.main() == 0 and S.load_registry()["registry_version"] == 7
