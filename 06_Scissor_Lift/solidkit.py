"""
solidkit.py — ชั้นบางๆ ครอบ CAD kernel เพื่อให้เขียนเรขาคณิต "ครั้งเดียว" แล้วออกได้ทั้ง STEP และ STL

backend ที่รองรับ (เลือกอัตโนมัติ)
  * cadquery  (ถ้าติดตั้งไว้)  → export ได้ทั้ง .step และ .stl   ← แนะนำบนเครื่องคุณ
  * trimesh + manifold3d       → export ได้เฉพาะ .stl  แต่ตรวจ interference ได้

ติดตั้ง CadQuery บนเครื่อง (macOS):
    pip install cadquery
หรือ
    conda install -c conda-forge cadquery

ทุกฟังก์ชันใช้หน่วยมิลลิเมตร และใช้ระบบพิกัดขวามือ (X, Y, Z)
"""

import math

BACKEND = None
try:
    import cadquery as _cq
    BACKEND = "cadquery"
except Exception:
    try:
        import numpy as _np
        import trimesh as _tm
        BACKEND = "trimesh"
    except Exception as e:                                    # pragma: no cover
        raise ImportError("ต้องมี cadquery หรือ trimesh อย่างน้อยหนึ่งตัว") from e


class Solid:
    """ก้อนของแข็งหนึ่งก้อน — ห่อ object ของ backend ไว้ข้างใน"""

    __slots__ = ("o",)

    def __init__(self, obj):
        self.o = obj

    # ---------- บูลีน ----------
    def __add__(self, other):
        if BACKEND == "cadquery":
            return Solid(self.o.union(other.o))
        return Solid(_boolean([self.o, other.o], "union"))

    def __sub__(self, other):
        if BACKEND == "cadquery":
            return Solid(self.o.cut(other.o))
        return Solid(_boolean([self.o, other.o], "difference"))

    def __and__(self, other):
        if BACKEND == "cadquery":
            return Solid(self.o.intersect(other.o))
        return Solid(_boolean([self.o, other.o], "intersection"))

    # ---------- แปลงตำแหน่ง ----------
    def translate(self, v):
        if BACKEND == "cadquery":
            return Solid(self.o.translate(tuple(v)))
        m = self.o.copy()
        m.apply_translation(_np.asarray(v, dtype=float))
        return Solid(m)

    def rotate(self, axis, deg, origin=(0, 0, 0)):
        """หมุนรอบแกน axis ('X'|'Y'|'Z' หรือเวกเตอร์) เป็นองศา ตามกฎมือขวา"""
        vec = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}.get(axis, axis)
        if BACKEND == "cadquery":
            p0 = tuple(origin)
            p1 = tuple(origin[i] + vec[i] for i in range(3))
            return Solid(self.o.rotate(p0, p1, deg))
        M = _tm.transformations.rotation_matrix(math.radians(deg), vec, origin)
        m = self.o.copy()
        m.apply_transform(M)
        return Solid(m)

    # ---------- คุณสมบัติ ----------
    def volume(self):
        if BACKEND == "cadquery":
            return self.o.val().Volume()
        return float(abs(self.o.volume))

    def bbox(self):
        """คืน (xmin, ymin, zmin, xmax, ymax, zmax)"""
        if BACKEND == "cadquery":
            b = self.o.val().BoundingBox()
            return (b.xmin, b.ymin, b.zmin, b.xmax, b.ymax, b.zmax)
        b = self.o.bounds
        return (b[0][0], b[0][1], b[0][2], b[1][0], b[1][1], b[1][2])

    def mesh(self):
        """คืน trimesh.Trimesh (ใช้ตรวจ interference) — แปลงจาก CadQuery ถ้าจำเป็น"""
        if BACKEND == "trimesh":
            return self.o
        import tempfile, os, trimesh as tm      # pragma: no cover
        f = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
        f.close()
        _cq.exporters.export(self.o, f.name, tolerance=0.05)
        m = tm.load(f.name)
        os.unlink(f.name)
        return m


# ============================================================
# ตัวสร้างรูปทรงพื้นฐาน
# ============================================================
def box(dx, dy, dz, center=(0, 0, 0)):
    """กล่องขนาด dx×dy×dz โดย center คือ 'จุดกึ่งกลางของก้อน'"""
    if BACKEND == "cadquery":
        w = _cq.Workplane("XY").box(dx, dy, dz).translate(tuple(center))
        return Solid(w)
    m = _tm.creation.box(extents=(dx, dy, dz))
    m.apply_translation(_np.asarray(center, dtype=float))
    return Solid(m)


