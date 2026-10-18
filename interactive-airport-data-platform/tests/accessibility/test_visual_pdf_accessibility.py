import io

from pypdf import PdfReader

from airport_analytics.reports.export import export_report_pdf
from tests.integration.test_visual_exports import _relationship_report


def _resolve(node):
    return node.get_object() if hasattr(node, "get_object") else node


def _roles(node, seen=None):
    visited = seen if seen is not None else set()
    node = _resolve(node)
    if id(node) in visited:
        return set()
    visited.add(id(node))
    roles = set()
    if isinstance(node, dict):
        role = node.get("/S")
        if isinstance(role, str):
            roles.add(role)
        children = node.get("/K")
        if isinstance(children, list):
            for child in children:
                roles.update(_roles(child, visited))
        elif children is not None:
            roles.update(_roles(children, visited))
    return roles


def _figures(node, seen=None):
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
                figures.extend(_figures(child, visited))
        elif children is not None:
            figures.extend(_figures(children, visited))
    return figures


def test_export_defaults_pdf_has_tagged_chart_and_table_structure():
    reader = PdfReader(io.BytesIO(export_report_pdf(_relationship_report())))
    root = reader.trailer["/Root"]

    assert root.get("/Lang") == "en"
    assert "/StructTreeRoot" in root
    tree = root["/StructTreeRoot"]
    assert {"/Document", "/H1", "/Figure", "/Table", "/TR", "/TH", "/TD"} <= _roles(tree)
    figures = _figures(tree)
    assert figures
    assert all(isinstance(figure.get("/Alt"), str) and figure["/Alt"] for figure in figures)
