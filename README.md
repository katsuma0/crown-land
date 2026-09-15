# crown-land

Crown land polygons for BC, Alberta, Saskatchewan, Manitoba and Ontario, pulled from each province's open GIS server and written out as KML files that load into Gaia GPS on an iPhone. I made it so I could see where I'm allowed to pull off and camp without cell service.

Three files do the work. `fetch.py` takes a province code and a bounding box, asks the province's server for every polygon inside the box in WGS84, pages through the server's feature cap, retries with backoff when the server times out, reprojects if the server sends back BC Albers or 10TM anyway, and saves the raw GeoJSON to `data/raw/{province}_{bbox_hash}.geojson`. `to_kml.py` reads that file, throws away every attribute except one name field, simplifies the outlines with a tolerance in degrees, and writes `out/{province}.kml`. If the file lands over 5 MB it doubles the tolerance and tries again up to six times, because Gaia on an iPhone gets sluggish above that. It prints the final size and feature count. `run.sh` runs both for all five provinces with default boxes and warns about any output over 5 MB. The sources themselves, endpoint, layer, name field candidates, live in `sources.py`.

Setup is `pip install -r requirements.txt`, then `./run.sh`. To do one province by hand:

```
python3 fetch.py bc -123.5,48.3,-121.0,50.5
python3 to_kml.py bc --tolerance 0.0005
```

The bbox is `lon_min,lat_min,lon_max,lat_max` in decimal degrees, west is negative, so every box in Canada starts with a minus sign. The defaults in `run.sh` cover the populated, road accessible south of each province, not the whole thing. To change one, edit the `BOXES` array in `run.sh` or pass your own box to `fetch.py`. Each box gets its own raw file, so old fetches stick around until you delete them, and `to_kml.py` picks the newest one for that province unless you pass `--input`. A tolerance of 0.0005 degrees is about 50 m on the ground, which is fine for deciding whether a lake shore is crown. Go to 0.0001 if you want tighter lines and can live with a bigger file.

`fetch.py` prints the endpoint, the layer it picked and the layer's fields before it downloads anything, so you can see what you are getting. For the ArcGIS provinces it looks the layer up by name at run time instead of trusting a hard coded id, since those ids move.

What each province actually is, because only one of them is a true crown land layer.

BC is the TANTALIS Crown Land Inventory, a WFS layer on openmaps.gov.bc.ca. It is real crown parcel data and it takes an EPSG:4326 request directly.

Alberta is the Land Ownership layer on geospatial.alberta.ca, the title mapping data behind GeoDiscover. It holds freehold, crown and unpatented parcels together, so `fetch.py` filters to crown on the first ownership type field it finds. If the field names on the live layer do not match my guesses it warns and fetches everything, and you pass `--where` with the right field from the printed list. Calgary, Edmonton and federal land are not in it.

Saskatchewan is Ministry of Agriculture crown land by quarter section from gis.saskatchewan.ca. A quarter shows up when any part of it is agricultural crown land, and most of it is under lease, so it tells you the Crown owns it, not that you can camp on it. Saskatchewan Environment resource land, which is the stuff you can camp on, has no public API I could find.

Manitoba has no open crown land parcel layer at all. The old Manitoba Land Initiative shapefiles stopped updating in February 2022 and Data MB does not carry a parcel level ownership layer. I use Manitoba Provincial Forests from the province's ArcGIS Online, which is crown land withdrawn from sale and where most Manitoba crown camping happens anyway. It is a coarse substitute.

Ontario is the Crown Land Use Policy Atlas provincial layer from Land Information Ontario. It covers the area of the undertaking, roughly everything north of the French and Mattawa rivers, and includes provincial parks and conservation reserves as their own polygons. Southern Ontario is mostly private, so a box down there returns little. The name field is the policy area name, which is more useful in Gaia than a parcel id.

Getting the KML onto the phone. AirDrop or iCloud Drive the file from `out/` so it shows up in the Files app. In Files, long press the KML, pick Share, and choose Gaia GPS from the share sheet. Gaia imports it as a folder of tracks under Saved. If Gaia is not in the sheet, scroll to the end, tap More, and turn it on. Do all of this on Wi-Fi with the maps downloaded for the area first, because the import itself does not fetch any tiles.

Gaia draws KML polygons as outlines with no fill, no matter what the style block in the file says. You get a green line around each crown parcel and nothing inside it. That is enough to tell which side of the line you are on, but it means a dense area of small parcels looks like a tangle at low zoom. Zoom in.

Raw GeoJSON and KML are git ignored. The provincial data ranges from a few MB to a few GB depending on the box, none of it belongs in the repo.
