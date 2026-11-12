# t.rast.import.cru

> This addon is work in progress.

A GRASS GIS addon that imports monthly climate data of the
[CRU TS](https://crudata.uea.ac.uk/cru/data/hrg/) dataset into a GRASS GIS
project. CRU TS files are NetCDF files holding one climate variable on a
global 0.5 degree grid, with one layer per month since January 1901.

The addon

* imports every monthly layer as a raster map named `<basename>_YYYY_MM`,
  reading the gzip compressed files as CRU distributes them,
* timestamps each map with the month it describes, read from the time axis of
  the input file itself, and
* registers the maps in a space time raster dataset (STRDS), which it either
  creates or appends to.

## Installation

The addon needs GRASS GIS 8.5 or newer and the GDAL Python bindings
(`osgeo.gdal`). Install it from a local copy of this repository with

```sh
g.extension extension=t.rast.import.cru url=/path/to/RS2grass
```

or point `url=` at the repository itself once it is published.

## Usage

```sh
t.rast.import.cru -o input=cru_ts4.10.1901.2025.tmn.dat.nc.gz output=CRU_tmn
```

This imports the monthly minimum temperature of the whole CRU TS series as
the raster maps `tmn_1901_01` up to `tmn_2025_12` and registers them in the
space time raster dataset `CRU_tmn`. The `-o` flag is needed because the
NetCDF files carry too little information about their CRS for *r.in.gdal* to
match it against the one of the project.

All options, and more examples, are in the manual page: run
`t.rast.import.cru --help`, or read
[t.rast.import.cru.md](t.rast.import.cru.md).

## Contents

| File | |
| --- | --- |
| `t.rast.import.cru.py` | the module |
| `t.rast.import.cru.md` | manual page, as GRASS GIS 8.5 and newer build it |
| `t.rast.import.cru.html` | manual page in HTML, which the build still needs |
| `Makefile`, `CMakeLists.txt` | build files for the two GRASS build systems |

## License

GNU General Public License, version 2 or any later version.
