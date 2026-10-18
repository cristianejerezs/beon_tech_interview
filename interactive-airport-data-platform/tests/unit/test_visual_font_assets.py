import hashlib
import json
from importlib.resources import files

import pytest
from fontTools.ttLib import TTFont

FONTS = files("airport_analytics").joinpath("reports", "assets", "fonts")
MANIFEST = json.loads(FONTS.joinpath("manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("asset", MANIFEST["assets"], ids=lambda asset: asset["filename"])
def test_packaged_fonts_are_pinned_static_embeddable_and_licensed(asset):
    resource = FONTS.joinpath(asset["filename"])
    data = resource.read_bytes()
    assert hashlib.sha256(data).hexdigest() == asset["sha256"]
    license_data = FONTS.joinpath(asset["license_file"]).read_bytes()
    assert hashlib.sha256(license_data).hexdigest() == MANIFEST["license_sha256"]
    assert "SIL OPEN FONT LICENSE Version 1.1" in license_data.decode("utf-8")
    with resource.open("rb") as stream, TTFont(stream) as font:
        assert "fvar" not in font
        assert font["OS/2"].fsType == 0
        cmap = font.getBestCmap()
        sample = "Montreal Sao Paulo " + "\u00e9\u00f1\u0391\u03b8\u0410\u044f"
        assert {ord(char) for char in sample} <= cmap.keys()
        assert font["OS/2"].usWeightClass == asset["weight"]
        notices = {
            record.nameID: record.toUnicode()
            for record in font["name"].names
            if record.platformID == 3
        }
        assert notices[0] == asset["embedded_copyright"]
        assert "SIL Open Font License, Version 1.1" in notices[13]
