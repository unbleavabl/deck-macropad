#!/usr/bin/env python3
"""Pack the keycap STLs into Bambu Studio 3MF projects, one plate each, centred on a
256 mm bed (P1S / X1 / A1). Every piece is its own object; a label is one object with
two parts, body on filament 1 (black) and legend on filament 2 (white), so the slicer
opens it ready to print with one colour swap. Printer, process and the two filament
slots (PLA Basic, black and white) come from bambu_p1s_settings.json, a project
config exported by Bambu Studio 2.8 for a P1S 0.4 with 0.20mm Standard, set to the
Textured PEI plate at 65 / 60 C (the export said Cool Plate, 35 C: thin labels warped). Run by
build.sh after the STLs.

    3mf/keycaps.3mf            the 12 caps, filament 1
    3mf/labels.3mf             the 12 labels, body filament 1 + legend filament 2
    3mf/fit_keycap_caps.3mf    the 3 fit-test caps
    3mf/fit_keycap_labels.3mf  the 3 fit-test labels, two colours
    3mf/labels_blank_white.3mf 12 plain labels on filament 2 (white), for the clear stickers
    3mf/glue_labels.3mf        12 glue-on labels for a bought flat cap (KeyCap v4), two
                               colours, ironing on every top surface (black and white), 3 mm brim
"""

import uuid
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STL = HERE / "stl"
OUT = HERE / "3mf"
BED = 256
SETTINGS = HERE / "bambu_p1s_settings.json"


def read_stl(path):
    """ASCII STL (OpenSCAD's) -> (vertices, triangles), shared vertices merged."""
    verts, index, tris, cur = [], {}, [], []
    for line in open(path):
        w = line.split()
        if w and w[0] == "vertex":
            v = tuple(float(x) for x in w[1:4])
            if v not in index:
                index[v] = len(verts)
                verts.append(v)
            cur.append(index[v])
            if len(cur) == 3:
                tris.append(tuple(cur))
                cur = []
    return verts, tris


def pieces(path):
    """Split an STL into its separate solids (connected by shared vertices)."""
    verts, tris = read_stl(path)
    parent = list(range(len(verts)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in tris:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    groups = {}
    for t in tris:
        groups.setdefault(find(t[0]), []).append(t)
    out = []
    for ts in groups.values():
        remap, vs = {}, []
        for t in ts:
            for i in t:
                if i not in remap:
                    remap[i] = len(vs)
                    vs.append(verts[i])
        out.append((vs, [tuple(remap[i] for i in t) for t in ts]))
    return out


def bbox(mesh):
    vs = mesh[0]
    return [min(v[k] for v in vs) for k in range(3)], [max(v[k] for v in vs) for k in range(3)]


def centre_xy(mesh):
    lo, hi = bbox(mesh)
    return ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)


def merge(meshes):
    vs, ts = [], []
    for m in meshes:
        n = len(vs)
        vs += m[0]
        ts += [(a + n, b + n, c + n) for a, b, c in m[1]]
    return vs, ts


def sort_grid(meshes):
    """Back row first, left to right (the order OpenSCAD laid them out in)."""
    return sorted(meshes, key=lambda m: (-round(centre_xy(m)[1]), centre_xy(m)[0]))


def labels_with_legends(body_stl, legend_stl):
    """Pair each label body with the legend pieces standing on it."""
    bodies = sort_grid(pieces(body_stl))
    legends = [[] for _ in bodies]
    for p in pieces(legend_stl):
        x, y = centre_xy(p)
        for i, b in enumerate(bodies):
            lo, hi = bbox(b)
            if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1]:
                legends[i].append(p)
                break
        else:
            raise SystemExit(f"legend piece at {x:.1f},{y:.1f} is on no label")
    return [(b, merge(l)) for b, l in zip(bodies, legends)]


def write_3mf(path, objects, object_settings=None):
    """objects: [(name, [(part name, mesh, filament)])], meshes in plate layout coords.
    The layout is centred on the bed; each object keeps its place. object_settings: process
    settings for every object ({key: value}, as in Bambu Studio's per-object settings)."""
    allv = [v for _, parts in objects for _, m, _ in parts for v in m[0]]
    shift = (BED / 2 - (min(v[0] for v in allv) + max(v[0] for v in allv)) / 2,
             BED / 2 - (min(v[1] for v in allv) + max(v[1] for v in allv)) / 2)
    z = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
    z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>
