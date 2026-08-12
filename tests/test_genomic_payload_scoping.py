import importlib, json, re

chrome = importlib.import_module("common.chrome")


def _payload_from_html(html):
    m = re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S)
    assert m, "payload script block not found"
    return json.loads(m.group(1))


def test_genomic_key_only_on_genomic_page():
    payload = {"geometry": {"type": "FeatureCollection", "features": []},
               "zone_data": {}, "layers": [], "genomic": {"tree": "#NEXUS", "tips": []}}
    gen = _payload_from_html(chrome.render_page("genomic-epidemiology", payload))
    assert "genomic" in gen and gen["genomic"]["tree"] == "#NEXUS"
    other = _payload_from_html(chrome.render_page("trends", payload))
    assert "genomic" not in other            # stripped from every other page
