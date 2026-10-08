#!/usr/bin/env python3
"""embed_files.py — intègre des fichiers bruts dans un JSON (option tar.gz)."""

import argparse
import base64
import io
import json
import os
import sys
import tarfile
from pathlib import Path


def is_excluded(path: Path, exclude_dirs: set, exclude_exts: set, exclude_names: set) -> bool:
    name = path.name
    if name in exclude_names:
        return True
    for ext in exclude_exts:
        if name.endswith(ext):
            return True
    return False


def collect_files(roots: list[str], recursive: bool,
                  exclude_dirs: set, exclude_exts: set, exclude_names: set) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        p = Path(root)
        if not p.exists():
            sys.exit(f"Erreur: '{root}' introuvable.")

        if p.is_file():
            if not is_excluded(p, exclude_dirs, exclude_exts, exclude_names):
                files.append(p)
        elif p.is_dir():
            if recursive:
                for dirpath, dirnames, filenames in os.walk(p):
                    dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
                    for fn in filenames:
                        fp = Path(dirpath) / fn
                        if not is_excluded(fp, exclude_dirs, exclude_exts, exclude_names):
                            files.append(fp)
            else:
                for fn in sorted(p.iterdir()):
                    if fn.is_file() and not is_excluded(fn, exclude_dirs, exclude_exts, exclude_names):
                        files.append(fn)
    return files


def read_content(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        return f"[binaire, {path.stat().st_size} octets]"


def build_tar_gz(files: list[Path]) -> bytes:
    """Crée un tar.gz en mémoire avec les fichiers (chemins relatifs)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in files:
            # Chemin relatif par rapport au cwd (ou tel quel si absolu)
            arcname = str(f)
            if arcname.startswith("./"):
                arcname = arcname[2:]
            tar.add(str(f), arcname=arcname, recursive=False)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser(
        description="Intègre des fichiers bruts dans un fichier JSON."
    )
    parser.add_argument("paths", nargs="+", help="Fichiers ou répertoires à intégrer")
    parser.add_argument("-o", "--output", default="integrated.json",
                        help="Fichier JSON de sortie (défaut: integrated.json)")
    parser.add_argument("-n", "--no-recursive", action="store_true",
                        help="Ne pas descendre dans les sous-répertoires")
    parser.add_argument("-d", "--exclude-dir", action="append", default=[],
                        metavar="NOM", help="Exclure un répertoire par nom (répétable)")
    parser.add_argument("-e", "--exclude-ext", action="append", default=[],
                        metavar="EXT", help="Exclure par extension (répétable)")
    parser.add_argument("-x", "--exclude-name", action="append", default=[],
                        metavar="NOM", help="Exclure par nom exact (répétable)")
    parser.add_argument("--tar", action="store_true",
                        help="Emballer les fichiers en tar.gz (base64) au lieu du contenu brut")

    args = parser.parse_args()

    exclude_dirs = set(args.exclude_dir)
    exclude_exts = {e if e.startswith(".") else f".{e}" for e in args.exclude_ext}
    exclude_names = set(args.exclude_name)

    files = collect_files(
        args.paths,
        recursive=not args.no_recursive,
        exclude_dirs=exclude_dirs,
        exclude_exts=exclude_exts,
        exclude_names=exclude_names,
    )

    if not files:
        sys.exit("Aucun fichier à intégrer.")

    if args.tar:
        # ─── Mode tar.gz ───────────────────────────────────────────────────
        raw = build_tar_gz(files)
        b64 = base64.b64encode(raw).decode("ascii")

        data = {
            "format": "tar.gz",
            "size_bytes": len(raw),
            "file_count": len(files),
            "file_list": [str(f) for f in files],
            "archive": b64,
            "decode_instructions": (
                "L'archive est encodée en base64. Pour la décompresser :\n"
                "  import base64, tarfile, io\n"
                "  buf = io.BytesIO(base64.b64decode(archive))\n"
                "  with tarfile.open(fileobj=buf, mode='r:gz') as t:\n"
                "      t.extractall()"
            ),
        }
    else:
        # ─── Mode contenu brut ─────────────────────────────────────────────
        data = {}
        for f in files:
            key = str(f)
            if key.startswith("./"):
                key = key[2:]
            data[key] = read_content(f)

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)

    mode = "tar.gz" if args.tar else "brut"
    print(f"✓ {args.output}  ({len(files)} fichier(s), mode {mode})")


if __name__ == "__main__":
    main()   