from healthflow.tools.denial_codes import DenialCodeDB


def test_lookup_known_code():
    db = DenialCodeDB()
    result = db.lookup("CO-50")
    assert result is not None
    assert result["code"] == "CO-50"
    assert "medical necessity" in result["description"].lower()
    assert result["category"] == "Medical Necessity"
    assert len(result["appeal_grounds"]) > 0
    assert len(result["precedents"]) > 0


def test_lookup_unknown_code():
    db = DenialCodeDB()
    result = db.lookup("CO-9999")
    assert result is None


def test_keyword_search():
    db = DenialCodeDB()
    result = db.search_by_keyword("medical necessity")
    assert result is not None
    assert "medical necessity" in result["description"].lower() or "medical necessity" in result["category"].lower()


def test_keyword_search_case_insensitive():
    db = DenialCodeDB()
    result = db.search_by_keyword("TIMELY FILING")
    assert result is not None


def test_keyword_search_no_match():
    db = DenialCodeDB()
    result = db.search_by_keyword("xyznonexistentterm123")
    assert result is None


def test_all_codes_have_required_fields():
    db = DenialCodeDB()
    required_fields = {"code", "description", "category", "cms_rule", "appeal_grounds", "precedents"}
    for code_entry in db.all_codes():
        for field in required_fields:
            assert field in code_entry, f"Code {code_entry.get('code', '?')} missing field: {field}"
        assert isinstance(code_entry["appeal_grounds"], list)
        assert isinstance(code_entry["precedents"], list)
        assert len(code_entry["appeal_grounds"]) > 0
        assert len(code_entry["precedents"]) > 0


def test_minimum_code_count():
    db = DenialCodeDB()
    codes = db.all_codes()
    assert len(codes) >= 25
