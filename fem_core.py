import re
import math
import numpy as np


SECTION_LIBRARY = {
    "W360x44": {"A": 0.00560, "Iy": 1.75e-4, "Iz": 3.10e-5, "J": 7.0e-7, "E": 200e9, "G": 77e9},
    "W310x60": {"A": 0.00765, "Iy": 1.95e-4, "Iz": 5.80e-5, "J": 1.1e-6, "E": 200e9, "G": 77e9},
    "W410x60": {"A": 0.00765, "Iy": 2.80e-4, "Iz": 4.20e-5, "J": 9.5e-7, "E": 200e9, "G": 77e9},
    "W460x74": {"A": 0.00940, "Iy": 4.20e-4, "Iz": 5.60e-5, "J": 1.4e-6, "E": 200e9, "G": 77e9},
    "W530x85": {"A": 0.01080, "Iy": 5.80e-4, "Iz": 6.80e-5, "J": 1.8e-6, "E": 200e9, "G": 77e9},
    "HSS203x203x9.5": {"A": 0.00720, "Iy": 4.50e-5, "Iz": 4.50e-5, "J": 7.0e-5, "E": 200e9, "G": 77e9},
}


def _fmt(value, nd=2):
    return f"{value:,.{nd}f}"


def parse_nodes_text(text):
    pattern = re.findall(r'(\d+)\s*\(\s*([^)]+)\)', text)
    if not pattern:
        raise ValueError("Wrong node format. Use: 1(0 0 0) 2(6 0 0)")

    nodes = {}
    for node_id_str, coord_text in pattern:
        node_id = int(node_id_str)
        parts = re.split(r'[\s,]+', coord_text.strip())
        parts = [p for p in parts if p]
        if len(parts) != 3:
            raise ValueError(f"Node {node_id} must have exactly 3 coordinates.")

        x, y, z = map(float, parts)
        if node_id in nodes:
            raise ValueError(f"Duplicate node id found: {node_id}")
        nodes[node_id] = (x, y, z)
    return nodes


def parse_members_text(text, nodes):
    pattern = re.findall(r'(\d+)\s*\(\s*(\d+)\s+(\d+)\s*\)', text)
    if not pattern:
        raise ValueError("Wrong member format. Use: 1(1 3) 2(2 4)")

    members = {}
    for mem_id_str, ni_str, nj_str in pattern:
        mem_id = int(mem_id_str)
        ni = int(ni_str)
        nj = int(nj_str)

        if mem_id in members:
            raise ValueError(f"Duplicate member id found: {mem_id}")
        if ni not in nodes or nj not in nodes:
            raise ValueError(f"Member {mem_id} uses undefined node(s).")
        if ni == nj:
            raise ValueError(f"Member {mem_id} cannot connect a node to itself.")

        members[mem_id] = (ni, nj)
    return members


def parse_supports_text(text, nodes):
    parts = text.replace(",", " ").split()
    if len(parts) < 2 or len(parts) % 2 != 0:
        raise ValueError("Wrong support format. Use pairs like: 1 fixed 2 pinned")

    supports = {}
    for i in range(0, len(parts), 2):
        node_id = int(parts[i])
        support_type = parts[i + 1].strip().lower()

        if node_id not in nodes:
            raise ValueError(f"Support references undefined node {node_id}")
        if support_type not in ["fixed", "pinned"]:
            raise ValueError(f"Node {node_id} has invalid support type '{support_type}'")

        supports[node_id] = support_type
    return supports


def parse_nodal_loads_text(text, nodes):
    pattern = re.findall(r'(\d+)\s*\(\s*([^)]+)\)', text)
    if not pattern:
        raise ValueError("Wrong nodal load format. Use: 3(0 0 -50 0 0 0)")

    loads = {}
    for node_id_str, vals_text in pattern:
        node_id = int(node_id_str)
        if node_id not in nodes:
            raise ValueError(f"Load references undefined node {node_id}")

        parts = re.split(r'[\s,]+', vals_text.strip())
        parts = [p for p in parts if p]
        if len(parts) != 6:
            raise ValueError(f"Nodal load for node {node_id} must have 6 values.")

        vals = tuple(map(float, parts))
        loads[node_id] = vals
    return loads


