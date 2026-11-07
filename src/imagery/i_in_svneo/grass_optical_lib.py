"""grass_optical_lib — sensor-agnostic helpers for optical-imagery import addons.

This module collects the shared building blocks used by the
``i.in.svneo`` (SuperView-NEO) and ``i.in.pneo`` (Pleiades-NEO) GRASS GIS
addons. It contains nothing sensor-specific: no band lists, no XML
parsers, no radiance formulas. Each addon stays responsible for parsing
its own metadata and producing the per-band ``gain`` / ``bias`` values
used in the radiance expression of its own choice.

The library currently provides:

* generic numeric / datetime helpers (:func:`safe_float`,
  :func:`decimal_hour_utc`, :func:`day_of_year`,
  :func:`earth_sun_distance_au`);
* AERONET parsing and AOD-550 selection
  (:func:`parse_aeronet_rows`, :func:`extract_aeronet_aod550`,
  :func:`read_aeronet_file_aod`);
* CAMS NetCDF / GRIB AOD-550 retrieval (:func:`read_cams_aod`);
* a high-level AOD-550 / visibility resolver that dispatches between the
  ``manual``, ``visibility``, ``aeronet_file`` and ``cams`` sources
  (:func:`resolve_aod550`);
* 6S geometry and atmospheric-model helpers
  (:func:`auto_atmospheric_model`, :func:`choose_geometry`,
  :func:`write_icnd_file`);
* dark-object estimation (single-tile and tiled) for DOS-style
  corrections (:func:`get_dark_object_dn`,
  :func:`get_dark_ols_intercept`, :func:`get_dark_quantile`,
  :func:`estimate_dark_object`,
  :func:`estimate_tiled_dnmin_points`,
  :func:`interpolate_tiled_dnmin_points`);
* a generic raster-metadata tagger (:func:`set_map_metadata`).

Authorship and history
----------------------
The bulk of this code was originally written by Paulo van Breugel for
``i.in.pneo``. It was extracted verbatim (with light parameterisation,
e.g. configurable temp-raster prefixes) so that additional sensor
importers can share the same atmospheric-correction plumbing. The
original module-level docstrings on the source functions have been
preserved.

License
-------
Released under the GNU General Public License (>= v2), same as the
addons it serves. See the file ``COPYING`` that comes with GRASS for
details.
"""

import csv
import io
import math
import os
import re
import tempfile
from datetime import datetime, timezone

import grass.script as gs


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

#: 6S atmospheric model codes (used by both ``i.atcorr`` and
#: :func:`auto_atmospheric_model`).
ATM_MODEL_NAMES = {
    0: "no gaseous absorption",
    1: "tropical",
    2: "midlatitude summer",
    3: "midlatitude winter",
    4: "subarctic summer",
    5: "subarctic winter",
    6: "US Standard 1962",
}

#: CAMS NetCDF / GRIB variable names that have been seen to carry
#: AOD-550. Searched in order.
CAMS_AOD550_VARNAMES = [
    "aod550",
    "tcaod550",
    "total_aerosol_optical_depth_550nm",
]


# ---------------------------------------------------------------------------
# Generic numeric / datetime helpers
# ---------------------------------------------------------------------------


