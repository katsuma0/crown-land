#!/usr/bin/env bash
# Fetch and convert all five provinces with default bboxes, or just the
# ones named on the command line: ./run.sh bc on
# Boxes cover the populated, road accessible south of each province,
# not the whole thing. Edit the values below or run fetch.py by hand.
set -uo pipefail
cd "$(dirname "$0")"

MAX_MB=${MAX_MB:-5}
TOLERANCE=${TOLERANCE:-0.0005}

# province  lon_min,lat_min,lon_max,lat_max
BOXES=(
  "bc  -128.5,48.3,-114.0,52.0"   # Vancouver Island, Lower Mainland, Okanagan, Kootenays, Cariboo
  "ab  -116.5,49.0,-112.5,54.5"   # Eastern Slopes and foothills, Waterton up past Edson. Parcel data, so kept narrow
  "sk  -110.0,49.0,-101.4,55.0"   # Grain belt and the near north up to La Ronge
  "mb  -101.5,49.0,-95.0,54.0"    # Whiteshell, Sandilands, Duck and Porcupine mountains
  "on   -95.2,44.0,-76.0,50.5"    # Kenora to Ottawa valley, north to Red Lake and Cochrane
)

wanted="$*"
failed=()
for entry in "${BOXES[@]}"; do
  read -r prov bbox <<<"$entry"
  if [ -n "$wanted" ] && [[ " $wanted " != *" $prov "* ]]; then
    continue
  fi
  echo "== $prov  $bbox"
  if ! python3 fetch.py "$prov" "$bbox"; then
    echo "!! fetch failed for $prov"
    failed+=("$prov")
    continue
  fi
  if ! python3 to_kml.py "$prov" --tolerance "$TOLERANCE" --max-mb "$MAX_MB"; then
    echo "!! kml failed for $prov"
    failed+=("$prov")
  fi
done

echo
echo "== output"
for f in out/*.kml; do
  [ -e "$f" ] || continue
  bytes=$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f")
  mb=$(awk -v b="$bytes" 'BEGIN { printf "%.2f", b / 1e6 }')
  if awk -v b="$bytes" -v m="$MAX_MB" 'BEGIN { exit !(b > m * 1e6) }'; then
    echo "WARNING: $f is $mb MB, over $MAX_MB MB. Gaia will crawl. Raise TOLERANCE or shrink the bbox."
  else
    echo "$f  $mb MB"
  fi
done

if [ ${#failed[@]} -gt 0 ]; then
  echo "failed: ${failed[*]}"
  exit 1
fi
