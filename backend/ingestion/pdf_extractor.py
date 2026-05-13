"""
Extraction de texte brut à partir des fichiers PDF (pdfplumber).
"""

from __future__ import annotations

import os
from pathlib import Path

import pdfplumber


def _racine_projet() -> Path:
    """Racine du projet (dossier contenant `backend/` et, par défaut, `data/`)."""
    return Path(__file__).resolve().parent.parent.parent


def get_data_directory() -> Path:
    """
    Dossier contenant les PDF sources.

    Si la variable d'environnement ``ADALA_DATA_DIR`` (ou ``LEXMAROC_DATA_DIR``)
    est définie (chemin absolu ou relatif à la racine du projet), elle est utilisée.
    Sinon, le dossier par défaut ``<racine>/data`` est retourné.
    """
    override = (
        os.environ.get("ADALA_DATA_DIR", "").strip()
        or os.environ.get("LEXMAROC_DATA_DIR", "").strip()
    )
    if override:
        chemin = Path(override).expanduser()
        if not chemin.is_absolute():
            chemin = (_racine_projet() / chemin).resolve()
        else:
            chemin = chemin.resolve()
        return chemin
    return (_racine_projet() / "data").resolve()


def extract_all_pdfs() -> dict[str, str]:
    """
    Parcourt le dossier des données, lit chaque PDF page par page et retourne
    un dictionnaire {nom_fichier.pdf: texte_complet}.
    """
    data_dir = get_data_directory()
    if not data_dir.is_dir():
        raise FileNotFoundError(
            f"Le dossier des données est introuvable : {data_dir}"
        )
    pdf_paths = sorted(data_dir.glob("*.pdf"))
    result: dict[str, str] = {}
    for path in pdf_paths:
        parts: list[str] = []
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    parts.append(text)
        except Exception as exc:
            raise RuntimeError(
                f"Impossible de lire le PDF « {path.name} » : {exc}"
            ) from exc
        result[path.name] = "\n".join(parts)
    return result
