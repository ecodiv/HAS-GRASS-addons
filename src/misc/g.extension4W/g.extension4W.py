#!/usr/bin/env python

############################################################################
#
# MODULE:       g.extension4W
# AUTHOR(S):    Paulo van Breugel
# PURPOSE:      Install a GRASS GIS addon from a local .zip file into the
#               current user's addon directory (Windows). Optionally
#               registers the addon in extensions.xml and modules.xml so
#               it appears in the GRASS module tree.
#
#               The zip file must follow the layout produced by
#               build_addon_zip.py:
#                   bin/<module>.bat
#                   scripts/<module>.py
#                   docs/html/<module>.html
#                   docs/html/<asset>...        (optional images / CSS)
#                   docs/man/man1/<module>.1    (optional)
#                   etc/<modulename>/<dirname>/ (optional shared library)
#
# COPYRIGHT:    (C) 2026 Paulo van Breugel and the GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
#############################################################################

# %Module
# % description: Install a GRASS addon from a local zip file into the addon directory (Windows).
# % keyword: general
# % keyword: installation
# % keyword: extension
# % keyword: addons
# %end

# %option G_OPT_F_BIN_INPUT
# % key: zip_file
# % label: Path to addon zip file
# % description: Zip file produced by build_addon_zip.py, containing bin/, scripts/, and docs/html/ at the root.
# % required: yes
# % guisection: Input
# %end

# %option G_OPT_M_DIR
# % key: addon_base
# % label: Override addon base directory
# % description: Destination for installation. If empty, resolved from GRASS_ADDON_BASE, then GRASS_ADDON_PATH, then %APPDATA%\GRASS<N>\addons.
# % required: no
# %end

# %option
# % key: description
# % type: string
# % label: Short module description (for modules.xml registration)
# % description: One-line description written to modules.xml. Only used when -r flag is set. If omitted, a placeholder is used.
# % required: no
# % guisection: Input
# %end

# %option
# % key: keywords
# % type: string
# % label: Comma-separated keywords (for modules.xml registration)
# % description: Keywords written to modules.xml. Only used when -r flag is set. Example: 'vector,export,Maxent'
# % required: no
# % guisection: Input
# %end

# %option
# % key: libgis_revision
# % type: string
# % label: libgis revision tag (for XML registration)
# % description: Value written as the libgis revision attribute in both XML files. Defaults to the running GRASS version (e.g. '8.4.1').
# % answer: 8.5
# % required: no
# %end

# %flag
# % key: f
# % label: Force overwrite
# % description: Overwrite existing addon files. Without this flag the module stops if any destination file already exists.
# %end

# %flag
# % key: n
# % label: Dry run
# % description: Show what would be installed/registered without writing anything.
# %end

# %flag
# % key: r
# % label: Register in XML files
# % description: Add the addon to extensions.xml and modules.xml after installation.
# % guisection: Input
# %end

import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import grass.script as gs


# ---------------------------------------------------------------------------
# Style files (shared documentation assets from the GRASS install)
# ---------------------------------------------------------------------------

_STYLE_FILES = (
    "grassdocs.css",
    "grass_logo.png",
    "hamburger_menu.svg",
    "hamburger_menu_close.svg",
)


def copy_style_files(addon_html_dir, gisbase=None):
    """Copy GRASS documentation style files into *addon_html_dir*.

    Adapted from g.extension.check_style_file(). Non-fatal if files
    are missing (issues a warning instead).
    """
    gisbase = gisbase or os.environ.get("GISBASE", "")
    if not gisbase:
        gs.warning(_("GISBASE is not set; cannot copy style files to addon docs/html."))
        return
    src_html = Path(gisbase) / "docs" / "html"
    for name in _STYLE_FILES:
        src  = src_html / name
        dest = addon_html_dir / name
        try:
            shutil.copyfile(str(src), str(dest))
        except shutil.SameFileError:
            pass
        except OSError as exc:
            gs.warning(_(
                "Unable to copy '{}' to addon docs/html: {}. "
                "Is the GRASS documentation package installed? "
                "Installation continues, but documentation may not look right."
            ).format(name, exc))


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

