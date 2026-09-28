"""sync_supabase.py กับ ingest ปลอมบน localhost — แถวก่อน crop · ปฏิเสธรายแถว · เน็ตล้มไม่เสียข้อมูล · ไม่เขียนทับ jsonl"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import aria_store as S       # noqa: E402
import sync_supabase as Y    # noqa: E402
from test_aria_store import make  # noqa: E402

TOKEN = "t" * 43


class FakeIngest(BaseHTTPRequestHandler):
    calls, rows, crops = [], {}, {}
    reject = set()

    def log_message(self, *a): pass

    def _reply(self, code, body):
        b = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _auth(self):
        if self.headers.get("x-device-token") != TOKEN:
            self._reply(401, {"error": "unknown or revoked device token"}); return False
        return True

    def do_POST(self):
        if not self._auth(): return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeIngest.calls.append(("POST", self.path, body))
        acc, rej = [], []
        for r in body["rows"]:
            if r["local_id"] in FakeIngest.reject: rej.append({"local_id": r["local_id"], "reason": "nope"})
            else: FakeIngest.rows[r["local_id"]] = r; acc.append(r["local_id"])
        self._reply(200, {"accepted": acc, "rejected": rej})

    def do_PUT(self):
        if not self._auth(): return
        lid = self.path.rsplit("/", 1)[1]
        data = self.rfile.read(int(self.headers["Content-Length"]))
        FakeIngest.calls.append(("PUT", self.path, len(data)))
        if lid not in FakeIngest.rows: return self._reply(409, {"error": "send row first"})
        FakeIngest.crops[lid] = data
        self._reply(200, {"attached": True})


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "DATA_DIR", tmp_path)
    (tmp_path / "images").mkdir()
    FakeIngest.calls, FakeIngest.rows, FakeIngest.crops, FakeIngest.reject = [], {}, {}, set()
    srv = HTTPServer(("127.0.0.1", 0), FakeIngest)
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    monkeypatch.setattr(Y, "INGEST_URL", f"http://127.0.0.1:{srv.server_port}/ingest")
    monkeypatch.setattr(Y, "LOCAL_STATUS_URL", "http://127.0.0.1:9/none")      # ไม่มีเว็บรัน
    monkeypatch.setenv("ARIA_DEVICE_TOKEN", TOKEN)
    monkeypatch.setattr(sys, "argv", ["sync_supabase.py"])
    yield tmp_path
    srv.shutdown()


def keep(data, lid, crop=True):
    make(data, lid, crop=crop)
    assert S.decide(lid, True, "204", "water")[0]


def test_rows_then_crops_and_state_file(env):
    keep(env, "aaaaaaaaaaaa"); keep(env, "bbbbbbbbbbbb", crop=False)
    make(env, "cccccccccccc")                                        # ยังไม่ตัดสิน → ห้ามขึ้นคลาวด์
    before = (env / "readings.jsonl").read_bytes()
    assert Y.main() == 0
    kinds = [c[0] for c in FakeIngest.calls]
    assert kinds == ["POST", "PUT"]                                   # แถวก่อน รูปทีหลัง · b ไม่มี crop
    body = FakeIngest.calls[0][2]
    assert sorted(r["local_id"] for r in body["rows"]) == ["aaaaaaaaaaaa", "bbbbbbbbbbbb"]
    assert set(body["rows"][0]) == set(Y.ROW_FIELDS)                  # ไม่มี status/confirmed_value/synced_at หลุดไป
    assert body["heartbeat"]["pending_rows"] == 2 and body["heartbeat"]["pending_decisions"] == 1
    assert (env / "readings.jsonl").read_bytes() == before            # jsonl ไม่ถูกเขียนทับ
    st = S.load_sync_state()
    assert st["aaaaaaaaaaaa"]["row"] and st["aaaaaaaaaaaa"]["crop"] and st["bbbbbbbbbbbb"]["crop"] is None
    FakeIngest.calls.clear()
    assert Y.main() == 0
    assert [c[0] for c in FakeIngest.calls] == ["POST"] and FakeIngest.calls[0][2]["rows"] == []   # รอบถัดไป: heartbeat อย่างเดียว


def test_rejected_row_not_resent_unless_retry(env, monkeypatch):
    keep(env, "aaaaaaaaaaaa"); FakeIngest.reject = {"aaaaaaaaaaaa"}
    assert Y.main() == 0
    assert S.load_sync_state()["aaaaaaaaaaaa"]["error"] == "nope" and S.sync_counts()["sync_errors"] == 1
    FakeIngest.calls.clear(); Y.main()
    assert FakeIngest.calls[0][2]["rows"] == []
    FakeIngest.reject = set(); monkeypatch.setattr(sys, "argv", ["x", "--retry-errors"]); FakeIngest.calls.clear()
    assert Y.main() == 0 and S.load_sync_state()["aaaaaaaaaaaa"]["error"] is None


def test_network_down_keeps_everything(env, monkeypatch):
    keep(env, "aaaaaaaaaaaa")
    monkeypatch.setattr(Y, "INGEST_URL", "http://127.0.0.1:9/ingest")      # ไม่มีใครฟัง
    assert Y.main() == 1
    assert S.sync_counts()["pending_rows"] == 1


def test_wrong_token(env, monkeypatch):
    keep(env, "aaaaaaaaaaaa"); monkeypatch.setenv("ARIA_DEVICE_TOKEN", "x" * 43)
    assert Y.main() == 1 and S.sync_counts()["pending_rows"] == 1


def test_no_token(env, monkeypatch):
    monkeypatch.delenv("ARIA_DEVICE_TOKEN"); monkeypatch.setattr(Y, "TOKEN_FILE", env / "none")
    assert Y.main() == 2


def test_oversize_crop_skipped_not_blocking(env):
    keep(env, "aaaaaaaaaaaa"); keep(env, "bbbbbbbbbbbb")
    (env / "crops" / "aaaaaaaaaaaa.jpg").write_bytes(b"\xff\xd8" + b"0" * (Y.MAX_CROP_BYTES + 1))
    assert Y.main() == 0
    st = S.load_sync_state()
    assert st["aaaaaaaaaaaa"]["crop"] == "too_large" and st["bbbbbbbbbbbb"]["crop"]
    assert ("PUT", "/ingest/crops/aaaaaaaaaaaa", Y.MAX_CROP_BYTES + 3) not in FakeIngest.calls
