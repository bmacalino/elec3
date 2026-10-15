from remittrend import config


def test_raw_input_find(tmp_path):
    ofwp = next(r for r in config.RAW_INPUTS if r.key == "ofwp")
    assert ofwp.find(tmp_path) is None
    (tmp_path / "ofwp.xls").write_bytes(b"")
    assert ofwp.find(tmp_path).name == "ofwp.xls"


def test_ofw_pattern_does_not_match_ofwp(tmp_path):
    (tmp_path / "ofwp.xls").write_bytes(b"")
    ofw = next(r for r in config.RAW_INPUTS if r.key == "ofw")
    assert ofw.find(tmp_path) is None


def test_settings_are_consistent():
    assert config.MODEL_SELECTION in {"rolling", "test"}
    assert config.TEST_MONTHS == config.FORECAST_HORIZON
    assert 1 <= config.INDICATOR_LAG < config.FORECAST_HORIZON
    assert config.RELATIONSHIP_RECENT_START > config.STUDY_START
