## DESCRIPTION

> [!WARNING]  
> This addon is work in progress (consider it alpha version), so use at your own risk. If you find any bug,
> of if you have suggestions for improvements, please file a bug report.

*i.in.svneo* imports SuperView-NEO satellite imagery
(GeoTIFF) into GRASS GIS and enriches each raster band with metadata
extracted from the accompanying NSO ISO 19115 XML file.

The module is to import BOA reflectance products, which is 
available since 2026 through https://www.satellietdataportaal.nl/.

The module is a thin wrapper around
[r.in.gdal](https://grass.osgeo.org/grass-stable/manuals/r.in.gdal.html).
It imports the 4-band BGRN GeoTIFF, renames the bands to meaningful
names, and sets the following metadata on each output raster:

- **Title** derived from the band name and input filename
  (e.g. *red from 20260321_133213_SVNEO-04_30cm_...tif*)
- **Semantic label** following the generic naming convention
  (`gen_b`, `gen_g`, `gen_r`, `gen_nir`)
- **Timestamp** from the acquisition datetime in the XML metadata
- **Units** detected from the product name (e.g. *reflectance*
  for BOA products)
- **Color table** set to *grey*

The expected band order in the GeoTIFF is blue, green, red, NIR,
matching the BGRN convention used in SuperView-NEO products
distributed through the Netherlands Space Office (NSO)
Satellietdataportaal.

By default the full image extent is imported. When the **-r** flag
is set, import is restricted to the current computational region
(the flag is passed through to *r.in.gdal*).

## NOTES

The module expects the NSO metadata XML file that accompanies the
GeoTIFF download. This is an ISO 19115 file containing acquisition
time, satellite name, product name, gain/offset values, cloud cover,
and incidence angle in the `supplementalInformation` element.

SuperView-NEO BOA (Bottom-Of-Atmosphere) products are already
atmospherically corrected surface reflectance data with values in the
0–1 range (Float32). No further radiometric conversion is needed.
The module detects BOA products from the product name in the metadata
and sets the units accordingly.

## EXAMPLES

### Import a SuperView-NEO BOA scene

```bash
i.in.svneo input=20260321_133213_SVNEO-04_30cm_RD_32bit_BOA_BGRN_Rhoon.tif \
           metadata=20260321_133213_SVNEO-04_30cm_RD_32bit_BOA_BGRN_Rhoon.xml \
           output=rhoon
```

This creates four raster maps: `rhoon_blue`, `rhoon_green`,
`rhoon_red`, `rhoon_nir`, each with the acquisition timestamp,
semantic label, and appropriate title set.

### Import clipped to the current region

```bash
g.region vector=study_area
i.in.svneo -r \
           input=20260321_133213_SVNEO-04_30cm_RD_32bit_BOA_BGRN_Rhoon.tif \
           metadata=20260321_133213_SVNEO-04_30cm_RD_32bit_BOA_BGRN_Rhoon.xml \
           output=rhoon
```

### Inspect the metadata of an imported band

```bash
r.info rhoon_red
r.timestamp rhoon_red
```

## SEE ALSO

[r.in.gdal](https://grass.osgeo.org/grass-stable/manuals/r.in.gdal.html),
[i.in.pneo](i.in.pneo.html)

## AUTHORS

[Paulo van Breugel](https://ecodiv.earth)

<a href="https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/"><img src="../logos/logo_IBM.png" height=100/></a> <a href="https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/"><img src="../logos/logo_KRL.png" height=100/></a> <a href="https://www.combined-project.eu/"><img src="../logos/logo_combined.png" height=80/></a> <a href="https://savethetiger.nl/"><img src="../logos/logo_STGW.png" height=80/></a>