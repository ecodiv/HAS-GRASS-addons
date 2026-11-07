#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# validate_kde.R  --  KDE-parity check for r.niche.espace
#
# Isolates the ONE analysis-stage difference that only matters in the
# all-GRASS lane: humboldt's adehabitatHR::kernelUD (bivariate-normal KDE)
# vs. the addon's "bin into RxR + smooth" grid.
#
# It feeds the SAME score clouds to both methods, so any difference is purely
# the smoothing algorithm/bandwidth -- not thinning, trimming or PCA (those
# are checked separately; see NOTES in r.niche.espace.md).
#
# Finding (synthetic data, R=100):
#   With a GAUSSIAN filter of sigma = 0.03 * R * kern.smooth  (== humboldt's
#   Kern.SmZ, humboldt88.R:96), the reported statistics agree to
#   dD ~ 0.005-0.04 and dI ~ 0.03-0.05. A boxcar filter, or a mismatched
#   bandwidth, diverges badly (dD up to ~0.5) -- that was a calibration bug,
#   not a fundamental one.
#
# Requires: sp, adehabitatHR, adehabitatMA, terra, and the humboldt source
#           file (for the reference humboldt.grid.espace).
#
# Usage:  Rscript validate_kde.R /path/to/humboldt88.R
# ---------------------------------------------------------------------------

suppressMessages({
  library(sp); library(adehabitatHR); library(adehabitatMA); library(terra)
})

args <- commandArgs(trailingOnly = TRUE)
hum_src <- if (length(args) >= 1) args[1] else "R/humboldt88.R"

## --- load ONLY the reference humboldt.grid.espace from the package source ---
src <- readLines(hum_src, warn = FALSE)
a <- grep("^humboldt.grid.espace <- function", src)
b <- grep("^humboldt.pnt.index <- function", src)[1]
eval(parse(text = paste(src[a:(b - 1)], collapse = "\n")))

## --- faithful reproduction of the GRASS grid: bin RxR, then gaussian smooth --
bin_grid <- function(glob_g, sp, R) {
  xmin <- min(glob_g[, 1]); xmax <- max(glob_g[, 1])
  ymin <- min(glob_g[, 2]); ymax <- max(glob_g[, 2])
  bx <- (xmax - xmin) / R;  by <- (ymax - ymin) / R
  col <- pmin(R - 1, pmax(0, floor((sp[, 1] - xmin) / bx)))
  row <- pmin(R - 1, pmax(0, floor((sp[, 2] - ymin) / by)))
  g <- matrix(0, R, R)
  for (i in seq_along(col)) g[row[i] + 1, col[i] + 1] <- g[row[i] + 1, col[i] + 1] + 1
  g
}
gauss_smooth <- function(g, sigma) {         # separable gaussian, zero padding
  R <- nrow(g); rad <- ceiling(3 * sigma); k <- seq(-rad, rad)
  w <- exp(-(k^2) / (2 * sigma^2)); w <- w / sum(w)
  conv1 <- function(m) {
    out <- matrix(0, nrow(m), ncol(m))
    for (j in seq_along(k)) {
      s <- k[j]; r0 <- max(1, 1 - s):min(R, R - s)
      out[r0, ] <- out[r0, ] + w[j] * m[r0 + s, ]
    }
    out
  }
  sm <- conv1(g); sm <- t(conv1(t(sm))); sm
}

## --- r.niche.similarity math (D & I) between two grids ----------------------
DI <- function(p1, p2) {
  p1 <- p1 / sum(p1); p2 <- p2 / sum(p2)
  c(D = 1 - 0.5 * sum(abs(p1 - p2)),
    I = 1 - 0.5 * sum((sqrt(p1) - sqrt(p2))^2))
}

## --- test data: two clustered species in a shared background ----------------
set.seed(1)
glob_g <- data.frame(cbind(rnorm(4000), rnorm(4000)))
sp1 <- data.frame(cbind(rnorm(300, -0.6, 0.5), rnorm(300,  0.3, 0.5)))
sp2 <- data.frame(cbind(rnorm(300,  0.5, 0.5), rnorm(300, -0.2, 0.5)))
R <- 100

cat(sprintf("%-12s %-8s %-18s %-18s %-14s %s\n",
            "kern.smooth", "sigma", "humboldt D/I", "GRASS D/I", "dD/dI", "grid-cor"))
for (kern in c(0.5, 1, 2)) {
  zK1 <- humboldt.grid.espace(glob_g, glob_g, sp1, R = R, kern.smooth = kern)
  zK2 <- humboldt.grid.espace(glob_g, glob_g, sp2, R = R, kern.smooth = kern)
  mK1 <- zK1$z.uncor; mK2 <- zK2$z.uncor       # occurrence density grids

  sigma <- 0.03 * R * kern                      # == humboldt Kern.SmZ * R
  mG1 <- gauss_smooth(bin_grid(glob_g, sp1, R), sigma)
  mG2 <- gauss_smooth(bin_grid(glob_g, sp2, R), sigma)

  dK <- DI(mK1, mK2); dG <- DI(mG1, mG2)
  cat(sprintf("%-12.1f %-8.1f %6.3f / %-9.3f %6.3f / %-9.3f %5.3f / %-6.3f %.3f\n",
              kern, sigma, dK["D"], dK["I"], dG["D"], dG["I"],
              abs(dK["D"] - dG["D"]), abs(dK["I"] - dG["I"]),
              cor(as.vector(mK1), as.vector(mG1))))
}

## --- OPTIONAL: compare against the ACTUAL GRASS output -----------------------
## On a GRASS 8.5+ box, export the addon's grid and diff cell-by-cell:
##   r.out.xyz input=z_sp1 output=z_sp1.xyz separator=comma
## then load z_sp1.xyz here as a matrix and DI() it against mK1 above.
