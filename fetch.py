#!/usr/bin/env python3
"""Fetch crown land polygons for one province inside a bbox.

    python3 fetch.py bc -123.5,48.3,-121.0,50.5

Writes data/raw/{province}_{bbox_hash}.geojson in EPSG:4326. Pages through
the server's feature cap, retries on timeouts with backoff, and reprojects
if the server hands back a projected CRS anyway.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import geopandas as gpd
import requests

from sources import SOURCES

RAW_DIR = Path(__file__).parent / "data" / "raw"
TIMEOUT = 120
RETRIES = 5
BACKOFF = 2.0


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def bbox_hash(bbox):
    return hashlib.sha1(",".join(f"{v:.4f}" for v in bbox).encode()).hexdigest()[:8]


def parse_bbox(text):
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be lon_min,lat_min,lon_max,lat_max")
    lon0, lat0, lon1, lat1 = parts
    if not (lon0 < lon1 and lat0 < lat1):
        raise argparse.ArgumentTypeError("bbox min must be less than max")
    if not (-180 <= lon0 <= 180 and -90 <= lat0 <= 90):
        raise argparse.ArgumentTypeError("bbox must be in WGS84 degrees")
    return parts


def get(session, url, params, want="json"):
    """GET with retries. Backs off on timeouts, connection drops and 5xx."""
    last = None
    for attempt in range(RETRIES):
        try:
            r = session.get(url, params=params, timeout=TIMEOUT)
            if r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} from server", response=r)
            if r.status_code >= 400:
                # A 404 or 400 will not fix itself, so do not burn retries on it.
                raise SystemExit(f"{r.status_code} from {r.url}\n{r.text[:300]}")
            data = r.json() if want == "json" else r.text
            # ArcGIS reports errors as 200 with an error body.
            if isinstance(data, dict) and "error" in data:
                raise requests.HTTPError(f"server error body: {data['error']}", response=r)
            return data
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ValueError) as e:
            last = e
            wait = BACKOFF ** attempt
            log(f"  attempt {attempt + 1}/{RETRIES} failed ({e}); retrying in {wait:.0f}s")
            time.sleep(wait)
    raise SystemExit(f"gave up after {RETRIES} attempts: {last}")


# WFS (GeoServer) ------------------------------------------------------------

def fetch_wfs(session, src, bbox, page_size):
    url = src["url"]
    layer = src["layer"]
    log(f"endpoint: {url}")
    log(f"layer: {layer} (WFS 1.1.0, GeoJSON, EPSG:4326 requested)")
    features = []
    start = 0
    while True:
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": layer,
            "outputFormat": "json",
            "srsName": "EPSG:4326",
            "bbox": ",".join(str(v) for v in bbox) + ",EPSG:4326",
            "maxFeatures": page_size,
            "startIndex": start,
        }
        data = get(session, url, params)
        page = data.get("features", [])
        features.extend(page)
        total = data.get("totalFeatures") or data.get("numberMatched")
        log(f"  page at {start}: {len(page)} features" + (f" of {total}" if total else ""))
        if len(page) < page_size:
            break
        start += page_size
    crs = (data.get("crs") or {}).get("properties", {}).get("name", "")
    return features, crs


# ArcGIS REST ----------------------------------------------------------------

def arcgis_pick_layer(session, src):
    """Find the layer by name pattern, falling back to the configured id."""
    info = get(session, src["url"], {"f": "json"})
    layers = info.get("layers", [])
    pat = re.compile(src.get("layer_name_pattern", "$^"), re.I)
    log(f"endpoint: {src['url']}")
    log("layers on this service:")
    chosen = None
    for lyr in layers:
        mark = ""
        if chosen is None and pat.search(lyr.get("name", "")):
            chosen = lyr
            mark = "   <-- using this one"
        log(f"  [{lyr['id']}] {lyr['name']}{mark}")
    if chosen is None:
        chosen = {"id": src["layer"], "name": f"layer {src['layer']} (name not matched, using configured id)"}
        log(f"  no layer name matched /{pat.pattern}/, falling back to id {src['layer']}")
    log(f"layer: [{chosen['id']}] {chosen['name']}")
    return chosen["id"]


def arcgis_layer_info(session, layer_url):
    info = get(session, layer_url, {"f": "json"})
    fields = [f["name"] for f in info.get("fields", [])]
    log(f"fields: {', '.join(fields)}")
    caps = info.get("advancedQueryCapabilities", {})
    return {
        "fields": fields,
        "max": info.get("maxRecordCount", 1000),
        "paging": bool(caps.get("supportsPagination", info.get("supportsPagination", False))),
        "oid": info.get("objectIdField") or next((f["name"] for f in info.get("fields", []) if f.get("type") == "esriFieldTypeOID"), "OBJECTID"),
        "wkid": (info.get("extent", {}).get("spatialReference", {}) or {}).get("latestWkid")
                or (info.get("extent", {}).get("spatialReference", {}) or {}).get("wkid"),
    }


def build_where(src, fields, override):
    if override:
        return override
    cf = src.get("crown_filter")
    if not cf:
        return "1=1"
    for f in cf["fields"]:
        if f in fields:
            where = cf["sql"].format(field=f)
            log(f"crown filter: {where}")
            return where
    log(f"WARNING: none of {cf['fields']} exist on this layer, fetching unfiltered. "
        f"Pass --where to filter on one of the fields printed above.")
    return "1=1"


def fetch_arcgis(session, src, bbox, page_size, where_override):
    layer_id = arcgis_pick_layer(session, src)
    layer_url = f"{src['url'].rstrip('/')}/{layer_id}"
    info = arcgis_layer_info(session, layer_url)
    log(f"native wkid: {info['wkid']}, maxRecordCount: {info['max']}, offset paging: {info['paging']}")
    page_size = min(page_size, info["max"])
    where = build_where(src, info["fields"], where_override)
    base = {
        "where": where,
        "geometry": ",".join(str(v) for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "outSR": 4326,
        "returnGeometry": "true",
        "f": "geojson",
    }
    query = f"{layer_url}/query"
    features = []
    if info["paging"]:
        offset = 0
        while True:
            data = get(session, query, {**base, "resultOffset": offset, "resultRecordCount": page_size})
            page = data.get("features", [])
            features.extend(page)
            log(f"  page at {offset}: {len(page)} features")
            more = data.get("properties", {}).get("exceededTransferLimit") or data.get("exceededTransferLimit")
            if len(page) < page_size and not more:
                break
            if not page:
                break
            offset += len(page)
    else:
        # Old servers: pull every object id in the bbox, then fetch in chunks.
        ids = get(session, query, {**base, "returnIdsOnly": "true", "f": "json"})
        oid_field = ids.get("objectIdFieldName", info["oid"])
        oids = sorted(ids.get("objectIds") or [])
        log(f"  {len(oids)} object ids in bbox, fetching by id in chunks of {page_size}")
        for i in range(0, len(oids), page_size):
            chunk = oids[i:i + page_size]
            data = get(session, query, {**base, "where": f"{oid_field} >= {chunk[0]} AND {oid_field} <= {chunk[-1]}"})
            page = data.get("features", [])
            features.extend(page)
            log(f"  ids {chunk[0]}..{chunk[-1]}: {len(page)} features")
    crs = (data.get("crs") or {}).get("properties", {}).get("name", "") if features else ""
    return features, crs


# Main -----------------------------------------------------------------------

def crs_is_4326(crs_name):
    if not crs_name:
        return True  # GeoJSON default is WGS84
    return bool(re.search(r"(4326|CRS84)", crs_name))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Western Canada is all negative longitudes, so every bbox starts with
    # "-" and argparse would read it as an option. Teach it that a leading
    # negative number followed by a comma is still a value.
    ap._negative_number_matcher = re.compile(r"^-\d+$|^-\d*\.\d+$|^-\d+(\.\d+)?,")
    ap.add_argument("province", choices=sorted(SOURCES))
    ap.add_argument("bbox", type=parse_bbox, help="lon_min,lat_min,lon_max,lat_max in WGS84")
    ap.add_argument("--page-size", type=int, help="features per request (default per source)")
    ap.add_argument("--where", help="ArcGIS SQL where clause, replaces the default crown filter")
    ap.add_argument("--out", help="output path (default data/raw/{province}_{hash}.geojson)")
    args = ap.parse_args()

    src = SOURCES[args.province]
    log(f"{args.province}: {src['note']}")
    page_size = args.page_size or src.get("page_size", 1000)
    session = requests.Session()
    session.headers["User-Agent"] = "crown-land-export/1.0 (+github.com/katsuma0/crown-land)"

    if src["kind"] == "wfs":
        features, crs = fetch_wfs(session, src, args.bbox, page_size)
    else:
        features, crs = fetch_arcgis(session, src, args.bbox, page_size, args.where)

    log(f"fetched {len(features)} features, server crs: {crs or 'unspecified (WGS84)'}")
    if not features:
        log("nothing came back for that bbox, not writing a file")
        sys.exit(2)

    fc = {"type": "FeatureCollection", "features": features}
    if not crs_is_4326(crs):
        # Pull the EPSG code out of strings like "urn:ogc:def:crs:EPSG::3005".
        m = re.search(r"EPSG:+(\d+)", crs)
        if not m:
            raise SystemExit(f"server returned unknown CRS {crs!r}, cannot reproject")
        epsg = int(m.group(1))
        log(f"server returned EPSG:{epsg}, reprojecting to EPSG:4326")
        gdf = gpd.GeoDataFrame.from_features(features, crs=f"EPSG:{epsg}").to_crs(4326)
        fc = json.loads(gdf.to_json())

    out = Path(args.out) if args.out else RAW_DIR / f"{args.province}_{bbox_hash(args.bbox)}.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(fc, f)
    log(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    print(out)


if __name__ == "__main__":
    main()