def safe_float(value):
    """Convert a text value to float, returning ``None`` on empty or invalid data.

    Recognises a small set of textual ``not-a-value`` markers (``N/A``,
    ``NA``, ``NAN``, ``#N/A``, ``-999``, ``-999.0``) and returns
    ``None`` for them too. Useful when scraping values out of XML or
    CSV cells that may be empty or stub-filled.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.upper() in {"N/A", "NA", "NAN", "#N/A", "-999", "-999.0"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def decimal_hour_utc(dt):
    """Return the decimal UTC hour-of-day for a :class:`datetime.datetime`.

    ``2023-01-01T12:30:00`` -> ``12.5``. Used to feed 6S geometry
    code 6 (``date + lat/lon`` form).
    """
    return dt.hour + dt.minute / 60.0 + dt.second / 3600.0 + dt.microsecond / 3600e6


def day_of_year(dt):
    """Day-of-year (1..366) for a :class:`datetime.datetime`."""
    return dt.timetuple().tm_yday


def earth_sun_distance_au(doy):
    """Approximate Earth-Sun distance in astronomical units.

    Uses the cosine approximation
    :math:`d = 1 - 0.01672 \\cos(0.9856 (\\text{doy} - 4))`,
    accurate to a few parts in 10\\ :sup:`4`. Sufficient for
    DOS-style reflectance conversions.
    """
    return 1.0 - 0.01672 * math.cos(math.radians(0.9856 * (doy - 4)))


# ---------------------------------------------------------------------------
# AERONET / CAMS aerosol retrieval
# ---------------------------------------------------------------------------


def parse_aeronet_datetime(row):
    """Extract a UTC :class:`datetime` from an AERONET CSV row.

    AERONET ALL_POINTS / DAILY files put the timestamp in two columns
    named ``Date(dd:mm:yyyy)`` and ``Time(hh:mm:ss)``. The exact
    parenthesised format string varies between product releases, so we
    only look for the prefix.

    Returns ``None`` if either column is missing or cannot be parsed.
    """
    date_key = next((k for k in row if k.lower().startswith("date(")), None)
    time_key = next((k for k in row if k.lower().startswith("time(")), None)
    if not date_key or not time_key:
        return None
    date_val = (row.get(date_key) or "").strip()
    time_val = (row.get(time_key) or "").strip()
    for fmt in ("%d:%m:%Y %H:%M:%S", "%d:%m:%Y %H:%M:%S.%f"):
        try:
            return datetime.strptime(f"{date_val} {time_val}", fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def parse_aeronet_rows(text):
    """Parse the body of an AERONET download into ``[{datetime, data}]``.

    The function tolerates the AERONET preamble (XML-ish ``<...>``
    metadata lines and blank lines), locates the CSV header row by
    looking for both ``date(`` and ``time(`` markers, and yields one
    dict per record. Records whose timestamp cannot be parsed are
    silently dropped.
    """
    lines = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("<"):
            continue
        lines.append(raw)
    header_idx = None
    for idx, line in enumerate(lines):
        low = line.lower()
        if "date(" in low and "time(" in low:
            header_idx = idx
            break
    if header_idx is None:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    rows = []
    for row in reader:
        dt = parse_aeronet_datetime(row)
        if dt is not None:
            rows.append({"datetime": dt, "data": row})
    return rows


def available_aod_wavelengths(row):
    """Return a ``{wavelength_nm: tau}`` map from a single AERONET row.

    Columns matched by the regex ``AOD[_-]?(\\d{3,4})nm`` (case
    insensitive) are picked up. Negative or zero AODs (commonly used
    as fill values for unavailable wavelengths in AERONET) are
    discarded.
    """
    out = {}
    for key, value in row.items():
        m = re.match(r"AOD[_-]?(\d{3,4})nm$", key.strip(), flags=re.IGNORECASE)
        if not m:
            continue
        tau = safe_float(value)
        if tau is not None and tau > 0:
            out[int(m.group(1))] = tau
    return out


def angstrom_aod(target_nm, wl1, tau1, wl2, tau2):
    """Angstrom interpolation of :math:`\\tau(\\lambda)` to ``target_nm``.

    Fits :math:`\\tau = \\tau_1 (\\lambda / \\lambda_1)^{-\\alpha}`
    with :math:`\\alpha` derived from the (``wl1``, ``wl2``) pair.
    Returns ``None`` if the inputs are invalid (non-positive AOD or
    equal wavelengths).
    """
    if tau1 <= 0 or tau2 <= 0 or wl1 == wl2:
        return None
    alpha = -math.log(tau1 / tau2) / math.log(float(wl1) / float(wl2))
    return tau1 * (float(target_nm) / float(wl1)) ** (-alpha)


def extract_aeronet_aod550(row):
    """Get AOD-550 (and the method used) from one AERONET row.

    Returns a ``(aod550, method)`` tuple. ``method`` is one of
    ``"direct"`` (a 550/551/555 nm column was present), or
    ``"angstrom_<wl1>_<wl2>"`` if interpolation was needed.
    Preference order: direct, then 500/675 (the AERONET-recommended
    Angstrom pair for visible bands), then the closest enclosing pair.
    """
    for key in ("AOD_550nm", "AOD_551nm", "AOD_555nm"):
        if key in row:
            val = safe_float(row[key])
            if val is not None and val >= 0:
                return val, "direct"
    wl_map = available_aod_wavelengths(row)
    if 500 in wl_map and 675 in wl_map:
        val = angstrom_aod(550, 500, wl_map[500], 675, wl_map[675])
        if val is not None:
            return val, "angstrom_500_675"
    lower = sorted((wl for wl in wl_map if wl < 550), key=lambda w: abs(w - 550))
    upper = sorted((wl for wl in wl_map if wl > 550), key=lambda w: abs(w - 550))
    if lower and upper:
        wl1 = lower[0]
        wl2 = upper[0]
        val = angstrom_aod(550, wl1, wl_map[wl1], wl2, wl_map[wl2])
        if val is not None:
            return val, f"angstrom_{wl1}_{wl2}"
    return None, None


def select_best_aeronet_observation(rows, scene_dt, time_window_minutes):
    """Pick the AERONET row closest in time to ``scene_dt``.

    Only rows within ``±time_window_minutes`` minutes of ``scene_dt``
    are considered, and only rows that yield a valid AOD-550 (direct
    or via :func:`angstrom_aod`) are eligible. Returns ``None`` if no
    row qualifies.
    """
    best = None
    best_delta = None
    for item in rows:
        delta_min = abs((item["datetime"] - scene_dt).total_seconds()) / 60.0
        if delta_min > time_window_minutes:
            continue
        aod550, method = extract_aeronet_aod550(item["data"])
        if aod550 is None:
            continue
        if best is None or delta_min < best_delta:
            best = {
                "datetime": item["datetime"],
                "aod550": aod550,
                "method": method,
                "minutes_delta": delta_min,
                "row": item["data"],
            }
            best_delta = delta_min
    return best


def read_aeronet_file_aod(aeronet_file, scene_dt, time_window_minutes):
    """Resolve AOD-550 from an AERONET file for a given scene.

    Raises :class:`RuntimeError` if no observation falls inside the
    ``±time_window_minutes`` window. The returned dict carries
    ``aod550``, ``datetime``, ``method``, ``minutes_delta``, ``row``,
    ``source="aeronet_file"`` and ``station=<basename>``.
    """
    with open(aeronet_file, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    rows = parse_aeronet_rows(text)
    best = select_best_aeronet_observation(rows, scene_dt, time_window_minutes)
    if best is None:
        raise RuntimeError(
            f"No suitable AERONET observation found in file within "
            f"±{time_window_minutes} minutes"
        )
    best["source"] = "aeronet_file"
    best["station"] = os.path.basename(aeronet_file)
    return best


def read_cams_aod(cams_file, scene_dt, region_bounds, time_window_minutes=180):
    """Extract AOD-550 from a CAMS NetCDF or GRIB file.

    The nearest valid time step within ``time_window_minutes`` of
    ``scene_dt`` is selected. Spatial value is the mean over all grid
    cells overlapping ``region_bounds`` (a ``{n, s, e, w}`` dict of
    WGS84 latitudes/longitudes); if none overlap, the nearest grid
    cell to the region centre is used as a fallback.

    Returns a dict with ``aod550``, ``datetime``, ``minutes_delta``,
    ``n_cells``, ``variable`` and ``source="cams"``. Requires
    ``xarray`` and ``numpy``; GRIB files additionally require
    ``cfgrib`` and ``eccodes``.
    """
    try:
        import xarray as xr
    except ImportError:
        raise RuntimeError(
            "Python package 'xarray' is required for CAMS support. "
            "Install with: pip install xarray"
        )
    try:
        import numpy as np
    except ImportError:
        raise RuntimeError(
            "Python package 'numpy' is required for CAMS support. "
            "Install with: pip install numpy"
        )

    file_lower = cams_file.lower()
    try:
        if file_lower.endswith((".grib", ".grib2", ".grb", ".grb2")):
            try:
                ds = xr.open_dataset(cams_file, engine="cfgrib")
            except Exception as grib_err:
                raise RuntimeError(
                    f"Failed to open GRIB file (install cfgrib + eccodes): "
                    f"{grib_err}"
                ) from grib_err
        else:
            ds = xr.open_dataset(cams_file)
    except RuntimeError:
        raise
    except Exception as err:
        raise RuntimeError(f"Failed to open CAMS file '{cams_file}': {err}") from err

    try:
        aod_varname = None
        for vname in CAMS_AOD550_VARNAMES:
            if vname in ds.data_vars:
                aod_varname = vname
                break
        if aod_varname is None:
            available = [
                v for v in ds.data_vars if "aod" in v.lower() or "aerosol" in v.lower()
            ]
            raise RuntimeError(
                f"No AOD550 variable found in CAMS file. Tried: "
                f"{', '.join(CAMS_AOD550_VARNAMES)}. "
                f"Available: {', '.join(available) if available else 'none'}"
            )

        aod_da = ds[aod_varname]
        scene_utc = scene_dt.replace(tzinfo=None) if scene_dt.tzinfo else scene_dt
        scene_np = np.datetime64(scene_utc)

        has_time = "time" in aod_da.dims
        has_step = "step" in aod_da.dims
        has_valid_time = "valid_time" in ds.coords

        if has_time and has_step and has_valid_time:
            vt = ds["valid_time"].values
            vt_flat = vt.flatten()
            deltas = np.abs(vt_flat - scene_np) / np.timedelta64(1, "m")
            best_flat_idx = int(np.argmin(deltas))
            best_delta = float(deltas[best_flat_idx])
            if best_delta > time_window_minutes:
                raise RuntimeError(
                    f"No CAMS time step within ±{time_window_minutes} min of "
                    f"{scene_dt.isoformat()}; nearest is {best_delta:.0f} min."
                )
            n_step = vt.shape[1]
            time_idx = best_flat_idx // n_step
            step_idx = best_flat_idx % n_step
            best_time_np = vt_flat[best_flat_idx]
            aod_da = aod_da.isel(time=time_idx, step=step_idx)
        elif has_time:
            time_values = ds["time"].values
            deltas = np.abs(time_values - scene_np) / np.timedelta64(1, "m")
            best_tidx = int(np.argmin(deltas))
            best_delta = float(deltas[best_tidx])
            if best_delta > time_window_minutes:
                raise RuntimeError(
                    f"No CAMS time step within ±{time_window_minutes} min of "
                    f"{scene_dt.isoformat()}; nearest is {best_delta:.0f} min."
                )
            best_time_np = time_values[best_tidx]
            aod_da = aod_da.isel(time=best_tidx)
        else:
            best_delta = 0.0
            best_time_np = scene_np

        best_time = np.datetime64(best_time_np, "s").astype("datetime64[s]").item()

        for dim in list(aod_da.dims):
            if dim not in ("latitude", "longitude", "lat", "lon"):
                if aod_da.sizes[dim] == 1:
                    aod_da = aod_da.squeeze(dim)
                else:
                    aod_da = aod_da.isel({dim: 0})

        lat_name = next((n for n in ("latitude", "lat") if n in ds.coords), None)
        lon_name = next((n for n in ("longitude", "lon") if n in ds.coords), None)
        if lat_name is None or lon_name is None:
            raise RuntimeError("Could not find latitude/longitude in CAMS file")

        lats = ds[lat_name].values
        lons = ds[lon_name].values
        rn, rs = region_bounds["n"], region_bounds["s"]
        re_, rw = region_bounds["e"], region_bounds["w"]

        lat_res = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 0.5
        lon_res = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 0.5
        lat_mask = (lats >= (rs - lat_res / 2.0)) & (lats <= (rn + lat_res / 2.0))
        lon_mask = (lons >= (rw - lon_res / 2.0)) & (lons <= (re_ + lon_res / 2.0))

        if not np.any(lat_mask) or not np.any(lon_mask):
            center_lat = (rn + rs) / 2.0
            center_lon = (re_ + rw) / 2.0
            lat_idx = int(np.argmin(np.abs(lats - center_lat)))
            lon_idx = int(np.argmin(np.abs(lons - center_lon)))
            aod_val = float(
                aod_da.isel({lat_name: lat_idx, lon_name: lon_idx}).values.item()
            )
            n_cells = 1
        else:
            lat_indices = np.where(lat_mask)[0]
            lon_indices = np.where(lon_mask)[0]
            subset = aod_da.isel({lat_name: lat_indices, lon_name: lon_indices})
            values = subset.values.flatten()
            valid = values[~np.isnan(values)]
            if len(valid) == 0:
                raise RuntimeError(
                    f"All CAMS AOD values are NaN at {best_time.isoformat()}"
                )
            aod_val = float(np.mean(valid))
            n_cells = int(len(valid))
    finally:
        ds.close()

    return {
        "aod550": aod_val,
        "datetime": best_time,
        "minutes_delta": best_delta,
        "n_cells": n_cells,
        "variable": aod_varname,
        "source": "cams",
    }


def get_region_bounds_wgs84():
    """Return the current GRASS computational region in WGS84 lat/lon.

    Calls ``g.proj`` to find out whether the mapset is already
    latlon, and ``m.proj`` to reproject the four corners otherwise.
    Returned dict has keys ``n``, ``s``, ``e``, ``w``.
    Raises :class:`RuntimeError` if ``m.proj`` produces nothing usable.
    """
    proj_info = gs.parse_command("g.proj", flags="g")
    is_latlon = proj_info.get("proj") == "ll" or proj_info.get(
        "name", ""
    ).startswith("Lat")
    region = gs.region()
    if is_latlon:
        return {"n": region["n"], "s": region["s"], "e": region["e"], "w": region["w"]}

    corners = [
        f"{region['e']}|{region['n']}",
        f"{region['w']}|{region['n']}",
        f"{region['e']}|{region['s']}",
        f"{region['w']}|{region['s']}",
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write("\n".join(corners) + "\n")
        tmp_path = tmp.name
    try:
        result = gs.read_command(
            "m.proj", input=tmp_path, flags="od", separator="|"
        )
    finally:
        gs.try_remove(tmp_path)
    lons, lats = [], []
    for line in result.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= 2:
            lon = safe_float(parts[0])
            lat = safe_float(parts[1])
            if lon is not None and lat is not None:
                lons.append(lon)
                lats.append(lat)
    if not lons or not lats:
        raise RuntimeError("Could not reproject region bounds to WGS84")
    return {"n": max(lats), "s": min(lats), "e": max(lons), "w": min(lons)}


def resolve_aod550(options, scene_dt, center_lon, center_lat):
    """Resolve AOD-550 (or visibility) according to ``options``.

    ``options`` must behave like a GRASS ``parser()`` options dict and
    is expected to contain at least ``aod_source``, ``visibility_or_aod``,
    ``aeronet_file``, ``aeronet_time_window``, ``cams_file`` and
    ``cams_time_window``. Returns a dict with:

    * ``mode``: ``"none"``, ``"aod"``, or ``"visibility"``;
    * ``aod550`` (or ``None``);
    * ``visibility_km`` (or ``None``);
    * ``description``: human-readable provenance string;
    * ``details``: sub-dict from the underlying source (only when
      applicable).

    The function ``gs.fatal``\\ s when an inconsistent combination is
    given (e.g. ``aod_source=cams`` without ``cams_file``).
    """
    source = (options["aod_source"] or "").strip().lower()
    vis_or_aod = (options["visibility_or_aod"] or "").strip()

    manual_aod = None
    manual_visibility = None
    if vis_or_aod.lower().startswith("aod:"):
        manual_aod = safe_float(vis_or_aod.split(":", 1)[1])
    elif vis_or_aod:
        manual_visibility = safe_float(vis_or_aod)

    if not source:
        return {
            "mode": "none",
            "aod550": None,
            "visibility_km": None,
            "description": "no atmospheric data provided",
        }

    if source == "manual":
        if manual_aod is not None:
            return {
                "mode": "aod",
                "aod550": manual_aod,
                "visibility_km": None,
                "description": "manual AOD550",
            }
        if manual_visibility is not None:
            return {
                "mode": "visibility",
                "aod550": None,
                "visibility_km": manual_visibility,
                "description": "manual visibility",
            }
        gs.fatal("aod_source=manual requires a valid visibility_or_aod value")

    if source == "visibility":
        if manual_visibility is None:
            gs.fatal(
                "aod_source=visibility requires a numeric visibility_or_aod value"
            )
        return {
            "mode": "visibility",
            "aod550": None,
            "visibility_km": manual_visibility,
            "description": "manual visibility",
        }

    if source == "aeronet_file":
        if not options["aeronet_file"]:
            gs.fatal("aod_source=aeronet_file requires aeronet_file=")
        result = read_aeronet_file_aod(
            options["aeronet_file"],
            scene_dt,
            int(options["aeronet_time_window"]),
        )
        return {
            "mode": "aod",
            "aod550": result["aod550"],
            "visibility_km": None,
            "description": f"AERONET file ({result['method']})",
            "details": result,
        }

    if source == "cams":
        if not options["cams_file"]:
            gs.fatal("aod_source=cams requires cams_file=")
        region_bounds = get_region_bounds_wgs84()
        result = read_cams_aod(
            options["cams_file"],
            scene_dt,
            region_bounds,
            time_window_minutes=int(options["cams_time_window"]),
        )
        gs.message(
            f"CAMS AOD550: {result['aod550']:.4f} "
            f"(variable={result['variable']}, "
            f"time delta={result['minutes_delta']:.0f} min, "
            f"averaged over {result['n_cells']} grid cell(s))"
        )
        return {
            "mode": "aod",
            "aod550": result["aod550"],
            "visibility_km": None,
            "description": f"CAMS ({result['variable']}, {result['n_cells']} cells)",
            "details": result,
        }

    gs.fatal(f"Unsupported aod_source value: {source}")


# ---------------------------------------------------------------------------
# Geometry and 6S helpers
# ---------------------------------------------------------------------------


def auto_atmospheric_model(center_lat, scene_dt):
    """Derive the 6S atmospheric model code from latitude and date.

    Codes:

    * 1: tropical (|lat| <= 23.5°);
    * 2: midlatitude summer (23.5° < |lat| <= 66.5°, warm half-year);
    * 3: midlatitude winter (same band, cold half-year);
    * 4: subarctic summer (|lat| > 66.5°, warm half-year);
    * 5: subarctic winter (same, cold half-year).

    The hemisphere is taken from the sign of ``center_lat`` and the
    ``warm`` half-year is April-September in the northern hemisphere
    and October-March in the southern.
    """
    abs_lat = abs(center_lat)
    month = scene_dt.month
    if center_lat >= 0:
        is_warm = 4 <= month <= 9
    else:
        is_warm = month >= 10 or month <= 3
    if abs_lat <= 23.5:
        return 1
    elif abs_lat <= 66.5:
        return 2 if is_warm else 3
    else:
        return 4 if is_warm else 5


def choose_geometry(meta):
    """Pick a 6S geometry mode from a metadata dict.

    ``meta`` is expected to carry ``scene_datetime``, ``center_lon``,
    ``center_lat`` and a ``geometry`` sub-dict with optional
    ``sun_elevation``, ``sun_azimuth``, ``view_zenith`` and
    ``view_azimuth`` keys.

    Returns one of:

    * ``{"kind": "angles", ...}`` when all four angles plus the scene
      timestamp are known (corresponds to 6S geometry code 0,
      user-supplied);
    * ``{"kind": "latlon_time", ...}`` when only the time and
      lat/lon centre are known (6S code 6, time-based sun position).

    ``gs.fatal``\\ s if neither set of inputs is complete.
    """
    scene_dt = meta.get("scene_datetime")
    center_lon = meta.get("center_lon")
    center_lat = meta.get("center_lat")
    geom = meta.get("geometry", {})
    sun_elev = geom.get("sun_elevation")
    sun_az = geom.get("sun_azimuth")
    view_zen = geom.get("view_zenith")
    view_az = geom.get("view_azimuth")

    if (
        sun_elev is not None
        and sun_az is not None
        and view_zen is not None
        and view_az is not None
        and scene_dt is not None
    ):
        return {
            "kind": "angles",
            "scene_dt": scene_dt,
            "center_lon": center_lon,
            "center_lat": center_lat,
            "solar_zenith": 90.0 - float(sun_elev),
            "solar_azimuth": float(sun_az),
            "view_zenith": float(view_zen),
            "view_azimuth": float(view_az),
        }
    if scene_dt is not None and center_lon is not None and center_lat is not None:
        return {
            "kind": "latlon_time",
            "scene_dt": scene_dt,
            "center_lon": center_lon,
            "center_lat": center_lat,
        }
    gs.fatal("Could not derive a valid geometry from metadata")


def write_icnd_file(
    path,
    band_id,
    geometry,
    atmospheric_model,
    aerosol_model,
    aerosol_info,
    elevation_m,
    fwhm_nm,
):
    """Write an ``i.atcorr`` 6S control (``icnd``) file.

    Parameters
    ----------
    path : str
        Output filename.
    band_id : str
        Ignored at present (kept in the signature for future
        per-band overrides and for symmetry with addon code).
    geometry : dict
        Output of :func:`choose_geometry`.
    atmospheric_model : int
        6S code (see :data:`ATM_MODEL_NAMES`).
    aerosol_model : int
        6S aerosol model code (1 = continental, 2 = maritime, ...).
    aerosol_info : dict
        Output of :func:`resolve_aod550`.
    elevation_m : float
        Mean scene elevation in metres above sea level.
    fwhm_nm : tuple of float
        ``(start_nm, end_nm)`` band edges; 6S expects µm so they are
        divided by 1000 here.

    The resulting file is the standard ``i.atcorr`` input format
    (geometry block, then atmospheric model, then aerosol model,
    AOD/visibility block, target altitude, sensor altitude marker,
    user-defined-band flag and the FWHM range).
    """
    lines = []
    if geometry["kind"] == "angles":
        dt = geometry["scene_dt"]
        lines.append("0")
        lines.append(
            "{:.3f} {:.3f} {:.3f} {:.3f} {} {}".format(
                geometry["solar_zenith"],
                geometry["solar_azimuth"],
                geometry["view_zenith"],
                geometry["view_azimuth"],
                dt.month,
                dt.day,
            )
        )
    else:
        dt = geometry["scene_dt"]
        lines.append("6")
        lines.append(
            "{} {} {:.6f} {:.6f} {:.6f}".format(
                dt.month,
                dt.day,
                decimal_hour_utc(dt),
                geometry["center_lon"],
                geometry["center_lat"],
            )
        )

    lines.append(str(int(atmospheric_model)))
    lines.append(str(int(aerosol_model)))

    if aerosol_info["mode"] == "aod":
        aod = float(aerosol_info["aod550"])
        if aod <= 0:
            lines.append("-1")
        else:
            lines.append("0")
            lines.append("{:.6f}".format(aod))
    elif aerosol_info["mode"] == "visibility":
        vis = float(aerosol_info["visibility_km"])
        lines.append("{:.6f}".format(vis))
    else:
        lines.append("-1")

    lines.append("{:.6f}".format(-float(elevation_m) / 1000.0))
    lines.append("-1000")
    lines.append("0")
    lines.append("{:.6f} {:.6f}".format(fwhm_nm[0] / 1000.0, fwhm_nm[1] / 1000.0))

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Dark-object estimation
# ---------------------------------------------------------------------------
#
# These helpers operate on a DN raster and a nodata sentinel and are
# completely sensor-agnostic. Sensors differ only in what the DN
# value means physically; the estimation code is shared.
# ---------------------------------------------------------------------------


def get_dark_object_dn(mapname, nodata_value=0, min_pixel_count=1000):
    """Lowest DN in ``mapname`` with at least ``min_pixel_count`` pixels.

    Mirrors the dark-object selection used by ``i.landsat.toar``: scan
    the sorted-by-DN histogram and take the smallest DN whose pixel
    count crosses the threshold. ``min_pixel_count <= 0`` short-cuts
    to ``r.info``'s absolute minimum.

    Falls back to the absolute minimum (excluding ``nodata_value``)
    if nothing in the histogram qualifies, emitting a warning.
    """
    if min_pixel_count <= 0:
        info = gs.parse_command("r.info", map=mapname, flags="r")
        val = safe_float(info.get("min"))
        if val is None:
            gs.fatal(f"Could not determine minimum value for {mapname}")
        return val

    output = gs.read_command(
        "r.stats", input=mapname, flags="cn", separator="pipe", quiet=True
    )
    for line in output.strip().splitlines():
        parts = line.split("|")
        if len(parts) != 2:
            continue
        dn = safe_float(parts[0])
        count = safe_float(parts[1])
        if dn is None or count is None:
            continue
        if int(dn) == nodata_value:
            continue
        if int(count) >= min_pixel_count:
            return float(int(dn))

    gs.warning(
        f"No DN value in {mapname} has >= {min_pixel_count} pixels; "
        f"falling back to absolute minimum (excluding nodata={nodata_value})"
    )
    for line in output.strip().splitlines():
        parts = line.split("|")
        if len(parts) != 2:
            continue
        dn = safe_float(parts[0])
        if dn is None or int(dn) == nodata_value:
            continue
        return float(int(dn))
    gs.fatal(f"Could not determine dark object DN for raster {mapname}")


def get_dark_ols_intercept(mapname, nodata_value=0, n_darkest=1000):
    """Estimate dark-object DN via OLS intercept through the darkest pixels.

    Replicates the DSF-style estimator: form the ``n_darkest`` lowest
    DN values (with repetition according to histogram counts), regress
    them against their rank, and take the intercept. Returns ``0`` if
    the regression matrix is degenerate.
    """
    output = gs.read_command(
        "r.stats", input=mapname, flags="cn", separator="pipe", quiet=True
    )
    dn_counts = []
    for line in output.strip().splitlines():
        parts = line.split("|")
        if len(parts) != 2:
            continue
        dn = safe_float(parts[0])
        count = safe_float(parts[1])
        if dn is None or count is None or int(dn) == nodata_value:
            continue
        dn_counts.append((int(dn), int(count)))
    if not dn_counts:
        gs.fatal(f"No valid pixels in {mapname} for OLS dark estimate")
    dark_dns = []
    for dn_val, cnt in dn_counts:
        take = min(cnt, n_darkest - len(dark_dns))
        dark_dns.extend([dn_val] * take)
        if len(dark_dns) >= n_darkest:
            break
    if len(dark_dns) < 2:
        return float(dark_dns[0]) if dark_dns else 0.0
    n = len(dark_dns)
    mean_x = (n - 1) / 2.0
    mean_y = sum(dark_dns) / float(n)
    sum_xy = sum(i * dark_dns[i] for i in range(n))
    sum_xx = sum(i * i for i in range(n))
    denom = sum_xx - n * mean_x * mean_x
    if denom == 0:
        return float(dark_dns[0])
    slope = (sum_xy - n * mean_x * mean_y) / denom
    intercept = mean_y - slope * mean_x
    return max(0.0, intercept)


def get_dark_quantile(mapname, nodata_value=0, percentile=1.0):
    """Estimate dark-object DN as a low percentile of the distribution.

    Uses ``r.quantile`` for the requested percentile (defaulting to
    the 1st). Falls back to ``r.info``'s absolute minimum if
    ``r.quantile`` returns nothing parseable.
    """
    output = gs.read_command(
        "r.quantile", input=mapname, percentiles=str(percentile), quiet=True
    )
    for line in output.strip().splitlines():
        parts = line.split(":")
        if len(parts) >= 2:
            val = safe_float(parts[-1])
            if val is not None:
                return val
    info = gs.parse_command("r.info", map=mapname, flags="r")
    val = safe_float(info.get("min"))
    if val is None:
        gs.fatal(f"Could not determine dark object DN for {mapname}")
    return val


def estimate_dark_object(
    mapname, nodata_value, dark_method, dark_parameter, n_darkest, dark_percentile=1.0
):
    """Dispatch to the requested dark-object estimator.

    ``dark_method`` is one of ``"quantile"``, ``"ols_intercept"`` or
    anything else (then :func:`get_dark_object_dn` is used).
    ``dark_parameter`` is the histogram threshold for the i.landsat.toar
    style estimator; ``n_darkest`` is the sample size for the OLS
    estimator; ``dark_percentile`` is the percentile for the quantile
    estimator.
    """
    if dark_method == "quantile":
        return get_dark_quantile(mapname, nodata_value, dark_percentile)
    elif dark_method == "ols_intercept":
        return get_dark_ols_intercept(mapname, nodata_value, n_darkest)
    else:
        return get_dark_object_dn(mapname, nodata_value, dark_parameter)


def estimate_tiled_dnmin_points(
    mapname,
    nodata_value,
    dark_method,
    dark_parameter,
    n_darkest,
    tile_size,
    dark_percentile=1.0,
    min_dark_fraction=0.001,
):
    """Tile-by-tile dark-object estimation.

    The current region is divided into ``tile_size``-pixel square
    tiles. For each tile :func:`estimate_dark_object` is called with
    the region temporarily clipped to the tile bounds. Tiles with
    fewer than ``tile_size * tile_size * min_dark_fraction`` valid
    pixels (or that fail estimation for any other reason) produce a
    ``None`` entry instead of a DN.

    Returns a list of ``(xc, yc, dnmin_or_None)`` tuples positioned at
    the tile centres. The result is meant as input to
    :func:`interpolate_tiled_dnmin_points`.
    """
    region = gs.region()
    nsres = region["nsres"]
    ewres = region["ewres"]
    north, south = region["n"], region["s"]
    east, west = region["e"], region["w"]
    tile_ns = tile_size * nsres
    tile_ew = tile_size * ewres
    n_rows = max(1, int(math.ceil((north - south) / tile_ns)))
    n_cols = max(1, int(math.ceil((east - west) / tile_ew)))
    gs.verbose(
        f"Tiled dark-object estimation: {n_rows} x {n_cols} tiles "
        f"({tile_size} pixels)"
    )
    points = []
    min_tile_pixels = max(10, int(tile_size * tile_size * min_dark_fraction))
    for tr in range(n_rows):
        for tc in range(n_cols):
            t_north = north - tr * tile_ns
            t_south = max(south, t_north - tile_ns)
            t_west = west + tc * tile_ew
            t_east = min(east, t_west + tile_ew)
            yc = 0.5 * (t_north + t_south)
            xc = 0.5 * (t_west + t_east)
            with gs.RegionManager(
                n=t_north, s=t_south, e=t_east, w=t_west,
                nsres=nsres, ewres=ewres,
            ):
                try:
                    info = gs.parse_command(
                        "r.univar", map=mapname, flags="g", quiet=True
                    )
                    nv = safe_float(info.get("n", "0"))
                    if nv is not None and nv < min_tile_pixels:
                        raise ValueError(f"{int(nv)} pixels < {min_tile_pixels}")
                    dnmin = estimate_dark_object(
                        mapname, nodata_value, dark_method,
                        dark_parameter, n_darkest,
                        dark_percentile=dark_percentile,
                    )
                except Exception:
                    dnmin = None
            points.append((xc, yc, dnmin))
    return points


def interpolate_tiled_dnmin_points(points, tile_size, nprocs=0, memory=300,
                                   tmp_prefix="tmp_opt_dnmin"):
    """Smooth and upscale the output of :func:`estimate_tiled_dnmin_points`.

    Pipeline: tile centres are loaded as a vector point map; missing
    tiles are filled with the median of the valid values;
    ``v.surf.idw`` produces a coarse grid; ``r.neighbors`` smooths it
    with an averaging kernel approximately the size of one tile; and
    ``r.resamp.interp`` bilinearly resamples the result back to the
    full resolution. Returns the name of the final raster.

    All intermediate maps are cleaned up before return.
    """
    point_name = gs.append_node_pid(f"{tmp_prefix}_pts")
    coarse_idw_name = gs.append_node_pid(f"{tmp_prefix}_cidw")
    smooth_name = gs.append_node_pid(f"{tmp_prefix}_smooth")
    interp_name = gs.append_node_pid(f"{tmp_prefix}_interp")
    valid_vals = [v for (_, _, v) in points if v is not None]
    fallback = sorted(valid_vals)[len(valid_vals) // 2] if valid_vals else 0.0
    ascii_path = gs.tempfile()
    try:
        with open(ascii_path, "w", encoding="utf-8") as tmp:
            for x, y, v in points:
                vv = v if v is not None else fallback
                tmp.write(f"{x:.12f}|{y:.12f}|{vv:.12f}\n")
        gs.run_command(
            "v.in.ascii", input=ascii_path, output=point_name,
            separator="pipe", x=1, y=2, cat=0,
            columns="x double precision, y double precision, dnmin double precision",
            overwrite=True, quiet=True,
        )
    finally:
        gs.try_remove(ascii_path)
    region = gs.region()
    nsres = region["nsres"]
    ewres = region["ewres"]
    coarse_factor = max(1, tile_size // 100)
    coarse_nsres = nsres * coarse_factor
    coarse_ewres = ewres * coarse_factor
    smooth_cells = max(3, tile_size // coarse_factor)
    if smooth_cells % 2 == 0:
        smooth_cells += 1
    pad_cells = smooth_cells // 2 + 1
    pad_ns = pad_cells * coarse_nsres
    pad_ew = pad_cells * coarse_ewres
    with gs.RegionManager(
        n=region["n"] + pad_ns, s=region["s"] - pad_ns,
        e=region["e"] + pad_ew, w=region["w"] - pad_ew,
        nsres=coarse_nsres, ewres=coarse_ewres,
    ):
        gs.run_command(
            "v.surf.idw", input=point_name, column="dnmin",
            output=coarse_idw_name,
            npoints=min(12, len(valid_vals) if valid_vals else 1),
            overwrite=True, power=0.5, quiet=True,
        )
        gs.run_command(
            "r.neighbors", input=coarse_idw_name, output=smooth_name,
            size=smooth_cells, method="average", flags="c",
            nprocs=nprocs, memory=memory, overwrite=True, quiet=True,
        )
    gs.run_command(
        "r.resamp.interp", input=smooth_name, output=interp_name,
        method="bilinear", nprocs=nprocs, memory=memory,
        overwrite=True, quiet=True,
    )
    gs.run_command("g.remove", type="vector", name=point_name, flags="f", quiet=True)
    gs.run_command(
        "g.remove", type="raster",
        name=f"{coarse_idw_name},{smooth_name}", flags="f", quiet=True,
    )
    return interp_name


# ---------------------------------------------------------------------------
# Raster metadata tagging
# ---------------------------------------------------------------------------


def set_map_metadata(mapname, title, units, semantic_label, scene_dt=None,
                     color="grey"):
    """Tag a GRASS raster with title, units, semantic label and timestamp.

    Wraps :func:`grass.script.run_command` calls to ``r.support``,
    ``r.colors`` and (when ``scene_dt`` is non-``None``) ``r.timestamp``.
    Also records the call in ``raster_history``. ``title`` is
    truncated to 79 characters with an ellipsis to fit the GRASS
    title field.

    Sensor-specific addons typically build ``title`` and
    ``semantic_label`` from their own band-name tables and call this
    once per band.
    """
    if len(title) > 79:
        title = title[:76] + "..."
    gs.raster_history(mapname)
    gs.run_command(
        "r.support", map=mapname, title=title, units=units,
        semantic_label=semantic_label,
    )
    if color:
        gs.run_command("r.colors", map=mapname, color=color, quiet=True)
    if scene_dt:
        months = ["", "jan", "feb", "mar", "apr", "may", "jun",
                  "jul", "aug", "sep", "oct", "nov", "dec"]
        ts = (
            f"{scene_dt.day} {months[scene_dt.month]} "
            f"{scene_dt.year} {scene_dt.strftime('%H:%M:%S')}"
        )
        gs.run_command("r.timestamp", map=mapname, date=ts)


# ---------------------------------------------------------------------------
# Dark-object diagnostics
# ---------------------------------------------------------------------------


def diagnose_dark_objects(
    band_darks,
    band_order,
    floor_dn=10.0,
    floor_radiance_frac=0.25,
    sensor_name="sensor",
):
    """Sanity-check per-band dark-object estimates for DOS reflectance.

    Dark-object subtraction (DOS) assumes the darkest pixels are dark
    *because of atmospheric path radiance*. That assumption breaks when
    the darkest pixels are dark for other reasons — most commonly deep
    shadow (dark by geometry) or water (which is near-zero in the NIR
    regardless of the atmosphere). When that happens, the estimated
    dark object in the affected band collapses toward the sensor floor,
    while neighbouring bands stay at a sensible haze level. The
    resulting asymmetric subtraction badly distorts ratio indices such
    as NDVI, inflating them in shadow and over water.

    The dark-object *radiance* ``L_dark`` is the only fair way to
    compare dark objects across bands. This routine does **not** compute
    it: different sensors use different gain conventions (SuperView-NEO
    uses multiplicative ``L = DN*gain + bias`` while Pléiades-NEO uses
    divisive ``L = DN/gain + bias``), so the caller computes ``L_dark``
    with its own convention and passes it in. The routine then applies
    two convention-agnostic checks:

    1. **Floor check.** A band whose dark-object DN is at or below
       ``floor_dn`` is flagged: its dark object is sitting on the
       sensor floor, the tell-tale signature of shadow/water
       domination.

    2. **Monotonicity check.** Atmospheric path radiance decreases
       smoothly from short to long wavelengths, so ``L_dark`` should
       decline gently along ``band_order`` (deep-blue → blue → green →
       red → red-edge → NIR). A band whose ``L_dark`` drops below
       ``floor_radiance_frac`` times the previous band's ``L_dark`` is
       flagged as breaking that decline — a sudden cliff rather than a
       gentle slope.

    Parameters
    ----------
    band_darks : dict
        ``{band_id: {"dnmin": float, "L_dark": float}}``. ``L_dark`` is
        the dark-object radiance, precomputed by the caller using its
        own gain convention. ``dnmin`` is the raw dark-object DN, used
        for the floor check. Bands missing either key are skipped.
    band_order : list of str
        Band ids in increasing-wavelength order, e.g.
        ``["B", "G", "R", "NIR"]`` (SuperView-NEO) or
        ``["DB", "B", "G", "R", "RE", "NIR"]`` (Pléiades-NEO). Only ids
        present in both ``band_order`` and ``band_darks`` are
        considered, so the caller's natural band-processing order can
        differ from this wavelength order.
    floor_dn : float
        DN at or below which a dark object is considered "on the
        floor". Default 10.
    floor_radiance_frac : float
        Fraction of the previous band's ``L_dark`` below which the
        decline is considered broken. Default 0.25 (i.e. a drop to
        less than a quarter of the previous band is suspicious).
    sensor_name : str
        Used only in the messages, e.g. "SuperView-NEO".

    Returns
    -------
    dict
        ``{"radiances": {band_id: L_dark}, "warnings": [str, ...],
        "ok": bool}``. ``ok`` is ``True`` when no warning fired. The
        function does not print anything itself; the caller decides how
        to surface ``warnings`` (e.g. via ``gs.warning`` and/or the
        processing summary).
    """
    ids = [b for b in band_order if b in band_darks]
    radiances = {}
    for bid in ids:
        rec = band_darks[bid]
        dnmin = rec.get("dnmin")
        ld = rec.get("L_dark")
        if dnmin is None or ld is None:
            continue
        radiances[bid] = float(ld)

    warnings = []

    # 1. Floor check
    for bid in ids:
        rec = band_darks.get(bid, {})
        dnmin = rec.get("dnmin")
        if dnmin is not None and float(dnmin) <= floor_dn:
            warnings.append(
                f"{sensor_name} band {bid}: dark-object DN={float(dnmin):.0f} "
                f"is on the sensor floor (<= {floor_dn:.0f}). The darkest "
                f"pixels in this band are most likely deep shadow or water, "
                f"not atmospheric haze. DOS will over-suppress the other "
                f"bands relative to {bid} and inflate ratio indices (e.g. "
                f"NDVI) in shadow/water. Consider supplying a shadow/water "
                f"mask via cloud_mask= or switching dark_method to "
                f"'quantile'."
            )

    # 2. Monotonicity / cliff check (along increasing wavelength)
    rad_ids = [b for b in ids if b in radiances]
    for prev, cur in zip(rad_ids, rad_ids[1:]):
        lp = radiances[prev]
        lc = radiances[cur]
        if lp > 0 and lc < floor_radiance_frac * lp:
            warnings.append(
                f"{sensor_name} dark-object radiance drops sharply from band "
                f"{prev} (L={lp:.2f}) to band {cur} (L={lc:.2f}) — a cliff "
                f"rather than the gentle short->long wavelength decline "
                f"expected from atmospheric path radiance. Band {cur}'s dark "
                f"object is probably contaminated by shadow/water. Same "
                f"remedies as above (cloud_mask= or dark_method=quantile)."
            )

    return {
        "radiances": radiances,
        "warnings": warnings,
        "ok": not warnings,
    }


def format_dark_object_table(diagnosis, band_darks, band_order, band_names=None):
    """Format the dark-object diagnosis as summary text lines.

    Returns a list of strings (no trailing newlines) suitable for
    appending to a processing summary. ``band_names`` optionally maps
    band ids to human-readable names for the table (e.g.
    ``{"NIR": "nir"}``); ids are used verbatim when absent.

    The table shows the per-band dark-object DN and the derived
    dark-object radiance ``L_dark`` (computed by the caller with its own
    gain convention and carried through :func:`diagnose_dark_objects`),
    followed by any warnings from :func:`diagnose_dark_objects`.
    """
    band_names = band_names or {}
    radiances = diagnosis.get("radiances", {})
    lines = ["  Dark-object diagnostics (L_dark = dark-object radiance):"]
    for bid in band_order:
        if bid not in band_darks:
            continue
        rec = band_darks[bid]
        name = band_names.get(bid, bid)
        dnmin = rec.get("dnmin")
        ld = radiances.get(bid)
        dn_txt = "n/a" if dnmin is None else f"{float(dnmin):<10g}"
        ld_txt = "n/a" if ld is None else f"{ld:.3f}"
        lines.append(f"    {name:10s} DNmin={dn_txt}  ->  L_dark={ld_txt}")
    if diagnosis.get("warnings"):
        lines.append("    WARNING(S):")
        for w in diagnosis["warnings"]:
            # Wrap long warnings to keep the summary readable.
            lines.append(f"      - {w}")
    else:
        lines.append("    All bands show a sensible short->long wavelength "
                     "dark-object decline; no shadow/water contamination "
                     "flagged.")
    return lines
