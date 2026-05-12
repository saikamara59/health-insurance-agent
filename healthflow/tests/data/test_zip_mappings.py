"""Unit tests for scripts.refresh_data.build_zip_mappings."""

from scripts.refresh_data import build_zip_mappings


def test_build_zip_mappings_basic():
    plan_county_map = {
        "P1": {"36061"},          # Manhattan
        "P2": {"36061", "36047"}, # Manhattan + Brooklyn
        "P3": {"06001"},          # Connecticut, no NYC ZIPs
    }
    zip_county_map = {
        "10001": {"36061"},                    # Manhattan only
        "11201": {"36047"},                    # Brooklyn only
        "10004": {"36061", "36047"},           # straddles boroughs
    }
    result = build_zip_mappings(plan_county_map, zip_county_map)
    assert result == {
        "10001": ["P1", "P2"],
        "11201": ["P2"],
        "10004": ["P1", "P2"],
    }


def test_build_zip_mappings_empty_inputs():
    assert build_zip_mappings({}, {}) == {}
    assert build_zip_mappings({"P1": {"36061"}}, {}) == {}
    assert build_zip_mappings({}, {"10001": {"36061"}}) == {}


def test_build_zip_mappings_zip_with_no_plans_is_omitted():
    plan_county_map = {"P1": {"36061"}}
    zip_county_map = {
        "10001": {"36061"},   # has plan
        "99999": {"99999"},   # county not served by any plan
    }
    result = build_zip_mappings(plan_county_map, zip_county_map)
    assert "99999" not in result
    assert result == {"10001": ["P1"]}


def test_build_zip_mappings_accepts_lists_not_just_sets():
    """After a cache round-trip via JSON, sets become lists. Function must still work."""
    plan_county_map = {"P1": ["36061", "36047"]}
    zip_county_map = {"10001": ["36061"]}
    assert build_zip_mappings(plan_county_map, zip_county_map) == {"10001": ["P1"]}


def test_build_zip_mappings_dedupes_plans():
    """A ZIP touching two counties both served by the same plan should list it once."""
    plan_county_map = {"P1": {"A", "B"}}
    zip_county_map = {"10001": {"A", "B"}}
    assert build_zip_mappings(plan_county_map, zip_county_map) == {"10001": ["P1"]}


def test_build_zip_mappings_output_is_sorted():
    plan_county_map = {"P_z": {"X"}, "P_a": {"X"}, "P_m": {"X"}}
    zip_county_map = {"10001": {"X"}}
    assert build_zip_mappings(plan_county_map, zip_county_map) == {
        "10001": ["P_a", "P_m", "P_z"],
    }