def parse_section_setup_text(text):
    parts = text.replace(",", " ").split()
    if len(parts) < 2 or len(parts) % 2 != 0:
        raise ValueError("Wrong section setup. Use: beam W360x44 column W310x60 brace HSS203x203x9.5")

    out = {}
    for i in range(0, len(parts), 2):
        family = parts[i].strip().lower()
        sec = parts[i + 1].strip()

        if family not in ["beam", "column", "brace"]:
            raise ValueError(f"Unknown family '{family}'. Use beam, column, or brace.")
        if sec not in SECTION_LIBRARY:
            raise ValueError(f"Section '{sec}' is not in the library.")

        out[family] = sec

    out.setdefault("beam", "W360x44")
    out.setdefault("column", "W310x60")
    out.setdefault("brace", "HSS203x203x9.5")
    return out


def update_nodes(existing_nodes, edit_text):
    edits = parse_nodes_text(edit_text)
    new_nodes = dict(existing_nodes)

    for node_id, coords in edits.items():
        if node_id not in new_nodes:
            raise ValueError(f"Cannot edit undefined node {node_id}")
        new_nodes[node_id] = coords
    return new_nodes


def classify_member(node_i, node_j, tol=1e-8):
    x1, y1, z1 = node_i
    x2, y2, z2 = node_j

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    dz = abs(z2 - z1)

    if dx <= tol and dy <= tol and dz > tol:
        return "column"
    if dz <= tol and (dx > tol or dy > tol):
        return "beam"
    return "brace"


def member_length(node_i, node_j):
    x1, y1, z1 = node_i
    x2, y2, z2 = node_j
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)


def get_levels(nodes):
    return sorted({round(coords[2], 6) for coords in nodes.values()})


def dof_map(node_ids):
    mapping = {}
    for idx, nid in enumerate(sorted(node_ids)):
        base = idx * 6
        mapping[nid] = [base + i for i in range(6)]
    return mapping


def local_frame_stiffness(E, G, A, Iy, Iz, J, L):
    if L <= 0:
        raise ValueError("Zero or negative member length.")

    k = np.zeros((12, 12), dtype=float)

    EA_L = E * A / L
    GJ_L = G * J / L
    EIy = E * Iy
    EIz = E * Iz
    L2 = L * L
    L3 = L2 * L

    k[0, 0] = EA_L
    k[0, 6] = -EA_L
    k[6, 0] = -EA_L
    k[6, 6] = EA_L

    k[3, 3] = GJ_L
    k[3, 9] = -GJ_L
    k[9, 3] = -GJ_L
    k[9, 9] = GJ_L

    kz = np.array([
        [12 * EIz / L3,  6 * EIz / L2, -12 * EIz / L3,  6 * EIz / L2],
        [ 6 * EIz / L2,  4 * EIz / L,  -6 * EIz / L2,  2 * EIz / L ],
        [-12 * EIz / L3, -6 * EIz / L2, 12 * EIz / L3, -6 * EIz / L2],
        [ 6 * EIz / L2,  2 * EIz / L,  -6 * EIz / L2,  4 * EIz / L ],
    ])

    ky = np.array([
        [12 * EIy / L3, -6 * EIy / L2, -12 * EIy / L3, -6 * EIy / L2],
        [-6 * EIy / L2,  4 * EIy / L,   6 * EIy / L2,  2 * EIy / L ],
        [-12 * EIy / L3,  6 * EIy / L2, 12 * EIy / L3,  6 * EIy / L2],
        [-6 * EIy / L2,  2 * EIy / L,   6 * EIy / L2,  4 * EIy / L ],
    ])

    dofs_z = [1, 5, 7, 11]
    dofs_y = [2, 4, 8, 10]

    for i in range(4):
        for j in range(4):
            k[dofs_z[i], dofs_z[j]] += kz[i, j]
            k[dofs_y[i], dofs_y[j]] += ky[i, j]

    return k


