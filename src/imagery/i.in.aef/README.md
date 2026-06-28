## NAME

_i.in.aef_: Imports AlphaEarth Foundations satellite embedding COGs into GRASS GIS.

> [!WARNING]  
> This addon is work in progress, with limited testing. Consider this an early alpha version!! Use at your own risk.
> Do you encounter bugs of do you have suggestions for improvements, please file a bug report.

## SYNOPSIS

**i.in.aef**  

**i.in.aef --help**  

**i.in.aef** \[-**lq**\] **input**\=_name_ \[**prefix**\=_string_\] \[**mapset**\=_string_\] \[**year**\=_integer_\] \[**utm\_zone**\=_string_\] \[**memory**\=_integer_\] \[**nprocs**\=_integer_\] \[--**help**\] \[--**verbose**\] \[--**quiet**\] \[--**ui**\]

### Flags:

* **\-l** List available UTM zones, years, and tile counts, then exit
* **\-q** Keep quantized (int8) bands, skip de-quantization
* **\--help** Print usage summary
* **\--verbose** Verbose module output
* **\--quiet** Quiet module output
* **\--ui** Force launching GUI dialog

### Parameters:

* **input**\=_name_ **\[required\]**: Path to the AEF tile index JSON file
* **prefix**\=_string_: Prefix layers for output map names (default: aef\_<zone>)
* **mapset**\=_string_: Mapset name
* **year**\=_integer_: Year to import (e.g. 2018, 2021). Default: _2024_
* **utm\_zone**\=_string_: UTM zone code to import (e.g. 44N)
* **memory**\=_integer_: Maximum memory to be used (in MB). Default: _300_
* **nprocs**\=_integer_: Number of threads for parallel processing. Default: _1_

## DESCRIPTION

> [!WARNING]  
> This addon is work in progress. Consider this an early alpha version!! Use at your own risk.
> Do you encounter bugs of do you have suggestions for improvements, please file a bug report.

*i.in.aef* downloads and imports
[AlphaEarth Foundations (AEF)](https://source.coop/tge-labs/aef)
satellite embedding data into GRASS GIS.

The AEF dataset provides 64-channel embeddings derived from satellite imagery, distributed as Cloud-Optimized GeoTIFFs (COGs) on Source Cooperative.

The module reads a JSON tile index (as provided by the dataset) and, for a user-selected year, downloads the relevant COGs, imports them into per-UTM-zone GRASS projects, patches overlapping tiles, and applies de-quantization to recover the original floating-point embedding values.

The area of interest is determined by the **current computational region**. Only tiles that intersect the region are downloaded, and only the portion within the region is fetched from each COG (via HTTP range requests).

## Workflow

For each UTM zone that contains intersecting tiles, the module:

1. Saves the current computational region as a temporary vector using *v.in.region*.
2. Creates a GRASS project (location) for the UTM zone if it does not already exist (e.g. `UTM44N` with EPSG:32644).
3. Switches to that project and reprojects the region vector into it using *v.proj*.
4. Sets the computational region from the reprojected vector and reads back the UTM-native bounds.
5. For each tile, uses `gdal.Warp` via `/vsicurl/` with those UTM bounds to fetch only the needed COG blocks and simultaneously fix the bottom-up pixel layout.
6. Imports all 64 bands with *r.in.gdal* (creating maps named `<tile>.1` through `<tile>.64`).
7. Sets the region from the imported rasters and patches tiles per band with *r.patch*.
8. Applies de-quantization with *r.mapcalc*.
9. Groups all de-quantized bands into an imagery group with *i.group*.
10. Switches back to the original project and mapset.

## Listing mode

When the **-l** flag is set, the module prints a summary table of all UTM zones, years, and the number of tiles for each combination, then exits. No download or import is performed.

## Bottom-up orientation

The COGs in this dataset have a “bottom-up” pixel layout (origin at bottom-left, positive y-resolution). The module uses `gdal.Warp` to re-orient each file to the standard north-up layout expected by GRASS GIS.

## COG subsetting

Because the source files are Cloud-Optimized GeoTIFFs, GDAL uses HTTP range requests to retrieve only the internal tiles that intersect the requested UTM bounding box. This can drastically reduce transfer volume compared to downloading entire files.

## De-quantization

The AEF embeddings are stored as signed 8-bit integers after a quantization step that applies a square-root transform and scaling. The module reverses this to produce floating-point maps with values in [-1, 1]. The value `-128` is treated as a masked (NULL) pixel.

De-quantization formula:

```
rescaled = q / 127.5
x = sign(rescaled) * |rescaled|^2.0
```

## Output

For each UTM zone processed, the module creates a GRASS project named `UTM<zone>` (e.g. `UTM44N`) containing:

- 64 de-quantized raster maps named `aef_<zone>_dq.1` through `aef_<zone>_dq.64`
- An imagery group `aef_<zone>_dq` referencing all bands

# EXAMPLES

## List available data

```
i.in.aef input=aef_index.json -l
```

## Import for a year using the current region

```
# Set the region to the area of interest (any projection)
g.region n=30.3 s=29.6 e=78.5 w=77.5

# Import tiles intersecting the region
i.in.aef input=aef_index.json year=2021
```

## Import a specific UTM zone only

```
i.in.aef input=aef_index.json year=2021 utm_zone=44N
```

## Import from a vector map extent

```
# Set the region to match a study area vector
g.region vector=study_area

# Import
i.in.aef input=aef_index.json year=2018
```

# NOTES

The module creates new GRASS projects (locations) in the current GISDBASE for each UTM zone encountered. After processing, it switches back to the original project and mapset. The user can then access the imported data by switching to the relevant UTM project.

The current computational region determines which tiles are downloaded and how they are clipped. Set the region to your study area before running this module.

# REQUIREMENTS

- GDAL Python bindings with `/vsicurl/` support (network access)
- Internet connection for downloading COGs from Source Cooperative
- GRASS GIS 8.5+ (for `grass.tools` and `gs.create_project`)

# REFERENCES

- Brown, A. et al. (2024). AlphaEarth Foundations Satellite Embeddings.  
  https://source.coop/tge-labs/aef
- Cloud-Native Geospatial Forum (2025). Building Frictionless Geospatial AI.  
  https://cloudnativegeo.org/blog/2025/11/building-frictionless-geospatial-ai-making-alphaearth-foundations-embeddings-accessible/

# SEE ALSO

*r.in.gdal*, *r.patch*, *r.mapcalc*, *i.group*, *v.in.region*, *v.proj*, *g.mapset*

# AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green
academy](https://has.nl), [Innovative Biomonitoring research
group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research
group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)