""")
    z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
""")
    ns = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
          'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
          'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p"')
    res, build, rels, settings, inst = [], [], [], [], []
    next_id = 1
    for n, (name, parts) in enumerate(objects):
        cx, cy = centre_xy(merge([m for _, m, _ in parts]))
        obj_file = f"3D/Objects/object_{n + 1}.model"
        part_xml, comps, part_cfg = [], [], []
        for pname, (vs, ts), fil in parts:
            pid = next_id
            next_id += 1
            v = "\n".join(f'     <vertex x="{x - cx:.5f}" y="{y - cy:.5f}" z="{zz:.5f}"/>' for x, y, zz in vs)
            t = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in ts)
            part_xml.append(f'  <object id="{pid}" p:UUID="{uuid.uuid4()}" type="model">\n   <mesh>\n    <vertices>\n{v}\n    </vertices>\n'
                            f'    <triangles>\n{t}\n    </triangles>\n   </mesh>\n  </object>')
            comps.append(f'    <component p:path="/{obj_file}" objectid="{pid}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>')
            part_cfg.append(f'    <part id="{pid}" subtype="normal_part">\n'
                            f'      <metadata key="name" value="{pname}"/>\n'
                            f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                            f'      <metadata key="extruder" value="{fil}"/>\n'
                            f'      <mesh_stat face_count="{len(ts)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
                            f'    </part>')
        z.writestr(obj_file, f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" {ns}>\n'
                             f' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n' + "\n".join(part_xml) +
                   '\n </resources>\n <build/>\n</model>\n')
        rels.append(f' <Relationship Target="/{obj_file}" Id="rel-{n + 1}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
        oid = next_id
        next_id += 1
        res.append(f'  <object id="{oid}" p:UUID="{uuid.uuid4()}" type="model">\n   <components>\n' + "\n".join(comps) + '\n   </components>\n  </object>')
        build.append(f'  <item objectid="{oid}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 {cx + shift[0]:.4f} {cy + shift[1]:.4f} 0" printable="1"/>')
        settings.append(f'  <object id="{oid}">\n    <metadata key="name" value="{name}"/>\n    <metadata key="extruder" value="{parts[0][2]}"/>\n'
                        + "".join(f'    <metadata key="{k}" value="{v}"/>\n' for k, v in (object_settings or {}).items())
                        + "\n".join(part_cfg) + '\n  </object>')
        inst.append(f'    <model_instance>\n      <metadata key="object_id" value="{oid}"/>\n      <metadata key="instance_id" value="0"/>\n'
                    f'      <metadata key="identify_id" value="{100 + n}"/>\n    </model_instance>')
    z.writestr("3D/3dmodel.model", f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" {ns}>\n'
                                   ' <metadata name="Application">BambuStudio-02.08.03.66</metadata>\n'
                                   ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
                                   f' <metadata name="Title">{path.stem}</metadata>\n'
                                   ' <resources>\n' + "\n".join(res) + '\n </resources>\n'
                                   f' <build p:UUID="{uuid.uuid4()}">\n' + "\n".join(build) + '\n </build>\n</model>\n')
    z.writestr("3D/_rels/3dmodel.model.rels", '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n' + "\n".join(rels) + '\n</Relationships>\n')
    z.writestr("Metadata/project_settings.config", SETTINGS.read_text())
    z.writestr("Metadata/model_settings.config", '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + "\n".join(settings) +
               '\n  <plate>\n    <metadata key="plater_id" value="1"/>\n'
               f'    <metadata key="plater_name" value="{path.stem}"/>\n    <metadata key="locked" value="false"/>\n'
               '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
               + "\n".join(inst) + '\n  </plate>\n</config>\n')
    z.close()
    print(f"== 3mf/{path.name}: {len(objects)} objects")


def main():
    OUT.mkdir(exist_ok=True)
    cap = pieces(STL / "keycaps/keycap.stl")
    assert len(cap) == 1
    # 12 caps, 4 x 3, 24 mm apart
    caps = []
    for i in range(12):
        dx, dy = (i % 4) * 24, -(i // 4) * 24
        vs = [(x + dx, y + dy, zz) for x, y, zz in cap[0][0]]
        caps.append((f"keycap {i + 1}", [("keycap", (vs, cap[0][1]), 1)]))
    write_3mf(OUT / "keycaps.3mf", caps)

    labels = labels_with_legends(STL / "keycaps/label_body.stl", STL / "keycaps/label_legend.stl")
    assert len(labels) == 12
    write_3mf(OUT / "labels.3mf", [(f"K{i + 1} label", [("body", b, 1), ("legend", l, 2)])
                                   for i, (b, l) in enumerate(labels)])

    blank = pieces(STL / "keycaps/label_blank.stl")
    assert len(blank) == 1
    blanks = []
    for i in range(12):
        dx, dy = (i % 3) * 18, -(i // 3) * 18
        vs = [(x + dx, y + dy, zz) for x, y, zz in blank[0][0]]
        blanks.append((f"blank label {i + 1}", [("label", (vs, blank[0][1]), 2)]))
    write_3mf(OUT / "labels_blank_white.3mf", blanks)

    glue = labels_with_legends(STL / "glue/glue_body.stl", STL / "glue/glue_legend.stl")
    assert len(glue) == 12
    write_3mf(OUT / "glue_labels.3mf", [(f"K{i + 1} glue label", [("body", b, 1), ("legend", l, 2)])
                                        for i, (b, l) in enumerate(glue)],
              {"ironing_type": "top", "brim_type": "outer_only", "brim_width": "3"})

    fit_caps = sorted(pieces(STL / "fit-tests/fit_keycap_caps.stl"), key=lambda m: centre_xy(m)[0])
    assert len(fit_caps) == 3
    write_3mf(OUT / "fit_keycap_caps.3mf", [(f"cap {i + 1} dot{'s' if i else ''} cross {4.0 + 0.1 * i:.1f} x {1.2 + 0.1 * i:.1f}", [("keycap", m, 1)])
                                            for i, m in enumerate(fit_caps)])

    fit_labels = labels_with_legends(STL / "fit-tests/fit_keycap_labels.stl", STL / "fit-tests/fit_keycap_legend.stl")
    fit_labels.sort(key=lambda bl: centre_xy(bl[0])[0])
    assert len(fit_labels) == 3
    write_3mf(OUT / "fit_keycap_labels.3mf", [(f"label {i + 1} dot{'s' if i else ''} clearance {0.05 * i:.2f}", [("body", b, 1), ("legend", l, 2)])
                                              for i, (b, l) in enumerate(fit_labels)])


if __name__ == "__main__":
    main()
