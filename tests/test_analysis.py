from datetime import datetime
from pathlib import Path

import pytest

from comfortmap.__main__ import main
from comfortmap.analysis import (Complaint, balance, load, matrix, select, shade, svg_heatmap, text_table)

EX = Path(__file__).resolve().parent.parent / "examples"
GOOD = str(EX / "complaints.csv")
BAD = str(EX / "complaints_with_errors.csv")


def c(ts, zone, kind):
    return Complaint(datetime.strptime(ts, "%Y-%m-%d %H:%M"), zone, kind)


@pytest.fixture(scope="module")
def data():
    return load(GOOD)[0]


def test_load_sample_clean():
    items, problems = load(GOOD)
    assert len(items) == 95 and problems == []


def test_load_reports_each_bad_row():
    items, problems = load(BAD)
    assert len(items) == 5 and len(problems) == 4
    assert any("bad timestamp '2026-09-31 10:00'" in p for p in problems)
    assert any("zone is empty" in p for p in problems)
    assert any("'Smelly'" in p for p in problems)


def test_load_missing_column(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("timestamp,zone\n2026-01-05 09:00,A\n")
    with pytest.raises(ValueError, match="kind"):
        load(str(f))


def test_select_hot_and_cold(data):
    assert all(x.kind == "Too Hot" for x in select(data, "hot"))
    assert len(select(data, "hot")) + len(select(data, "cold")) <= len(data)
    assert len(select(data, "all")) == len(data)


def test_matrix_weekday_totals(data):
    zones, cols, grid = matrix(data, "weekday")
    assert cols == ["Mon", "Tue", "Wed", "Thu", "Fri"] and len(zones) == 6
    assert sum(sum(v) for v in grid.values()) == len(data)


def test_matrix_by_hour_counts_one_item():
    zones, cols, grid = matrix([c("2026-09-07 09:10", "A", "Too Hot"), c("2026-09-07 11:50", "A", "Too Hot")], "hour")
    assert cols == ["09h", "10h", "11h"] and grid["A"] == [1, 0, 1]


def test_weekend_is_left_out_of_weekday_view():
    zones, cols, grid = matrix([c("2026-09-12 09:10", "A", "Too Hot")], "weekday")
    assert grid["A"] == [0, 0, 0, 0, 0]


def test_balance_net_is_hot_minus_cold():
    rows = balance([c("2026-09-07 09:00", "A", "Too Hot"), c("2026-09-07 09:05", "A", "Too Hot"),
                    c("2026-09-07 09:10", "A", "Too Cold"), c("2026-09-07 09:10", "B", "Too Cold"),
                    c("2026-09-07 09:10", "B", "Stuffy")])
    assert dict((z, n) for z, h, k, n in rows) == {"A": 1, "B": -1}


def test_balance_sorted_by_absolute_net(data):
    nets = [abs(r[3]) for r in balance(data)]
    assert nets == sorted(nets, reverse=True)


def test_south_1_is_hottest(data):
    zone, hot, cold, net = balance(data)[0]
    assert net > 0 and hot > cold


def test_shade_scale():
    assert shade(0, 10) == " " and shade(10, 10) == "#" and shade(1, 10) in ".:"


def test_text_table_has_row_per_zone(data):
    lines = text_table(data).splitlines()
    assert len(lines) == 7 and lines[0].rstrip().endswith("total")


def test_text_table_empty():
    assert text_table([]) == "no complaints"


def test_svg_is_well_formed_and_escaped():
    import xml.dom.minidom as md
    svg = svg_heatmap([c("2026-09-07 09:00", "A & B <x>", "Too Hot")], title="T & <t>")
    assert md.parseString(svg).documentElement.tagName == "svg"
    assert "A &amp; B &lt;x&gt;" in svg


def test_cli_codes(tmp_path, capsys):
    assert main(["table", GOOD]) == 0
    assert main(["zones", GOOD, "--strict"]) == 0
    assert main(["table", BAD, "--strict"]) == 1
    assert main(["table", "nope.csv"]) == 2
    out = tmp_path / "h.svg"
    assert main(["svg", GOOD, "-o", str(out), "--kind", "hot", "--by", "hour"]) == 0
    assert out.read_text().startswith("<svg")
