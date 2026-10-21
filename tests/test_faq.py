from app.llm.faq import match_faq


def test_faq_rules():
    hit = match_faq("Как правильно фотографировать мишень?")
    assert hit is not None
    assert "мишень" in hit.answer.lower() or "Правила" in hit.answer


def test_faq_tape():
    hit = match_faq("Учитываете ли вы скотч?")
    assert hit is not None
    assert "скотч" in hit.answer.lower()


def test_faq_miss():
    assert match_faq("погода в екатеринбурге сегодня") is None
