"""Tagged-PDF runtime: locate WeasyPrint's native Pango libraries and render safely."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

from airport_analytics.errors import PdfRuntimeUnavailableError

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
DLL_ENV = "WEASYPRINT_DLL_DIRECTORIES"
# Common Windows locations of the MSYS2 Pango build; used only when DLL_ENV is unset.
_WINDOWS_PANGO_DIRS = (
    Path(r"C:\msys64\ucrt64\bin"),
    Path(r"C:\msys64\mingw64\bin"),
)


def _configure_dll_directories() -> None:
    if sys.platform != "win32" or os.environ.get(DLL_ENV):
        return
    for directory in _WINDOWS_PANGO_DIRS:
        if (directory / "libgobject-2.0-0.dll").is_file():
            os.environ[DLL_ENV] = str(directory)
            return


@lru_cache(maxsize=1)
def _load_weasyprint() -> tuple[ModuleType | None, str | None]:
    _configure_dll_directories()
    try:
        import weasyprint
    except (ImportError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return weasyprint, None


def pdf_runtime_status() -> tuple[bool, str | None]:
    """Return whether tagged PDFs can be rendered, plus a diagnostic when they cannot."""
    module, problem = _load_weasyprint()
    return module is not None, problem


def require_pdf_runtime() -> ModuleType:
    module, problem = _load_weasyprint()
    if module is None:
        raise PdfRuntimeUnavailableError(f"Tagged PDF runtime unavailable ({problem}).")
    return module


def font_face_css(family: str = "AirportNoto") -> str:
    regular = (FONT_DIR / "NotoSans-Regular.ttf").as_uri()
    bold = (FONT_DIR / "NotoSans-Bold.ttf").as_uri()
    return (
        f"@font-face{{font-family:{family};src:url('{regular}');font-weight:normal}}"
        f"@font-face{{font-family:{family};src:url('{bold}');font-weight:bold}}"
    )


def render_tagged_pdf(document: str) -> bytes:
    """Render semantic HTML to a tagged PDF; only bundled fonts and data URIs are fetched."""
    weasyprint = require_pdf_runtime()
    from weasyprint.urls import URLFetcher

    allowed = {path.resolve() for path in FONT_DIR.glob("*.ttf")}

    class LocalOnlyFetcher(URLFetcher):
        def __init__(self) -> None:
            super().__init__(allowed_protocols={"file", "data"})

        def fetch(self, url, headers=None):
            parts = urlsplit(url)
            if parts.scheme == "file":
                path = Path(url2pathname(unquote(parts.path))).resolve()
                if path not in allowed:
                    raise ValueError("Only bundled PDF fonts may be loaded.")
            elif parts.scheme != "data":
                raise ValueError("Only local PDF resources are allowed.")
            return super().fetch(url, headers=headers)

    content = weasyprint.HTML(string=document, url_fetcher=LocalOnlyFetcher()).write_pdf(
        pdf_tags=True
    )
    if not content or not content.startswith(b"%PDF-"):
        raise RuntimeError("The PDF renderer returned no document.")
    return content
