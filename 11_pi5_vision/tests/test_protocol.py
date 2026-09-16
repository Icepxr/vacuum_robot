"""ทดสอบ mrc_protocol.py — stdlib ล้วน รันได้ทุกเครื่อง:  python -m pytest tests/ -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import mrc_protocol as P  # noqa: E402


def test_crc8_vector_shared_with_cpp():
    # ค่านี้ต้องตรงกับคอมเมนต์ใน src/robot/comm.cpp — ถ้าเปลี่ยนต้องเปลี่ยนทั้งสองที่
    assert P.crc8(b"123456789") == 0xF4          # ค่า check มาตรฐานของ CRC-8 poly 0x07
    assert P.crc8(b"E,1000,CAPTURE_REQ,1") == 0xE0
    assert P.crc8(b"") == 0x00
    assert P.crc8(b"K,1,1") == P.crc8(b"K,1,1")


def test_encode_capture_req_format():
    line = P.capture_req(1000, 1)
    assert line == b"#E,1000,CAPTURE_REQ,1*E0\n"


def test_roundtrip():
    for line in (P.capture_req(12345, 7), P.capture_ack(7, True), P.capture_ack(7, False)):
        fr = P.decode(line)
        assert fr is not None
        assert P.encode(fr.kind, *fr.fields) == line


def test_is_capture_req():
    assert P.is_capture_req(P.decode(P.capture_req(1, 3)))
    assert not P.is_capture_req(P.decode(P.capture_ack(3, True)))
    assert not P.is_capture_req(None)


def test_bad_crc_rejected_silently():
    good = P.capture_req(1000, 1)
    bad = good[:-3] + b"00\n"
    assert P.decode(bad) is None


def test_boot_log_garbage_ignored():
    for junk in (b"ESP-ROM:esp32s3-20210327\r\n", b"rst:0x1 (POWERON),boot:0x8\n",
                 b"", b"\xff\xfe\x00garbage", b"#", b"#E*", b"$K,1,1*ZZ\n"):
        assert P.decode(junk) is None


def test_field_with_star_or_newline_rejected():
    import pytest
    with pytest.raises(ValueError):
        P.encode("#", "E", "a*b")
    with pytest.raises(ValueError):
        P.encode("$", "K", "1\n")


def test_cmd_limits_frame():
    fr = P.decode(P.cmd_limits(7, 300, 2000))
    assert fr.kind == "$" and fr.type == "L" and fr.fields == ["L", "7", "300", "2000"]
