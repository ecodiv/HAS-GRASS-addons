## DESCRIPTION

*t.rast.import.cru* imports a monthly climate data file of the
[CRU TS](https://crudata.uea.ac.uk/cru/data/hrg/) dataset and registers the
imported raster maps in a space time raster dataset (STRDS). A CRU TS file is
a NetCDF file that holds one climate variable on a global 0.5 degree grid,
with one layer per month since January 1901.

Every monthly layer becomes one raster map, named *basename*`_YYYY_MM`. The
dates are read from the time axis of the input file itself, so no start or end
date has to be given. Each map is registered with the interval of the month it
describes, running from the first day of that month up to the first day of the
next, which leaves no gaps in the series.

The **input** file may be gzip compressed, as CRU distributes it. It is then
decompressed into a temporary directory, which is removed again afterwards.

The climate **variable** does not need to be named. A CRU TS file holds a
single climate variable next to `stn`, the number of stations that contributed
to each cell, and that one variable is found by itself. Name the variable
explicitly to import `stn`, or to import from a file that holds more than one
climate variable.

The title and the unit of each imported raster map are taken from the
`long_name` and `units` attributes of the NetCDF variable. The **title**,
**description** and **semantictype** of the space time raster dataset are set
with the options of the same name. For precipitation, `semantictype=sum`
describes the data better than the default `mean`.

With the **-a** flag the maps are registered in an existing space time raster
dataset instead of a newly created one, which is how the decadal files CRU
distributes are collected into one series.

## NOTES

Only monthly series can be imported. The module stops when the layers of the
input file do not form one unbroken run of months, because both the map names
and the registered intervals depend on that.

CRU TS data lie on a plain geographic grid and belong in a WGS84 latitude-longitude
project. The NetCDF files carry little information about their CRS, so
*r.in.gdal* may report that it does not match the one of the project. The
**-o** flag then lets the import proceed, as in the examples below.

A full CRU TS series holds 1500 monthly layers (1901-2025). Importing all of
them and writing their metadata takes considerably longer than importing one
of the decadal files that CRU also distributes.

The module needs the GDAL Python bindings (`osgeo.gdal`) to read the time axis
of the input file.

When the module stops with an error, the raster maps it had already imported
are removed again.

## EXAMPLES

The examples use the files as CRU distributes them, in a WGS84
latitude-longitude project.

Import the monthly minimum temperature of the whole series:

```sh
t.rast.import.cru -o input=cru_ts4.10.1901.2025.tmn.dat.nc.gz output=CRU_tmn
```

This gives the raster maps `tmn_1901_01` up to `tmn_2025_12`, registered in
the space time raster dataset `CRU_tmn`.

Import monthly precipitation as a monthly sum, under a basename of its own:

```sh
t.rast.import.cru -o input=cru_ts4.10.1901.2025.pre.dat.nc.gz output=CRU_pre \
    basename=precipitation semantictype=sum
```

Import the four variables that are used most often:

```sh
for variable in tmn tmx tmp pre ; do
    t.rast.import.cru -o input=cru_ts4.10.1901.2025.${variable}.dat.nc.gz \
        output=CRU_${variable}
done
```

Collect three of the decadal files into a single space time raster dataset,
creating it with the first file and appending to it with the **-a** flag:

```sh
t.rast.import.cru -o input=cru_ts4.10.1901.1910.tmn.dat.nc.gz output=CRU_tmn
for decade in 1911.1920 1921.1930 ; do
    t.rast.import.cru -o -a input=cru_ts4.10.${decade}.tmn.dat.nc.gz \
        output=CRU_tmn
done
```

Import only the part of the grid that covers the current region, then give the
series a colour table and aggregate it to yearly minima:

```sh
g.region n=14 s=4 w=-18 e=-4 res=0.5
t.rast.import.cru -o -r input=cru_ts4.10.1901.2025.tmn.dat.nc.gz output=CRU_tmn
t.rast.colors input=CRU_tmn color=celsius
t.rast.aggregate input=CRU_tmn output=CRU_tmn_yearly basename=tmn_year \
    granularity="1 years" method=minimum
```

## SEE ALSO

*[r.in.gdal](https://grass.osgeo.org/grass-stable/manuals/r.in.gdal.html),
[t.create](https://grass.osgeo.org/grass-stable/manuals/t.create.html),
[t.register](https://grass.osgeo.org/grass-stable/manuals/t.register.html),
[t.rast.aggregate](https://grass.osgeo.org/grass-stable/manuals/t.rast.aggregate.html),
[t.rast.colors](https://grass.osgeo.org/grass-stable/manuals/t.rast.colors.html),
[t.rast.import](https://grass.osgeo.org/grass-stable/manuals/t.rast.import.html),
[t.rast.import.netcdf](https://grass.osgeo.org/grass-stable/manuals/addons/t.rast.import.netcdf.html)*

## REFERENCES

Harris, I., Osborn, T.J., Jones, P., Lister, D. (2020). Version 4 of the CRU
TS monthly high-resolution gridded multivariate climate dataset. *Scientific
Data* 7. DOI:
[10.1038/s41597-020-0453-3](https://doi.org/10.1038/s41597-020-0453-3)

CRU TS data are published at
[crudata.uea.ac.uk/cru/data/hrg](https://crudata.uea.ac.uk/cru/data/hrg/).

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth),
[Innovative Biomonitoring](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/)
and
[Climate-robust Landscapes](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)
research groups at the [HAS green academy](https://has.nl)

