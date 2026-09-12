from decimal import Decimal

from app.domains.interconnection.equipment.lookup import lookup, manifest


def test_snapshot_is_pinned_and_described() -> None:
    m = manifest()
    assert m["rows"] > 3000 and m["list_data_as_of"] and len(m["source_sha256"]) == 64
    assert "Proxy" in m["use"]


def test_listed_model_is_found_case_and_space_insensitive() -> None:
    r = lookup("pvi-3.0-outd-s-us-a")
    assert r.listed and r.matches[0].manufacturer == "ABB"
    assert lookup("PVI-3.0-OUTD-S-US-A ").listed


def test_voltage_option_narrows_the_match() -> None:
    r = lookup("PVI-3.0-OUTD-S-US-A", nominal_vac=Decimal("277"))
    assert {m.nominal_vac for m in r.matches} == {Decimal("277")}


def test_certification_reflects_ul1741_flags() -> None:
    r = lookup("PVI-3.0-OUTD-S-US-A")
    assert r.certified is True and "UL 1741 SA" in r.basis()


def test_typo_is_reported_as_near_match_not_accepted() -> None:
    r = lookup("PVI-3.0-OUTD-S-US-AA")
    assert not r.listed and not r.certified
    assert "PVI-3.0-OUTD-S-US-A" in r.near_matches and "near matches" in r.basis()


def test_unknown_model() -> None:
    r = lookup("TOTALLY-MADE-UP-9000")
    assert not r.listed and r.near_matches == ()
