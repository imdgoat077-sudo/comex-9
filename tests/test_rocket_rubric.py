"""The rocket scorer, checked on hand-built scenes before it is used to judge any run."""

from benchmarks.rocket_rubric import COMPONENTS, color_class, score


def el(t, x, y, w, h, bg="transparent", stroke="#1e1e1e", fill="solid"):
    return {"type": t, "x": x, "y": y, "width": w, "height": h, "backgroundColor": bg, "strokeColor": stroke, "fillStyle": fill}


def perfect_scene():
    s = [el("rectangle", 250, 90, 900, 590, "#0b132b")]                      # sky
    s.append(el("rectangle", 640, 250, 120, 250, "#ffffff"))                   # body
    s.append(el("diamond", 640, 170, 120, 85, "#e03131"))                      # nose
    s += [el("rectangle", 640, 295, 120, 25, "#e03131"), el("rectangle", 640, 440, 120, 25, "#e03131")]   # stripes
    s += [el("ellipse", 675, 335, 50, 50, "#1864ab"), el("ellipse", 685, 345, 30, 30, "#74c0fc")]       # porthole
    s += [el("line", 585, 400, 55, 95, "#e03131"), el("line", 760, 400, 55, 95, "#e03131")]            # fins
    s += [el("rectangle", 660, 500, 80, 20, "#495057"), el("rectangle", 665, 520, 25, 20, "#868e96"), el("rectangle", 710, 520, 25, 20, "#868e96")]
    s += [el("diamond", 660, 540, 80, 80, "#f08c00"), el("diamond", 680, 545, 40, 50, "#ffd43b")]       # flames
    s += [el("diamond", 300 + i * 70, 120, 14, 14, "#ffd43b") for i in range(6)]                       # stars
    return s


def test_colour_classes_cover_the_palette_in_the_prompt():
    assert [color_class(c) for c in ("#0b132b", "#ffffff", "#e03131", "#f08c00", "#ffd43b", "#1864ab", "#74c0fc", "#495057", "#868e96", "transparent")] == \
        ["dark", "white", "red", "orange", "yellow", "blue", "blue", "dark", "grey", "none"]


def test_a_complete_rocket_scores_nine_of_nine():
    r = score(perfect_scene())
    assert r["components"] == {c: True for c in COMPONENTS}, r
    assert r["score"] == 9 and r["complete"]


def test_empty_and_outline_only_scenes_score_zero_or_low():
    assert score([])["score"] == 0
    outline_only = [{**e, "backgroundColor": "transparent"} for e in perfect_scene()]
    assert score(outline_only)["score"] == 0, "unfilled shapes must not count"


def test_each_missing_part_is_reported_and_leftovers_do_not_inflate_the_score():
    scene = perfect_scene()
    no_stars = [e for e in scene if not (e["y"] == 120 and e["width"] == 14)]
    r = score(no_stars)
    assert r["components"]["stars"] is False and r["score"] == 8
    deleted = [{**e, "isDeleted": True} if e["backgroundColor"] == "#e03131" else e for e in scene]
    r2 = score(deleted)
    assert not r2["components"]["nose"] and not r2["components"]["fins"] and not r2["components"]["stripes"]
    wrong_place_stars = [e if e["width"] != 14 else {**e, "x": 680, "y": 300} for e in scene]   # stars on the rocket do not count
    assert score(wrong_place_stars)["components"]["stars"] is False


def test_version_2_measures_lines_by_their_points_and_counts_slate_as_grey():
    # a left fin: starts at the body edge and its points run LEFT of the start (width is the extent, x is the start)
    fin = {**el("line", 570, 350, 70, 90, "#e63946"), "points": [[0, 0], [-70, 90], [0, 90], [0, 0]]}
    from benchmarks.rocket_rubric import _box, greyish
    assert _box(fin) == (500.0, 350.0, 570.0, 440.0)
    scene = [e for e in perfect_scene() if not (e["type"] == "line" and e["x"] == 585)]
    right = {**el("line", 710, 350, 70, 90, "#e63946"), "points": [[0, 0], [70, 90], [0, 90], [0, 0]]}
    assert score(scene + [fin, right])["components"]["fins"] is True
    # slate nozzles count as grey; a light blue does not
    assert greyish("#8d99ae") and greyish("#495057") and not greyish("#a8dadc") and not greyish("#e03131")
    slate = [{**e, "backgroundColor": "#8d99ae"} if e["backgroundColor"] in ("#495057", "#868e96") else e for e in perfect_scene()]
    assert score(slate)["components"]["engine"] is True