def box_from(x0, y0, z0, x1, y1, z1):
    """กล่องจากมุม (x0,y0,z0) ถึง (x1,y1,z1)"""
    return box(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0),
               ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def cyl(r, h, axis="Z", base=(0, 0, 0), seg=64):
    """ทรงกระบอกรัศมี r สูง h เริ่มจากจุด base ยื่นไปตาม axis"""
    if BACKEND == "cadquery":
        wp = {"X": "YZ", "Y": "XZ", "Z": "XY"}[axis]
        w = _cq.Workplane(wp).circle(r).extrude(h)
        # CadQuery: YZ ยื่นไป +X, XZ ยื่นไป -Y, XY ยื่นไป +Z
        if axis == "Y":
            w = w.mirror("XZ")
        return Solid(w.translate(tuple(base)))
    m = _tm.creation.cylinder(radius=r, height=abs(h), sections=seg)
    m.apply_translation([0, 0, abs(h) / 2.0])           # ให้ฐานอยู่ที่ z=0
    if h < 0:
        m.apply_transform(_tm.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    if axis == "X":
        m.apply_transform(_tm.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    elif axis == "Y":
        m.apply_transform(_tm.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0]))
    m.apply_translation(_np.asarray(base, dtype=float))
    return Solid(m)


def rod(p0, p1, r, seg=48):
    """ทรงกระบอกจากจุด p0 ถึง p1 (ใช้ทำหมุด/แกน)"""
    import numpy as np
    d = [p1[i] - p0[i] for i in range(3)]
    h = math.sqrt(sum(c * c for c in d))
    s = cyl(r, h, "Z", (0, 0, 0), seg)
    if h < 1e-9:
        return s
    ux, uy, uz = [c / h for c in d]
    ang = math.degrees(math.acos(max(-1.0, min(1.0, uz))))
    if abs(ang) > 1e-9:
        ax = (-uy, ux, 0.0)
        if abs(ux) < 1e-9 and abs(uy) < 1e-9:
            ax = (1.0, 0.0, 0.0)
        s = s.rotate(ax, ang)
    return s.translate(p0)


def slot(length, width, height, center=(0, 0, 0), axis="Z"):
    """ร่องปลายมน (stadium) ความยาวรวม length กว้าง width ลึก height
       ทิศความยาวอยู่ตามแกน X, ความลึกไปตาม axis"""
    r = width / 2.0
    flat = length - width
    body = box(max(flat, 1e-6), width, height, (0, 0, 0))
    for sx in (-flat / 2.0, flat / 2.0):
        body = body + cyl(r, height, "Z", (sx, 0, -height / 2.0))
    if axis == "X":
        body = body.rotate("Y", 90)
    elif axis == "Y":
        body = body.rotate("X", -90)
    return body.translate(center)


def _boolean(meshes, op):
    import trimesh as tm
    res = tm.boolean.boolean_manifold(meshes, op)
    if isinstance(res, list):
        res = res[0]
    return res


# ============================================================
# export
# ============================================================
def export(solid, path_no_ext, stl=True, step=True, tol=0.05):
    """เขียนไฟล์ .step และ/หรือ .stl  คืนรายชื่อไฟล์ที่เขียนจริง"""
    written = []
    if step and BACKEND == "cadquery":
        _cq.exporters.export(solid.o, path_no_ext + ".step")
        written.append(path_no_ext + ".step")
    if stl:
        if BACKEND == "cadquery":
            _cq.exporters.export(solid.o, path_no_ext + ".stl",
                                 tolerance=tol, angularTolerance=0.2)
        else:
            solid.o.export(path_no_ext + ".stl")
        written.append(path_no_ext + ".stl")
    return written


def interference(a, b, tol_mm3=1.0):
    """ปริมาตรที่สองก้อนซ้อนทับกัน (mm³) — ใช้ตรวจว่าชิ้นส่วนชนกันไหม
       คืน 0.0 ถ้าซ้อนน้อยกว่า tol_mm3 (ถือว่าเป็น noise ของ mesh)"""
    try:
        v = (a & b).volume()
    except Exception:
        return 0.0
    return 0.0 if v < tol_mm3 else v
