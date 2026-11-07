## DESCRIPTION

*g.extension4W* installs a GRASS GIS addon from a local *.zip* file or
source folder into the current user's addon directory on Windows. It is a
local-install counterpart to *[g.extension](g.extension.html)*, which
normally fetches addons from the official GRASS addons repository or a
remote URL.

The module is aimed at developers and advanced users who want to distribute
or test addons privately, for example during development, within an
organisation, or in environments without internet access.

## INPUT

Provide either **zip_file** or **input_folder**, not both.

When using **zip_file**, the archive must follow this layout:

```
bin/<module>.bat
scripts/<module>.py
docs/html/<module>.html
docs/man/man1/        (optional)
etc/                  (optional)
```

The module name is derived from the single *.py* file under *scripts/*;
the matching *.bat* and *.html* filenames must use the same stem. All
files present in the zip are installed as-is.

When using **input_folder**, the folder must contain exactly one *.py*
script and one *.md* manual page with matching stems (e.g.
*r.maxent.setup.py* and *r.maxent.setup.md*). The *.bat* launcher and the
*.html* manual page are generated automatically at install time. The manual
page is generated from the Markdown file combined with the parameter
descriptions extracted from the script. Any image or other asset files
referenced in the Markdown are detected and copied to *docs/html/*
alongside the manual page.

## ADDON DIRECTORY RESOLUTION

Unless overridden via **addon_base**, the destination directory is resolved
in the following order:

1. *GRASS_ADDON_BASE* environment variable (set automatically by GRASS at
   startup).
2. *GRASS_ADDON_PATH* environment variable (first entry if a list).
3. The Windows default *%APPDATA%\\GRASS\<N\>\\addons*, where *\<N\>* is
   derived from *GRASS_VERSION*, *\<GISBASE\>/etc/VERSIONNUMBER*, or the
   GISBASE folder name.

## XML REGISTRATION

When the **-r** flag is set, the module registers the installed addon in
the two XML metadata files that GRASS uses to populate the module tree:

- *extensions.xml* — records the list of files belonging to the addon.
- *modules.xml* — records the description and keywords used in the module
  search index.

The **description** and **keywords** parameters supply the text written to
*modules.xml*. When installing from a folder, these can be left empty and
the values are read from the script's `# %Module` block instead. The
**libgis_revision** parameter controls the `libgis` attribute written to
both files (default: *8.4.1*).

Both XML files must already exist in **addon_base** before the **-r** flag
can be used. They are created automatically the first time any addon is
installed via *g.extension*, so install at least one addon through the
normal route first.

## NOTES

- The module refuses to overwrite existing files unless the **-f** flag is
  given. This protects neighbouring addons from being silently overwritten
  when multiple addons share the same addon base directory.
- The **-n** flag performs a dry run: the installation plan is printed but
  nothing is written to disk.
- Zip entries containing *..*,  absolute paths, or Windows drive letters
  are rejected to prevent zip-slip attacks.
- Module names are validated against the GRASS naming convention
  (*prefix.word[.word…]*) before anything is written.
- The module does not compile C/C++ source code; it only installs the files
  present in the zip or source folder. For addons written in Python this is
  sufficient.

## EXAMPLES

Install an addon from a local zip file:

```
g.extension4W zip_file=C:\Users\me\Downloads\r.maxent.setup.zip
```

Install directly from a source folder (generates the .bat and .html automatically):

```
g.extension4W input_folder=C:\dev\r.maxent.setup
```

Dry run to preview what would be installed:

```
g.extension4W zip_file=r.maxent.setup.zip -n
```

Reinstall, overwriting existing files:

```
g.extension4W zip_file=r.maxent.setup.zip -f
```

Install into a custom directory:

```
g.extension4W zip_file=r.maxent.setup.zip addon_base="C:\grass_addons"
```

Install from a folder and register in the XML metadata files:

```
g.extension4W input_folder=C:\dev\r.maxent.setup description="Install Maxent" keywords="modeling,Maxent" -r
```

## SEE ALSO

*[g.extension](g.extension.html)*,
*[g.extension.all](g.extension.all.html)*

## AUTHORS

[Paulo van Breugel](https://ecodiv.earth),
[HAS green academy](https://has.nl),
[Innovative Biomonitoring research group](https://www.has.nl/en/research/professorships/innovative-bio-monitoring-professorship/),
[Climate-robust Landscapes research group](https://www.has.nl/en/research/professorships/climate-robust-landscapes-professorship/)