def element_rotation_matrix(node_i, node_j):
    xi = np.array(node_i, dtype=float)
    xj = np.array(node_j, dtype=float)

    vx = xj - xi
    L = np.linalg.norm(vx)
    if L <= 0:
        raise ValueError("Zero length element.")
    ex = vx / L

    ref = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(ex, ref)) > 0.95:
        ref = np.array([0.0, 1.0, 0.0])

    ey = np.cross(ref, ex)
    ey_norm = np.linalg.norm(ey)
    if ey_norm <= 0:
        raise ValueError("Failed to build local axis.")
    ey = ey / ey_norm

    ez = np.cross(ex, ey)
    ez = ez / np.linalg.norm(ez)

    R = np.vstack([ex, ey, ez])
    return R, L


def transformation_12x12(R):
    T = np.zeros((12, 12), dtype=float)
    for block in [0, 3, 6, 9]:
        T[block:block + 3, block:block + 3] = R
    return T


def build_global_load_vector(node_ids, dofs, nodal_loads):
    ndof = len(node_ids) * 6
    F = np.zeros(ndof, dtype=float)

    for nid, vals in nodal_loads.items():
        fx, fy, fz, mx, my, mz = vals
        idx = dofs[nid]
        vec = np.array([fx, fy, fz, mx, my, mz], dtype=float)
        vec[:3] *= 1e3
        vec[3:] *= 1e3
        F[idx] += vec

    return F


def restrained_dofs_from_supports(dofs, supports):
    restrained = []
    for nid, stype in supports.items():
        nd = dofs[nid]
        if stype == "fixed":
            restrained.extend(nd)
        elif stype == "pinned":
            restrained.extend(nd[:3])
    return sorted(set(restrained))


def recommend_beam_section(max_moment_kNm, max_shear_kN):
    if max_moment_kNm <= 60 and max_shear_kN <= 50:
        return "W360x44"
    if max_moment_kNm <= 160 and max_shear_kN <= 100:
        return "W410x60"
    if max_moment_kNm <= 300 and max_shear_kN <= 180:
        return "W460x74"
    return "W530x85"


def recommend_column_section(max_moment_kNm, max_shear_kN):
    """Map to sections present in SECTION_LIBRARY only."""
    if max_moment_kNm <= 80 and max_shear_kN <= 60:
        return "W310x60"
    if max_moment_kNm <= 200 and max_shear_kN <= 110:
        return "W410x60"
    if max_moment_kNm <= 350 and max_shear_kN <= 180:
        return "W460x74"
    return "W530x85"


def drift_denominator_for_code(building_code: str) -> float:
    code = (building_code or "US").strip().upper()
    if code in ("CANADA", "CA", "NBC"):
        return 500.0
    if code in ("PHILIPPINES", "PH", "NSCP"):
        return 400.0
    return 400.0


def drift_limit_mm_for_height(total_height_m: float, building_code: str) -> float:
    if total_height_m <= 0:
        return 0.0
    d = drift_denominator_for_code(building_code)
    return (total_height_m * 1000.0) / d


def group_members_by_forces(rows, member_type):
    if not rows:
        return [], {}

    rows = sorted(rows, key=lambda r: (r["moment_max_kNm"], r["shear_max_kN"]))
    groups = []
    mapping = {}

    if member_type == "beam":
        m_ratio = 0.20
        v_ratio = 0.20
        prefix = "BG"
    else:
        m_ratio = 0.25
        v_ratio = 0.25
        prefix = "CG"

    for row in rows:
        placed = False
        for g in groups:
            m_ok = row["moment_max_kNm"] <= g["max_moment_kNm"] * (1 + m_ratio) if g["max_moment_kNm"] > 0 else True
            v_ok = row["shear_max_kN"] <= g["max_shear_kN"] * (1 + v_ratio) if g["max_shear_kN"] > 0 else True
            if m_ok and v_ok:
                g["members"].append(row["member_id"])
                g["max_moment_kNm"] = max(g["max_moment_kNm"], row["moment_max_kNm"])
                g["max_shear_kN"] = max(g["max_shear_kN"], row["shear_max_kN"])
                mapping[row["member_id"]] = g["group"]
                placed = True
                break

        if not placed:
            gname = f"{prefix}{len(groups) + 1}"
            groups.append({
                "group": gname,
                "members": [row["member_id"]],
                "max_moment_kNm": row["moment_max_kNm"],
                "max_shear_kN": row["shear_max_kN"],
            })
            mapping[row["member_id"]] = gname

    for g in groups:
        if member_type == "beam":
            g["recommended_section"] = recommend_beam_section(g["max_moment_kNm"], g["max_shear_kN"])
        else:
            g["recommended_section"] = recommend_column_section(g["max_moment_kNm"], g["max_shear_kN"])

    return groups, mapping


