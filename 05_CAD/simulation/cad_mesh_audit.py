"""Audit exported STL geometry without third-party CAD libraries.

The script intentionally treats STL as geometry only.  STL contains no material,
joint, constraint, or print-setting metadata; reported masses are therefore
solid-volume equivalents, not predictions for slicer infill.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection


PETG_DENSITY_G_MM3 = 1.27e-3


@dataclass
class MeshResult:
    file: str
    triangles: int
    size_x_mm: float
    size_y_mm: float
    size_z_mm: float
    min_x_mm: float
    min_y_mm: float
    min_z_mm: float
    max_x_mm: float
    max_y_mm: float
    max_z_mm: float
    area_mm2: float
    signed_volume_mm3: float
    volume_mm3: float
    petg_solid_mass_g: float
    volume_centroid_x_mm: float
    volume_centroid_y_mm: float
    volume_centroid_z_mm: float
    boundary_edges: int
    nonmanifold_edges: int
    watertight: bool


def load_stl(path: Path) -> np.ndarray:
    """Return triangles with shape (n, 3, 3) from binary or ASCII STL."""
    data = path.read_bytes()
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        if 84 + count * 50 == len(data):
            record = np.dtype(
                [
                    ("normal", "<f4", (3,)),
                    ("vertices", "<f4", (3, 3)),
                    ("attribute", "<u2"),
                ]
            )
            return np.frombuffer(data, dtype=record, count=count, offset=84)[
                "vertices"
            ].astype(np.float64)

    vertices: list[list[float]] = []
    for raw_line in data.decode("utf-8", errors="ignore").splitlines():
        fields = raw_line.strip().split()
        if len(fields) == 4 and fields[0].lower() == "vertex":
            vertices.append([float(fields[1]), float(fields[2]), float(fields[3])])
    if len(vertices) % 3:
        raise ValueError(f"Malformed ASCII STL: {path}")
    return np.asarray(vertices, dtype=np.float64).reshape((-1, 3, 3))


def edge_health(triangles: np.ndarray, tolerance_mm: float = 1e-4) -> tuple[int, int]:
    """Count boundary and non-manifold edges after coordinate quantisation."""
    vertices = np.rint(triangles.reshape((-1, 3)) / tolerance_mm).astype(np.int64)
    unique_vertices, inverse = np.unique(vertices, axis=0, return_inverse=True)
    del unique_vertices
    faces = inverse.reshape((-1, 3))
    edges = np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0
    )
    edges.sort(axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return int(np.count_nonzero(counts == 1)), int(np.count_nonzero(counts > 2))


def component_rows(triangles: np.ndarray, tolerance_mm: float = 1e-4) -> list[dict[str, float | int]]:
    """Split triangles by shared mesh edges and return per-shell geometry."""
    quantised = np.rint(triangles.reshape((-1, 3)) / tolerance_mm).astype(np.int64)
    _, inverse = np.unique(quantised, axis=0, return_inverse=True)
    faces = inverse.reshape((-1, 3))
    edges = np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0
    )
    edges.sort(axis=1)
    face_ids = np.tile(np.arange(len(faces), dtype=np.int64), 3)
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    sorted_edges = edges[order]
    sorted_faces = face_ids[order]
    same = np.all(sorted_edges[1:] == sorted_edges[:-1], axis=1)

    parent = np.arange(len(faces), dtype=np.int64)

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = int(parent[item])
        return item

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for position in np.flatnonzero(same):
        union(int(sorted_faces[position]), int(sorted_faces[position + 1]))
    labels = np.fromiter((find(i) for i in range(len(faces))), dtype=np.int64)
    roots, component_ids = np.unique(labels, return_inverse=True)
    del roots

    rows: list[dict[str, float | int]] = []
    for component_id in range(int(component_ids.max()) + 1):
        part = triangles[component_ids == component_id]
        points = part.reshape((-1, 3))
        minimum, maximum = points.min(axis=0), points.max(axis=0)
        cross = np.cross(part[:, 1] - part[:, 0], part[:, 2] - part[:, 0])
        signed_volume = np.einsum("ij,ij->i", part[:, 0], cross).sum() / 6.0
        centroid = points.mean(axis=0)
        unique_points = np.unique(np.rint(points / tolerance_mm).astype(np.int64), axis=0)
        unique_points = unique_points.astype(np.float64) * tolerance_mm
        covariance = np.cov(unique_points, rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        principal = eigenvectors[:, int(np.argmax(eigenvalues))]
        if principal[1] < 0:
            principal = -principal
        principal_span = float(np.ptp(unique_points @ principal))
        rows.append(
            {
                "triangles": int(len(part)),
                "centroid_x_mm": float(centroid[0]),
                "centroid_y_mm": float(centroid[1]),
                "centroid_z_mm": float(centroid[2]),
                "size_x_mm": float(maximum[0] - minimum[0]),
                "size_y_mm": float(maximum[1] - minimum[1]),
                "size_z_mm": float(maximum[2] - minimum[2]),
                "volume_mm3": abs(float(signed_volume)),
                "principal_x": float(principal[0]),
                "principal_y": float(principal[1]),
                "principal_z": float(principal[2]),
                "principal_span_mm": principal_span,
                "angle_from_vertical_deg": float(
                    math.degrees(math.acos(min(1.0, max(-1.0, principal[1]))))
                ),
            }
        )
    rows.sort(key=lambda row: int(row["triangles"]), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["component"] = index
    return rows


def audit(path: Path) -> tuple[MeshResult, np.ndarray]:
    triangles = load_stl(path)
    points = triangles.reshape((-1, 3))
    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    size = maximum - minimum

    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    area = 0.5 * np.linalg.norm(cross, axis=1).sum()
    signed_volume = np.einsum("ij,ij->i", triangles[:, 0], cross).sum() / 6.0
    tetra_volumes = np.einsum("ij,ij->i", triangles[:, 0], cross) / 6.0
    if abs(float(tetra_volumes.sum())) > 1e-12:
        volume_centroid = (
            tetra_volumes[:, None]
            * (triangles[:, 0] + triangles[:, 1] + triangles[:, 2])
            / 4.0
        ).sum(axis=0) / tetra_volumes.sum()
    else:
        volume_centroid = points.mean(axis=0)
    boundary, nonmanifold = edge_health(triangles)
    volume = abs(float(signed_volume))
    result = MeshResult(
        file=str(path.as_posix()),
        triangles=int(len(triangles)),
        size_x_mm=float(size[0]),
        size_y_mm=float(size[1]),
        size_z_mm=float(size[2]),
        min_x_mm=float(minimum[0]),
        min_y_mm=float(minimum[1]),
        min_z_mm=float(minimum[2]),
        max_x_mm=float(maximum[0]),
        max_y_mm=float(maximum[1]),
        max_z_mm=float(maximum[2]),
        area_mm2=float(area),
        signed_volume_mm3=float(signed_volume),
        volume_mm3=volume,
        petg_solid_mass_g=volume * PETG_DENSITY_G_MM3,
        volume_centroid_x_mm=float(volume_centroid[0]),
        volume_centroid_y_mm=float(volume_centroid[1]),
        volume_centroid_z_mm=float(volume_centroid[2]),
        boundary_edges=boundary,
        nonmanifold_edges=nonmanifold,
        watertight=boundary == 0 and nonmanifold == 0,
    )
    return result, triangles


def render_views(triangles: np.ndarray, output: Path, title: str) -> None:
    points = triangles.reshape((-1, 3))
    maximum_points = 160_000
    stride = max(1, math.ceil(len(points) / maximum_points))
    sample = points[::stride]
    views = [(0, 2, "X–Z"), (1, 2, "Y–Z"), (0, 1, "X–Y")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    for axis, (a, b, label) in zip(axes, views):
        axis.scatter(sample[:, a], sample[:, b], s=0.18, alpha=0.35, rasterized=True)
        axis.set_title(label)
        axis.set_xlabel("XYZ"[a] + " (mm)")
        axis.set_ylabel("XYZ"[b] + " (mm)")
        axis.set_aspect("equal", adjustable="box")
        axis.grid(True, linewidth=0.25, alpha=0.45)
    fig.suptitle(title)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def render_solid_projection(
    triangles: np.ndarray,
    output: Path,
    axes_pair: tuple[int, int] = (1, 2),
    depth_axis: int = 0,
) -> None:
    """Render a depth-coloured orthographic projection for visual CAD QA."""
    maximum_faces = 90_000
    stride = max(1, math.ceil(len(triangles) / maximum_faces))
    sample = triangles[::stride]
    depth = sample[:, :, depth_axis].mean(axis=1)
    order = np.argsort(depth)
    polygons = sample[order][:, :, list(axes_pair)]
    depth = depth[order]
    normalised = (depth - depth.min()) / max(float(np.ptp(depth)), 1e-12)
    colours = plt.get_cmap("viridis")(normalised)
    colours[:, 3] = 0.65
    fig, axis = plt.subplots(figsize=(8, 12), constrained_layout=True)
    axis.add_collection(PolyCollection(polygons, facecolors=colours, edgecolors="none"))
    points = polygons.reshape((-1, 2))
    margin = np.ptp(points, axis=0) * 0.03
    axis.set_xlim(points[:, 0].min() - margin[0], points[:, 0].max() + margin[0])
    axis.set_ylim(points[:, 1].min() - margin[1], points[:, 1].max() + margin[1])
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlabel("XYZ"[axes_pair[0]] + " (mm)")
    axis.set_ylabel("XYZ"[axes_pair[1]] + " (mm)")
    axis.set_title("Assembly solid projection (colour = depth)")
    axis.grid(True, linewidth=0.3, alpha=0.3)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--cad-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results")
    args = parser.parse_args()

    cad_root = args.cad_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stl_files = sorted(cad_root.rglob("*.stl"))
    if not stl_files:
        raise SystemExit(f"No STL files found under {cad_root}")

    results: list[MeshResult] = []
    assembly_triangles: np.ndarray | None = None
    for path in stl_files:
        result, triangles = audit(path)
        result.file = str(path.relative_to(cad_root).as_posix())
        results.append(result)
        if path.name.lower() == "arm assembly.stl":
            assembly_triangles = triangles

    csv_path = output / "mesh_audit.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(item) for item in results)

    json_path = output / "mesh_audit.json"
    json_path.write_text(
        json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if assembly_triangles is not None:
        render_views(assembly_triangles, output / "arm_assembly_views.png", "Scissor arm assembly")
        render_solid_projection(
            assembly_triangles,
            output / "arm_assembly_side_solid.png",
            axes_pair=(1, 2),
            depth_axis=0,
        )
        components = component_rows(assembly_triangles)
        component_path = output / "arm_assembly_components.csv"
        with component_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(components[0].keys()))
            writer.writeheader()
            writer.writerows(components)
        print(f"Assembly shells: {len(components)} ({component_path})")

    print(f"Audited {len(results)} STL files")
    print(f"CSV:  {csv_path}")
    print(f"JSON: {json_path}")
    for item in results:
        print(
            f"{item.file}: {item.size_x_mm:.2f} x {item.size_y_mm:.2f} x "
            f"{item.size_z_mm:.2f} mm, V={item.volume_mm3:.1f} mm^3, "
            f"watertight={item.watertight}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
