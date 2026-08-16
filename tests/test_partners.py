import importlib

ds = importlib.import_module("common.data_sources")


def test_every_partner_has_a_group_and_a_scale():
    # The footer strip is unboxed, so a logo's group (which gap precedes it)
    # and its optical scale are what place it. A logo added to PARTNER_ORDER
    # without entries here would silently fall into group 0 at scale 1.0 --
    # wrong affiliation, wrong visual weight, no error.
    missing_group = [f for f in ds.PARTNER_ORDER if f not in ds.PARTNER_GROUPS]
    missing_scale = [f for f in ds.PARTNER_ORDER if f not in ds.PARTNER_SCALE]
    assert not missing_group, f"no PARTNER_GROUPS entry for {missing_group}"
    assert not missing_scale, f"no PARTNER_SCALE entry for {missing_scale}"


def test_no_orphan_group_or_scale_entries():
    # The reverse drift: a logo dropped from PARTNER_ORDER leaves dead entries.
    order = set(ds.PARTNER_ORDER)
    assert set(ds.PARTNER_GROUPS) <= order
    assert set(ds.PARTNER_SCALE) <= order


def test_groups_are_contiguous_in_render_order():
    # buildPartners() opens a new .partner-group whenever the group index
    # changes as it walks the flat list, so a group split across
    # non-adjacent positions would render as two groups with a wide gap
    # between halves of one affiliation.
    seen = []
    for fname in ds.PARTNER_ORDER:
        group = ds.PARTNER_GROUPS[fname]
        if not seen or seen[-1] != group:
            assert group not in seen, f"group {group} is split around {fname}"
            seen.append(group)


def test_scales_are_within_sane_bounds():
    for fname, scale in ds.PARTNER_SCALE.items():
        assert 0.5 <= scale <= 1.0, f"{fname} scale {scale} outside 0.5-1.0"


def test_load_partners_carries_group_and_scale(monkeypatch):
    monkeypatch.setattr(ds, "load_logo_data_uri", lambda f: "data:image/png;base64,AA")
    partners = ds.load_partners()
    assert partners, "expected the branding directory to yield partners"
    assert len(partners) == len(ds.PARTNER_ORDER)
    for entry in partners:
        assert isinstance(entry["group"], int)
        assert isinstance(entry["scale"], float)
    # Order is preserved, so group indices never decrease down the strip.
    groups = [entry["group"] for entry in partners]
    assert groups == sorted(groups)