# Valid GRASS module names: letter-or-digit segments separated by dots,
# first character of each segment must be a letter.  Examples: r.maxent.setup,
# r3.mapcalc, g.extension4W, t.rast.aggregate.
_GRASS_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+$')
_MAX_NAME_LEN  = 128   # no legitimate GRASS module name approaches this
_MAX_STR_LEN   = 1024  # for description / keywords / libgis_revision


def _validate_module_name(name):
    """Fatal-exit if *name* is not a valid GRASS module name.

    Rejects null bytes, shell-special characters, XML-special characters,
    path separators, and names that do not follow the 'prefix.word[.word…]'
    convention.  ElementTree would escape XML specials anyway, but we reject
    them early to keep the XML files clean and to catch obviously bad input.
    """
    if not name:
        gs.fatal(_("Module name is empty."))
    if '\x00' in name:
        gs.fatal(_("Module name contains a null byte: {}").format(repr(name)))
    if len(name) > _MAX_NAME_LEN:
        gs.fatal(_(
            "Module name is unreasonably long ({} chars, max {}): {}"
        ).format(len(name), _MAX_NAME_LEN, name))
    if not _GRASS_NAME_RE.match(name):
        gs.fatal(_(
            "Invalid module name '{}'. "
            "Expected format: 'prefix.word' or 'prefix.word.word' "
            "(letters and digits only, first character of each segment must be a letter). "
            "Examples: r.maxent.setup, g.extension4W, t.rast.aggregate."
        ).format(name))


def _sanitise_text(value, field_name, allow_empty=True):
    """Return *value* stripped of leading/trailing whitespace.

    Fatal-exits on null bytes or excessively long strings.  The actual XML
    escaping of <, >, &, quotes is handled by ElementTree automatically.
    """
    if value is None:
        value = ""
    value = value.strip()
    if '\x00' in value:
        gs.fatal(_("{} contains a null byte.").format(field_name))
    if len(value) > _MAX_STR_LEN:
        gs.fatal(_(
            "{} is unreasonably long ({} chars, max {})."
        ).format(field_name, len(value), _MAX_STR_LEN))
    if not allow_empty and not value:
        gs.fatal(_("{} must not be empty.").format(field_name))
    return value


def _validate_libgis_revision(value):
    """Reject anything that is not a simple version string like '8.4.1'."""
    value = _sanitise_text(value, "libgis_revision")
    if value and not re.match(r'^\d+(\.\d+)*$', value):
        gs.fatal(_(
            "libgis_revision must be a dot-separated version number "
            "(e.g. '8.4.1'), got: {}"
        ).format(value))
    return value or "8.4.1"


# ---------------------------------------------------------------------------
# Resolving the addon base directory
# ---------------------------------------------------------------------------

def _grass_version_major(gisbase):
    """Return GRASS major version as a string ('8', '7', ...) from GISBASE."""
    ver = os.environ.get("GRASS_VERSION", "").strip()
    if ver:
        m = re.match(r"(\d+)", ver)
        if m:
            return m.group(1)

    vnum = Path(gisbase) / "etc" / "VERSIONNUMBER"
    if vnum.is_file():
        try:
            first = vnum.read_text(encoding="utf-8", errors="replace").strip().split()[0]
            m = re.match(r"(\d+)", first)
            if m:
                return m.group(1)
        except OSError:
            pass

    m = re.search(r"(\d+)", Path(gisbase).name)
    if m:
        return m.group(1)

    return None


