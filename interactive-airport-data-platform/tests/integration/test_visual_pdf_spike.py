import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from fontTools.ttLib import TTFont
from pypdf import PdfReader

from airport_analytics.reports.assets import __path__ as report_assets_path

FONTS = Path(next(iter(report_assets_path))) / "fonts"


def _resolve(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def _structure_roles(node: Any, seen: set[int] | None = None) -> set[str]:
    visited = seen if seen is not None else set()
    node = _resolve(node)
    if id(node) in visited:
        return set()
    visited.add(id(node))
    roles: set[str] = set()
    if isinstance(node, dict):
        role = node.get("/S")
        if isinstance(role, str):
            roles.add(role)
        children = node.get("/K")
        if isinstance(children, list):
            for child in children:
                roles.update(_structure_roles(child, visited))
        elif children is not None:
            roles.update(_structure_roles(children, visited))
    return roles


def _structure_figures(node: Any, seen: set[int] | None = None) -> list[Any]:
    visited = seen if seen is not None else set()
    node = _resolve(node)
    if id(node) in visited:
        return []
    visited.add(id(node))
    figures = []
    if isinstance(node, dict):
        if node.get("/S") == "/Figure":
            figures.append(node)
        children = node.get("/K")
        if isinstance(children, list):
            for child in children:
                figures.extend(_structure_figures(child, visited))
        elif children is not None:
            figures.extend(_structure_figures(children, visited))
    return figures


def _structure_relations(node: Any, seen: set[int] | None = None) -> set[tuple[str, str]]:
    visited = seen if seen is not None else set()
    node = _resolve(node)
    if id(node) in visited:
        return set()
    visited.add(id(node))
    relations: set[tuple[str, str]] = set()
    if isinstance(node, dict):
        role = node.get("/S")
        parent = _resolve(node.get("/P"))
        parent_role = parent.get("/S") if isinstance(parent, dict) else None
        if isinstance(role, str) and isinstance(parent_role, str):
            relations.add((role, parent_role))
        children = node.get("/K")
        if isinstance(children, list):
            for child in children:
                relations.update(_structure_relations(child, visited))
        elif children is not None:
            relations.update(_structure_relations(children, visited))
    return relations


def _synthetic_html(svg_path: Path, *, landscape: bool) -> str:
    regular = (FONTS / "NotoSans-Regular.ttf").as_uri()
    bold = (FONTS / "NotoSans-Bold.ttf").as_uri()
    orientation = "landscape" if landscape else "portrait"
    rows = "".join(
        f"<tr><td>{index:03} — Aéroport São José</td><td>Repeated name / code {index:03}</td></tr>"
        for index in range(90)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Synthetic tagged visual report</title>
  <style>
    @font-face {{ font-family: Noto; src: url("{regular}"); font-weight: 400; }}
    @font-face {{ font-family: Noto; src: url("{bold}"); font-weight: 700; }}
    @page {{ size: A4 {orientation}; margin: 16mm; }}
    body {{ font-family: Noto, sans-serif; font-size: 10pt; }}
    h1, h2 {{ font-size: 12pt; }}
    figure {{ margin: 6mm 0; }}
    figure img {{ width: 150mm; height: auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    thead {{ display: table-header-group; }}
    th, td {{ border: 0.4pt solid #555; padding: 2mm; font-size: 10pt; }}
    tr {{ break-inside: avoid; }}
  </style>
</head>
<body>
  <h1>Synthetic visual report</h1>
  <p>Snapshot-local evidence; no live source data.</p>
  <figure>
    <img src="{svg_path.as_uri()}" alt="Flights by origin; observed counts are 12 and 0.">
    <figcaption>Flights by origin; observed counts are 12 and 0.</figcaption>
  </figure>
  <h2>Exact evidence table</h2>
  <table>
    <thead><tr><th scope="col">Origin code and name</th>
    <th scope="col">Exact measure and note</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""


def _file_only_url_fetcher():
    from weasyprint.urls import URLFetcher

    class FileOnlyURLFetcher(URLFetcher):
        def __init__(self):
            super().__init__(allowed_protocols={"file"})
            self.urls = []
            self.non_file_urls = []

        def fetch(self, url, headers=None):
            if urlsplit(url).scheme != "file":
                self.non_file_urls.append(url)
                raise ValueError("The synthetic PDF spike only permits local files.")
            self.urls.append(url)
            return super().fetch(url, headers=headers)

    return FileOnlyURLFetcher()


@pytest.fixture
def pdf_runtime(monkeypatch):
    monkeypatch.setenv("WEASYPRINT_DLL_DIRECTORIES", r"C:\msys64\ucrt64\bin")
    from weasyprint import HTML

    return HTML


@pytest.mark.parametrize("landscape", [False, True], ids=["portrait", "landscape"])
def test_synthetic_tagged_pdf_preserves_chart_text_table_language_and_pages(
    tmp_path,
    pdf_runtime,
    landscape,
):
    import vl_convert

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.20.1.json",
        "data": {
            "values": [
                {"origin": "SFO", "count": 12},
                {"origin": "SFO duplicate code", "count": 0},
            ]
        },
        "width": 360,
        "height": 150,
        "config": {
            "axis": {"labelFontSize": 16, "titleFontSize": 16, "labelLimit": 0},
        },
        "mark": {"type": "bar"},
        "encoding": {
            "y": {
                "field": "origin",
                "type": "nominal",
                "title": "Origin — São José",
                "axis": {"titlePadding": 30},
            },
            "x": {"field": "count", "type": "quantitative", "title": "Flights"},
        },
    }
    svg_path = tmp_path / "synthetic.svg"
    svg_path.write_text(vl_convert.vegalite_to_svg(spec), encoding="utf-8")
    pdf_path = tmp_path / "synthetic.pdf"
    html = _synthetic_html(svg_path, landscape=landscape)
    fetcher = _file_only_url_fetcher()

    pdf_runtime(
        string=html,
        base_url=tmp_path.as_uri(),
        url_fetcher=fetcher,
    ).write_pdf(
        pdf_path,
        pdf_variant="pdf/ua-1",
        pdf_tags=True,
    )

    reader = PdfReader(pdf_path)
    assert len(reader.pages) >= 3
    assert reader.trailer["/Root"]["/Lang"] == "en"
    assert "/StructTreeRoot" in reader.trailer["/Root"]
    roles = _structure_roles(reader.trailer["/Root"]["/StructTreeRoot"])
    assert {"/H1", "/H2", "/Figure", "/Table", "/TR", "/TH", "/TD"} <= roles
    relations = _structure_relations(reader.trailer["/Root"]["/StructTreeRoot"])
    assert {("/TR", "/THead"), ("/TR", "/TBody"), ("/TH", "/TR"), ("/TD", "/TR")} <= relations
    figures = _structure_figures(reader.trailer["/Root"]["/StructTreeRoot"])
    assert figures
    assert figures[0].get("/Alt") == ("Flights by origin; observed counts are 12 and 0.")
    page_text = [page.extract_text() or "" for page in reader.pages]
    assert any("Aéroport São José" in text for text in page_text)
    assert any("Origin — São José" in text for text in page_text)
    assert "Flights by origin; observed counts are 12 and 0." in page_text[0]
    combined_text = "\n".join(page_text)
    assert all(f"{index:03} — Aéroport São José" in combined_text for index in range(90))
    assert all("Origin code and name" in text for text in page_text[1:])
    assert all(
        (float(page.mediabox.width) > float(page.mediabox.height)) == landscape
        for page in reader.pages
    )
    text_sizes = []

    def collect_text_sizes(text, current_matrix, text_matrix, font, font_size):
        if text.strip():
            scale = (current_matrix[0] ** 2 + current_matrix[1] ** 2) ** 0.5
            text_sizes.append(font_size * scale)

    for page in reader.pages:
        page.extract_text(visitor_text=collect_text_sizes)
    assert text_sizes
    # WeasyPrint quantizes CSS pixel sizes before converting them to PDF points.
    assert min(text_sizes) >= 10 - 0.001
    assert fetcher.urls
    assert not fetcher.non_file_urls


def test_bundled_font_glyph_coverage():
    font = TTFont(FONTS / "NotoSans-Regular.ttf")
    codepoints = set().union(*(set(table.cmap) for table in font["cmap"].tables))
    assert {ord(character) for character in "Aéroport São José"} <= codepoints
    unsupported = ord("\U0001f9ea")
    assert unsupported not in codepoints


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="WEASYPRINT_DLL_DIRECTORIES only controls native library lookup on Windows.",
)
def test_missing_native_renderer_resource_fails_without_pdf_bytes(tmp_path):
    output = tmp_path / "missing-resource.pdf"
    missing_dlls = tmp_path / "no-native-renderer"
    env = os.environ.copy()
    env["WEASYPRINT_DLL_DIRECTORIES"] = str(missing_dlls)
    source = (
        f"from weasyprint import HTML; HTML(string='<h1>synthetic</h1>').write_pdf({str(output)!r})"
    )

    result = subprocess.run(
        [sys.executable, "-c", source],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert not output.exists()


def test_synthetic_renderer_worker_respects_a_technical_timeout():
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            capture_output=True,
            timeout=0.1,
            check=False,
        )
