## DESCRIPTION

> Experimental / in development. Do not use unless you like to experiment (and possibly to contribute)

*r.niche.espace* prepares occurrence points and environmental raster data for
niche-overlap analysis with the R package
[humboldt](https://github.com/jasonleebrown/humboldt) (Brown & Carnaval 2019).
It ports the **data-preparation** half of humboldt to GRASS so it streams over
large rasters, then hands off small tables to R:

```
thin  ->  trim  ->  sample  ->  humboldt-format CSV tables
```

The niche statistics, PCA and kernel density stay in humboldt. Geographic
overlap/divergence **maps** are produced afterwards by
*[r.niche.map](r.niche.map.md)*.

### Stages

1. **Thinning** (`thin_*`) — replaces `humboldt.occ.rarefy`.
   `thin_method=grid` (default) snaps occurrences to a grid of cell size
   `thin_distance`, keeping one point per cell (fast, O(n); points move to
   cell centres). `thin_method=nn` drops one point of the closest pair until
   none are closer than `thin_distance` (O(n³); modest occurrence counts,
   exact coords). It approximates `humboldt.occ.rarefy` rather than
   reproducing it — humboldt measures in azimuthal-equidistant metres and
   breaks ties on the 2nd–6th nearest neighbours — so the two can keep
   different subsets of a clustered set.
2. **Trimming** (`trim_*`) — replaces the MCP / RADIUS / MASK branches of
   `humboldt.g2e`, via `v.hull` + `v.buffer` (buffering scales with the small
   occurrence set, not the raster). The result becomes a raster **MASK** so the
   background reads are restricted natively.
3. **Sampling** — `v.what.rast` attaches env values to occurrences;
   `r.stats` streams background cell values. Replaces `humboldt.sample.spp`.

### Outputs

Two humboldt-format tables per species:

* `table_1` / `table_2` — occurrences with sampled env (`x,y,cat,var…`); add the
  `sp` name column in R.
* `bg_table_1` / `bg_table_2` — trimmed background cells (`x,y,var…`).

Feed these to `humboldt.g2e()` in R with **`env.trim=FALSE`** and
**`rarefy.dist=0`** (trimming and thinning are already done here). See
`../r.niche.map/examples/niche_workflow.R` for the full chain.

## NOTES

* **Requires GRASS GIS 8.5+** (`grass.tools.Tools`, `gs.MaskManager` /
  `gs.RegionManager`).
* `memory` is passed to `v.to.rast` (grid thinning). Among the modules used,
  that is the one with a `memory` option; none take `nprocs`.
* For a lat/long location, `km` distances use a flat-degree approximation
  (`/111`); humboldt applies a latitude-dependent correction. Reproject to an
  equal-distance CRS for exact parity.
* `grid` thinning moves points to cell centres (up to half `thin_distance`);
  use `nn` when original coordinates must be preserved.

## EXAMPLE

Prepare tables for humboldt (see the full workflow in
`../r.niche.map/examples/niche_workflow.R`):

```sh
r.niche.espace env=bio1,bio2,bio12,bio15 \
    occ_1=occ_native occ_2=occ_invasive \
    thin_distance=50 thin_units=km thin_method=grid \
    trim_method=mcp trim_buffer=200 \
    table_1=sp1.csv  table_2=sp2.csv \
    bg_table_1=env1.csv bg_table_2=env2.csv
```

## SEE ALSO

*[r.niche.map](r.niche.map.md)* (geographic overlap/divergence maps),
*[r.niche.similarity](r.niche.similarity.md)* (D & I overlap statistics),
*[v.what.rast](v.what.rast.md)*, *[v.hull](v.hull.md)*,
*[v.buffer](v.buffer.md)*, *[r.stats](r.stats.md)*

## REFERENCES

* Brown, J.L. & Carnaval, A.C. (2019) *A tale of two niches.*
  Frontiers of Biogeography 11, e44158.
* Broennimann, O. et al. (2012) *Measuring ecological niche overlap.*
  Global Ecology and Biogeography 21, 481–497.

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl), [Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/), [Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)