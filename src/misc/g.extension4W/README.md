## DESCRIPTION

*g.extension.local* installs a GRASS GIS addon from a local `.zip` file into the current user's addon directory. It is a local-install counterpart to *g.extension*, which normally fetches addons from the official GRASS addons repository or a remote URL. 

The module is aimed at developers and advanced users who want to distribute or test addons privately, for example during development, within an organisation, or in environments without internet access.

### INPUT

The **input** parameter must point to a zip archive with the layout:

```
bin/<module>.bat
scripts/<module>.py
docs/html/<module>.html
docs/man/man1/        (optional)
etc/                  (optional)
```

The module name is derived from the single `.py` file under `scripts/`; the matching `.bat` and `.html` filenames must use the same stem.

A companion packaging script, *build_addon_zip.py*, produces zip files in exactly this layout from a source folder containing the addon's `.py` and `.html` files.

On install, each file in the zip is copied directly into the shared `bin/`, `scripts/`, and `docs/` subdirectories of the addon base directory, alongside any other installed addons.

### ADDON DIRECTORY RESOLUTION

Unless overridden via **addon_base**, the destination is resolved in the following order:

1. `GRASS_ADDON_BASE` environment variable (set by GRASS at startup)
2. `GRASS_ADDON_PATH` environment variable (first entry if a list)
3. The Windows default `%APPDATA%\GRASS<N>\addons`, where `<N>` is derived from:

   * `GRASS_VERSION`
   * `<GISBASE>/etc/VERSIONNUMBER`
   * or the GISBASE folder name

## NOTES

* The module refuses to overwrite existing files unless the **-f** flag is given. This protects neighbouring addons from being silently overwritten when multiple addons share a file name.
* The **-n** flag performs a dry run: the installation plan is printed but nothing is written to disk.
* Zip entries containing `..`, absolute paths, or Windows drive letters are rejected to prevent zip-slip attacks.
* The module does not compile C/C++ source code; it only installs the files contained in the zip. For addons written in Python or as shell scripts this is sufficient.

## EXAMPLES

Install an addon from a local zip using the addon directory of the current GRASS session:

```
g.extension.local input=C:\Users\me\Downloads\r.maxent.setup.zip
```

Preview the installation without writing anything:

```
g.extension.local input=r.maxent.setup.zip -n
```

Reinstall (overwrite existing files):

```
g.extension.local input=r.maxent.setup.zip -f
```

Install into a custom directory:

```
g.extension.local input=r.maxent.setup.zip addon_base="C:\grass_addons"
```


## SEE ALSO

* g.extension
* g.extension.all


## AUTHOR

[Paulo van Breugel](https://ecodiv.earth), [HAS green academy](https://has.nl), [Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/), [Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)