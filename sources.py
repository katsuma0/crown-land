"""Where each province's crown land polygons come from.

Every entry is one of two kinds. "wfs" is an OGC WFS endpoint (GeoServer
style, paginates with startIndex). "arcgis" is an ArcGIS REST MapServer or
FeatureServer layer (paginates with resultOffset, or by object id when the
server does not support offset paging).

Only BC has a true crown land inventory layer that is open and queryable.
The other four are the closest public layer I could find. The notes say
what each one actually is so nobody mistakes the map for a title search.
"""

SOURCES = {
    "bc": {
        "kind": "wfs",
        # The shared WFS endpoint and WFS 2.0 paging, which is what the
        # bcdata R and Python packages use. The per layer /ows endpoint
        # answered the first live run with something that was not JSON.
        "url": "https://openmaps.gov.bc.ca/geo/pub/wfs",
        "layer": "pub:WHSE_TANTALIS.TA_CROWN_INVENTORY_SVW",
        "sort_by": "OBJECTID",
        "name_fields": ["CROWN_LANDS_FILE", "CROWN_INVENTORY_ID", "OBJECTID"],
        "page_size": 10000,
        "note": "TANTALIS Crown Land Inventory. Active and applied for crown "
                "inventory dispositions, served in EPSG:4326 on request.",
    },
    "ab": {
        "kind": "arcgis",
        # Crown Ownership Classes, a hosted layer built from the Land
        # Ownership parcels and cut down to titles held by provincial,
        # federal and municipal crown agencies. The old titan
        # cadastral_and_land_ownership service returned 404 on 2026-10-18.
        # The "owndership" spelling is theirs. It is a project layer, so if
        # it vanishes the job log will show a 404 and this entry needs a
        # new home.
        "url": "https://geospatial.alberta.ca/arcgis/rest/services/Hosted/"
               "Land_use_owndership_NN_project/FeatureServer",
        "layer_name_pattern": r"crown\s*ownership",
        "layer": 10,
        # CROWNNAME is the title holder, which tells provincial crown from a
        # town or the federal government on the map.
        "name_fields": ["CROWNNAME", "SHORTLEGAL", "CROWNCLASS", "OBJECTID"],
        "page_size": 2000,
        "note": "Alberta crown ownership classes from the Land Ownership "
                "parcels. Provincial, federal and municipal crown titles, "
                "named by the title holder. No Calgary, the city keeps its "
                "own data.",
    },
    "sk": {
        "kind": "arcgis",
        "url": "https://gis.saskatchewan.ca/arcgis/rest/services/Agriculture/CrownLand_AG/MapServer",
        "layer_name_pattern": r"crown\s*land",
        "layer": 2,
        "name_fields": ["NAME", "QUARTER", "OBJECTID"],
        "page_size": 2000,
        # Sixty thousand quarter sections made a 16 MB KML. Touching quarters
        # are merged into blocks before writing, which is also a better map.
        "dissolve": True,
        "note": "Ministry of Agriculture crown land by quarter section and "
                "river lot. A quarter is shown when any part of it is "
                "agricultural crown land, and most of it is under lease. "
                "Saskatchewan Environment resource land is not in a public API.",
    },
    "mb": {
        "kind": "arcgis",
        "url": "https://services.arcgis.com/mMUesHYPkXjaFGfS/arcgis/rest/services/"
               "Manitoba_Provincial_Forests___Version_6/FeatureServer",
        "layer_name_pattern": r"provincial\s*forest",
        "layer": 1,
        "name_fields": ["PROV_FOREST_NAME", "NAME", "FOREST_NAME", "OBJECTID"],
        "page_size": 2000,
        "note": "Manitoba Provincial Forests from Data MB. Manitoba has no "
                "open crown land parcel layer, and the old MLI downloads "
                "stopped updating in 2022. Provincial forests are crown land "
                "withdrawn from sale, which is where most crown camping happens.",
    },
    "on": {
        "kind": "arcgis",
        "url": "https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/LIO_OPEN_DATA/LIO_Open06/MapServer",
        "layer_name_pattern": r"clupa\s*provincial",
        "layer": 5,
        "name_fields": ["NAME_ENG", "POLICY_IDENT", "OGF_ID"],
        # Pages of 1000 full resolution polygons timed the LIO server out at
        # two minutes. Small pages, and the server generalizes the geometry
        # to about 50 m before sending, which is all the KML keeps anyway.
        "page_size": 250,
        # The server leaves exceededTransferLimit out of GeoJSON and sent
        # 249 for a page of 250, so offset paging cannot tell where the end
        # is. Fetching by object id chunks also prints the true total.
        "page_by_ids": True,
        "query_extra": {"maxAllowableOffset": 0.0005, "geometryPrecision": 5},
        "note": "CLUPA provincial from Land Information Ontario. Every crown "
                "land use area in the area of the undertaking, which is the "
                "north. Includes parks and conservation reserves as their own "
                "polygons. Southern Ontario is mostly private and has little here.",
    },
}

PROVINCES = list(SOURCES)