def get_ai_context_from_result(result):
    if not result or not result.get("ok"):
        return "No analysis result available."

    r = result["results"]
    code = result.get("building_code") or "US"
    return (
        f"Current model summary:\n"
        f"- Building code (drift basis): {code}\n"
        f"- Roof displacement: {_fmt(r['roof_disp_mm'])} mm\n"
        f"- Drift limit: {_fmt(r['drift_limit_mm'])} mm\n"
        f"- Drift result: {r['drift_result']}\n"
        f"- Beam groups: {len(r['beam_groups'])}\n"
        f"- Column groups: {len(r['column_groups'])}\n"
        f"- Reaction nodes: {len(r['support_reactions'])}\n"
        f"- Members with FEM forces: {len(r['member_forces'])}\n"
    )


def charts_payload_from_result(result):
    """Plotly-friendly series for the browser."""
    if not result or not result.get("ok"):
        return None
    r = result["results"]
    mf = r.get("member_forces") or []
    beams = [x for x in mf if x.get("type") == "beam"]
    cols = [x for x in mf if x.get("type") == "column"]
    return {
        "level_curve": {
            "z_levels_m": r.get("z_levels") or [],
            "max_abs_ux_mm": r.get("level_displacements_mm") or [],
        },
        "beam_moments": {
            "ids": [f"M{x['member_id']}" for x in beams],
            "moment_kNm": [x["moment_max_kNm"] for x in beams],
        },
        "column_moments": {
            "ids": [f"M{x['member_id']}" for x in cols],
            "moment_kNm": [x["moment_max_kNm"] for x in cols],
        },
        "reactions": {
            "nodes": [x["node"] for x in r.get("support_reactions") or []],
            "Fz_kN": [x["Fz_kN"] for x in r.get("support_reactions") or []],
        },
    }


def etabs_style_export_text(nodes, members, supports, nodal_loads, family_sections):
    """Human-readable model snapshot useful for manual ETABS entry (not a binary .edb)."""
    lines = [
        "ETABS / SAP2000 style snapshot (manual entry reference)",
        "Units implied: meters, kilonewtons, kilonewton-meters where applicable.",
        "",
        "TABLE: JOINT COORDINATES",
    ]
    for nid in sorted(nodes.keys()):
        x, y, z = nodes[nid]
        lines.append(f"  Joint={nid}  X={x:g}  Y={y:g}  Z={z:g}")
    lines.extend(["", "TABLE: CONNECTIVITY - FRAME"])
    for mid in sorted(members.keys()):
        ni, nj = members[mid]
        lines.append(f"  Frame={mid}  JointI={ni}  JointJ={nj}")
    lines.extend(["", "TABLE: RESTRAINTS (fixed=all, pinned=translations only in app)"])
    for nid in sorted(supports.keys()):
        lines.append(f"  Joint={nid}  Type={supports[nid]}")
    lines.extend(["", "TABLE: JOINT LOADS - FORCE"])
    for nid in sorted(nodal_loads.keys()):
        fx, fy, fz, mx, my, mz = nodal_loads[nid]
        lines.append(
            f"  Joint={nid}  Fx={fx:g} Fy={fy:g} Fz={fz:g} Mx={mx:g} My={my:g} Mz={mz:g}  (kN, kNm as entered)"
        )
    lines.extend(["", "TABLE: ASSIGNED SECTIONS (by member family in solver)"])
    lines.append(f"  beam={family_sections.get('beam')}  column={family_sections.get('column')}  brace={family_sections.get('brace')}")
    return "\n".join(lines)


