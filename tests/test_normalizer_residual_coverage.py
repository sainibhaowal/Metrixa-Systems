from __future__ import annotations

from metrixa_engine.entity_resolution.normalizer import normalize_phone_e164


def test_phone_manual_fallback_after_parser_failure(monkeypatch):
    import metrixa_engine.entity_resolution.normalizer as module

    monkeypatch.setattr(
        module.phonenumbers,
        "parse",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad number")),
    )
    assert normalize_phone_e164("0049 30 123456") == "+4930123456"
    assert normalize_phone_e164("030 1234567") == "+49301234567"
    assert normalize_phone_e164("1234567") == "+491234567"
    assert normalize_phone_e164("12345") is None
