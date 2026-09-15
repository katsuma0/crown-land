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
        "url": "https://openmaps.gov.bc.ca/geo/pub/WHSE_TANTALIS.TA_CROWN_INVENTORY_SVW/ows",
        "layer": "pub:WHSE_TANTALIS.TA_CROWN_INVENTORY_SVW",
        "name_fields": ["CROWN_LANDS_FILE", "CROWN_INVENTORY_ID", "OBJECTID"],
        "page_size": 10000,
        "note": "TANTALIS Crown Land Inventory. Active and applied for crown "
                "inventory dispositions, served in EPSG:4326 on request.",
    },
    "ab": {
        "kind": "arcgis",
        "url": "https://geospatial.alberta.ca/titan/rest/services/cadastre/"
               "cadastral_and_land_ownership_view_only_10tm_nad83_aep/MapServer",
        # Layer ids on this service are not stable, so fetch.py looks the
        # layer up by name and prints what it picked.
        "layer_name_pattern": r"land\s*ownership",
        "layer": 11,
        "name_fields": ["PID", "LINC", "PARCEL_ID", "OBJECTID"],
        # Land Ownership holds freehold, crown and unpatented parcels
        # together. Keep only the crown ones. The first field in this list
        # that exists on the layer is used. If none exists the fetch runs
        # unfiltered and warns.
        "crown_filter": {
            "fields": ["OWNERSHIP_TYPE", "OWNER_TYPE", "OWNERSHIP", "PARCEL_TYPE", "TITLE_TYPE"],
            "sql": "UPPER({field}) LIKE '%CROWN%' OR UPPER({field}) LIKE '%UNTITLED%' OR UPPER({field}) LIKE '%UNPATENTED%'",
        },
        "page_size": 2000,
        "note": "Alberta Land Ownership (Alberta Data Partnerships title "
                "mapping via GeoDiscover). Parcel extents for freehold, crown "
                "and unpatented land outside Calgary, Edmonton and federal "
                "lands. Served in 10TM NAD83, reprojected here.",
    },
    "sk": {
        "kind": "arcgis",
        "url": "https://gis.saskatchewan.ca/arcgis/rest/services/Agriculture/CrownLand_AG/MapServer",
        "layer_name_pattern": r"crown\s*land",
        "layer": 2,
        "name_fields": ["NAME", "QUARTER", "OBJECTID"],
        "page_size": 2000,
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
        "name_fields": ["NAME", "FOREST_NAME", "NAME_E", "PF_NAME", "OBJECTID"],
        "page_size": 2000,
        "note": "Manitoba Provincial Forests from Data MB. Manitoba has no "
                "open crown land parcel layer, and the old MLI downloads "
                "stopped updating in 2022. Provincial forests are crown land "
                "withdrawn from sale, which is where most crown camping happens.",
    },
    "on": {
        "kind": "arcgis",
        "url": "https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/LIO_OPEN_DATA/LIO_Open06/MapServer",
        "layer_name_pattern": r"crown\s*land\s*use\s*policy\s*area.*provincial",
        "layer": 5,
        "name_fields": ["ENGLISH_NAME", "NAME_ENG", "POLICY_NAME_ENG", "POLICY_IDENT", "OGF_ID"],
        "page_size": 1000,
        "note": "CLUPA provincial from Land Information Ontario. Every crown "
                "land use area in the area of the undertaking, which is the "
                "north. Includes parks and conservation reserves as their own "
                "polygons. Southern Ontario is mostly private and has little here.",
    },
}

PROVINCES = list(SOURCES)
