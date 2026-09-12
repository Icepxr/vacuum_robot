#!/usr/bin/env python3
"""
mrc_protocol.py — เฟรมข้อความ ESP32 ⇄ Pi 5 ตาม system_architecture.md §7 (ส่วนที่ใช้ในขั้น C)

รูปแบบบรรทัด (จบด้วย '\\n'):
    Pi5 → ESP32 : $<ฟิลด์>,<ฟิลด์>,...*CC
    ESP32 → Pi5 : #<ฟิลด์>,<ฟิลด์>,...*CC

CRC8 — นิยามที่ต้องตรงกับ src/robot/comm.cpp ทุกบิต:
    poly 0x07 · init 0x00 · ไม่ reflect · ไม่ xor-out
    คำนวณจาก **ทุกตัวอักษรหลัง sentinel ($ หรือ #) จนถึงก่อน '*'**
    CC = เลขฐานสิบหก 2 หลัก ตัวพิมพ์ใหญ่
    test vector: crc8(b"123456789") == 0xF4 (ค่า check มาตรฐานของ CRC-8) · crc8(b"E,1000,CAPTURE_REQ,1") == 0xE0
    ← ฝั่ง C++ (src/robot/comm.cpp) ต้องได้ค่าเดียวกัน

ข้อความที่นิยามแล้ว (C18 ปิด 12 ก.ย. 2026):
    #E,<ms>,CAPTURE_REQ,<n>*CC   ESP32 บอกว่าเสานิ่งแล้ว ถ่ายได้ · n = ลำดับครั้ง
    $K,<seq>,<1|0>*CC            Pi5 ตอบ: 1 = ภาพลง SD แล้ว · 0 = ล้ม · seq = n เดิม

ไฟล์นี้ไม่รู้จัก serial/กล้อง — ทดสอบได้ด้วย stdlib ล้วน (tests/test_protocol.py)
"""
from dataclasses import dataclass, field


def crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


@dataclass
class Frame:
    kind: str                       # '#' (จาก ESP32) หรือ '$' (จาก Pi5)
    fields: list = field(default_factory=list)   # ['E', '1000', 'CAPTURE_REQ', '1']

    @property
    def type(self) -> str:
        return self.fields[0] if self.fields else ""


def encode(kind: str, *fields) -> bytes:
    """สร้างบรรทัดพร้อม CRC และ '\\n' — ฟิลด์ห้ามมี ',' '*' หรือขึ้นบรรทัดใหม่"""
    assert kind in ("#", "$")
    body = ",".join(str(f) for f in fields)
    if any(ch in body for ch in ",*\r\n" if ch != ","):
        raise ValueError(f"ฟิลด์มีตัวอักษรต้องห้าม: {body!r}")
    return f"{kind}{body}*{crc8(body.encode('ascii')):02X}\n".encode("ascii")


def decode(line: bytes):
    """คืน Frame ถ้าบรรทัดถูกต้อง · คืน None ถ้าไม่ใช่เฟรม/CRC ผิด — **ไม่โยน exception**
    เพราะ ROM bootloader ของ ESP32 พ่น boot log ออก UART0 ทุกครั้งที่รีเซ็ต (§3.7 ข้อ 3)
    parser ต้องทิ้งเงียบๆ ไม่ใช่ crash"""
    try:
        s = line.decode("ascii").strip()
    except UnicodeDecodeError:
        return None
    if len(s) < 4 or s[0] not in "#$":
        return None
    star = s.rfind("*")
    if star < 1 or len(s) - star != 3:
        return None
    body, cc = s[1:star], s[star + 1:]
    try:
        want = int(cc, 16)
    except ValueError:
        return None
    if crc8(body.encode("ascii")) != want:
        return None
    return Frame(kind=s[0], fields=body.split(","))


# ── ตัวช่วยเฉพาะข้อความที่ใช้ในขั้น C ─────────────────────────

def capture_req(ms: int, n: int) -> bytes:
    return encode("#", "E", ms, "CAPTURE_REQ", n)


def capture_ack(seq: int, ok: bool) -> bytes:
    return encode("$", "K", seq, 1 if ok else 0)


def is_capture_req(fr: Frame) -> bool:
    return fr is not None and fr.kind == "#" and fr.type == "E" \
        and len(fr.fields) >= 4 and fr.fields[2] == "CAPTURE_REQ"
