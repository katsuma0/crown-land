#!/usr/bin/env python3
"""Turn a raw GeoJSON into a small KML for Gaia GPS.

    python3 to_kml.py bc --tolerance 0.0005

Keeps geometry and one name field, drops everything else, simplifies with
the given tolerance (degrees), and writes out/{province}.kml. If the file
is still over --max-mb the tolerance doubles and it tries again, because
Gaia on an iPhone gets slow above about 5 MB.
"""

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon

from sources import SOURCES

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_DIR = Path(__file__).parent / "out"


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def newest_raw(province):
    files = sorted(RAW_DIR.glob(f"{province}_*.geojson"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f"no data/raw/{province}_*.geojson, run fetch.py first")
    return files[-1]


def pick_name_field(gdf, candidates):
    for c in candidates:
        if c in gdf.columns:
            return c
    strings = [c for c in gdf.columns if c != "geometry" and gdf[c].dtype == object]
    return strings[0] if strings else None


def ring(coords):
    # Six decimals is about 10 cm, which is plenty for a crown boundary and
    # keeps the file small.
    return " ".join(f"{x:.6f},{y:.6f}" for x, y in coords)


def polygon_kml(poly):
    parts = [f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{ring(poly.exterior.coords)}</coordinates></LinearRing></outerBoundaryIs>"]
    for hole in poly.interiors:
        parts.append(f"<innerBoundaryIs><LinearRing><coordinates>{ring(hole.coords)}</coordinates></LinearRing></innerBoundaryIs>")
    parts.append("</Polygon>")
    return "".join(parts)


def geom_kml(geom):
    if isinstance(geom, Polygon):
        return polygon_kml(geom)
    if isinstance(geom, MultiPolygon):
        return "<MultiGeometry>" + "".join(polygon_kml(p) for p in geom.geoms) + "</MultiGeometry>"
    return None


def write_kml(gdf, name_field, title, path):
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n'
                f"<name>{escape(title)}</name>\n"
                # Gaia ignores fill anyway. Outline only keeps other apps honest.
                '<Style id="crown"><LineStyle><color>ff00a000</color><width>2</width></LineStyle>'
                '<PolyStyle><fill>0</fill><outline>1</outline></PolyStyle></Style>\n')
        names = gdf[name_field].tolist() if name_field else [""] * len(gdf)
        for geom, name in zip(gdf.geometry, names):
            body = geom_kml(geom)
            if body is None:
                continue
            name = "" if name is None else str(name)
            f.write(f"<Placemark><name>{escape(name)}</name><styleUrl>#crown</styleUrl>{body}</Placemark>\n")
            n += 1
        f.write("</Document></kml>\n")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("province", choices=sorted(SOURCES))
    ap.add_argument("--input", help="GeoJSON to read (default newest data/raw/{province}_*.geojson)")
    ap.add_argument("--tolerance", type=float, default=0.0005, help="simplify tolerance in degrees, about 50 m at 0.0005")
    ap.add_argument("--max-mb", type=float, default=5.0, help="retry with a coarser tolerance above this size")
    ap.add_argument("--name-field", help="attribute to keep as the placemark name")
    ap.add_argument("--out", help="output path (default out/{province}.kml)")
    args = ap.parse_args()

    src = Path(args.input) if args.input else newest_raw(args.province)
    log(f"reading {src}")
    gdf = gpd.read_file(src, engine="fiona")
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    elif gdf.crs.to_epsg() != 4326:
        log(f"input is {gdf.crs}, reprojecting to EPSG:4326")
        gdf = gdf.to_crs(4326)

    name_field = args.name_field or pick_name_field(gdf, SOURCES[args.province]["name_fields"])
    log(f"name field: {name_field or '(none, placemarks will be unnamed)'}")
    keep = ["geometry"] + ([name_field] if name_field else [])
    gdf = gdf[keep]
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    out = Path(args.out) if args.out else OUT_DIR / f"{args.province}.kml"
    out.parent.mkdir(parents=True, exist_ok=True)
    title = f"Crown land {args.province.upper()}"

    tol = args.tolerance
    for attempt in range(6):
        simp = gdf.copy()
        simp["geometry"] = simp.geometry.simplify(tol, preserve_topology=True)
        simp = simp[~simp.geometry.is_empty]
        n = write_kml(simp, name_field, title, out)
        mb = out.stat().st_size / 1e6
        log(f"tolerance {tol:g}: {n} features, {mb:.2f} MB")
        if mb <= args.max_mb:
            break
        tol *= 2
        log(f"over {args.max_mb} MB, retrying with tolerance {tol:g}")
    else:
        log(f"WARNING: still over {args.max_mb} MB after {attempt + 1} passes, shrink the bbox")

    print(f"{out}\t{mb:.2f} MB\t{n} features\ttolerance {tol:g}")


if __name__ == "__main__":
    main()
