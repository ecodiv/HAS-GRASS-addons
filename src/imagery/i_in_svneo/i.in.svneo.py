#!/usr/bin/env python

############################################################################
#
# MODULE:    i.in.svneo
# AUTHOR(S): Paulo van Breugel
# PURPOSE:   Import and (optionally) preprocess SuperView-NEO imagery from the
#            satellietdataportaal. Supports BOA reflectance products (import
#            and metadata enrichment only) as well as 11/12-bit DN products
#            (DN to TOA radiance conversion and, optionally, surface
#            reflectance via DOS or i.atcorr/6S). Metadata are read from the
#            NSO ISO 19115 XML and/or the raw SVN1-04 L1B MUX XML.
# COPYRIGHT: (C) 2026 by Paulo van Breugel and the GRASS Development Team
#
# This program is free software under the GNU General Public
# License (>=v2). Read the file COPYING that comes with GRASS
# for details.
#
############################################################################

# %module
# % description: Import SuperView-NEO imagery (BOA or DN) and enrich raster metadata. Optional DN->TOA radiance conversion, DOS surface reflectance, or i.atcorr/6S atmospheric correction with optional AERONET/CAMS-based AOD550.
# % keyword: imagery
# % keyword: import
# % keyword: radiometric conversion
# % keyword: radiance
# % keyword: reflectance
# % keyword: atmospheric correction
# % keyword: aerosol
# % keyword: satellite
# % keyword: SuperView-NEO
# %end

# %option G_OPT_F_BIN_INPUT
# % key: input
# % label: Input GeoTIFF file
# % description: SuperView-NEO GeoTIFF file with 4 bands (blue, green, red, NIR). Not required when the four band options (blue, green, red, nir) are provided.
# % required: no
# % guisection: input
# %end

# %option G_OPT_R_INPUT
# % key: blue
# % label: Pre-imported blue band
# % description: Name of an already-imported raster holding the blue band. Provide all four band options (blue, green, red, nir) to skip the GeoTIFF import step. Mutually exclusive with input=.
# % required: no
# % guisection: input
# %end

# %option G_OPT_R_INPUT
# % key: green
# % label: Pre-imported green band
# % description: Name of an already-imported raster holding the green band.
# % required: no
# % guisection: input
# %end

# %option G_OPT_R_INPUT
# % key: red
# % label: Pre-imported red band
# % description: Name of an already-imported raster holding the red band.
# % required: no
# % guisection: input
# %end

# %option G_OPT_R_INPUT
# % key: nir
# % label: Pre-imported NIR band
# % description: Name of an already-imported raster holding the near-infrared band.
# % required: no
# % guisection: input
# %end

# %rules
# % exclusive: input,blue
# % exclusive: input,green
# % exclusive: input,red
# % exclusive: input,nir
# % collective: blue,green,red,nir
# %end

# %option G_OPT_F_BIN_INPUT
# % key: metadata
# % label: NSO metadata file
# % description: NSO metadata XML file (.xml, ISO 19115) accompanying the SuperView-NEO product, or the raw SVN1-04 L1B MUX XML when only that file is available. Auto-detected.
# % required: yes
# % guisection: input
# %end

# %option G_OPT_F_BIN_INPUT
# % key: geometry_metadata
# % label: Raw L1B MUX XML metadata file
# % description: Optional raw SVN1-04 L1B MUX XML file. Provides scene geometry (sun elevation/azimuth, view angle), ESUN values, and spectral ranges that are not present in the NSO ISO 19115 XML. Required for target_level=atcorr or target_level=dos when sun elevation is needed and not available from the primary metadata file.
# % required: no
# % guisection: input
# %end

# %option
# % key: output
# % type: string
# % label: Output prefix
# % description: Prefix for output raster maps. Band names and product type suffixes are appended automatically (e.g., output=AA produces AA_blue, AA_red_rad, AA_nir_dos).
# % required: yes
# % guisection: output
# %end

# %option
# % key: processing_level
# % type: string
# % label: Input product processing level
# % description: Processing level of the input GeoTIFF. auto: detect from NSO XML ProductNaam (default). boa: bottom-of-atmosphere surface reflectance product (32-bit, scaled). dn: digital numbers (11-bit or 12-bit raw or geometry-corrected).
# % options: auto,boa,dn
# % answer: auto
# % required: no
# % guisection: input
# %end

# %option
# % key: boa_scale
# % type: double
# % label: BOA scale factor
# % description: Divisor to convert raw BOA pixel values into unitless reflectance (0-1). Set to 1.0 if the BOA GeoTIFF already stores reflectance as floats in [0,1] (typical for 32-bit BOA products). Set to 10000 for integer BOA products scaled by 10000.
# % answer: 1.0
# % required: no
# % guisection: input
# %end

# %option
# % key: target_level
# % type: string
# % label: Desired output processing level
# % description: as_is: keep input values (default for BOA input; just import and tag metadata). dn: keep input DN values (default for DN input when no processing requested). radiance: convert DN to TOA radiance only. dos: TOA radiance plus Dark Object Subtraction surface reflectance (a coarse approximation; see manual). atcorr: TOA radiance plus i.atcorr/6S surface reflectance (requires geometry_metadata and aerosol input).
# % options: as_is,dn,radiance,dos,atcorr
# % answer: as_is
# % required: no
# % guisection: output
# %end

# %option G_OPT_F_OUTPUT
# % key: icnd_basename
# % label: i.atcorr parameter file basename
# % description: Basename for i.atcorr parameter files (one per band). Only used for target_level=atcorr or with flag -a.
# % required: no
# % guisection: output
# %end

# %option
# % key: atmospheric_model
# % type: string
# % label: Atmospheric model
# % description: Atmospheric model for 6S (auto=derive from location/date, 0=no gas, 1=tropical, 2=midlat summer, 3=midlat winter, 4=subarctic summer, 5=subarctic winter, 6=US62)
# % options: auto,0,1,2,3,4,5,6
# % answer: auto
# % required: no
# % guisection: parameters
# %end

# %option
# % key: aerosol_model
# % type: integer
# % label: Aerosol model
# % description: Aerosol model for 6S (0=no aerosols, 1=continental, 2=maritime, 3=urban, 5=desert, 6=biomass burning, 7=stratospheric)
# % options: 0,1,2,3,5,6,7
# % answer: 1
# % required: no
# % guisection: parameters
# %end

# %option
# % key: visibility_or_aod
# % type: string
# % label: Visibility or AOD
# % description: Visibility in km or AOD at 550 nm with prefix aod:VALUE (e.g., aod:0.12). Required when aod_source is manual or visibility.
# % required: no
# % guisection: parameters
# %end

# %option
# % key: aod_source
# % type: string
# % label: Aerosol source
# % description: Aerosol source: manual (use visibility_or_aod value), aeronet_file (local AERONET file), cams (CAMS NetCDF/GRIB file), visibility (use visibility_or_aod as visibility in km). Required for target_level=atcorr; ignored otherwise.
# % options: manual,aeronet_file,cams,visibility
# % required: no
# % guisection: parameters
# %end

# %option G_OPT_F_BIN_INPUT
# % key: aeronet_file
# % label: AERONET file
# % description: Local AERONET all-points CSV/TXT file
# % required: no
# % guisection: aeronet
# %end

# %option
# % key: aeronet_time_window
# % type: integer
# % label: AERONET time window
# % description: Maximum absolute time difference in minutes for matching an AERONET observation
# % answer: 120
# % required: no
# % guisection: aeronet
# %end

# %option G_OPT_F_BIN_INPUT
# % key: cams_file
# % label: CAMS data file (NetCDF or GRIB)
# % description: CAMS global atmospheric composition file (NetCDF or GRIB) containing AOD at 550nm (e.g., from Copernicus ADS). The nearest time step to the acquisition is used and AOD is averaged over the analysis region. Requires Python package xarray (and cfgrib for GRIB files).
# % required: no
# % guisection: cams
# %end

# %option
# % key: cams_time_window
# % type: integer
# % label: CAMS time window
# % description: Maximum absolute time difference in minutes for matching a CAMS time step
# % answer: 180
# % required: no
# % guisection: cams
# %end

# %option
# % key: elevation
# % type: double
# % label: Elevation
# % description: Mean target elevation above sea level in meters (used in i.atcorr parameter file and as fallback when no elevation map is provided)
# % answer: 0
# % required: no
# % guisection: parameters
# %end

# %option
# % key: dark_parameter
# % type: integer
# % label: Dark object pixel threshold
# % description: For histogram method: minimum number of pixels a DN value must have to qualify as the dark object. For ols_intercept method: number of darkest pixels to include in the OLS regression. Set to 0 to use the absolute band minimum (not recommended for high-resolution imagery).
# % answer: 1000
# % required: no
# % guisection: parameters
# %end

# %option
# % key: dark_method
# % type: string
# % label: Dark object estimation method
# % description: histogram (i.landsat.toar convention), ols_intercept (DSF-inspired OLS through darkest N pixels), or quantile (low percentile of the DN distribution).
# % options: histogram,ols_intercept,quantile
# % answer: histogram
# % required: no
# % guisection: parameters
# %end

# %option
# % key: dark_percentile
# % type: double
# % label: Dark object percentile
# % description: Percentile of the per-band DN distribution used by dark_method=quantile. A small but non-zero value (e.g. 0.5-1.0) steps just above the sensor floor, avoiding latching onto deep-shadow or water pixels that sit at DN~0 in the NIR.
# % answer: 1.0
# % options: 0.01-50.0
# % required: no
# % guisection: parameters
# %end