def analyze_structure(nodes, members, supports, nodal_loads, family_sections, building_code="US"):
    if not nodes:
        return {"ok": False, "message": "No nodes defined."}
    if not members:
        return {"ok": False, "message": "No members defined."}
    if not supports:
        return {"ok": False, "message": "No supports defined."}

    dofs = dof_map(nodes.keys())
    node_order = sorted(nodes.keys())
    ndof = len(node_order) * 6
    K = np.zeros((ndof, ndof), dtype=float)

    element_store = {}
    member_rows = []

    for mem_id, (ni, nj) in sorted(members.items()):
        ni_xyz = nodes[ni]
        nj_xyz = nodes[nj]
        mtype = classify_member(ni_xyz, nj_xyz)

        section_name = family_sections.get(mtype, family_sections.get("beam"))
        if section_name not in SECTION_LIBRARY:
            return {"ok": False, "message": f"Section '{section_name}' not found in library."}

        sec = SECTION_LIBRARY[section_name]
        R, L = element_rotation_matrix(ni_xyz, nj_xyz)
        T = transformation_12x12(R)
        k_local = local_frame_stiffness(sec["E"], sec["G"], sec["A"], sec["Iy"], sec["Iz"], sec["J"], L)
        k_global = T.T @ k_local @ T

        edofs = dofs[ni] + dofs[nj]
        for a in range(12):
            for b in range(12):
                K[edofs[a], edofs[b]] += k_global[a, b]

        element_store[mem_id] = {
            "ni": ni,
            "nj": nj,
            "type": mtype,
            "length_m": L,
            "section": section_name,
            "T": T,
            "k_local": k_local,
            "edofs": edofs,
        }

    F = build_global_load_vector(node_order, dofs, nodal_loads)
    restrained = restrained_dofs_from_supports(dofs, supports)
    free = [i for i in range(ndof) if i not in restrained]

    if not free:
        return {"ok": False, "message": "All DOFs are restrained. The model cannot solve."}

    Kff = K[np.ix_(free, free)]
    Ff = F[free]

    try:
        df = np.linalg.solve(Kff, Ff)
    except np.linalg.LinAlgError:
        return {"ok": False, "message": "The FEM stiffness matrix is singular. The model is unstable or under-supported."}

    d = np.zeros(ndof, dtype=float)
    d[free] = df
    reactions = K @ d - F

    for mem_id, est in element_store.items():
        edofs = est["edofs"]
        u_global = d[edofs]
        u_local = est["T"] @ u_global
        f_local = est["k_local"] @ u_local

        shear_max_kN = max(abs(f_local[1]), abs(f_local[2]), abs(f_local[7]), abs(f_local[8])) / 1e3
        moment_max_kNm = max(abs(f_local[4]), abs(f_local[5]), abs(f_local[10]), abs(f_local[11])) / 1e3
        axial_max_kN = max(abs(f_local[0]), abs(f_local[6])) / 1e3

        member_rows.append({
            "member_id": mem_id,
            "start_node": est["ni"],
            "end_node": est["nj"],
            "type": est["type"],
            "section": est["section"],
            "length_m": est["length_m"],
            "axial_max_kN": axial_max_kN,
            "shear_max_kN": shear_max_kN,
            "moment_max_kNm": moment_max_kNm,
        })

    beam_rows = [r for r in member_rows if r["type"] == "beam"]
    column_rows = [r for r in member_rows if r["type"] == "column"]

    beam_groups, beam_map = group_members_by_forces(beam_rows, "beam")
    column_groups, column_map = group_members_by_forces(column_rows, "column")

    for row in member_rows:
        if row["type"] == "beam":
            row["group"] = beam_map.get(row["member_id"], "-")
        elif row["type"] == "column":
            row["group"] = column_map.get(row["member_id"], "-")
        else:
            row["group"] = "BR-1"

    disp_rows = []
    z_levels = get_levels(nodes)
    level_disp_mm = []

    for z in z_levels:
        level_nodes = [nid for nid, xyz in nodes.items() if round(xyz[2], 6) == round(z, 6)]
        ux_vals = [d[dofs[nid][0]] * 1000.0 for nid in level_nodes]
        max_abs_ux = max((abs(v) for v in ux_vals), default=0.0)
        level_disp_mm.append(max_abs_ux)

    roof_disp_mm = max(level_disp_mm) if level_disp_mm else 0.0
    total_height_m = max((xyz[2] for xyz in nodes.values()), default=0.0) - min((xyz[2] for xyz in nodes.values()), default=0.0)
    drift_limit_mm = drift_limit_mm_for_height(total_height_m, building_code)
    drift_result = "PASS" if roof_disp_mm <= drift_limit_mm else "FAIL"

    for nid in node_order:
        idx = dofs[nid]
        ux, uy, uz, rx, ry, rz = d[idx]
        disp_rows.append({
            "node": nid,
            "ux_mm": ux * 1000.0,
            "uy_mm": uy * 1000.0,
            "uz_mm": uz * 1000.0,
            "rx_rad": rx,
            "ry_rad": ry,
            "rz_rad": rz,
        })

    reaction_rows = []
    for nid in sorted(supports):
        idx = dofs[nid]
        reaction_rows.append({
            "node": nid,
            "Fx_kN": reactions[idx[0]] / 1e3,
            "Fy_kN": reactions[idx[1]] / 1e3,
            "Fz_kN": reactions[idx[2]] / 1e3,
            "Mx_kNm": reactions[idx[3]] / 1e3,
            "My_kNm": reactions[idx[4]] / 1e3,
            "Mz_kNm": reactions[idx[5]] / 1e3,
        })

    beam_group_text = "\n".join(
        f"{g['group']}: members {g['members']} | Mmax={_fmt(g['max_moment_kNm'])} kNm | "
        f"Vmax={_fmt(g['max_shear_kN'])} kN | section {g['recommended_section']}"
        for g in beam_groups
    ) or "No beam groups identified."

    column_group_text = "\n".join(
        f"{g['group']}: members {g['members']} | Mmax={_fmt(g['max_moment_kNm'])} kNm | "
        f"Vmax={_fmt(g['max_shear_kN'])} kN | section {g['recommended_section']}"
        for g in column_groups
    ) or "No column groups identified."

    dcode = drift_denominator_for_code(building_code)
    summary = f"""
FULL FEM FRAME ANALYSIS SUMMARY

1. MODEL
Nodes                : {len(nodes)}
Members              : {len(members)}
Supports             : {len(supports)}
Drift basis          : building code {building_code} (height / {int(dcode)})

2. GLOBAL RESPONSE
Roof Displacement    : {_fmt(roof_disp_mm)} mm
Allowable Drift      : {_fmt(drift_limit_mm)} mm
Drift Result         : {drift_result}

3. PRACTICAL BEAM GROUPS
{beam_group_text}

4. PRACTICAL COLUMN GROUPS
{column_group_text}

5. NOTE
This run uses real 3D frame FEM stiffness analysis and actual member end forces for grouping.
""".strip()

    return {
        "ok": True,
        "message": summary,
        "building_code": building_code,
        "inputs": {
            "nodes": nodes,
            "members": members,
            "supports": supports,
            "nodal_loads": nodal_loads,
            "family_sections": family_sections,
        },
        "results": {
            "roof_disp_mm": roof_disp_mm,
            "drift_limit_mm": drift_limit_mm,
            "drift_result": drift_result,
            "level_displacements_mm": level_disp_mm,
            "z_levels": z_levels,
            "node_displacements": disp_rows,
            "support_reactions": reaction_rows,
            "member_forces": member_rows,
            "beam_groups": beam_groups,
            "column_groups": column_groups,
            "total_height_m": total_height_m,
        }
    }


