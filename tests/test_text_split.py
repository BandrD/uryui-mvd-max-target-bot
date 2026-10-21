from app.llm.text_split import split_text


def test_split_short():
    assert split_text("привет") == ["привет"]


def test_split_long():
    text = ("слово " * 900).strip()
    parts = split_text(text, limit=400)
    assert all(len(p) <= 400 for p in parts)
    assert "".join(parts).replace(" ", "") == text.replace(" ", "")