# %option
# % key: tile_size
# % type: integer
# % label: Tile size for spatially variable DOS correction
# % description: When > 0, the dark object DN is estimated per square tile of this size (pixels) and spatially interpolated across the scene. Set to 0 (default) for a single whole-scene dark object estimate.
# % answer: 0
# % required: no
# % guisection: parameters
# %end

# %option G_OPT_R_INPUT
# % key: elevation_map
# % label: Elevation raster map
# % description: Input elevation raster map in meters for spatially variable atmospheric correction with i.atcorr.
# % required: no
# % guisection: parameters
# %end

# %option G_OPT_R_INPUT
# % key: cloud_mask
# % label: Cloud, shadow and water mask
# % description: Raster map where non-null cells mark pixels to EXCLUDE from dark-object estimation (clouds, cloud/terrain shadows, and water). This is the recommended way to keep deep shadow and water from contaminating the per-band dark object: such pixels are dark for non-atmospheric reasons and otherwise drag the NIR dark object to the sensor floor, inflating NDVI in shadow/water. Note: excluded pixels still receive output values; mask them in post-processing if you want them removed from the result. Any existing MASK must be removed before running this module.
# % required: no
# % guisection: input
# %end

# %option
# % key: nprocs
# % type: integer
# % label: Number of parallel threads
# % description: Number of threads for parallel computing in r.mapcalc (0=OpenMP default)
# % answer: 0
# % required: no
# %end

# %option
# % key: memory
# % type: integer
# % label: Memory in MB
# % description: Maximum memory in MB for r.in.gdal GDAL cache.
# % answer: 300
# % required: no
# %end

# %flag
# % key: a
# % label: Parameter files only (no atmospheric correction)
# % description: Do not run i.atcorr; only create i.atcorr parameter files. Requires icnd_basename to be set. Implies target_level handled separately.
# % guisection: output
# %end

# %flag
# % key: p
# % label: Use single-precision (float) output
# % description: Use float instead of double precision for radiance and reflectance maps. Reduces disk usage at the cost of minor precision loss.
# % guisection: parameters
# %end

# %flag
# % key: k
# % label: Keep intermediate maps
# % description: Keep imported DN bands and intermediate radiance maps. By default both are removed after processing to save disk space.
# % guisection: output
# %end

# %flag
# % key: r
# % label: Limit import to current region
# % description: By default the full image extent is imported. When this flag is set, only the portion within the current computational region is imported (-r to r.in.gdal).
# % guisection: input
# %end

# %option
# % key: rescale
# % type: string
# % label: i.atcorr output rescale range
# % description: Output range for i.atcorr reflectance values (min,max)
# % answer: 0,1
# % required: no
# % guisection: output
# %end

# %option G_OPT_F_OUTPUT
# % key: summary_file
# % label: Summary output file
# % description: Path for saving the processing summary to a text file
# % required: no
# % guisection: output
# %end

import atexit
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import grass.script as gs

# ---------------------------------------------------------------------------
# Make the shared library (grass_optical_lib.py) importable.
#
# The Makefile ships grass_optical_lib.py as an ETCFILE, so at install time
# it lands flat in $GISBASE/etc/i.in.svneo/ (or the $GRASS_ADDON_BASE
# equivalent). That directory is not on sys.path by default. set_path() is
# the GRASS-native helper that resolves etc/<modulename>/ and prepends it,
# and also handles the from-source and g.extension-compilation cases. We
# pass only the module name: the library file is flat in that directory,
# not inside a further sub-folder, so dirname/path are intentionally
# omitted.
# ---------------------------------------------------------------------------
from grass.script.utils import set_path

set_path(modulename="i.in.svneo")

# Sensor-agnostic helpers (AERONET / CAMS, 6S geometry, dark-object
# estimation, raster metadata tagging) shared with other optical-import
# addons. See grass_optical_lib.py.
from grass_optical_lib import (
    ATM_MODEL_NAMES,
    auto_atmospheric_model,
    choose_geometry,
    day_of_year,
    decimal_hour_utc,
    diagnose_dark_objects,
    earth_sun_distance_au,
    estimate_dark_object,
    estimate_tiled_dnmin_points,
    format_dark_object_table,
    interpolate_tiled_dnmin_points,
    resolve_aod550,
    safe_float,
    set_map_metadata,
    write_icnd_file,
)


# ---------------------------------------------------------------------------
# SuperView-NEO band conventions
# ---------------------------------------------------------------------------
# Band order in 4-band BGRN GeoTIFFs and in the L1B XML AbsCalibrationGain
# field: Blue, Green, Red, NIR.
BAND_IDS = ["B", "G", "R", "NIR"]
BAND_NAMES = {"B": "blue", "G": "green", "R": "red", "NIR": "nir"}
BAND_LABELS = {"B": "gen_b", "G": "gen_g", "R": "gen_r", "NIR": "gen_nir"}

# Mapping from band id to the parser option key that names the pre-imported
# raster for that band. Pre-imported bands are now given explicitly (one
# raster name per band) rather than guessed from a prefix + suffix, so there
# is no naming convention to detect and no ambiguity to resolve.
BAND_OPTION_KEY = {"B": "blue", "G": "green", "R": "red", "NIR": "nir"}

# Fallback ESUN (solar irradiance, W m-2 um-1) values for SuperView-NEO PMS
# bands. These are the values reported in the SVN1-04 L1B MUX XML
# <ESUN> element delivered with satellietdataportaal raw products:
#   ESUN = 1945.3, 1850.1, 1553.8, 1084.3  (order: B, G, R, NIR).
# Scene-specific values from the L1B XML override these when available.
HARDCODED_ESUN = {"B": 1945.3, "G": 1850.1, "R": 1553.8, "NIR": 1084.3}

# Fallback FWHM (full width at half maximum, nm) for SuperView-NEO PMS bands.
# Same provenance as HARDCODED_ESUN. Values from L1B XML
# <SpectralRangeStart> / <SpectralRangeEnd> (converted from µm to nm).
HARDCODED_FWHM = {
    "B": (450, 520),
    "G": (520, 590),
    "R": (630, 690),
    "NIR": (770, 890),
}

# ---------------------------------------------------------------------------
# SVN-NEO specific helpers
# ---------------------------------------------------------------------------
# Generic numeric and datetime helpers (safe_float, decimal_hour_utc,
# day_of_year, earth_sun_distance_au) are imported from grass_optical_lib
# above. The XML-specific datetime parser stays here because it is the
# one piece of metadata handling that is sensor-format-dependent.


