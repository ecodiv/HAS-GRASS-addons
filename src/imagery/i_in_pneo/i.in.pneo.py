#!/usr/bin/env python

############################################################################
#
# MODULE:    i.in.pneo
# AUTHOR(S): Paulo van Breugel
# PURPOSE:   Import and (optionally) preprocess Pléiades-NEO imagery from the
#            satellietdataportaal. The input is always a DN product (12-bit
#            raw Full Bundle, or 11-bit RD ortho/pansharpened). Supports DN
#            passthrough (import and metadata enrichment only), DN to TOA
#            radiance conversion, DOS approximate surface reflectance, and
#            i.atcorr/6S atmospheric correction with optional AERONET/CAMS
#            -based AOD550. Metadata are read from the Airbus DIMAP V2 XML.
# COPYRIGHT: (C) 2026 by Paulo van Breugel and the GRASS Development Team
#
# This program is free software under the GNU General Public
# License (>=v2). Read the file COPYING that comes with GRASS
# for details.
#
############################################################################

# %module
# % description: Import Pléiades-NEO imagery (DN) and enrich raster metadata. Optional DN->TOA radiance conversion, DOS surface reflectance, or i.atcorr/6S atmospheric correction with optional AERONET/CAMS-based AOD550.
# % keyword: imagery
# % keyword: import
# % keyword: radiometric conversion
# % keyword: radiance
# % keyword: reflectance
# % keyword: atmospheric correction
# % keyword: aerosol
# % keyword: satellite
# % keyword: Pléiades-NEO
# %end

# %option G_OPT_F_BIN_INPUT
# % key: input
# % label: Input GeoTIFF file
# % description: Pléiades-NEO GeoTIFF file with 6 bands (red, green, blue, NIR, red-edge, deep-blue). Not required when the six band options (red, green, blue, nir, rededge, deepblue) are provided.
# % required: no
# % guisection: input
# %end

# %option G_OPT_R_INPUT
# % key: red
# % label: Pre-imported red band
# % description: Name of an already-imported raster holding the red band. Provide all six band options (red, green, blue, nir, rededge, deepblue) to skip the GeoTIFF import step. Mutually exclusive with input=.
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
# % key: blue
# % label: Pre-imported blue band
# % description: Name of an already-imported raster holding the blue band.
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

# %option G_OPT_R_INPUT
# % key: rededge
# % label: Pre-imported red-edge band
# % description: Name of an already-imported raster holding the red-edge band.
# % required: no
# % guisection: input
# %end

# %option G_OPT_R_INPUT
# % key: deepblue
# % label: Pre-imported deep-blue band
# % description: Name of an already-imported raster holding the deep-blue band.
# % required: no
# % guisection: input
# %end

# %rules
# % exclusive: input,red
# % exclusive: input,green
# % exclusive: input,blue
# % exclusive: input,nir
# % exclusive: input,rededge
# % exclusive: input,deepblue
# % collective: red,green,blue,nir,rededge,deepblue
# %end

# %option G_OPT_F_BIN_INPUT
# % key: dimap
# % label: DIMAP metadata file
# % description: Airbus DIMAP V2 metadata XML file (DIM_PNEO*.XML). Provides scene geometry, per-band gain/bias, ESUN, and spectral ranges.
# % required: yes
# % guisection: input
# %end

# %option
# % key: output
# % type: string
# % label: Output prefix
# % description: Prefix for output raster maps. Band names and product type suffixes are appended automatically (e.g., output=AA produces AA_red, AA_nir_rad, AA_blue_dos).
# % required: yes
# % guisection: output
# %end

# %option
# % key: processing_level
# % type: string
# % label: Input product processing level
# % description: Processing level of the input GeoTIFF. auto: detect from DIMAP metadata (default). dn: digital numbers (12-bit raw or 11-bit ortho/pansharpened). Pléiades-NEO products from the satellietdataportaal are always DN; there is no BOA surface-reflectance product, so auto always resolves to dn.
# % options: auto,dn
# % answer: auto
# % required: no
# % guisection: input
# %end

