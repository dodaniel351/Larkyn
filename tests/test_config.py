from larkyn.config import DEFAULT_ENDPOINT, DEFAULT_MODEL, AppConfig


def test_defaults_match_spec():
    cfg = AppConfig()
    assert cfg.llm.model == "gemma4:e2b-it-qat" == DEFAULT_MODEL
    assert cfg.llm.endpoint == DEFAULT_ENDPOINT
    assert cfg.llm.temperature == 0.2
    assert cfg.llm.top_p == 0.9
    assert cfg.llm.max_tokens == 4096
    assert cfg.output.mode == "paste"
    assert cfg.hotkey.toggle == "<ctrl>+<alt>+<space>"
    # spec vocabulary seeded
    assert "LibreNMS" in cfg.vocabulary


def test_round_trip(tmp_path):
    path = tmp_path / "config.json"
    cfg = AppConfig()
    cfg.output.mode = "clipboard"
    cfg.vocabulary.append("Custom Term")
    cfg.save(path)

    loaded = AppConfig.load(path)
    assert loaded.output.mode == "clipboard"
    assert "Custom Term" in loaded.vocabulary
    assert loaded.llm.model == "gemma4:e2b-it-qat"


def test_corrupt_config_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ not valid json", encoding="utf-8")
    cfg = AppConfig.load(path)
    assert cfg.llm.model == "gemma4:e2b-it-qat"