def report_sections(result, materials=None, brain_line=""):
    """Structured blocks for the UI (analysis vs design vs narrative)."""
    materials = materials or {}
    fc = materials.get("fc_MPa")
    fy = materials.get("fy_MPa")
    sbc = materials.get("sbc_kPa")
    mat_parts = []
    if fc is not None:
        mat_parts.append(f"f'c = {fc} MPa")
    if fy is not None:
        mat_parts.append(f"fy = {fy} MPa")
    if sbc is not None:
        mat_parts.append(f"SBC = {sbc} kPa")
    mat_line = "; ".join(mat_parts) if mat_parts else "Not specified (add fc, fy, SBC in the sidebar)."

    if not result or not result.get("ok"):
        return {
            "summary": "No successful FEM run yet.",
            "analysis": "",
            "design": "",
            "recommendation": brain_line or "",
            "conclusion": "Build or load a model, then run analysis.",
            "materials_line": mat_line,
        }

    r = result["results"]
    code = result.get("building_code") or "US"
    mf = r.get("member_forces") or []
    top_beams = sorted(
        [x for x in mf if x.get("type") == "beam"],
        key=lambda x: x.get("moment_max_kNm") or 0,
        reverse=True,
    )[:6]
    top_cols = sorted(
        [x for x in mf if x.get("type") == "column"],
        key=lambda x: x.get("moment_max_kNm") or 0,
        reverse=True,
    )[:6]

    def _line(m):
        return (
            f"M{m['member_id']} ({m['start_node']}-{m['end_node']}) "
            f"type={m['type']} section={m['section']} "
            f"|M|max={_fmt(m['moment_max_kNm'])} kNm Vmax={_fmt(m['shear_max_kN'])} kN "
            f"Pmax={_fmt(m['axial_max_kN'])} kN group={m.get('group', '-')}"
        )

    analysis_body = "\n".join(_line(m) for m in top_beams + top_cols) or "No beam/column lines parsed."

    bg = r.get("beam_groups") or []
    cg = r.get("column_groups") or []
    design_lines = []
    for g in bg:
        design_lines.append(
            f"{g['group']}: {len(g['members'])} members → suggested section {g['recommended_section']} "
            f"(|M|max={_fmt(g['max_moment_kNm'])} kNm, Vmax={_fmt(g['max_shear_kN'])} kN)"
        )
    for g in cg:
        design_lines.append(
            f"{g['group']}: {len(g['members'])} members → suggested section {g['recommended_section']} "
            f"(|M|max={_fmt(g['max_moment_kNm'])} kNm, Vmax={_fmt(g['max_shear_kN'])} kN)"
        )
    design_text = "\n".join(design_lines) if design_lines else "No grouped design lines."

    summary = (
        f"Materials (sidebar): {mat_line}\n\n"
        f"Code drift basis: {code} (height / {int(drift_denominator_for_code(code))}). "
        f"Roof displacement {_fmt(r['roof_disp_mm'])} mm vs limit {_fmt(r['drift_limit_mm'])} mm → {r['drift_result']}. "
        f"{len(mf)} members, {len(bg)} beam groups, {len(cg)} column groups."
    )

    rec_parts = [
        "Verify load combinations and accidental torsion in ETABS; this app uses a single linear nodal-load case.",
        "Match section groups in ETABS to the suggested W-shapes; re-run P-Δ if slenderness demands it.",
    ]
    if r["drift_result"] != "PASS":
        rec_parts.insert(0, "Drift check failed for the selected code basis—increase lateral stiffness or revisit loads.")
    if brain_line:
        rec_parts.append(brain_line)

    conclusion = (
        f"Linear 3D frame FEM is consistent for initial sizing. "
        f"Drift: {r['drift_result']}. "
        f"Export the ETABS snapshot and rebuild the same topology for code checks ({code})."
    )

    return {
        "summary": summary,
        "analysis": f"Governing member envelopes (sample):\n{analysis_body}",
        "design": f"Grouped design (FEM-based suggestions):\n{design_text}",
        "recommendation": "\n".join(f"• {p}" for p in rec_parts),
        "conclusion": conclusion,
        "materials_line": mat_line,
    }