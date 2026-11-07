#!/usr/bin/env Rscript
###############################################################################
# End-to-end niche workflow:
#
#     r.niche.espace  (GRASS prep)  -->  humboldt (R analysis)  -->  r.niche.map
#
# rgrass is the glue: execGRASS() runs the two GRASS addons, humboldt runs in
# between. Start R FROM the GRASS command line (grass ... --exec R, or `R`
# inside a GRASS session) so the GISRC/region are already set -- no
# initGRASS(), no environment fiddling needed here.
#
# Requires: rgrass, humboldt (and its deps). GRASS 8.5+ with r.niche.espace
# and r.niche.map installed (g.extension).
###############################################################################

library(rgrass)
library(humboldt)

## Names of your GRASS maps (adjust to your mapset) --------------------------
env_rasters <- c("bio1", "bio2", "bio12", "bio15")      # env stack in GRASS
occ_1_vec   <- "occ_native"                              # occurrence points
occ_2_vec   <- "occ_invasive"
env_res_dd  <- 0.0083                                    # env resolution (deg)
correct.env <- TRUE   # correct densities for environmental prevalence; used
                      # for both the statistics and the exported niche grids

## ===========================================================================
## STEP 1 - GRASS: prepare humboldt-format tables (thin, trim, sample)
##          Runs over the full rasters in GRASS; writes small CSVs.
## ===========================================================================
execGRASS("r.niche.espace",
          env         = paste(env_rasters, collapse = ","),
          occ_1       = occ_1_vec,
          occ_2       = occ_2_vec,
          thin_distance = 50, thin_units = "km", thin_method = "grid",
          trim_method = "mcp", trim_buffer = 200,
          table_1     = "sp1.csv",  table_2    = "sp2.csv",
          bg_table_1  = "env1.csv", bg_table_2 = "env2.csv",
          flags = "overwrite")

## ===========================================================================
## STEP 2 - R / humboldt: the analysis (PCA, kernel density, statistics)
##          Thinning + trimming already done in GRASS -> switch them OFF.
## ===========================================================================
env1 <- read.csv("env1.csv", header = FALSE)             # x, y, var1..varN
env2 <- read.csv("env2.csv", header = FALSE)
colnames(env1) <- colnames(env2) <- c("x", "y", env_rasters)

o1 <- read.csv("sp1.csv", header = FALSE)                # x, y, cat, var...
o2 <- read.csv("sp2.csv", header = FALSE)
sp1 <- data.frame(sp = "native",   x = o1[[1]], y = o1[[2]])
sp2 <- data.frame(sp = "invasive", x = o2[[1]], y = o2[[2]])

env1 <- humboldt.scrub.env(env1)
env2 <- humboldt.scrub.env(env2)
num.var.e <- ncol(env1)

zz <- humboldt.g2e(env1 = env1, env2 = env2, sp1 = sp1, sp2 = sp2,
                   reduce.env = 0, reductype = "PCA",
                   non.analogous.environments = "YES",
                   env.trim   = FALSE,      # <- trimming done by r.niche.espace
                   rarefy.dist = 0,         # <- thinning done by r.niche.espace
                   e.var = c(3:num.var.e), col.env = c(3:num.var.e),
                   env.reso = env_res_dd, kern.smooth = 1, R = 100,
                   run.silent = FALSE)

scores.env12 <- rbind(zz$scores.env1[1:2], zz$scores.env2[1:2])
z.sp1 <- humboldt.grid.espace(scores.env12, zz$scores.env1[1:2],
                              zz$scores.sp1[1:2], kern.smooth = 1, R = 100)
z.sp2 <- humboldt.grid.espace(scores.env12, zz$scores.env2[1:2],
                              zz$scores.sp2[1:2], kern.smooth = 1, R = 100)

## (the usual humboldt statistics still live here)
sim <- humboldt.niche.similarity(z.sp1, z.sp2, correct.env = correct.env)
cat(sprintf("Schoener D = %.3f   Hellinger I = %.3f\n", sim$D, sim$I))

## ===========================================================================
## STEP 3a - export what r.niche.map needs: humboldt's PCA rotation + niche grids
## ===========================================================================
pca <- zz$pca.cal                                        # ade4 dudi.pca object
rotation <- data.frame(
  variable = env_rasters,
  center   = pca$cent,          # column means used by humboldt
  norm     = pca$norm,          # column scalings used by humboldt
  pc1      = pca$c1[, 1],       # loadings (normed column scores)
  pc2      = pca$c1[, 2]
)
write.csv(rotation, "rotation.csv", row.names = FALSE)

## write each E-space niche grid to GRASS as a raster in a PC-space region.
## Use explicit PC coordinates (orientation-proof) via an XYZ import.
write_niche_grid <- function(z, gmap, correct.env) {
  R  <- length(z$x)
  ## humboldt.niche.similarity reads z.cor when correct.env=TRUE and z.uncor
  ## otherwise, so export the grid the reported D/I was measured on. It also
  ## applies thresh.espace.z and the nae mask on top of that grid; what is
  ## written here is the unthresholded version.
  dens <- if (correct.env) z$z.cor else z$z.uncor
  ## z$x / z$y are the PC axes.
  ## humboldt stores both grids as matrix(<terra raster>, nrow=R); terra reads
  ## north-first, so the matrix columns run PC2 DESCENDING while z$y ascends.
  ## Pair the values with rev(z$y) so PC2 is not flipped (verified against
  ## humboldt.grid.espace on a cloud with a known peak location).
  g  <- expand.grid(x = z$x, y = rev(z$y))               # x varies fastest
  g$z <- as.vector(dens)
  xyz <- tempfile(fileext = ".csv")
  write.table(g, xyz, row.names = FALSE, col.names = FALSE, sep = ",")
  bx <- diff(range(z$x)) / (R - 1)
  by <- diff(range(z$y)) / (R - 1)
  ## region = PC extent padded half a cell so the R x R centres line up
  execGRASS("g.region",
            n = max(z$y) + by/2, s = min(z$y) - by/2,
            e = max(z$x) + bx/2, w = min(z$x) - bx/2,
            rows = R, cols = R)
  execGRASS("r.in.xyz", input = xyz, output = gmap, method = "mean",
            separator = "comma", x = 1, y = 2, z = 3, flags = "overwrite")
}
write_niche_grid(z.sp1, "niche_sp1", correct.env)
write_niche_grid(z.sp2, "niche_sp2", correct.env)

## ===========================================================================
## STEP 3b - GRASS: back-project to geographic overlap / divergence maps
##           Restore the geographic region first (r.in.xyz changed it).
## ===========================================================================
execGRASS("g.region", raster = env_rasters[1])
execGRASS("r.niche.map",
          env        = paste(env_rasters, collapse = ","),
          rotation   = "rotation.csv",
          niche_1    = "niche_sp1", niche_2 = "niche_sp2",
          suit_1     = "suit_native", suit_2 = "suit_invasive",
          overlap    = "niche_overlap",
          divergence = "niche_divergence",
          flags = "overwrite")

cat("Created GRASS rasters: suit_native, suit_invasive, niche_overlap, ",
    "niche_divergence\n", sep = "")
