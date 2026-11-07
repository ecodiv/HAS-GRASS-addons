## DESCRIPTION

> Experimental / in development. Do not use unless you like to experiment (and possibly to contribute)

*r.niche.map* produces **geographic** maps of niche **overlap** and
**divergence** for two species/populations.

It accompanies the R package [humboldt](https://github.com/jasonleebrown/humboldt), which analyses
niches in *environmental* space (PC1 × PC2). It does not show where, in geographic space, two niches overlap or diverge. *r.niche.map* fills that gap. It back-projects humboldt's E-space
niche grids onto geography, using its PCA rotation.

### How it works

1. **Rebuild PC rasters**: from the environmental stack and humboldt's PCA
   rotation, each ground cell's principal-component score is computed per axis
   as: `PC = Σ loadingⱼ · (envⱼ − centerⱼ) / normⱼ`
2. **Look up the niche**: for each location on the map, read its two PC scores,
   find the matching cell in the species' environmental-space niche grid, and
   assign that cell's niche value to the location. The result is a
   **suitability** raster — how well each location's environment matches the
   species' niche.
3. **Combine** — `overlap = min(suit_1, suit_2)` (both niches suitable);
   `divergence = suit_1 − suit_2` (> 0 favours species 1, < 0 favours
   species 2).

## NOTES

* **Requires GRASS GIS 8.5+** (`grass.tools.Tools`, `gs.RegionManager`).
* **Inputs come from humboldt, via R.** `rotation` is a CSV exported from the
  `dudi.pca` object (`variable,center,norm,pc1,pc2`); `niche_1`/`niche_2` are
  the E-space niche grids (`humboldt.grid.espace` output) imported into GRASS
  as rasters in a PC-space region. The `examples/niche_workflow.R` script does
  the whole chain with **rgrass**.
* **`env` order must match `rotation` row order** exactly, and be the same
  variables (and PCA `e.var` subset) humboldt used.
* The module reads the PC-space extent from the `niche_1` raster's own region
  and reuses it for `niche_2`, so the two must share that region. This is
  checked, and a mismatch is an error. They match when both come from
  `humboldt.grid.espace` calls with the same `R` on one `humboldt.g2e` run.
* Cells where **any** `env` raster is NULL are NULL in all four outputs. A cell
  that has env data but whose PC scores fall outside the niche grid scores 0 —
  "this environment is not in the species' E-space" — which is deliberately
  distinct from no data.
* Because it reuses humboldt's grids and rotation, this module is **not**
  affected by the GRASS-vs-kernelUD smoothing question (that only matters if
  the niche grids are built in GRASS instead of humboldt).

## EXAMPLE

See `examples/niche_workflow.R` for the full
`r.niche.espace → humboldt → r.niche.map` pipeline. The final GRASS step:

```sh
r.niche.map env=bio1,bio2,bio12,bio15 rotation=rotation.csv \
    niche_1=niche_sp1 niche_2=niche_sp2 \
    suit_1=suit_native suit_2=suit_invasive \
    overlap=niche_overlap divergence=niche_divergence
```

## SEE ALSO

*[r.niche.espace](r.niche.espace.md)* (data preparation),
*[r.niche.similarity](r.niche.similarity.md)* (D & I overlap statistics),
*[i.pca](i.pca.md)*, *[r.recode](r.recode.md)*, *[r.mapcalc](r.mapcalc.md)*

## REFERENCES

* Brown, J.L. & Carnaval, A.C. (2019) *A tale of two niches.*
  Frontiers of Biogeography 11, e44158.

## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl), [Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/), [Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)