def _parse_datetime_utc(text):
    """Parse a datetime string into a timezone-aware UTC datetime, or None."""
    if not text:
        return None
    txt = text.strip().rstrip("Z")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(txt, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Metadata parsing: NSO ISO 19115 XML and raw L1B MUX XML
# ---------------------------------------------------------------------------


# Regex patterns for the NSO supplementalInformation free-text block. The
# block uses a mix of "Gain-band-red"/"Gain-band-NIR" (hyphenated) and
# "Offset-band_NIR" (underscore!) — the regex below tolerates both.
_NSO_GAIN_PATTERN = re.compile(
    r"Gain[-_]band[-_]({})\s*[:=]\s*([0-9eE.+\-]+)",
    flags=re.IGNORECASE,
)
_NSO_OFFSET_PATTERN = re.compile(
    r"Offset[-_]band[-_]({})\s*[:=]\s*([0-9eE.+\-]+)",
    flags=re.IGNORECASE,
)


def _nso_band_token(bid):
    """Map our internal band ID to the NSO XML band label tokens."""
    return {"B": "blue", "G": "green", "R": "red", "NIR": "NIR"}[bid]


def parse_nso_xml(xml_path):
    """Parse NSO ISO 19115 XML and extract SuperView-NEO scene metadata.

    Returns a dict with the following keys (any may be None if not found):

      scene_datetime       datetime in UTC
      satellite_name       string (e.g. "SuperView-NEO")
      product_name         string (e.g. "30cm_BGRN_BOA_32bit_SVNEO")
      product_kind         "boa" if "BOA" in product_name (case-insensitive),
                           "11bit" / "12bit" if a bit-depth tag is present,
                           "dn" if neither but a gain/bias block is present,
                           else None.
      incidence_angle      float (degrees)
      cloud_cover          float (percent)
      center_lon           float (degrees)
      center_lat           float (degrees)
      west / east /        floats (degrees) — geographic bounding box from
      south / north        gmd:EX_GeographicBoundingBox
      gain_bias            dict {bid: {"gain": float, "bias": float}} as
                           parsed from the supplementalInformation block.
                           Empty if no per-band gain/bias is reported.
      nodata               int (0 by default for SVN-NEO products)
    """
    ns = {
        "gmd": "http://www.isotc211.org/2005/gmd",
        "gco": "http://www.isotc211.org/2005/gco",
        "gml": "http://www.opengis.net/gml",
    }
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as err:
        gs.fatal(f"Failed to parse NSO XML {xml_path}: {err}")
    root = tree.getroot()

    suppl_el = root.find(".//gmd:supplementalInformation/gco:CharacterString", ns)
    suppl = suppl_el.text if suppl_el is not None and suppl_el.text else ""

    # Scene datetime from temporal extent
    begin_pos = root.findtext(".//gml:beginPosition", namespaces=ns)
    scene_datetime = _parse_datetime_utc(begin_pos)

    # Geographic bounding box (always WGS84 per ISO 19115)
    west = east = south = north = None
    bbox = root.find(".//gmd:EX_GeographicBoundingBox", ns)
    if bbox is not None:
        west = safe_float(
            bbox.findtext("gmd:westBoundLongitude/gco:Decimal", namespaces=ns)
        )
        east = safe_float(
            bbox.findtext("gmd:eastBoundLongitude/gco:Decimal", namespaces=ns)
        )
        south = safe_float(
            bbox.findtext("gmd:southBoundLatitude/gco:Decimal", namespaces=ns)
        )
        north = safe_float(
            bbox.findtext("gmd:northBoundLatitude/gco:Decimal", namespaces=ns)
        )
    center_lon = (west + east) / 2.0 if (west is not None and east is not None) else None
    center_lat = (south + north) / 2.0 if (south is not None and north is not None) else None

    # Free-text supplementalInformation block
    satellite_name = None
    m = re.search(r"SatelliteName\s*[:=]\s*(.+)", suppl)
    if m:
        satellite_name = m.group(1).strip().splitlines()[0].strip()

    product_name = None
    m = re.search(r"ProductNaam\s*[:=]\s*(.+)", suppl)
    if m:
        product_name = m.group(1).strip().splitlines()[0].strip()

    incidence_angle = None
    m = re.search(r"Incidence[_ ]angle\s*[:=]\s*([0-9eE.+\-]+)", suppl)
    if m:
        incidence_angle = safe_float(m.group(1))

    cloud_cover = None
    m = re.search(r"Cloudcover\s*[:=]\s*([0-9eE.+\-]+)", suppl)
    if m:
        cloud_cover = safe_float(m.group(1))

    # Per-band gain and bias from supplementalInformation
    gain_bias = {}
    for bid in BAND_IDS:
        token = _nso_band_token(bid)
        gm = re.search(
            rf"Gain[-_]band[-_]{token}\s*[:=]\s*([0-9eE.+\-]+)",
            suppl,
            flags=re.IGNORECASE,
        )
        bm = re.search(
            rf"Offset[-_]band[-_]{token}\s*[:=]\s*([0-9eE.+\-]+)",
            suppl,
            flags=re.IGNORECASE,
        )
        gain = safe_float(gm.group(1)) if gm else None
        bias = safe_float(bm.group(1)) if bm else None
        if gain is not None:
            gain_bias[bid] = {"gain": gain, "bias": 0.0 if bias is None else bias}

    # Classify product kind
    product_kind = None
    if product_name:
        pn_upper = product_name.upper()
        if "BOA" in pn_upper:
            product_kind = "boa"
        elif "11BIT" in pn_upper or "11_BIT" in pn_upper:
            product_kind = "11bit"
        elif "12BIT" in pn_upper or "12_BIT" in pn_upper:
            product_kind = "12bit"
        elif gain_bias:
            product_kind = "dn"

    return {
        "scene_datetime": scene_datetime,
        "satellite_name": satellite_name,
        "product_name": product_name,
        "product_kind": product_kind,
        "incidence_angle": incidence_angle,
        "cloud_cover": cloud_cover,
        "center_lon": center_lon,
        "center_lat": center_lat,
        "west": west,
        "east": east,
        "south": south,
        "north": north,
        "gain_bias": gain_bias,
        # NSO SVN-NEO products use 0 as nodata for the 4-band imagery
        "nodata": 0,
    }


def _split_csv_floats(text):
    """Split a CSV-like string into a list of floats, ignoring empty tokens."""
    if not text:
        return []
    return [v for v in (safe_float(t) for t in text.split(",")) if v is not None]


def parse_l1b_xml(xml_path):
    """Parse a CRESDA SuperView-NEO L1B MUX XML.

    Two distinct schemas are issued by the CRESDA ground segment, with the
    cutover around 2026-02-01 (the date the satellietdataportaal mentions
    for the introduction of ``AbsCalibrationGain``/``AbsCalibrationBias``):

      * **v1** (pre-2026-02-01) — flat ``<ProductMetaData>`` root (note the
        capital D in "Data"). Calibration is in ``Gain``/``Offset`` tags
        directly under the root, geometry uses zenith angles
        (``SolarZenith``, ``SatelliteZenith``), spectral ranges are absent,
        bit depth is in ``ValidPixelBits``.
      * **v2** (post-2026-02-01) — nested ``<ProductMetadata>`` root with
        ``<ProductInfo>``/``<ProcessInfo>``/``<AuxInfo>`` sections.
        Calibration is in ``AbsCalibrationGain``/``AbsCalibrationBias``
        inside ``ProcessInfo``, geometry uses elevation angles
        (``SolarElevation``, ``SatelliteElevation``), spectral ranges are
        present in micrometers, bit depth is in ``ValidDataBits``.

    This dispatcher detects the schema from the root tag and forwards to
    the appropriate schema-specific parser. Both parsers return the same
    dict shape so callers don't have to care which vintage they got:

      scene_datetime    datetime in UTC (parsed from first AttTime), or None
      sun_elevation     float (degrees)   -- always elevation, even if the
                                              source XML carried zenith
      sun_azimuth       float (degrees)
      view_angle        float (degrees) -- pitch+roll combined
      satellite_azimuth float (degrees)
      satellite_elev    float (degrees)   -- always elevation, see above
      center_lon        float (degrees)
      center_lat        float (degrees)
      esun              dict {bid: float}
      fwhm              dict {bid: (start_nm, end_nm)} -- empty for v1
      gain_bias         dict {bid: {"gain": float, "bias": float}}
      valid_data_bits   int  -- 11 (v1 default) or 12 (v2 default)
      cloud_percent     float

    The acquisition time fields (Centertime/CenterTime, StartTime, EndTime)
    have been seen in Beijing time (UTC+8) in some past deliveries, while
    the AttTime entries inside AuxInfo are reliably UTC. Both parsers
    therefore prefer the first AttTime and only fall back to CenterTime if
    no AttData is present.
    """
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as err:
        gs.fatal(f"Failed to parse L1B MUX XML {xml_path}: {err}")
    root = tree.getroot()
    root_tag = root.tag.split("}", 1)[1] if "}" in root.tag else root.tag

    if root_tag == "ProductMetaData":
        return _parse_l1b_v1_xml(xml_path, root)
    if root_tag == "ProductMetadata":
        return _parse_l1b_v2_xml(xml_path, root)
    gs.fatal(
        f"L1B XML {xml_path} has an unexpected root element <{root_tag}>; "
        f"expected <ProductMetaData> (pre-2026-02-01) or "
        f"<ProductMetadata> (post-2026-02-01)."
    )


def _zenith_to_elevation(zenith):
    """Convert a zenith angle in degrees to an elevation angle, or None."""
    return None if zenith is None else 90.0 - zenith


def _attdata_scene_datetime(aux_elem):
    """Return the first AttData/AttTime as a UTC datetime, or None.

    ``aux_elem`` may be None (some deliveries lack AuxInfo); in that case
    the function returns None and the caller falls back to CenterTime.
    """
    if aux_elem is None:
        return None
    att = aux_elem.find(".//AttData/AttTime")
    if att is None or not att.text:
        return None
    return _parse_datetime_utc(att.text)


def _parse_l1b_v1_xml(xml_path, root):
    """Parse a pre-2026-02-01 SuperView-NEO L1B MUX XML (flat schema).

    The v1 schema is entirely flat under ``<ProductMetaData>``: calibration
    is in ``<Gain>`` and ``<Offset>`` (both CSV in B,G,R,NIR order),
    geometry is reported as zenith angles, and spectral ranges are absent.
    """
    # Acquisition time: AuxInfo/AttParam/AttData/AttTime (UTC), with a
    # CenterTime fallback. CenterTime has historically been seen in Beijing
    # time in some deliveries, hence the preference for AttTime.
    aux = root.find("AuxInfo")
    scene_dt = _attdata_scene_datetime(aux)
    if scene_dt is None:
        scene_dt = _parse_datetime_utc(root.findtext("CenterTime"))

    # Geometry: v1 reports zenith; convert to elevation so the returned
    # dict has the same shape across both schemas.
    sun_elev = _zenith_to_elevation(safe_float(root.findtext("SolarZenith")))
    sun_az = safe_float(root.findtext("SolarAzimuth"))
    view_angle = safe_float(root.findtext("ViewAngle"))
    sat_az = safe_float(root.findtext("SatelliteAzimuth"))
    sat_elev = _zenith_to_elevation(safe_float(root.findtext("SatelliteZenith")))
    center_lon = safe_float(root.findtext("CenterLongitude"))
    center_lat = safe_float(root.findtext("CenterLatitude"))

    # ESUN, gain, and bias are all CSV in B,G,R,NIR order at the root.
    esun_vals = _split_csv_floats(root.findtext("ESUN"))
    esun = {bid: esun_vals[i] for i, bid in enumerate(BAND_IDS)
            if i < len(esun_vals)}

    gain_vals = _split_csv_floats(root.findtext("Gain"))
    bias_vals = _split_csv_floats(root.findtext("Offset"))
    gain_bias = {}
    for i, bid in enumerate(BAND_IDS):
        gain = gain_vals[i] if i < len(gain_vals) else None
        bias = bias_vals[i] if i < len(bias_vals) else None
        if gain is not None:
            gain_bias[bid] = {"gain": gain, "bias": 0.0 if bias is None else bias}

    # v1 carries no SpectralRange* tags; downstream falls back to
    # HARDCODED_FWHM, whose values happen to match the per-scene values
    # reported by v2 (verified empirically).
    fwhm = {}

    # Bit depth: v1 calls it ValidPixelBits, defaults to 11.
    valid_bits_text = root.findtext("ValidPixelBits")
    try:
        valid_data_bits = int(valid_bits_text) if valid_bits_text else 11
    except ValueError:
        valid_data_bits = 11

    cloud_percent = safe_float(root.findtext("CloudPercent"))

    return {
        "scene_datetime": scene_dt,
        "sun_elevation": sun_elev,
        "sun_azimuth": sun_az,
        "view_angle": view_angle,
        "satellite_azimuth": sat_az,
        "satellite_elev": sat_elev,
        "center_lon": center_lon,
        "center_lat": center_lat,
        "esun": esun,
        "fwhm": fwhm,
        "gain_bias": gain_bias,
        "valid_data_bits": valid_data_bits,
        "cloud_percent": cloud_percent,
    }


def _parse_l1b_v2_xml(xml_path, root):
    """Parse a post-2026-02-01 SuperView-NEO L1B MUX XML (nested schema).

    The v2 schema groups fields under ``<ProductInfo>``, ``<ProcessInfo>``,
    and ``<AuxInfo>``. Calibration uses ``AbsCalibrationGain`` and
    ``AbsCalibrationBias`` (CSV in B,G,R,NIR order), geometry is reported
    as elevation angles, and spectral ranges are present.
    """
    pi = root.find("ProductInfo")
    pri = root.find("ProcessInfo")
    aux = root.find("AuxInfo")

    if pi is None:
        gs.fatal(
            f"L1B XML {xml_path} has root <ProductMetadata> but no "
            f"<ProductInfo> element; the post-2026-02-01 nested schema "
            f"requires <ProductInfo>."
        )

    # Acquisition time: AttTime in AuxInfo, with Centertime (note lowercase
    # 't' in v2) as a fallback.
    scene_dt = _attdata_scene_datetime(aux)
    if scene_dt is None:
        scene_dt = _parse_datetime_utc(pi.findtext("Centertime"))

    sun_elev = safe_float(pi.findtext("SolarElevation"))
    sun_az = safe_float(pi.findtext("SolarAzimuth"))
    view_angle = safe_float(pi.findtext("Viewangle"))
    sat_az = safe_float(pi.findtext("SatelliteAzimuth"))
    sat_elev = safe_float(pi.findtext("SatelliteElevation"))
    center_lon = safe_float(pi.findtext("CenterLongitude"))
    center_lat = safe_float(pi.findtext("CenterLatitude"))

    # ESUN (B, G, R, NIR) — trailing comma is tolerated by _split_csv_floats
    esun_vals = _split_csv_floats(pi.findtext("ESUN"))
    esun = {bid: esun_vals[i] for i, bid in enumerate(BAND_IDS)
            if i < len(esun_vals)}

    # Spectral ranges (µm -> nm)
    start_vals = _split_csv_floats(pi.findtext("SpectralRangeStart"))
    end_vals = _split_csv_floats(pi.findtext("SpectralRangeEnd"))
    fwhm = {}
    for i, bid in enumerate(BAND_IDS):
        if i < len(start_vals) and i < len(end_vals):
            fwhm[bid] = (
                int(round(start_vals[i] * 1000.0)),
                int(round(end_vals[i] * 1000.0)),
            )

    # Calibration gain and bias (B, G, R, NIR)
    gain_bias = {}
    if pri is not None:
        gain_vals = _split_csv_floats(pri.findtext("AbsCalibrationGain"))
        bias_vals = _split_csv_floats(pri.findtext("AbsCalibrationBias"))
        for i, bid in enumerate(BAND_IDS):
            gain = gain_vals[i] if i < len(gain_vals) else None
            bias = bias_vals[i] if i < len(bias_vals) else None
            if gain is not None:
                gain_bias[bid] = {"gain": gain, "bias": 0.0 if bias is None else bias}

    # Bit depth: v2 calls it ValidDataBits, defaults to 12.
    valid_bits_text = pi.findtext("ValidDataBits")
    try:
        valid_data_bits = int(valid_bits_text) if valid_bits_text else 12
    except ValueError:
        valid_data_bits = 12

    cloud_percent = safe_float(pi.findtext("CloudPercent"))

    return {
        "scene_datetime": scene_dt,
        "sun_elevation": sun_elev,
        "sun_azimuth": sun_az,
        "view_angle": view_angle,
        "satellite_azimuth": sat_az,
        "satellite_elev": sat_elev,
        "center_lon": center_lon,
        "center_lat": center_lat,
        "esun": esun,
        "fwhm": fwhm,
        "gain_bias": gain_bias,
        "valid_data_bits": valid_data_bits,
        "cloud_percent": cloud_percent,
    }


def detect_xml_type(xml_path):
    """Return 'nso' or 'l1b' based on the XML root element.

    Two CRESDA L1B MUX root spellings exist in the wild:
      * ``ProductMetaData`` — pre-2026-02-01 deliveries (flat schema with
        ``Gain``/``Offset``, ``SolarZenith``, ``ValidPixelBits``)
      * ``ProductMetadata`` — post-2026-02-01 deliveries (nested
        ``ProductInfo``/``ProcessInfo`` schema with ``AbsCalibrationGain``,
        ``SolarElevation``, ``ValidDataBits``)
    Both map to ``"l1b"`` here; ``parse_l1b_xml`` dispatches on the schema
    variant.
    """
    try:
        # iterparse + early stop is faster than ET.parse for large files
        for event, elem in ET.iterparse(xml_path, events=("start",)):
            tag = elem.tag
            # Strip namespace if present
            if "}" in tag:
                tag = tag.split("}", 1)[1]
            if tag == "MD_Metadata":
                return "nso"
            if tag in ("ProductMetadata", "ProductMetaData"):
                return "l1b"
            # Unrecognized root — give up immediately
            return "unknown"
    except ET.ParseError as err:
        gs.fatal(f"Failed to read XML {xml_path}: {err}")
    return "unknown"


def merge_metadata(nso, l1b):
    """Merge metadata from NSO XML and (optionally) raw L1B MUX XML.

    The NSO XML is treated as authoritative for the acquisition timestamp
    (it is reliably in UTC and matches gml:beginPosition), while the L1B
    XML is the only source of sun geometry, ESUN, and spectral ranges. For
    gain and bias either source is fine — we prefer the L1B values when
    both are present because they are written with more decimal places
    in the L1B XML.
    """
    if nso is None and l1b is None:
        gs.fatal("No metadata available")

    if nso is None:
        # Build a minimal nso-like dict from the L1B XML
        nso = {
            "scene_datetime": l1b["scene_datetime"],
            "satellite_name": "SuperView-NEO",
            "product_name": None,
            "product_kind": "dn",
            "incidence_angle": None,
            "cloud_cover": l1b.get("cloud_percent"),
            "center_lon": l1b.get("center_lon"),
            "center_lat": l1b.get("center_lat"),
            "west": None, "east": None, "south": None, "north": None,
            "gain_bias": l1b.get("gain_bias", {}),
            "nodata": 0,
        }

    scene_dt = nso.get("scene_datetime") or (
        l1b.get("scene_datetime") if l1b else None
    )
    center_lon = nso.get("center_lon")
    if center_lon is None and l1b:
        center_lon = l1b.get("center_lon")
    center_lat = nso.get("center_lat")
    if center_lat is None and l1b:
        center_lat = l1b.get("center_lat")

    # Prefer L1B gain/bias when both are present
    gain_bias = dict(nso.get("gain_bias", {}))
    if l1b and l1b.get("gain_bias"):
        gain_bias.update(l1b["gain_bias"])

    esun = dict(l1b.get("esun", {})) if l1b else {}
    fwhm = dict(l1b.get("fwhm", {})) if l1b else {}

    geometry = {
        "sun_elevation": l1b.get("sun_elevation") if l1b else None,
        "sun_azimuth": l1b.get("sun_azimuth") if l1b else None,
        "view_zenith": l1b.get("view_angle") if l1b else None,
        "view_azimuth": l1b.get("satellite_azimuth") if l1b else None,
        "incidence_angle": nso.get("incidence_angle"),
    }

    valid_data_bits = (l1b.get("valid_data_bits") if l1b else None) or 12

    return {
        "scene_datetime": scene_dt,
        "satellite_name": nso.get("satellite_name") or "SuperView-NEO",
        "product_name": nso.get("product_name"),
        "product_kind": nso.get("product_kind"),
        "incidence_angle": nso.get("incidence_angle"),
        "cloud_cover": nso.get("cloud_cover")
        if nso.get("cloud_cover") is not None
        else (l1b.get("cloud_percent") if l1b else None),
        "center_lon": center_lon,
        "center_lat": center_lat,
        "gain_bias": gain_bias,
        "esun": esun,
        "fwhm": fwhm,
        "geometry": geometry,
        "valid_data_bits": valid_data_bits,
        "nodata": 0,
    }


# ---------------------------------------------------------------------------
# AERONET / CAMS aerosol retrieval and AOD-550 resolution are provided by
# grass_optical_lib.resolve_aod550 (and its supporting functions).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 6S geometry and atmospheric-model selection (auto_atmospheric_model,
# choose_geometry, write_icnd_file) are provided by grass_optical_lib.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Radiance and DOS expressions for SuperView-NEO
# ---------------------------------------------------------------------------


def build_radiance_expression(inmap, outmap, gain, bias, nodata_value, use_float=False):
    """Build the r.mapcalc expression for DN -> TOA radiance.

    SuperView-NEO convention (satellietdataportaal documentation):

        L = DN * GAIN + BIAS              (multiplicative gain)

    This is the OPPOSITE convention from Pléiades-NEO / SPOT, where the gain
    enters as a divisor (L = DN/GAIN + BIAS). Make sure you do not feed an
    Airbus-style gain into this expression: the resulting radiance values
    would differ by 4–5 orders of magnitude.

    Nodata DN values are mapped to NULL in the output.
    """
    cast = "float" if use_float else "double"
    return (
        f"{outmap} = if({inmap} == {nodata_value}, null(), "
        f"{cast}({inmap}) * ({gain}) + ({bias}))"
    )


def build_dos_expression(
    radmap,
    inmap,
    outmap,
    gain,
    bias,
    esun,
    sun_elev_deg,
    doy,
    nodata_value,
    dnmin,
    use_float=False,
):
    """Build a DOS surface reflectance expression for SuperView-NEO.

    Dark Object Subtraction (Chavez, 1988; Moran et al., 1992) in the
    classic "DOS1" form: TAUv=1, TAUz=1, Esky=0. The dark object is
    assumed to have 1% surface reflectance, and its radiance is removed
    as a single scene-wide path-radiance constant.

    SuperView-NEO uses a *multiplicative* gain, so the radiance of the
    dark object is:

        L_dark = DNmin * GAIN + BIAS
        Lp     = L_dark - 0.01 * ESUN * sin(e) / (pi * d^2)
        rho    = pi * (L - Lp) * d^2 / (ESUN * sin(e))

    A previous version also offered a "DOS2" variant that scaled the
    transmittance by TAUz = sin(e) for bands below 1000 nm. It was
    removed: for ratio indices such as NDVI the TAUz factor applies
    identically to both bands and very nearly cancels (verified to move
    NDVI by <= 0.006 on real surfaces for this sensor), so it added an
    unvalidated Landsat-era heuristic with no practical benefit here.
    """
    dist = earth_sun_distance_au(doy)
    sin_e = math.sin(math.radians(sun_elev_deg))
    if sin_e <= 0:
        gs.fatal("SUN_ELEVATION must be > 0 for DOS reflectance")

    cast = "float" if use_float else "double"

    if isinstance(dnmin, str):
        dnmin_expr = dnmin
    else:
        dnmin_expr = f"{dnmin:.10g}"

    # L_dark = DNmin*GAIN + BIAS
    # Lp = L_dark - 0.01 * ESUN * sin(e) / (pi * d^2)
    lp = (
        f"(({dnmin_expr}) * ({gain}) + ({bias}) "
        f"- (0.01 * ({esun}) * {sin_e} / "
        f"(3.141592653589793 * {dist ** 2})))"
    )
    # rho = pi * (L - Lp) * d^2 / (ESUN * sin(e))
    unscaled = (
        f"(3.141592653589793 * ({cast}({radmap}) - {lp}) "
        f"* {dist ** 2} / (({esun}) * {sin_e}))"
    )
    return (
        f"{outmap} = if({inmap} == {nodata_value}, null(), "
        f"max(0.0, {unscaled}))"
    )


# ---------------------------------------------------------------------------
# Dark-object estimation (get_dark_object_dn, get_dark_ols_intercept,
# get_dark_quantile, estimate_dark_object, estimate_tiled_dnmin_points,
# interpolate_tiled_dnmin_points) is provided by grass_optical_lib. Those
# functions are sensor-agnostic and operate on DN rasters and a nodata
# sentinel.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Metadata tagging
# ---------------------------------------------------------------------------


def _set_map_metadata(mapname, bid, product_type, source_file, scene_dt, units):
    """Thin sensor-specific wrapper around grass_optical_lib.set_map_metadata.

    Builds the title and semantic label from the SuperView-NEO band tables
    (``BAND_NAMES``, ``BAND_LABELS``) and forwards the call to the generic
    tagger in the shared library.
    """
    source_basename = os.path.basename(source_file)
    title = f"{BAND_NAMES[bid]} {product_type} from {source_basename}"
    semantic_label = BAND_LABELS.get(bid, "")
    set_map_metadata(
        mapname,
        title=title,
        units=units,
        semantic_label=semantic_label,
        scene_dt=scene_dt,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


PROC_LEVEL_DESC = {
    "boa_passthrough": "BOA surface reflectance (import + metadata only)",
    "dn_passthrough":  "DN passthrough (import + metadata only)",
    "radiance":        "TOA radiance (DN -> radiance conversion)",
    "dos":             "DOS approximate surface reflectance",
    "atcorr":          "Full atmospheric correction (i.atcorr / 6S)",
    "atcorr_params":   "i.atcorr parameter files only (-a flag)",
}


def main():
    options, flags = gs.parser()

    # ---- Check for existing MASK --------------------------------------
    if gs.find_file("MASK", element="cell")["name"]:
        gs.fatal(
            "An active MASK was found. Please remove it with 'r.mask -r' "
            "before running i.in.svneo. If you need to exclude clouds or "
            "shadows from dark-object estimation, use the cloud_mask= "
            "parameter instead."
        )

    # ---- Validate inputs ----------------------------------------------
    input_tif = options["input"]
    # Explicit per-band rasters. The parser %rules enforce all-four-or-none
    # (collective) and mutual exclusion with input=, so here we only need to
    # detect which mode we are in.
    band_opts = {bid: (options[BAND_OPTION_KEY[bid]] or "").strip()
                 for bid in BAND_IDS}
    use_preimported = any(band_opts.values())
    if not input_tif and not use_preimported:
        gs.fatal(
            "Provide either input= (a 4-band GeoTIFF) or the four band "
            "options (blue=, green=, red=, nir=) naming pre-imported "
            "rasters."
        )

    file_keys = ["metadata", "geometry_metadata", "aeronet_file", "cams_file"]
    if not use_preimported and input_tif:
        file_keys.insert(0, "input")
    missing = []
    for key in file_keys:
        fp = options[key]
        if fp and not os.path.isfile(fp):
            missing.append(f"  {key}={fp}")
    if missing:
        gs.fatal("The following input file(s) were not found:\n" + "\n".join(missing))

    memory = int(options["memory"])
    output_prefix = options["output"].strip()
    if not output_prefix:
        gs.fatal("output= prefix must not be empty")

    # ---- Parse metadata ----------------------------------------------
    primary_xml = options["metadata"]
    primary_type = detect_xml_type(primary_xml)
    if primary_type == "unknown":
        gs.fatal(
            f"Could not detect XML type of {primary_xml}. Expected either "
            f"an NSO ISO 19115 (<MD_Metadata>) or a SuperView-NEO raw L1B "
            f"MUX XML (<ProductMetadata> for post-2026-02-01 deliveries, "
            f"or <ProductMetaData> for pre-2026-02-01 deliveries)."
        )

    nso_meta = None
    l1b_meta = None
    if primary_type == "nso":
        nso_meta = parse_nso_xml(primary_xml)
    else:
        l1b_meta = parse_l1b_xml(primary_xml)

    if options["geometry_metadata"]:
        geom_type = detect_xml_type(options["geometry_metadata"])
        if geom_type == "l1b":
            l1b_meta = parse_l1b_xml(options["geometry_metadata"])
        elif geom_type == "nso" and nso_meta is None:
            nso_meta = parse_nso_xml(options["geometry_metadata"])
        else:
            gs.warning(
                f"geometry_metadata={options['geometry_metadata']} did not "
                f"look like a raw L1B XML (root: {geom_type}); ignored."
            )

    meta = merge_metadata(nso_meta, l1b_meta)
    scene_dt = meta["scene_datetime"]
    if scene_dt is None:
        gs.warning("Could not determine acquisition datetime from metadata")

    # ---- Decide input processing level (BOA vs DN) -------------------
    proc_opt = options["processing_level"].strip().lower()
    if proc_opt == "auto":
        if meta.get("product_kind") == "boa":
            input_level = "boa"
        elif meta.get("product_kind") in ("11bit", "12bit", "dn"):
            input_level = "dn"
        else:
            # Default to BOA — the historical behaviour of i.in.svneo —
            # but warn the user that we are guessing.
            input_level = "boa"
            gs.warning(
                "processing_level=auto could not determine input level "
                "from the metadata ProductNaam; assuming BOA. Override "
                "with processing_level=dn if this is wrong."
            )
    else:
        input_level = proc_opt

    # ---- Decide target processing level -------------------------------
    target = options["target_level"].strip().lower()
    skip_atcorr = bool(flags["a"])

    # Interpret "as_is" depending on input
    if target == "as_is":
        target = "boa_pass" if input_level == "boa" else "dn_pass"

    # Validate combinations
    if input_level == "boa" and target not in ("boa_pass", "dn_pass"):
        gs.fatal(
            f"target_level={target} requires a DN input; the metadata "
            f"identifies a BOA product. Set processing_level=dn explicitly "
            f"if this is actually a DN product."
        )

    if input_level == "dn" and target == "boa_pass":
        # User explicitly asked for as_is/dn pass on a DN product
        target = "dn_pass"

    # DOS reflectance needs an explicit sun elevation value (it enters the
    # math directly as sin(e)). The NSO XML alone does not supply this, so
    # DOS without an L1B XML is a fatal error rather than a silent skip.
    if target == "dos":
        if meta["geometry"].get("sun_elevation") is None:
            gs.fatal(
                "target_level=dos requires the sun elevation angle, "
                "which is only available from the raw SVN1-04 L1B MUX XML. "
                "Provide the L1B XML via geometry_metadata= (or as the "
                "metadata= argument if you do not have the NSO XML)."
            )

    # i.atcorr/6S can take either explicit angles (geometry code 0) or
    # acquisition time + center lat/lon (geometry code 6); it computes
    # the sun position internally in the latter case. So atcorr only
    # needs *some* form of geometry.
    if target == "atcorr":
        has_angles = (
            meta["geometry"].get("sun_elevation") is not None
            and meta["geometry"].get("sun_azimuth") is not None
            and meta["geometry"].get("view_zenith") is not None
            and meta["geometry"].get("view_azimuth") is not None
        )
        has_latlon_time = (
            scene_dt is not None
            and meta.get("center_lon") is not None
            and meta.get("center_lat") is not None
        )
        if not has_angles and not has_latlon_time:
            gs.fatal(
                "target_level=atcorr requires either explicit sun and view "
                "angles (from the raw L1B MUX XML, passed via "
                "geometry_metadata=) or acquisition time + scene center "
                "coordinates (from the NSO XML)."
            )

    if target == "atcorr":
        if not options["aod_source"]:
            gs.fatal(
                "target_level=atcorr requires aod_source= to be set "
                "(manual, visibility, aeronet_file, or cams)."
            )

    if skip_atcorr:
        if not options["icnd_basename"]:
            gs.fatal(
                "Flag -a (parameter files only) requires icnd_basename= "
                "to be set."
            )
        if input_level != "dn":
            gs.fatal("Flag -a only applies to DN input")
        # -a means "no atmospheric correction": output is TOA radiance plus
        # i.atcorr parameter files. It overrides target_level=atcorr/dos.
        if target in ("atcorr", "dos"):
            target = "radiance"

    # ---- Import or attach pre-imported bands --------------------------
    if use_preimported:
        input_maps = [None] * len(BAND_IDS)
        missing = []
        for idx, bid in enumerate(BAND_IDS):
            name = band_opts[bid]
            if not gs.find_file(name, element="cell")["name"]:
                missing.append((bid, name))
            else:
                input_maps[idx] = name
        if missing:
            details = "; ".join(
                f"{BAND_NAMES[bid]}={name}" for bid, name in missing
            )
            gs.fatal(
                f"Pre-imported band raster(s) not found in the current "
                f"mapset search path: {details}."
            )
        # Label the scene by the common stem of the four band names if there
        # is one, else by the red band (an arbitrary but stable choice).
        common = os.path.commonprefix(
            [band_opts[bid] for bid in BAND_IDS]
        ).rstrip("._-")
        source_file_label = common if common else band_opts["R"]
        tif_basename = source_file_label
    else:
        tif_basename = os.path.splitext(os.path.basename(input_tif))[0]
        tif_basename = re.sub(r"[^A-Za-z0-9_]", "_", tif_basename)
        gdal_flags = "rk" if flags["r"] else "k"
        gs.message(f"Importing {input_tif} using r.in.gdal ...")
        gs.run_command(
            "r.in.gdal", flags=gdal_flags, input=input_tif,
            output=tif_basename, memory=memory, overwrite=gs.overwrite(),
        )
        input_maps = []
        for i in range(1, len(BAND_IDS) + 1):
            name = f"{tif_basename}.{i}"
            if not gs.find_file(name, element="cell")["name"]:
                gs.fatal(
                    f"Expected raster band not found after import: {name}. "
                    f"The TIFF must have exactly {len(BAND_IDS)} bands "
                    f"(blue, green, red, NIR)."
                )
            input_maps.append(name)
        source_file_label = input_tif

    # =================================================================
    # SHORT PATH — BOA or DN passthrough (no radiometric conversion)
    # =================================================================
    if target in ("boa_pass", "dn_pass"):
        # Set the computational region to match the imported raster extent.
        ref_band = input_maps[0]
        restrict = bool(flags["r"]) and not use_preimported
        region_kwargs = {"zoom": ref_band, "align": ref_band} if restrict \
            else {"raster": ref_band}

        boa_scale = safe_float(options["boa_scale"])
        if target == "boa_pass" and boa_scale is None:
            boa_scale = 1.0

        output_maps = []
        with gs.RegionManager(**region_kwargs):
            for idx, bid in enumerate(BAND_IDS):
                gdal_name = input_maps[idx]
                bname = BAND_NAMES[bid]
                final_name = f"{output_prefix}_{bname}"

                if target == "boa_pass" and boa_scale and boa_scale != 1.0:
                    # Apply a scale factor to convert integer BOA values to
                    # unitless reflectance in [0, 1].
                    cast = "float" if flags["p"] else "double"
                    expr = (
                        f"{final_name} = if({gdal_name} == {meta['nodata']}, "
                        f"null(), {cast}({gdal_name}) / ({boa_scale}))"
                    )
                    gs.mapcalc(expr, overwrite=gs.overwrite(),
                               nprocs=int(options["nprocs"]))
                    # We can remove the original gdal-named raster
                    if not use_preimported:
                        gs.run_command(
                            "g.remove", type="raster", name=gdal_name,
                            flags="f", quiet=True,
                        )
                else:
                    # No scaling — just rename (or keep, if pre-imported)
                    if use_preimported and gdal_name == final_name:
                        pass
                    else:
                        gs.run_command(
                            "g.rename", raster=f"{gdal_name},{final_name}",
                            overwrite=gs.overwrite(),
                        )

                if target == "boa_pass":
                    units = "reflectance"
                    product_type = "BOA reflectance"
                else:
                    units = "digital number"
                    product_type = "DN"
                _set_map_metadata(
                    final_name, bid, product_type,
                    source_file_label, scene_dt, units,
                )
                output_maps.append(final_name)

        _print_summary(
            meta=meta,
            source_file=source_file_label,
            output_prefix=output_prefix,
            input_level=input_level,
            target_label="boa_passthrough" if target == "boa_pass" else "dn_passthrough",
            output_maps=output_maps,
            summary_file=options["summary_file"],
        )
        return 0

    # =================================================================
    # LONG PATH — radiance / DOS / atcorr (DN input only)
    # =================================================================

    # Validate gain/bias availability
    gain_offset = meta["gain_bias"]
    missing_gain = [bid for bid in BAND_IDS if bid not in gain_offset]
    if missing_gain:
        gs.fatal(
            f"Gain/bias missing for band(s) {','.join(missing_gain)}. "
            f"Provide a metadata XML that contains the per-band Gain-band-* "
            f"values (NSO XML supplementalInformation block) or the "
            f"<AbsCalibrationGain> field (raw L1B MUX XML)."
        )

    # Build ESUN and FWHM maps (use hardcoded fallbacks)
    esun_map = dict(HARDCODED_ESUN)
    esun_from_xml = set()
    if meta["esun"]:
        esun_map.update(meta["esun"])
        esun_from_xml = set(meta["esun"].keys())

    fwhm_map = dict(HARDCODED_FWHM)
    fwhm_from_xml = set()
    if meta["fwhm"]:
        fwhm_map.update(meta["fwhm"])
        fwhm_from_xml = set(meta["fwhm"].keys())

    # Atmospheric / aerosol resolution (atcorr only)
    atm_opt = options["atmospheric_model"].strip().lower()
    atmospheric_model = None  # resolved later, inside RegionManager
    aerosol_model = int(options["aerosol_model"])

    nodata_value = meta["nodata"]
    use_float = bool(flags["p"])
    nprocs = int(options["nprocs"])

    dos_method = "dos" if target == "dos" else None
    do_dos = dos_method is not None
    do_atcorr = (target == "atcorr") and not skip_atcorr
    do_icnd = (target == "atcorr") or skip_atcorr

    dark_parameter = int(options["dark_parameter"])
    dark_method = options["dark_method"].strip().lower()
    tile_size = int(options["tile_size"])
    dark_percentile = float(options["dark_percentile"])
    n_darkest = dark_parameter if dark_parameter > 0 else 1000
    cloud_mask = options["cloud_mask"].strip() if options["cloud_mask"] else ""

    keep_radiance = bool(flags["k"]) or target == "radiance"

    # Pre-register temporary radiance map names for cleanup-on-exit
    tmp_rad_maps = {bid: gs.append_node_pid(f"tmp_svneo_rad_{bid}") for bid in BAND_IDS}
    tmp_icnd_files = []

    icnd_basename = options["icnd_basename"]
    save_icnd = bool(icnd_basename)
    if (do_icnd or do_atcorr) and not save_icnd:
        icnd_basename = gs.tempfile()
        gs.try_remove(icnd_basename)

    def cleanup():
        to_remove = [
            m for m in tmp_rad_maps.values()
            if gs.find_file(m, element="cell")["name"]
        ]
        if to_remove:
            gs.run_command(
                "g.remove", type="raster",
                name=",".join(to_remove), flags="f", quiet=True,
            )
        for f in tmp_icnd_files:
            gs.try_remove(f)

    atexit.register(cleanup)

    # Summary collectors
    summary_output_maps = []
    summary_warnings = []
    summary_icnd_files = []
    summary_atcorr_ranges = []
    summary_dos_params = []
    # Per-band dark-object records for the post-loop diagnostic. Keyed by
    # band id, each entry is {"dnmin": <scene-representative DN>, "gain":
    # <gain>, "bias": <bias>}. Only populated for DOS targets.
    dark_object_records = {}

    ref_band = input_maps[0]
    restrict = bool(flags["r"]) and not use_preimported
    region_kwargs = {"zoom": ref_band, "align": ref_band} if restrict \
        else {"raster": ref_band}

    aerosol = {"mode": "none"}
    geometry = None

    with gs.RegionManager(**region_kwargs):

        # Resolve atmospheric/aerosol settings inside RegionManager so that
        # CAMS spatial averaging uses the actual scene footprint.
        if do_atcorr or do_icnd:
            gs.message("Resolving aerosol optical depth / visibility ...")
            aerosol = resolve_aod550(
                options, scene_dt, meta["center_lon"], meta["center_lat"]
            )
            geometry = choose_geometry(meta)
            if atm_opt == "auto":
                if meta["center_lat"] is None or scene_dt is None:
                    gs.fatal(
                        "Cannot auto-detect atmospheric model: missing "
                        "center latitude or acquisition time. Provide "
                        "atmospheric_model= explicitly."
                    )
                atmospheric_model = auto_atmospheric_model(
                    meta["center_lat"], scene_dt
                )
            else:
                atmospheric_model = int(atm_opt)

        # ---- Per-band processing loop ----
        for idx, bid in enumerate(BAND_IDS):
            inmap = input_maps[idx]
            bname = BAND_NAMES[bid]
            gs.message(f"Processing band: {bname} ...")

            tmp_radmap = tmp_rad_maps[bid]
            final_radmap = f"{output_prefix}_{bname}_rad"
            gain = gain_offset[bid]["gain"]
            bias = gain_offset[bid]["bias"]

            # Always compute radiance first
            gs.mapcalc(
                build_radiance_expression(
                    inmap, tmp_radmap, gain, bias, nodata_value,
                    use_float=use_float,
                ),
                overwrite=gs.overwrite(), nprocs=nprocs,
            )
            gs.raster_history(tmp_radmap)

            # DOS approximate surface reflectance
            if do_dos:
                sun_elev = meta["geometry"].get("sun_elevation")
                esun = esun_map.get(bid)
                if sun_elev is None or esun is None or scene_dt is None:
                    summary_warnings.append(
                        f"Skipping {dos_method.upper()} for {bname}: "
                        f"missing sun elevation, ESUN, or scene datetime"
                    )
                else:
                    if bid not in esun_from_xml:
                        summary_warnings.append(
                            f"Using hardcoded ESUN ({esun}) for {bname} "
                            f"(no L1B XML provided)"
                        )
                    doy = day_of_year(scene_dt)
                    tmp_dnmin_raster = None

                    def _run_estimation():
                        if tile_size > 0:
                            return estimate_tiled_dnmin_points(
                                inmap, nodata_value, dark_method,
                                dark_parameter, n_darkest, tile_size,
                                dark_percentile=dark_percentile,
                            )
                        return estimate_dark_object(
                            inmap, nodata_value, dark_method,
                            dark_parameter, n_darkest,
                            dark_percentile=dark_percentile,
                        )

                    # When a cloud/shadow/water mask is supplied, exclude
                    # those pixels from dark-object estimation by setting an
                    # inverse MASK (non-null mask cells are removed). This is
                    # the sole masking mechanism: the previous built-in
                    # multi-band NIR dark mask was removed because it selected
                    # exactly the shadow/water pixels it should have excluded,
                    # dragging the NIR dark object to the sensor floor.
                    if tile_size > 0:
                        if cloud_mask:
                            with gs.MaskManager():
                                gs.run_command(
                                    "r.mask", raster=cloud_mask, flags="i",
                                    overwrite=True, quiet=True,
                                )
                                tile_points = _run_estimation()
                        else:
                            tile_points = _run_estimation()
                        tmp_dnmin_raster = interpolate_tiled_dnmin_points(
                            tile_points, tile_size, nprocs=nprocs,
                            memory=memory,
                            tmp_prefix="tmp_svneo_dnmin",
                        )
                        dnmin = tmp_dnmin_raster
                        univar = gs.parse_command(
                            "r.univar", map=tmp_dnmin_raster, flags="g",
                            quiet=True,
                        )
                        dnmin_summary = safe_float(
                            univar.get("median", univar.get("mean", "0"))
                        )
                    else:
                        if cloud_mask:
                            with gs.MaskManager():
                                gs.run_command(
                                    "r.mask", raster=cloud_mask, flags="i",
                                    overwrite=True, quiet=True,
                                )
                                dnmin = _run_estimation()
                        else:
                            dnmin = _run_estimation()
                        dnmin_summary = dnmin

                    dos_map = f"{output_prefix}_{bname}_{dos_method}"
                    fwhm = fwhm_map.get(bid)
                    fwhm_max_nm = fwhm[1] if fwhm else None
                    expr = build_dos_expression(
                        tmp_radmap, inmap, dos_map, gain, bias, esun,
                        sun_elev, doy, nodata_value, dnmin,
                        use_float=use_float,
                    )
                    gs.mapcalc(expr, overwrite=gs.overwrite(), nprocs=nprocs)

                    if tmp_dnmin_raster:
                        if keep_radiance:
                            dnmin_final = f"{output_prefix}_{bname}_dnmin"
                            gs.run_command(
                                "g.rename",
                                raster=f"{tmp_dnmin_raster},{dnmin_final}",
                                overwrite=gs.overwrite(),
                            )
                            summary_output_maps.append(dnmin_final)
                        else:
                            gs.run_command(
                                "g.remove", type="raster",
                                name=tmp_dnmin_raster, flags="f",
                                quiet=True,
                            )

                    _set_map_metadata(
                        dos_map, bid, "DOS reflectance",
                        source_file_label, scene_dt, "unitless",
                    )
                    summary_output_maps.append(dos_map)
                    tiled_tag = " (tiled median)" if tile_size > 0 else ""
                    summary_dos_params.append(
                        f"    {bname:10s} DNmin={dnmin_summary:<10g}{tiled_tag}"
                        f" ESUN={esun:<10g} gain={gain:<12g} bias={bias}"
                    )
                    # Record the scene-representative dark object (the tiled
                    # median, or the single-scene estimate) for the post-loop
                    # cross-band diagnostic. SuperView-NEO uses a
                    # multiplicative gain, so L_dark = DNmin*gain + bias.
                    dark_object_records[bid] = {
                        "dnmin": dnmin_summary,
                        "L_dark": float(dnmin_summary) * float(gain)
                        + float(bias or 0.0),
                    }

            # i.atcorr parameter file + optional execution
            if do_icnd:
                fwhm = fwhm_map.get(bid)
                if not fwhm:
                    gs.fatal(f"No spectral range available for band {bid}")
                if bid not in fwhm_from_xml:
                    summary_warnings.append(
                        f"Band {bname}: using hardcoded spectral range "
                        f"{fwhm} (no L1B XML provided)"
                    )
                if bid not in esun_from_xml:
                    summary_warnings.append(
                        f"Band {bname}: using hardcoded ESUN ({esun_map[bid]})"
                    )
                icnd_path = f"{icnd_basename}_{BAND_LABELS[bid]}.txt"
                write_icnd_file(
                    icnd_path, bid, geometry, atmospheric_model,
                    aerosol_model, aerosol,
                    float(options["elevation"]), fwhm,
                )
                if save_icnd:
                    summary_icnd_files.append(icnd_path)
                else:
                    tmp_icnd_files.append(icnd_path)

                if do_atcorr:
                    atcorr_map = f"{output_prefix}_{bname}_atcorr"
                    # SVN-NEO L1B is 12-bit, nodata=0, valid DN 1-4095.
                    # 11-bit upscaled products have a smaller range but the
                    # radiance bounds derived from gain/bias still bracket
                    # them, so 12-bit is the conservative choice.
                    valid_bits = meta.get("valid_data_bits") or 12
                    dn_min = nodata_value + 1 if nodata_value == 0 else 1
                    dn_max = (1 << valid_bits) - 1
                    rad_min = dn_min * gain + bias
                    rad_max = dn_max * gain + bias
                    if rad_min > rad_max:
                        rad_min, rad_max = rad_max, rad_min
                    rad_range = f"{rad_min},{rad_max}"
                    summary_atcorr_ranges.append(
                        f"    {bname:10s} range={rad_range}  "
                        f"rescale={options['rescale']}"
                    )
                    atcorr_kwargs = {
                        "input": tmp_radmap,
                        "parameters": icnd_path,
                        "output": atcorr_map,
                        "range": rad_range,
                        "rescale": options["rescale"],
                        "overwrite": gs.overwrite(),
                    }
                    if options["elevation_map"]:
                        atcorr_kwargs["elevation"] = options["elevation_map"]
                    gs.run_command("i.atcorr", **atcorr_kwargs)
                    rescale = options["rescale"]
                    if rescale in ("0,1", "0.0,1.0"):
                        atcorr_units = "unitless (reflectance 0-1)"
                    else:
                        atcorr_units = f"unitless (reflectance scaled to {rescale})"
                    _set_map_metadata(
                        atcorr_map, bid,
                        "surface reflectance (6S/i.atcorr)",
                        source_file_label, scene_dt, atcorr_units,
                    )
                    summary_output_maps.append(atcorr_map)

            # Keep or remove the temporary radiance map
            if keep_radiance:
                gs.run_command(
                    "g.rename", raster=f"{tmp_radmap},{final_radmap}",
                    overwrite=gs.overwrite(),
                )
                _set_map_metadata(
                    final_radmap, bid, "TOA radiance",
                    source_file_label, scene_dt, "W m-2 sr-1 um-1",
                )
                del tmp_rad_maps[bid]
                summary_output_maps.append(final_radmap)
            else:
                gs.run_command(
                    "g.remove", type="raster", name=tmp_radmap,
                    flags="f", quiet=True,
                )
                del tmp_rad_maps[bid]

        # Handle DN bands: rename or remove. When the user provided
        # pre-imported bands, never touch the originals.
        if use_preimported:
            gs.verbose("Pre-imported DN bands left unchanged")
        elif bool(flags["k"]):
            for idx, bid in enumerate(BAND_IDS):
                bname = BAND_NAMES[bid]
                dn_final = f"{output_prefix}_{bname}_dn"
                gs.run_command(
                    "g.rename", raster=f"{input_maps[idx]},{dn_final}",
                    overwrite=gs.overwrite(),
                )
                _set_map_metadata(
                    dn_final, bid, "DN", source_file_label, scene_dt,
                    "digital number",
                )
                summary_output_maps.append(dn_final)
        else:
            dn_names = ",".join(input_maps)
            gs.run_command(
                "g.remove", type="raster", name=dn_names,
                flags="f", quiet=True,
            )

    # ---- Dark-object diagnostic (DOS targets only) ----
    dark_diag_lines = None
    if do_dos and dark_object_records:
        diagnosis = diagnose_dark_objects(
            dark_object_records,
            band_order=BAND_IDS,
            floor_dn=10.0,
            floor_radiance_frac=0.25,
            sensor_name="SuperView-NEO",
        )
        dark_diag_lines = format_dark_object_table(
            diagnosis,
            dark_object_records,
            band_order=BAND_IDS,
            band_names=BAND_NAMES,
        )
        # Surface warnings live as well as in the summary, so users see them
        # during the run.
        for w in diagnosis["warnings"]:
            gs.warning(w)
        # Also fold them into the summary's warning section.
        summary_warnings.extend(diagnosis["warnings"])

    # ---- Final summary ----
    target_label = target
    if target == "atcorr" and skip_atcorr:
        target_label = "atcorr_params"
    _print_summary(
        meta=meta,
        source_file=source_file_label,
        output_prefix=output_prefix,
        input_level=input_level,
        target_label=target_label,
        output_maps=summary_output_maps,
        summary_file=options["summary_file"],
        atmospheric_model=atmospheric_model,
        aerosol_model=aerosol_model,
        aerosol=aerosol,
        atm_opt=atm_opt,
        icnd_files=summary_icnd_files,
        atcorr_ranges=summary_atcorr_ranges,
        dos_params=summary_dos_params,
        dark_diag_lines=dark_diag_lines,
        dos_method=dos_method,
        dark_method=dark_method,
        dark_parameter=dark_parameter,
        dark_percentile=dark_percentile,
        n_darkest=n_darkest,
        tile_size=tile_size,
        cloud_mask=cloud_mask,
        warnings=summary_warnings,
    )
    return 0


AEROSOL_MODEL_NAMES = {
    0: "no aerosols", 1: "continental", 2: "maritime", 3: "urban",
    5: "desert", 6: "biomass burning", 7: "stratospheric",
}


def _print_summary(
    *,
    meta,
    source_file,
    output_prefix,
    input_level,
    target_label,
    output_maps,
    summary_file,
    atmospheric_model=None,
    aerosol_model=None,
    aerosol=None,
    atm_opt=None,
    icnd_files=None,
    atcorr_ranges=None,
    dos_params=None,
    dark_diag_lines=None,
    dos_method=None,
    dark_method=None,
    dark_parameter=None,
    dark_percentile=None,
    n_darkest=None,
    tile_size=0,
    cloud_mask="",
    warnings=None,
):
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  i.in.svneo Processing Summary")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Input:             {os.path.basename(source_file)}")
    lines.append(f"  Output prefix:     {output_prefix}")
    lines.append(f"  Input level:       {input_level.upper()}")
    lines.append(
        f"  Processing level:  {PROC_LEVEL_DESC.get(target_label, target_label)}"
    )
    if meta.get("satellite_name"):
        lines.append(f"  Satellite:         {meta['satellite_name']}")
    if meta.get("product_name"):
        lines.append(f"  Product:           {meta['product_name']}")
    if meta.get("scene_datetime"):
        lines.append(
            f"  Acquired:          "
            f"{meta['scene_datetime'].strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        lines.append(f"  Day of year:       {day_of_year(meta['scene_datetime'])}")
    if meta.get("cloud_cover") is not None:
        lines.append(f"  Cloud cover:       {meta['cloud_cover']}%")
    if meta.get("incidence_angle") is not None:
        lines.append(f"  Incidence angle:   {meta['incidence_angle']}°")
    geom = meta.get("geometry", {})
    if geom.get("sun_elevation") is not None:
        lines.append("")
        lines.append("  Scene geometry:")
        lines.append(f"    Sun elevation:   {geom['sun_elevation']:.2f}°")
        if geom.get("sun_azimuth") is not None:
            lines.append(f"    Sun azimuth:     {geom['sun_azimuth']:.2f}°")
        if geom.get("view_zenith") is not None:
            lines.append(f"    View zenith:     {geom['view_zenith']:.2f}°")
    lines.append("")

    # DOS-specific summary
    if dos_method:
        lines.append(f"  {dos_method.upper()} atmospheric correction:")
        lines.append(
            "    Method: Dark Object Subtraction "
            "(Chavez, 1988; Moran et al., 1992)"
        )
        if dark_method == "ols_intercept":
            lines.append(
                f"    Dark object: OLS intercept through darkest "
                f"{n_darkest} pixels per band"
            )
        elif dark_method == "quantile":
            lines.append(
                f"    Dark object: {dark_percentile:.1f}th percentile of DN"
            )
        else:
            lines.append(
                f"    Dark object: lowest DN with >= {dark_parameter} pixels"
            )
        if tile_size > 0:
            lines.append(
                f"    Tiled processing: {tile_size} x {tile_size} pixel tiles"
            )
        if cloud_mask:
            lines.append(
                f"    Excluded from dark-object estimation (cloud/shadow/"
                f"water mask): {cloud_mask}"
            )
        else:
            lines.append(
                "    No cloud/shadow/water mask supplied. If the scene "
                "contains deep shadow or water, the dark object may be "
                "contaminated (see diagnostics below)."
            )
        lines.append(
            "    Assumes 1% surface reflectance for the dark object."
        )
        lines.append("    TAUv=1, TAUz=1, Esky=0 (DOS1 form)")
        lines.append(
            "    Note: DOS is a coarse Landsat-era heuristic, not validated "
            "for SuperView-NEO; it distorts ratio indices (e.g. NDVI) in "
            "shadow/water. Prefer atcorr or a BOA product where accuracy "
            "matters."
        )
        if meta.get("scene_datetime"):
            d = earth_sun_distance_au(day_of_year(meta["scene_datetime"]))
            lines.append(f"    Earth-Sun distance: {d:.6f} AU")
        if dos_params:
            lines.append("")
            lines.append("  DOS parameters per band:")
            for p in dos_params:
                lines.append(p)
        if dark_diag_lines:
            lines.append("")
            for dl in dark_diag_lines:
                lines.append(dl)
        lines.append("")

    # atcorr summary
    if atmospheric_model is not None:
        lines.append("  Atmospheric correction parameters (6S/i.atcorr):")
        atm_desc = ATM_MODEL_NAMES.get(atmospheric_model, str(atmospheric_model))
        if atm_opt == "auto":
            lines.append(
                f"    Atmospheric model: {atmospheric_model} ({atm_desc}) "
                f"[auto-detected]"
            )
        else:
            lines.append(
                f"    Atmospheric model: {atmospheric_model} ({atm_desc})"
            )
        aer_desc = AEROSOL_MODEL_NAMES.get(aerosol_model, str(aerosol_model))
        lines.append(f"    Aerosol model:     {aerosol_model} ({aer_desc})")
        if aerosol and aerosol.get("mode") == "aod":
            lines.append(f"    AOD550:            {aerosol['aod550']:.4f}")
            lines.append(f"    AOD source:        {aerosol['description']}")
        elif aerosol and aerosol.get("mode") == "visibility":
            lines.append(
                f"    Visibility:        {aerosol['visibility_km']} km"
            )
            lines.append(f"    Source:            {aerosol['description']}")
        lines.append("")

    if icnd_files:
        lines.append("  i.atcorr parameter files:")
        for p in icnd_files:
            lines.append(f"    {p}")
        lines.append("")
    if atcorr_ranges:
        lines.append("  i.atcorr radiance ranges:")
        for r in atcorr_ranges:
            lines.append(r)
        lines.append("")
    if output_maps:
        lines.append("  Output maps:")
        for m in output_maps:
            lines.append(f"    {m}")
        lines.append("")
    if warnings:
        lines.append("  Warnings:")
        for w in warnings:
            lines.append(f"    {w}")
        lines.append("")
    lines.append("=" * 60)
    text = "\n".join(lines)
    gs.message(text)
    if summary_file:
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        gs.message(f"Summary saved to: {summary_file}")


if __name__ == "__main__":
    sys.exit(main())