def resolve_addon_base(explicit):
    """Return the addon installation directory as a Path.

    Priority: explicit override -> GRASS_ADDON_BASE -> GRASS_ADDON_PATH ->
    Windows default %APPDATA%\\GRASS<N>\\addons.
    """
    if explicit:
        return Path(explicit).expanduser().resolve()

    env_base = os.environ.get("GRASS_ADDON_BASE", "").strip()
    if env_base:
        return Path(env_base).expanduser().resolve()

    env_path = os.environ.get("GRASS_ADDON_PATH", "").strip()
    if env_path:
        first = env_path.split(os.pathsep)[0].strip()
        if first:
            return Path(first).expanduser().resolve()

    gisbase = os.environ.get("GISBASE", "").strip()
    if not gisbase:
        gs.fatal(_(
            "Cannot determine the GRASS addon directory: none of "
            "GRASS_ADDON_BASE, GRASS_ADDON_PATH, or GISBASE are set. "
            "Run this module from a GRASS session, or pass addon_base=."
        ))

    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        gs.fatal(_(
            "APPDATA is not set; cannot compute the default Windows addon "
            "path. Pass addon_base= explicitly."
        ))

    major = _grass_version_major(gisbase) or ""
    folder = "GRASS{0}".format(major) if major else "GRASS"
    return (Path(appdata) / folder / "addons").resolve()


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _is_within(parent, child):
    """True if *child* is the same as or inside *parent*."""
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


# ---------------------------------------------------------------------------
# Install from a pre-built zip file
# ---------------------------------------------------------------------------

def install_from_zip(zip_path: Path, addon_base: Path,
                     force: bool = False, dry_run: bool = False) -> dict:
    """Install addon files from *zip_path* into *addon_base*.

    The zip must follow the layout produced by build_addon_zip.py:
      bin/<module>.bat
      scripts/<module>.py
      docs/html/<module>.html
      docs/html/<asset>...      (optional images / CSS)
      docs/man/man1/<module>.1  (optional)

    Steps:
    1. Open and validate the zip (non-traversal paths, expected entries).
    2. Derive the module name from the single scripts/*.py entry.
    3. Extract files into *addon_base*, respecting -f (force) and -n (dry-run).
    4. Copy GRASS style files into docs/html/ if not already present.

    Returns the standard report dict consumed by _report_install().
    """
    if not zip_path.is_file():
        gs.fatal(_("Zip file not found: {}").format(zip_path))

    addon_base = addon_base.resolve()

    with zipfile.ZipFile(str(zip_path), "r") as zf:
        names = zf.namelist()

        # --- security: reject any path-traversal entries ---
        for name in names:
            if ".." in Path(name).parts or name.startswith("/") or name.startswith("\\"):
                gs.fatal(_(
                    "Zip entry '{}' contains a path-traversal component. "
                    "Refusing to extract."
                ).format(name))

        # --- derive module name from the single scripts/*.py entry ---
        script_entries = [
            n for n in names
            if n.startswith("scripts/") and n.endswith(".py")
            and n.count("/") == 1 and len(Path(n).stem) > 0
        ]
        if not script_entries:
            gs.fatal(_(
                "No 'scripts/<module>.py' entry found in {}. "
                "Is this a valid addon zip?"
            ).format(zip_path.name))
        if len(script_entries) > 1:
            gs.fatal(_(
                "Expected exactly one 'scripts/*.py' entry in {}, found {}: {}"
            ).format(zip_path.name, len(script_entries),
                     ", ".join(script_entries)))

        module = Path(script_entries[0]).stem
        _validate_module_name(module)

        # --- collect entries to install (skip directory entries) ---
        entries_to_extract = [n for n in names if not n.endswith("/")]

        # --- check for conflicts before writing anything ---
        conflicts = []
        for rel in entries_to_extract:
            dest = (addon_base / rel).resolve()
            if not _is_within(addon_base, dest):
                gs.fatal(
                    _("Refusing to write outside addon base: {}").format(dest)
                )
            if dest.exists():
                conflicts.append(dest)

        if conflicts and not force:
            gs.fatal(_(
                "{} destination file(s) already exist (e.g. {}).\n"
                "Use the -f flag to overwrite."
            ).format(len(conflicts), conflicts[0]))

        # --- extract ---
        copied      = []
        overwritten = [str(p) for p in conflicts]

        for rel in entries_to_extract:
            dest = (addon_base / rel).resolve()
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(rel) as src_fh, open(str(dest), "wb") as dst_fh:
                    shutil.copyfileobj(src_fh, dst_fh)
            copied.append((rel, str(dest)))

    # --- copy GRASS style files (non-fatal if missing) ---
    html_dest_dir = addon_base / "docs" / "html"
    if not dry_run:
        copy_style_files(html_dest_dir)

    return {"module": module, "addon_base": str(addon_base),
            "copied": copied, "overwritten": overwritten}


