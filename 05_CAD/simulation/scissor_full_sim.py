"""Analytical simulation tied to the 2026-10-02 scissor CAD exports.

This is not a replacement for contact/nonlinear FEA.  It covers the portions
that can be verified from the exported STL/STEP geometry: kinematics, stow
clearance, virtual-work servo torque, first-order link/pin checks, and robot
tip stability sensitivity.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


G = 9.81
PETG_ALLOW_MPA = 15.0  # project estimate, not a coupon-test result
PETG_E_MPA = 2000.0
JOINT_EFFICIENCY = 0.65  # project estimate inherited from prior analyses
SERVO_STICTION_NM = 0.05
SERVO_5V_NM = 9.4 * 0.0980665  # project estimate; datasheet does not specify 5 V
SERVO_6V_NM = 11.0 * 0.0980665  # project datasheet value
LOAD_PATHS = 2
PIN_DIAMETER_MM = 3.0
LINK_THICKNESS_MM = 5.4
TARGET_STOW_MM = 100.0
TARGET_EXTENDED_MM = 550.0
DESIRED_CLEARANCE_MM = 0.4


@dataclass(frozen=True)
class Link:
    name: str
    length_mm: float
    mass_kg: float


def value(mesh: dict[str, dict[str, object]], suffix: str, field: str) -> float:
    matches = [record for name, record in mesh.items() if name.endswith(suffix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one mesh ending in {suffix!r}; got {len(matches)}")
    return float(matches[0][field])


def worst_link_order(links: list[Link]) -> tuple[list[Link], float]:
    """Return the ordering that maximises link self-weight virtual work."""
    best_order: tuple[Link, ...] | None = None
    best_coefficient = -math.inf
    for order in itertools.permutations(links):
        distance_m = 0.0
        coefficient = 0.0
        for link in order:
            length_m = link.length_mm / 1000.0
            coefficient += link.mass_kg * (distance_m + 0.5 * length_m)
            distance_m += length_m
        if coefficient > best_coefficient:
            best_order = order
            best_coefficient = coefficient
    assert best_order is not None
    return list(best_order), best_coefficient


def solve_clearance_angle(length_mm: float, required_gap_mm: float) -> float:
    ratio = 2.0 * required_gap_mm / length_mm
    if ratio > 1.0:
        return math.nan
    return 0.5 * math.degrees(math.asin(ratio))


def structural_check(
    theta_deg: float,
    effective_mass_kg: float,
    link_width_mm: float,
    link_length_mm: float,
) -> dict[str, float]:
    theta = math.radians(theta_deg)
    weight = effective_mass_kg * G
    horizontal_total = weight / max(math.tan(theta), 1e-9) / JOINT_EFFICIENCY
    horizontal_per_path = horizontal_total / LOAD_PATHS
    axial_per_path = weight / (LOAD_PATHS * max(math.sin(theta), 1e-9))
    net_area = (link_width_mm - PIN_DIAMETER_MM) * LINK_THICKNESS_MM
    section_modulus = (
        LINK_THICKNESS_MM
        * (link_width_mm**3 - PIN_DIAMETER_MM**3)
        / (6.0 * link_width_mm)
    )
    moment_nmm = horizontal_per_path * link_length_mm / 4.0
    bending_mpa = moment_nmm / section_modulus
    axial_mpa = axial_per_path / net_area
    combined_mpa = bending_mpa + axial_mpa
    bearing_mpa = axial_per_path / (PIN_DIAMETER_MM * LINK_THICKNESS_MM)
    inertia_weak = link_width_mm * LINK_THICKNESS_MM**3 / 12.0
    buckling_n = math.pi**2 * PETG_E_MPA * inertia_weak / link_length_mm**2
    return {
        "theta_deg": theta_deg,
        "effective_mass_kg": effective_mass_kg,
        "horizontal_force_total_n": horizontal_total,
        "axial_force_per_path_n": axial_per_path,
        "moment_per_path_nmm": moment_nmm,
        "bending_stress_mpa": bending_mpa,
        "axial_stress_mpa": axial_mpa,
        "combined_stress_mpa": combined_mpa,
        "static_sf": PETG_ALLOW_MPA / combined_mpa,
        "impact_2x_sf": PETG_ALLOW_MPA / (2.0 * combined_mpa),
        "impact_2x_kt2_sf": PETG_ALLOW_MPA / (4.0 * combined_mpa),
        "bearing_stress_mpa": bearing_mpa,
        "bearing_sf_using_15mpa": PETG_ALLOW_MPA / bearing_mpa,
        "euler_buckling_load_n": buckling_n,
        "buckling_sf": buckling_n / axial_per_path,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    script_dir = Path(__file__).resolve().parent
    result_dir = script_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    audit_path = result_dir / "mesh_audit.json"
    component_path = result_dir / "arm_assembly_components.csv"
    if not audit_path.exists() or not component_path.exists():
        raise SystemExit("Run cad_mesh_audit.py first")

    audit_records = json.loads(audit_path.read_text(encoding="utf-8"))
    mesh = {str(record["file"]): record for record in audit_records}

    links = [
        Link("arm_74.2", 74.2, value(mesh, "แขน (74.2mm).stl", "petg_solid_mass_g") / 1000),
        Link("close_74.2", 74.2, value(mesh, "แขนก้านชิด (74.2mm).stl", "petg_solid_mass_g") / 1000),
        Link("servo_74.2", 74.2, value(mesh, "แขน servo.stl", "petg_solid_mass_g") / 1000),
        Link("arm_85", 85.0, value(mesh, "แขน (85mm).stl", "petg_solid_mass_g") / 1000),
        Link("close_85", 85.0, value(mesh, "แขนก้านชิด (85mm).stl", "petg_solid_mass_g") / 1000),
        Link("servo_horn_85", 85.0, value(mesh, "แขน servo horn.stl", "petg_solid_mass_g") / 1000),
    ]
    link_length_total_mm = sum(link.length_mm for link in links)
    link_mass_total_kg = sum(link.mass_kg for link in links)
    worst_order, link_mass_coefficient_kgm = worst_link_order(links)

    arm_widths = [
        value(mesh, "แขน (74.2mm).stl", "size_y_mm"),
        value(mesh, "แขน (85mm).stl", "size_y_mm"),
        value(mesh, "แขนก้านชิด (74.2mm).stl", "size_y_mm"),
        value(mesh, "แขนก้านชิด (85mm).stl", "size_y_mm"),
    ]
    link_width_mm = float(np.median(arm_widths))
    shortest_link_mm = min(link.length_mm for link in links)

    assembly_key = next(name for name in mesh if name.endswith("assembly/arm assembly.stl"))
    assembly = mesh[assembly_key]
    assembly_height_mm = float(assembly["size_y_mm"])
    assembly_mass_proxy_kg = float(assembly["petg_solid_mass_g"]) / 1000.0
    assembly_cog_y_mm = float(assembly["volume_centroid_y_mm"])

    with component_path.open(encoding="utf-8-sig", newline="") as stream:
        component_rows = list(csv.DictReader(stream))
    angle_candidates = [
        float(row["angle_from_vertical_deg"])
        for row in component_rows
        if 70.0 < float(row["size_y_mm"]) < 100.0
        and 80.0 < float(row["principal_span_mm"]) < 105.0
        and float(row["size_z_mm"]) < 7.0
        and 10.0 < float(row["angle_from_vertical_deg"]) < 40.0
    ]
    current_angle_from_vertical_deg = float(np.median(angle_candidates))
    theta_current_deg = 90.0 - current_angle_from_vertical_deg
    current_link_height_mm = link_length_total_mm * math.sin(math.radians(theta_current_deg))
    overhead_mm = assembly_height_mm - current_link_height_mm
    maximum_height_mm = overhead_mm + link_length_total_mm

    theta_stow_deg = math.degrees(
        math.asin((TARGET_STOW_MM - overhead_mm) / link_length_total_mm)
    )
    clearance_at_stow_mm = (
        shortest_link_mm
        * math.sin(math.radians(theta_stow_deg))
        * math.cos(math.radians(theta_stow_deg))
        - link_width_mm
    )
    theta_clearance_deg = solve_clearance_angle(
        shortest_link_mm, link_width_mm + DESIRED_CLEARANCE_MM
    )
    clearance_height_mm = overhead_mm + link_length_total_mm * math.sin(
        math.radians(theta_clearance_deg)
    )

    housing_mass_kg = sum(
        value(mesh, suffix, "petg_solid_mass_g") / 1000.0
        for suffix in ("ฐานกล้อง.stl", "ฝาหน้ากล้อง.stl", "ฝาหลังกล้อง.stl")
    )
    payload_cases = {
        "sensitivity_95g": 0.095,
        "cad_solid_housing_plus_camera": housing_mass_kg + 0.060,
        "sensitivity_300g": 0.300,
    }

    theta_grid = np.linspace(max(5.0, theta_stow_deg), 90.0, 500)
    torque_rows: list[dict[str, float | int | str]] = []
    torque_curves: dict[tuple[str, int], np.ndarray] = {}
    for case_name, payload_kg in payload_cases.items():
        payload_coefficient = payload_kg * link_length_total_mm / 1000.0
        total_coefficient = payload_coefficient + link_mass_coefficient_kgm
        gravity_torque = G * total_coefficient * np.cos(np.radians(theta_grid))
        effective_mass = total_coefficient / (link_length_total_mm / 1000.0)
        for servo_count in (1, 2):
            torque = gravity_torque / (servo_count * JOINT_EFFICIENCY) + SERVO_STICTION_NM
            torque_curves[(case_name, servo_count)] = torque
            peak = float(torque.max())
            torque_rows.append(
                {
                    "case": case_name,
                    "payload_kg": payload_kg,
                    "effective_lift_mass_kg": effective_mass,
                    "servos": servo_count,
                    "peak_torque_per_servo_nm": peak,
                    "sf_5v": SERVO_5V_NM / peak,
                    "sf_6v": SERVO_6V_NM / peak,
                }
            )

    cad_payload_name = "cad_solid_housing_plus_camera"
    cad_row_two_servos = next(
        row for row in torque_rows if row["case"] == cad_payload_name and row["servos"] == 2
    )
    sf2_ratio_5v = float(cad_row_two_servos["peak_torque_per_servo_nm"]) / (SERVO_5V_NM / 2.0)
    sf2_ratio_6v = float(cad_row_two_servos["peak_torque_per_servo_nm"]) / (SERVO_6V_NM / 2.0)
    direct_travel_deg = 90.0 - theta_stow_deg
    structure = structural_check(
        theta_stow_deg,
        float(cad_row_two_servos["effective_lift_mass_kg"]),
        link_width_mm,
        max(link.length_mm for link in links),
    )

    # Stability baseline: remove the old 351 g mast model from the project's
    # 2.342 kg / 51.74 mm reference, then add the new CAD mast sensitivity.
    old_total_mass = 2.342
    old_cog_m = 0.05174
    old_lift_masses = (0.090, 0.166, 0.095)
    old_lift_heights = (0.100, 0.139, 0.178)
    base_mass_kg = old_total_mass - sum(old_lift_masses)
    base_moment_kgm = old_total_mass * old_cog_m - sum(
        mass * height for mass, height in zip(old_lift_masses, old_lift_heights)
    )
    base_cog_m = base_moment_kgm / base_mass_kg
    mast_cog_m = 0.100 + assembly_cog_y_mm / 1000.0
    support_half_width_m = 0.100
    stability_rows: list[dict[str, float]] = []
    for mast_mass_kg in np.linspace(0.50, 0.90, 81):
        total_mass = base_mass_kg + mast_mass_kg
        cog_m = (base_moment_kgm + mast_mass_kg * mast_cog_m) / total_mass
        tip_acceleration = G * support_half_width_m / cog_m
        stability_rows.append(
            {
                "mast_mass_kg": float(mast_mass_kg),
                "robot_mass_kg": total_mass,
                "robot_cog_m": cog_m,
                "tip_angle_deg": math.degrees(math.atan(support_half_width_m / cog_m)),
                "tip_acceleration_m_s2": tip_acceleration,
                "guard_at_sf_2_5_m_s2": tip_acceleration / 2.5,
            }
        )
    stability_current = min(
        stability_rows, key=lambda row: abs(row["mast_mass_kg"] - assembly_mass_proxy_kg)
    )

    # Existing project base-plate beam model, rerun with the new mast mass as
    # the central point load and an impact factor of 2.
    base_rows: list[dict[str, float]] = []
    base_span_m = 0.180
    base_effective_width_m = 0.080
    base_petg_e_pa = 2.1e9
    base_petg_allow_pa = 68e6 * 0.45
    base_dynamic_force_n = assembly_mass_proxy_kg * G * 2.0
    for thickness_mm in (2.0, 3.0, 4.0, 5.0, 6.0):
        thickness_m = thickness_mm / 1000.0
        inertia = base_effective_width_m * thickness_m**3 / 12.0
        moment = base_dynamic_force_n * base_span_m / 4.0
        stress_pa = moment * (thickness_m / 2.0) / inertia
        deflection_m = (
            base_dynamic_force_n
            * base_span_m**3
            / (48.0 * base_petg_e_pa * inertia)
        )
        base_rows.append(
            {
                "thickness_mm": thickness_mm,
                "dynamic_point_load_n": base_dynamic_force_n,
                "stress_mpa": stress_pa / 1e6,
                "safety_factor": base_petg_allow_pa / stress_pa,
                "deflection_mm": deflection_m * 1000.0,
            }
        )
    base_3mm = next(row for row in base_rows if row["thickness_mm"] == 3.0)

    summary = {
        "sources": {
            "assembly_stl": assembly_key,
            "mesh_audit": str(audit_path.relative_to(script_dir.parent)),
            "step_bom": "simulation/results/step_bom.csv",
        },
        "geometry": {
            "link_count": len(links),
            "link_lengths_mm": [link.length_mm for link in links],
            "link_length_total_mm": link_length_total_mm,
            "link_width_mm": link_width_mm,
            "link_thickness_assumed_mm": LINK_THICKNESS_MM,
            "cad_pose_angle_from_horizontal_deg": theta_current_deg,
            "cad_pose_total_height_mm": assembly_height_mm,
            "fixed_overhead_inferred_mm": overhead_mm,
            "maximum_total_height_mm": maximum_height_mm,
            "target_extended_mm": TARGET_EXTENDED_MM,
            "extended_shortfall_mm": TARGET_EXTENDED_MM - maximum_height_mm,
            "target_stow_mm": TARGET_STOW_MM,
            "stow_angle_deg": theta_stow_deg,
            "clearance_at_100mm_stow_mm": clearance_at_stow_mm,
            "height_for_0_4mm_clearance_mm": clearance_height_mm,
        },
        "mass": {
            "six_link_petg_solid_mass_kg": link_mass_total_kg,
            "camera_housing_petg_solid_mass_kg": housing_mass_kg,
            "assembly_petg_equivalent_mass_proxy_kg": assembly_mass_proxy_kg,
            "assembly_volume_centroid_y_mm": assembly_cog_y_mm,
        },
        "servo": {
            "joint_efficiency_assumed": JOINT_EFFICIENCY,
            "capacity_5v_nm_estimated": SERVO_5V_NM,
            "capacity_6v_nm_spec": SERVO_6V_NM,
            "direct_servo_travel_deg": direct_travel_deg,
            "ratio_needed_for_sf2_at_5v": sf2_ratio_5v,
            "servo_travel_with_sf2_ratio_5v_deg": direct_travel_deg * sf2_ratio_5v,
            "ratio_needed_for_sf2_at_6v": sf2_ratio_6v,
            "servo_travel_with_sf2_ratio_6v_deg": direct_travel_deg * sf2_ratio_6v,
            "results": torque_rows,
        },
        "structure": structure,
        "stability": {
            "base_mass_after_removing_old_lift_kg": base_mass_kg,
            "base_cog_m_inferred": base_cog_m,
            "new_mast_cog_m_at_cad_pose": mast_cog_m,
            "cad_mass_proxy_case": stability_current,
        },
        "base_plate_beam_check": {
            "assumptions": {
                "span_m": base_span_m,
                "effective_width_m": base_effective_width_m,
                "petg_allow_mpa": base_petg_allow_pa / 1e6,
                "impact_factor": 2.0,
            },
            "results": base_rows,
        },
        "limitations": [
            "The serial equal-angle six-link model is inferred from six CAD link components; Fusion joints were not exported to STL/STEP.",
            "STL has no material or print-infill metadata; CAD masses are solid PETG equivalents.",
            "The 5 V MG996R torque, joint efficiency, PETG allowable stress, and Kt=2 are estimates.",
            "Collision is represented by adjacent-link planar clearance; full 3D contact requires the Fusion assembly joints.",
            "Linear static FEA at holes, gear teeth, tapers, and layer interfaces remains required.",
        ],
    }
    (result_dir / "scissor_simulation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (result_dir / "servo_torque_cases.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(torque_rows[0].keys()))
        writer.writeheader()
        writer.writerows(torque_rows)
    with (result_dir / "stability_sensitivity.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(stability_rows[0].keys()))
        writer.writeheader()
        writer.writerows(stability_rows)
    with (result_dir / "base_plate_beam_check.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(base_rows[0].keys()))
        writer.writeheader()
        writer.writerows(base_rows)

    fig, axis = plt.subplots(figsize=(10, 6), constrained_layout=True)
    for (case_name, servo_count), torque in torque_curves.items():
        height = overhead_mm + link_length_total_mm * np.sin(np.radians(theta_grid))
        style = "-" if servo_count == 2 else "--"
        axis.plot(height, torque, style, label=f"{case_name}, {servo_count} servo")
    axis.axhline(SERVO_5V_NM, color="red", linewidth=1.2, label="MG996R @5 V estimate")
    axis.axhline(SERVO_5V_NM / 2.0, color="red", linewidth=1.0, linestyle=":", label="SF=2 limit @5 V")
    axis.set_xlabel("Overall lift height (mm)")
    axis.set_ylabel("Torque per lift servo (N·m)")
    axis.set_title("Servo torque from virtual work (no counterbalance spring)")
    axis.grid(True, alpha=0.35)
    axis.legend(fontsize=8)
    fig.savefig(result_dir / "servo_torque_vs_height.png", dpi=180)
    plt.close(fig)

    theta_height = np.linspace(5.0, 90.0, 500)
    height_plot = overhead_mm + link_length_total_mm * np.sin(np.radians(theta_height))
    theta_clearance = np.linspace(5.0, 30.0, 300)
    clearance_plot = (
        shortest_link_mm
        * np.sin(np.radians(theta_clearance))
        * np.cos(np.radians(theta_clearance))
        - link_width_mm
    )
    fig, (height_axis, clearance_axis) = plt.subplots(
        2, 1, figsize=(9, 8), constrained_layout=True
    )
    height_axis.plot(theta_height, height_plot)
    height_axis.axhline(TARGET_STOW_MM, color="orange", linestyle="--", label="100 mm stow")
    height_axis.axhline(TARGET_EXTENDED_MM, color="red", linestyle="--", label="550 mm target")
    height_axis.set_ylabel("Overall height (mm)")
    height_axis.grid(True, alpha=0.35)
    height_axis.legend()
    clearance_axis.plot(theta_clearance, clearance_plot)
    clearance_axis.axhline(0.0, color="red", linewidth=1.0)
    clearance_axis.axhline(DESIRED_CLEARANCE_MM, color="orange", linestyle="--")
    clearance_axis.set_xlabel("Common link angle from horizontal (deg)")
    clearance_axis.set_ylabel("Planar link clearance (mm)")
    clearance_axis.grid(True, alpha=0.35)
    fig.savefig(result_dir / "kinematics_and_clearance.png", dpi=180)
    plt.close(fig)

    masses = np.asarray([row["mast_mass_kg"] for row in stability_rows])
    accelerations = np.asarray([row["tip_acceleration_m_s2"] for row in stability_rows])
    guards = np.asarray([row["guard_at_sf_2_5_m_s2"] for row in stability_rows])
    fig, axis = plt.subplots(figsize=(9, 5.5), constrained_layout=True)
    axis.plot(masses, accelerations, label="tip threshold")
    axis.plot(masses, guards, label="recommended guard (SF 2.5)")
    axis.axvline(assembly_mass_proxy_kg, color="black", linestyle=":", label="CAD mass proxy")
    axis.set_xlabel("New mast mass (kg)")
    axis.set_ylabel("Horizontal acceleration (m/s²)")
    axis.set_title("Robot tip-stability sensitivity at the exported CAD pose")
    axis.grid(True, alpha=0.35)
    axis.legend()
    fig.savefig(result_dir / "stability_sensitivity.png", dpi=180)
    plt.close(fig)

    print(f"Link length total: {link_length_total_mm:.1f} mm")
    print(f"Inferred overhead: {overhead_mm:.1f} mm")
    print(f"Maximum overall height: {maximum_height_mm:.1f} mm")
    print(f"Shortfall versus 550 mm: {TARGET_EXTENDED_MM - maximum_height_mm:.1f} mm")
    print(f"Clearance at 100 mm stow: {clearance_at_stow_mm:.3f} mm")
    print(f"Height for 0.4 mm clearance: {clearance_height_mm:.1f} mm")
    for row in torque_rows:
        print(
            f"{row['case']}, {row['servos']} servo: peak {row['peak_torque_per_servo_nm']:.3f} N·m, "
            f"SF@5V {row['sf_5v']:.2f}"
        )
    print(
        f"Structure CAD-payload: SF static {structure['static_sf']:.2f}, "
        f"impact×2+Kt2 {structure['impact_2x_kt2_sf']:.2f}"
    )
    print(
        f"Gear ratio for SF2 with 2 servos @5V: {sf2_ratio_5v:.2f}:1, "
        f"required servo travel {direct_travel_deg * sf2_ratio_5v:.1f} deg"
    )
    print(
        f"Base plate 3 mm PETG beam proxy: SF {base_3mm['safety_factor']:.2f}, "
        f"deflection {base_3mm['deflection_mm']:.2f} mm"
    )
    print(
        f"Stability CAD-mass proxy: zCoG {stability_current['robot_cog_m']*1000:.1f} mm, "
        f"a_tip {stability_current['tip_acceleration_m_s2']:.2f} m/s², "
        f"guard {stability_current['guard_at_sf_2_5_m_s2']:.2f} m/s²"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
