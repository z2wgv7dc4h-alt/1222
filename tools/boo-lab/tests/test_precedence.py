from boo_lab.precedence import resolve_precedence


def test_no_sync_ok_spine_is_human():
    for sync_ok in (None, False):
        d = resolve_precedence(sync_ok=sync_ok, has_gp_markers=True,
                                has_pack=True, has_gp=True)
        assert d["spine"] == "human"
        assert d["sync_ok"] is False
        assert d["clock"] == "gp-notated"


def test_sync_ok_with_gp_markers_spine_is_gp_marker():
    d = resolve_precedence(sync_ok=True, has_gp_markers=True,
                            has_pack=True, has_gp=True)
    assert d["spine"] == "gp-marker"
    assert d["sync_ok"] is True
    assert d["clock"] == "clock_ratio"
    # A pack alongside markers doesn't demote the spine.
    d2 = resolve_precedence(sync_ok=True, has_gp_markers=True,
                             has_pack=False, has_gp=True)
    assert d2["spine"] == "gp-marker"


def test_sync_ok_with_pack_and_no_markers_spine_is_pack():
    d = resolve_precedence(sync_ok=True, has_gp_markers=False,
                            has_pack=True, has_gp=False)
    assert d["spine"] == "pack"
    assert d["clock"] == "pack-audio"


def test_sync_ok_with_no_markers_and_no_pack_spine_is_human():
    d = resolve_precedence(sync_ok=True, has_gp_markers=False,
                            has_pack=False, has_gp=False)
    assert d["spine"] == "human"
    assert d["clock"] == "gp-notated"


def test_notes_source_precedence():
    assert resolve_precedence(sync_ok=True, has_gp_markers=False,
                               has_pack=True, has_gp=True)["notes_source"] == "gp"
    assert resolve_precedence(sync_ok=False, has_gp_markers=False,
                               has_pack=True, has_gp=False)["notes_source"] == "pack"
    assert resolve_precedence(sync_ok=False, has_gp_markers=False,
                               has_pack=False, has_gp=False)["notes_source"] is None