# %option
# % key: target_level
# % type: string
# % label: Desired output processing level
# % description: as_is: keep input DN values (default; just import and tag metadata). dn: same as as_is. radiance: convert DN to TOA radiance only. dos: TOA radiance plus Dark Object Subtraction surface reflectance (a coarse approximation; see manual). atcorr: TOA radiance plus i.atcorr/6S surface reflectance (requires aerosol input).
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
# % description: Do not run i.atcorr; only create i.atcorr parameter files. Requires icnd_basename to be set. Output is TOA radiance plus parameter files.
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
# it lands flat in $GISBASE/etc/i.in.pneo/ (or the $GRASS_ADDON_BASE
# equivalent). That directory is not on sys.path by default. set_path() is
# the GRASS-native helper that resolves etc/<modulename>/ and prepends it,
# and also handles the from-source and g.extension-compilation cases. We
# pass only the module name: the library file is flat in that directory,
# not inside a further sub-folder, so dirname/path are intentionally
# omitted.
# ---------------------------------------------------------------------------
from grass.script.utils import set_path

set_path(modulename="i.in.pneo")

# Sensor-agnostic helpers (AERONET / CAMS, 6S geometry, dark-object
# estimation, raster metadata tagging) shared with other optical-import
# addons. See grass_optical_lib.py.
from grass_optical_lib import (
    ATM_MODEL_NAMES,
    auto_atmospheric_model,
    choose_geometry,
    day_of_year,
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
# Pléiades-NEO band conventions
# ---------------------------------------------------------------------------
# Band order in 6-band GeoTIFFs (as delivered by the satellietdataportaal and
# imported by r.in.gdal): Red, Green, Blue, NIR, Red-Edge, Deep-Blue.
BAND_IDS = ["R", "G", "B", "NIR", "RE", "DB"]
BAND_NAMES = {
    "R": "red",
    "G": "green",
    "B": "blue",
    "NIR": "nir",
    "RE": "rededge",
    "DB": "deepblue",
}
BAND_LABELS = {
    "R": "gen_r",
    "G": "gen_g",
    "B": "gen_b",
    "NIR": "gen_nir",
    "RE": "gen_re",
    "DB": "gen_db",
}

# Mapping from band id to the parser option key that names the pre-imported
# raster for that band. Pre-imported bands are given explicitly (one raster
# name per band) rather than guessed from a basename + index, so there is no
# naming convention to detect and no ambiguity to resolve.
BAND_OPTION_KEY = {
    "R": "red",
    "G": "green",
    "B": "blue",
    "NIR": "nir",
    "RE": "rededge",
    "DB": "deepblue",
}

# Band ids in increasing-wavelength order, used only for the cross-band
# dark-object diagnostic. The processing order (BAND_IDS, the GeoTIFF band
# order) is red-first, but atmospheric path radiance declines with
# wavelength, so the monotonicity check must walk the bands shortest- to
# longest-wavelength: Deep-Blue (400-450) -> Blue (450-520) -> Green
# (530-590) -> Red (620-690) -> Red-Edge (700-750) -> NIR (770-880).
# (Wavelengths per the satellietdataportaal Pléiades-NEO band table.)
BAND_WAVELENGTH_ORDER = ["DB", "B", "G", "R", "RE", "NIR"]

# Fallback ESUN (solar irradiance, W m-2 um-1) values for Pléiades-NEO bands.
# These are provisional defaults derived from an early PNEO-4 DIMAP delivery
# (Airbus DS, 2023). Scene-specific values from DIMAP metadata override these
# when available and are preferred. Slight per-scene variation is expected
# (e.g., DIMAP for PNEO-3 2025-04-25 reports R=1553.6 vs 1551.7 here).
# See: Airbus Defence & Space, "Pléiades Neo Imagery User Guide", v2.0, 2022.
# https://www.intelligence-airbusds.com/imagery/constellation/pleiades-neo/
HARDCODED_ESUN = {
    "R": 1551.7,
    "G": 1815.4,
    "B": 1972.0,
    "NIR": 1060.1,
    "RE": 1349.0,
    "DB": 1797.1,
}

# Fallback FWHM (full width at half maximum, nm) for Pléiades-NEO bands.
# Same provenance as HARDCODED_ESUN above. Scene-specific DIMAP values
# override these when available (differences are typically <= 1 nm).
HARDCODED_FWHM = {
    "R": (619, 690),
    "G": (533, 591),
    "B": (446, 520),
    "NIR": (768, 888),
    "RE": (697, 750),
    "DB": (416, 457),
}


# ---------------------------------------------------------------------------
# PNEO-specific metadata parsing (Airbus DIMAP V2)
# ---------------------------------------------------------------------------
# Generic numeric and datetime helpers (safe_float, decimal_hour_utc,
# day_of_year, earth_sun_distance_au) are imported from grass_optical_lib.
# The DIMAP parser is the one piece of metadata handling that is
# sensor-format-dependent and stays here.


def resolve_scene_metadata(dimap_meta):
    """Extract scene datetime and center coordinates from DIMAP metadata.

    Returns (scene_dt, center_lon, center_lat).
    """
    scene_dt = dimap_meta.get("scene_datetime")
    center_lon = dimap_meta.get("center_lon")
    center_lat = dimap_meta.get("center_lat")
    return scene_dt, center_lon, center_lat


def parse_dimap_xml(xml_path):
    """Parse Airbus DIMAP V2 metadata for a Pléiades-NEO scene.

    Returns a dict with keys: gain_bias, esun, fwhm, geometry,
    scene_datetime, center_lon, center_lat, nodata. Any value may be
    absent if the corresponding element is missing from the XML.
    """
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as err:
        gs.fatal(f"Failed to parse DIMAP XML {xml_path}: {err}")
    root = tree.getroot()

    gain_bias = {}
    for node in root.findall(".//Band_Radiance"):
        bid = (node.findtext("BAND_ID") or "").strip()
        if not bid:
            continue
        gain = safe_float(node.findtext("GAIN"))
        bias = safe_float(node.findtext("BIAS"))
        if gain is not None:
            gain_bias[bid] = {"gain": gain, "bias": 0.0 if bias is None else bias}

    esun = {}
    for node in root.findall(".//Band_Solar_Irradiance"):
        bid = (node.findtext("BAND_ID") or "").strip()
        value = safe_float(node.findtext("VALUE"))
        if bid and value is not None:
            esun[bid] = value

    fwhm = {}
    for node in root.findall(".//Band_Spectral_Range"):
        bid = (node.findtext("BAND_ID") or "").strip()
        fwhm_node = node.find("FWHM")
        if not bid or fwhm_node is None:
            continue
        wmin = safe_float(fwhm_node.findtext("MIN"))
        wmax = safe_float(fwhm_node.findtext("MAX"))
        if wmin is not None and wmax is not None:
            fwhm[bid] = (int(round(wmin)), int(round(wmax)))

    geometry = {
        "sun_elevation": None,
        "sun_azimuth": None,
        "view_zenith": None,
        "view_azimuth": None,
        "incidence_angle": None,
        "image_orientation": None,
        "satellite_altitude_km": None,
    }
    for node in root.findall(".//Located_Geometric_Values"):
        if (node.findtext("LOCATION_TYPE") or "").strip().lower() != "center":
            continue
        geometry["satellite_altitude_km"] = safe_float(
            node.findtext("SATELLITE_ALTITUDE")
        )
        acq = node.find("Acquisition_Angles")
        if acq is not None:
            geometry["view_azimuth"] = safe_float(acq.findtext("AZIMUTH_ANGLE"))
            geometry["view_zenith"] = safe_float(acq.findtext("VIEWING_ANGLE"))
            geometry["incidence_angle"] = safe_float(acq.findtext("INCIDENCE_ANGLE"))
            geometry["image_orientation"] = safe_float(
                acq.findtext("IMAGE_ORIENTATION")
            )
        sol = node.find("Solar_Incidences")
        if sol is not None:
            geometry["sun_azimuth"] = safe_float(sol.findtext("SUN_AZIMUTH"))
            geometry["sun_elevation"] = safe_float(sol.findtext("SUN_ELEVATION"))
        break

    scene_datetime = None
    start_val = root.findtext(".//Time_Range/START")
    if start_val:
        txt = start_val.strip().rstrip("Z")
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                scene_datetime = datetime.strptime(txt, fmt).replace(
                    tzinfo=timezone.utc
                )
                break
            except ValueError:
                continue
    if scene_datetime is None:
        img_date = root.findtext(".//IMAGING_DATE")
        img_time = root.findtext(".//IMAGING_TIME")
        if img_date and img_time:
            txt = f"{img_date} {img_time.rstrip('Z')}"
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    scene_datetime = datetime.strptime(txt, fmt).replace(
                        tzinfo=timezone.utc
                    )
                    break
                except ValueError:
                    continue

    center_lon = None
    center_lat = None
    center = root.find(".//Dataset_Extent/Center")
    if center is not None:
        center_lon = safe_float(center.findtext("LON"))
        center_lat = safe_float(center.findtext("LAT"))

    nodata = 0
    for node in root.findall(".//Special_Value"):
        label = (node.findtext("SPECIAL_VALUE_TEXT") or "").strip().upper()
        value = safe_float(node.findtext("SPECIAL_VALUE_COUNT"))
        if value is None:
            continue
        if label == "NODATA":
            nodata = int(value)

    return {
        "gain_bias": gain_bias,
        "esun": esun,
        "fwhm": fwhm,
        "geometry": geometry,
        "scene_datetime": scene_datetime,
        "center_lon": center_lon,
        "center_lat": center_lat,
        "nodata": nodata,
    }


# ---------------------------------------------------------------------------
# AERONET / CAMS aerosol retrieval and AOD-550 resolution, 6S geometry and
# atmospheric-model selection, dark-object estimation, and raster metadata
# tagging are all provided by grass_optical_lib. The library's choose_geometry
# reads scene_datetime / center_lon / center_lat / geometry straight from the
# DIMAP metadata dict, and resolve_aod550 dispatches between manual /
# visibility / aeronet_file / cams — DOS is no longer an aerosol source here
# (it is a target_level), so no wrapper is needed.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Radiance and DOS expressions for Pléiades-NEO
# ---------------------------------------------------------------------------


def build_radiance_expression(inmap, outmap, gain, bias, nodata_value, use_float=False):
    """Build the r.mapcalc expression for DN -> TOA radiance.

    Pléiades-NEO / Airbus convention (DIMAP Band_Radiance):

        L = DN / GAIN + BIAS              (divisive gain)

    This is the OPPOSITE convention from SuperView-NEO, where the gain
    enters as a multiplier (L = DN * GAIN + BIAS). Make sure you do not
    feed a SuperView-style gain into this expression: the resulting
    radiance values would differ by 4-5 orders of magnitude.

    Nodata DN values are mapped to NULL in the output.
    """
    cast = "float" if use_float else "double"
    return (
        f"{outmap} = if({inmap} == {nodata_value}, null(), "
        f"{cast}({inmap}) / ({gain}) + ({bias}))"
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
    """Build a DOS surface reflectance expression for Pléiades-NEO.

    Dark Object Subtraction (Chavez, 1988; Moran et al., 1992) in the
    classic "DOS1" form: TAUv=1, TAUz=1, Esky=0. The dark object is
    assumed to have 1% surface reflectance, and its radiance is removed
    as a single scene-wide path-radiance constant.

    Pléiades-NEO uses a *divisive* gain, so the radiance of the dark
    object is:

        L_dark = DNmin / GAIN + BIAS
        Lp     = L_dark - 0.01 * ESUN * sin(e) / (pi * d^2)
        rho    = pi * (L - Lp) * d^2 / (ESUN * sin(e))

    A previous version also offered a "DOS2" variant that scaled the
    transmittance by TAUz = sin(e) for bands below 1000 nm. It was
    removed: for ratio indices such as NDVI the TAUz factor applies
    identically to both bands and very nearly cancels (verified to move
    NDVI by <= 0.006 on real surfaces for this sensor), so it added an
    unvalidated Landsat-era heuristic with no practical benefit here.

    The ``dnmin`` parameter can be either a float/int scalar (a single
    whole-scene dark-object DN, embedded as a numeric constant) or a
    string (a GRASS raster map name from tiled estimation, referenced as
    a raster variable).
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

    # L_dark = DNmin/GAIN + BIAS
    # Lp = L_dark - 0.01 * ESUN * sin(e) / (pi * d^2)
    lp = (
        f"(({dnmin_expr}) / ({gain}) + ({bias}) "
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

    Builds the title and semantic label from the Pléiades-NEO band tables
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
    "dn_passthrough": "DN passthrough (import + metadata only)",
    "radiance":       "TOA radiance (DN -> radiance conversion)",
    "dos":            "DOS approximate surface reflectance",
    "atcorr":         "Full atmospheric correction (i.atcorr / 6S)",
    "atcorr_params":  "i.atcorr parameter files only (-a flag)",
}


def main():
    options, flags = gs.parser()

    # ---- Check for existing MASK --------------------------------------
    if gs.find_file("MASK", element="cell")["name"]:
        gs.fatal(
            "An active MASK was found. Please remove it with 'r.mask -r' "
            "before running i.in.pneo. If you need to exclude clouds or "
            "shadows from dark-object estimation, use the cloud_mask= "
            "parameter instead."
        )

    # ---- Validate inputs ----------------------------------------------
    input_tif = options["input"]
    # Explicit per-band rasters. The parser %rules enforce all-six-or-none
    # (collective) and mutual exclusion with input=, so here we only need to
    # detect which mode we are in.
    band_opts = {bid: (options[BAND_OPTION_KEY[bid]] or "").strip()
                 for bid in BAND_IDS}
    use_preimported = any(band_opts.values())
    if not input_tif and not use_preimported:
        gs.fatal(
            "Provide either input= (a 6-band GeoTIFF) or the six band "
            "options (red=, green=, blue=, nir=, rededge=, deepblue=) "
            "naming pre-imported rasters."
        )

    file_keys = ["dimap", "aeronet_file", "cams_file"]
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
    dimap_meta = parse_dimap_xml(options["dimap"])
    scene_dt, center_lon, center_lat = resolve_scene_metadata(dimap_meta)
    if scene_dt is None:
        gs.warning("Could not determine acquisition datetime from metadata")

    # ---- Decide input processing level --------------------------------
    # Pléiades-NEO products from the satellietdataportaal are always DN
    # (12-bit raw or 11-bit ortho/pansharpened); there is no BOA product.
    # The processing_level axis mirrors i.in.svneo for design symmetry, but
    # auto always resolves to dn here.
    proc_opt = options["processing_level"].strip().lower()
    if proc_opt in ("auto", "dn"):
        input_level = "dn"
    else:
        input_level = "dn"

    # ---- Decide target processing level -------------------------------
    target = options["target_level"].strip().lower()
    skip_atcorr = bool(flags["a"])

    # Interpret "as_is"/"dn" as DN passthrough (DN is the only input level).
    if target in ("as_is", "dn"):
        target = "dn_pass"

    # DOS reflectance needs an explicit sun elevation value (it enters the
    # math directly as sin(e)). DIMAP normally supplies it; fail clearly if
    # it is missing rather than silently skipping.
    if target == "dos":
        if dimap_meta["geometry"].get("sun_elevation") is None:
            gs.fatal(
                "target_level=dos requires the sun elevation angle, which "
                "is normally present in the DIMAP metadata. The supplied "
                "DIMAP XML does not contain a Solar_Incidences/SUN_ELEVATION "
                "value."
            )

    # i.atcorr/6S can take either explicit angles (geometry code 0) or
    # acquisition time + center lat/lon (geometry code 6); it computes the
    # sun position internally in the latter case. So atcorr only needs
    # *some* form of geometry.
    if target == "atcorr":
        geom = dimap_meta["geometry"]
        has_angles = (
            geom.get("sun_elevation") is not None
            and geom.get("sun_azimuth") is not None
            and geom.get("view_zenith") is not None
            and geom.get("view_azimuth") is not None
        )
        has_latlon_time = (
            scene_dt is not None
            and center_lon is not None
            and center_lat is not None
        )
        if not has_angles and not has_latlon_time:
            gs.fatal(
                "target_level=atcorr requires either explicit sun and view "
                "angles or acquisition time + scene center coordinates from "
                "the DIMAP metadata; neither is complete."
            )
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
        # Label the scene by the common stem of the six band names if there
        # is one, else by the red band (an arbitrary but stable choice).
        common = os.path.commonprefix(
            [band_opts[bid] for bid in BAND_IDS]
        ).rstrip("._-")
        source_file_label = common if common else band_opts["R"]
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
                    f"(red, green, blue, NIR, red-edge, deep-blue)."
                )
            input_maps.append(name)
        source_file_label = input_tif

    # =================================================================
    # SHORT PATH — DN passthrough (no radiometric conversion)
    # =================================================================
    if target == "dn_pass":
        ref_band = input_maps[0]
        restrict = bool(flags["r"]) and not use_preimported
        region_kwargs = {"zoom": ref_band, "align": ref_band} if restrict \
            else {"raster": ref_band}

        output_maps = []
        with gs.RegionManager(**region_kwargs):
            for idx, bid in enumerate(BAND_IDS):
                gdal_name = input_maps[idx]
                bname = BAND_NAMES[bid]
                final_name = f"{output_prefix}_{bname}"

                if use_preimported and gdal_name == final_name:
                    pass
                else:
                    gs.run_command(
                        "g.rename", raster=f"{gdal_name},{final_name}",
                        overwrite=gs.overwrite(),
                    )
                _set_map_metadata(
                    final_name, bid, "DN",
                    source_file_label, scene_dt, "digital number",
                )
                output_maps.append(final_name)

        _print_summary(
            dimap_meta=dimap_meta,
            source_file=source_file_label,
            output_prefix=output_prefix,
            input_level=input_level,
            target_label="dn_passthrough",
            output_maps=output_maps,
            summary_file=options["summary_file"],
            scene_dt=scene_dt,
            center_lat=center_lat,
        )
        return 0

    # =================================================================
    # LONG PATH — radiance / DOS / atcorr (DN input only)
    # =================================================================

    # Validate gain/bias availability
    gain_offset = dimap_meta["gain_bias"]
    missing_gain = [bid for bid in BAND_IDS if bid not in gain_offset]
    if missing_gain:
        gs.fatal(
            f"Gain/bias missing for band(s) {','.join(missing_gain)}. "
            f"Provide a DIMAP metadata XML that contains the per-band "
            f"Band_Radiance GAIN/BIAS values."
        )

    # Build ESUN and FWHM maps (use hardcoded fallbacks)
    esun_map = dict(HARDCODED_ESUN)
    esun_from_xml = set()
    if dimap_meta["esun"]:
        esun_map.update(dimap_meta["esun"])
        esun_from_xml = set(dimap_meta["esun"].keys())

    fwhm_map = dict(HARDCODED_FWHM)
    fwhm_from_xml = set()
    if dimap_meta["fwhm"]:
        fwhm_map.update(dimap_meta["fwhm"])
        fwhm_from_xml = set(dimap_meta["fwhm"].keys())

    # Atmospheric / aerosol resolution (atcorr only)
    atm_opt = options["atmospheric_model"].strip().lower()
    atmospheric_model = None  # resolved later, inside RegionManager
    aerosol_model = int(options["aerosol_model"])

    nodata_value = dimap_meta["nodata"]
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
    tmp_rad_maps = {bid: gs.append_node_pid(f"tmp_pneo_rad_{bid}") for bid in BAND_IDS}
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
    # band id, each entry is {"dnmin": <scene-representative DN>, "L_dark":
    # <dark-object radiance>}. Only populated for DOS targets.
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
            aerosol = resolve_aod550(options, scene_dt, center_lon, center_lat)
            geometry = choose_geometry(dimap_meta)
            if atm_opt == "auto":
                if center_lat is None or scene_dt is None:
                    gs.fatal(
                        "Cannot auto-detect atmospheric model: missing "
                        "center latitude or acquisition time. Provide "
                        "atmospheric_model= explicitly."
                    )
                atmospheric_model = auto_atmospheric_model(center_lat, scene_dt)
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
                sun_elev = dimap_meta["geometry"].get("sun_elevation")
                esun = esun_map.get(bid)
                if sun_elev is None or esun is None or scene_dt is None:
                    summary_warnings.append(
                        f"Skipping DOS for {bname}: missing sun elevation, "
                        f"ESUN, or scene datetime"
                    )
                else:
                    if bid not in esun_from_xml:
                        summary_warnings.append(
                            f"Using hardcoded ESUN ({esun}) for {bname} "
                            f"(not present in DIMAP)"
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
                            tmp_prefix="tmp_pneo_dnmin",
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
                    # cross-band diagnostic. Pléiades-NEO uses a divisive
                    # gain, so L_dark = DNmin/gain + bias.
                    dark_object_records[bid] = {
                        "dnmin": dnmin_summary,
                        "L_dark": float(dnmin_summary) / float(gain)
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
                        f"{fwhm} (not present in DIMAP)"
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
                    # Pléiades-NEO is 12-bit, nodata=0, valid DN 1-4095.
                    dn_min = nodata_value + 1 if nodata_value == 0 else 1
                    dn_max = 4095
                    rad_min = dn_min / gain + bias
                    rad_max = dn_max / gain + bias
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
            band_order=BAND_WAVELENGTH_ORDER,
            floor_dn=10.0,
            floor_radiance_frac=0.25,
            sensor_name="Pléiades-NEO",
        )
        dark_diag_lines = format_dark_object_table(
            diagnosis,
            dark_object_records,
            band_order=BAND_WAVELENGTH_ORDER,
            band_names=BAND_NAMES,
        )
        # Surface warnings live as well as in the summary, so users see them
        # during the run.
        for w in diagnosis["warnings"]:
            gs.warning(w)
        summary_warnings.extend(diagnosis["warnings"])

    # ---- Final summary ----
    target_label = target
    if target == "atcorr" and skip_atcorr:
        target_label = "atcorr_params"
    _print_summary(
        dimap_meta=dimap_meta,
        source_file=source_file_label,
        output_prefix=output_prefix,
        input_level=input_level,
        target_label=target_label,
        output_maps=summary_output_maps,
        summary_file=options["summary_file"],
        scene_dt=scene_dt,
        center_lat=center_lat,
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
    dimap_meta,
    source_file,
    output_prefix,
    input_level,
    target_label,
    output_maps,
    summary_file,
    scene_dt=None,
    center_lat=None,
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
    lines.append("  i.in.pneo Processing Summary")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Input:             {os.path.basename(source_file)}")
    lines.append(f"  Output prefix:     {output_prefix}")
    lines.append(f"  Input level:       {input_level.upper()}")
    lines.append(
        f"  Processing level:  {PROC_LEVEL_DESC.get(target_label, target_label)}"
    )
    if scene_dt:
        lines.append(
            f"  Acquired:          "
            f"{scene_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        lines.append(f"  Day of year:       {day_of_year(scene_dt)}")
    geom = dimap_meta.get("geometry", {}) if dimap_meta else {}
    if geom.get("incidence_angle") is not None:
        lines.append(f"  Incidence angle:   {geom['incidence_angle']}°")
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
        lines.append("  DOS atmospheric correction:")
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
            "for Pléiades-NEO; it distorts ratio indices (e.g. NDVI) in "
            "shadow/water. Prefer atcorr where accuracy matters."
        )
        if scene_dt:
            d = earth_sun_distance_au(day_of_year(scene_dt))
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
