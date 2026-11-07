## r.niche

> WARNING: this is work in progress, and probably not working right now!

Scripts that provide some helper function for GRASS users that want to use the R package
[humboldt](https://github.com/jasonleebrown/humboldt) (Brown & Carnaval 2019). 

- The `r.niche.espace`
ports the **data-preparation** half of humboldt to GRASS. It streams over
large rasters, then hands off small tables to R. 
- The `r.niche.map` Imports and back-projects humboldt's E-space niche grids onto geography, using its PCA rotation.

## TODO

Known gaps. None of them block the current design.

`r.niche.map`:

- [ ] `read_rotation` parses the `variable` column and then discards it.
  Compare it against the `env` basenames and warn on a mismatch: a wrong
  order or a wrong `e.var` subset is the likeliest user error, and it
  currently fails silently with a plausible-looking map.
- [ ] `r.recode` in `project` is called without `-d`, so the output type is
  inferred from the rules text (FCELL for float rules, CELL if a niche grid
  happens to hold only integers). Pass `-d` to make it deterministic.
- [ ] The module computes in whatever the current region is, and neither sets
  nor checks it. Document that, or set the region from `env`.
- [ ] `expr()` in `build_pc_rasters` uses `for l in [(l1, l2)]` purely to bind
  a name; `(l1, l2)[load_idx]` is the same thing, readable.
- [ ] `examples/niche_workflow.R` exports `pca$c1[, 1:2]`, which is only
  correct for `humboldt.g2e`'s default `pcx=1, pcy=2`. Derive the columns
  from `pcx`/`pcy`, or state the assumption in the script.

`r.niche.espace`:

- [ ] `thin_method=nn` approximates `humboldt.occ.rarefy` rather than matching
  it: map units instead of azimuthal-equidistant metres, and first-by-category
  instead of humboldt's 2nd-6th nearest-neighbour tie-break. Decide whether to
  reproduce humboldt exactly. It is also O(n^3), since the all-pairs scan runs
  once per removal.
- [ ] Check what `gs.MaskManager()` does to a mask the user has already set.
  With `trim_method=none` nothing calls `r.mask` inside the context, so their
  mask is likely ignored rather than honoured.
- [ ] The background table's resolution follows whatever region is set, and it
  has to match humboldt's `env.reso`. Document that, or set the region from
  `env`.
- [ ] `write_occ_table` samples env values onto the occurrences, but
  `niche_workflow.R` reads only x/y from that table and `humboldt.g2e`
  re-samples the values itself. Either use them or drop that stage.

Both modules:

- [ ] No testsuite.