# ---------------------------------------------------------------------------
# XML registration
# ---------------------------------------------------------------------------

def _indent_xml(elem, level=0):
    """Add pretty-print indentation in-place (4-space, matches existing files)."""
    indent       = "\n" + "    " * level
    child_indent = "\n" + "    " * (level + 1)
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = child_indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    if not elem.tail or not elem.tail.strip():
        elem.tail = indent
    if level == 0:
        elem.tail = "\n"


def _write_xml(tree, xml_path, dry_run=False):
    """Serialise *tree* back to *xml_path*, preserving the original header lines.

    The original <?xml ...?> and <!DOCTYPE ...> lines are read from the file
    and written back verbatim so ElementTree's omission of those declarations
    does not alter the file header.  CRLF line endings are used throughout to
    match the existing files.
    """
    original_header = []
    with open(str(xml_path), "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith("<?xml") or stripped.startswith("<!DOCTYPE"):
                original_header.append(line.rstrip("\r\n"))
            else:
                break

    _indent_xml(tree.getroot())
    xml_body = ET.tostring(tree.getroot(), encoding="unicode")
    output = "\r\n".join(original_header) + "\r\n" + xml_body + "\r\n"

    if not dry_run:
        with open(str(xml_path), "w", encoding="utf-8", newline="") as fh:
            fh.write(output)


def _remove_existing_task(root, module, xml_path, force):
    """Remove an existing <task name='module'> element, or fatal if not forced."""
    existing = root.find("task[@name='{}']".format(module))
    if existing is not None:
        if not force:
            gs.fatal(_(
                "'{}' already has an entry in {}.\n"
                "Use the -f flag to overwrite."
            ).format(module, xml_path))
        gs.warning(_("Replacing existing entry for '{}' in {}.").format(module, xml_path))
        root.remove(existing)


def register_extensions_xml(xml_path, module, addon_base, libgis_rev,
                             extra_basenames=None,
                             force=False, dry_run=False):
    """Add (or replace with -f) a <task> block in extensions.xml.

    The standard file list covers bin/, docs/html/<module>.html,
    docs/man/man1/<module>.1, and scripts/.  Any additional asset files
    (images etc.) passed in *extra_basenames* are added as extra
    docs/html/<basename> entries, matching what g.extension itself records.
    """
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    _remove_existing_task(root, module, xml_path, force)

    base = str(addon_base)
    file_paths = [
        "{}\\bin\\{}.bat".format(base, module),
        "{}\\docs\\html\\{}.html".format(base, module),
    ]
    for basename in (extra_basenames or []):
        file_paths.append("{}\\docs\\html\\{}".format(base, basename))
    file_paths += [
        "{}\\docs\\man\\man1\\{}.1".format(base, module),
        "{}\\scripts\\{}.py".format(base, module),
    ]

    task_elem = ET.SubElement(root, "task", name=module)
    binary_elem = ET.SubElement(task_elem, "binary")
    for fp in file_paths:
        ET.SubElement(binary_elem, "file").text = fp
    ET.SubElement(ET.SubElement(task_elem, "modules"), "module").text = module
    ET.SubElement(task_elem, "libgis", revision=libgis_rev)

    if dry_run:
        gs.message(_("  [dry run] Would add '{}' to {}").format(module, xml_path))
    else:
        _write_xml(tree, xml_path)
        gs.message(_("  Registered '{}' in {}").format(module, xml_path))


def register_modules_xml(xml_path, module, description, keywords, libgis_rev,
                         force=False, dry_run=False):
    """Add (or replace with -f) a <task> block in modules.xml.

    *description* and *keywords* are user-supplied strings that have been
    pre-sanitised by _sanitise_text().  ElementTree additionally escapes any
    remaining XML-special characters before writing.
    """
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    _remove_existing_task(root, module, xml_path, force)

    task_elem = ET.SubElement(root, "task", name=module)
    ET.SubElement(task_elem, "description").text = description or "(no description provided)"
    ET.SubElement(task_elem, "keywords").text    = keywords or "general"
    ET.SubElement(task_elem, "libgis", revision=libgis_rev)

    if dry_run:
        gs.message(_("  [dry run] Would add '{}' to {}").format(module, xml_path))
    else:
        _write_xml(tree, xml_path)
        gs.message(_("  Registered '{}' in {}").format(module, xml_path))


# ---------------------------------------------------------------------------
# Shared post-install reporting
# ---------------------------------------------------------------------------

def _report_install(report, dry_run):
    verb = "Would install" if dry_run else "Installed"
    gs.message(_("{} addon '{}' into: {}").format(
        verb, report["module"], report["addon_base"]
    ))
    for src, dest in report["copied"]:
        gs.verbose(_("  {}  ->  {}").format(src, dest))
    if report["overwritten"]:
        gs.message(_("Overwrote {} existing file(s).").format(len(report["overwritten"])))
    if not dry_run:
        bin_dir = Path(report["addon_base"]) / "bin"
        gs.message(_(
            "Next: ensure this folder is on your PATH: {}\n"
            "(GRASS adds it automatically when GRASS_ADDON_BASE is set.)\n"
            "Test it with:  {} --help"
        ).format(bin_dir, report["module"]))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(options, flags):
    zip_file = (options.get("zip_file") or "").strip()
    force    = bool(flags["f"])
    dry_run  = bool(flags["n"])
    register = bool(flags["r"])

    # The %option block declares zip_file as required, so GRASS will
    # refuse the call before we get here if it's missing — but defend in
    # depth in case g.extension4W is invoked from a context that doesn't
    # honor the parser declarations.
    if not zip_file:
        gs.fatal(_("zip_file is required."))

    addon_base = resolve_addon_base(options.get("addon_base") or None)

    # ---- install -----------------------------------------------------------
    if dry_run:
        gs.message(_("Dry run -- nothing will be written."))

    input_path = Path(os.path.normpath(zip_file)).resolve()
    report = install_from_zip(input_path, addon_base, force=force, dry_run=dry_run)

    _report_install(report, dry_run)
    module = report["module"]

    # ---- optional XML registration -----------------------------------------
    if not register:
        return

    extensions_xml = addon_base / "extensions.xml"
    modules_xml    = addon_base / "modules.xml"

    missing_xml = [p for p in (extensions_xml, modules_xml) if not p.is_file()]
    if missing_xml:
        gs.warning(_(
            "The following XML file(s) were not found and will be skipped:\n  {}\n"
            "Make sure at least one other addon has been installed via g.extension "
            "so that these files exist, or pass addon_base= to point to the right directory."
        ).format("\n  ".join(str(p) for p in missing_xml)))

    # Validate and sanitise all user-supplied strings before touching any file
    libgis_rev  = _validate_libgis_revision(options.get("libgis_revision") or "")
    description = _sanitise_text(options.get("description") or "", "description")
    keywords    = _sanitise_text(options.get("keywords")    or "", "keywords")

    gs.message(_("Updating XML registration files..."))

    # Collect asset basenames that were installed alongside the HTML page so
    # they can be listed in extensions.xml just as g.extension would record them.
    extra_basenames = [
        Path(dest).name
        for rel, dest in report["copied"]
        if rel.startswith("docs/html/") and not rel.endswith(".html")
    ]

    if extensions_xml.is_file():
        register_extensions_xml(
            extensions_xml, module, addon_base, libgis_rev,
            extra_basenames=extra_basenames,
            force=force, dry_run=dry_run,
        )

    if modules_xml.is_file():
        register_modules_xml(
            modules_xml, module, description, keywords, libgis_rev,
            force=force, dry_run=dry_run,
        )


if __name__ == "__main__":
    sys.exit(main(*gs.parser()))
