"""Export ทุก body ใน design ที่เปิดอยู่เป็น STL แยกไฟล์ โดยใช้พิกัดของ assembly (world)
ใช้คำนวณทางลม — ไฟล์ 08_การคำนวณ/16 §16.13
รัน: Fusion > Utilities > Add-Ins > Scripts and Add-Ins > (+) เลือกโฟลเดอร์นี้ > Run
"""
import adsk.core, adsk.fusion, os, traceback, json

BASE = os.path.expanduser('~/Documents/vacuum_project/05_CAD')


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('เปิด Asembly2 ใน workspace DESIGN ก่อน')
            return
        OUT = os.path.join(BASE, 'export_' + app.activeDocument.name.split(' v')[0].replace(' ', '_'))
        os.makedirs(OUT, exist_ok=True)
        em = design.exportManager
        root = design.rootComponent

        # ทั้งชิ้นรวมในไฟล์เดียว (ไว้เช็คว่าประกอบตรงกัน)
        opts = em.createSTLExportOptions(root, os.path.join(OUT, '_all.stl'))
        opts.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementMedium
        em.execute(opts)

        # รายชื่อ body + bbox ในพิกัด world (ไว้แยกก้อนใน _all.stl ว่าคือชิ้นไหน)
        # หมายเหตุ: ไม่ export STL รายชิ้นแล้ว — export จาก proxy ได้พิกัดของชิ้นเอง ไม่ใช่ world
        log = []
        for occ in root.allOccurrences:
            if not occ.isLightBulbOn:
                continue
            for i in range(occ.bRepBodies.count):
                b = occ.bRepBodies.item(i)
                if not b.isVisible:
                    continue
                bb = b.boundingBox
                log.append({'occ': occ.fullPathName, 'body': b.name,
                            'bbox_cm': [bb.minPoint.asArray(), bb.maxPoint.asArray()]})
        for i in range(root.bRepBodies.count):
            b = root.bRepBodies.item(i)
            if b.isVisible:
                bb = b.boundingBox
                log.append({'occ': '(root)', 'body': b.name,
                            'bbox_cm': [bb.minPoint.asArray(), bb.maxPoint.asArray()]})
        with open(os.path.join(OUT, '_bodies.json'), 'w') as f:
            json.dump(log, f, ensure_ascii=False, indent=1)
        ui.messageBox(f'export {len(log)} body → {OUT}')
    except Exception:
        if ui:
            ui.messageBox(traceback.format_exc())
