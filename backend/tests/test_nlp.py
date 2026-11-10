from ingest.nlp.normalize import fold, normalize_text
from ingest.nlp.tokenize import to_tsquery_or, tokenize_ko


def test_tokenize_korean_bigrams_and_vietnamese_words():
    assert tokenize_ko("체류기간을") == ["체류", "류기", "기간", "간을"]
    assert tokenize_ko("14일 이내") == ["14", "일", "이내"]
    assert tokenize_ko("gia hạn của visa") == ["gia", "hạn", "visa"]  # 불용어 제거


def test_tsquery_is_safe_and_unique():
    q = to_tsquery_or("체류 체류 & | !")
    assert q == "체류"


def test_fold_ignores_spacing_and_punctuation():
    assert fold("청장ㆍ사무소장  또는\n출장소장") == fold("청장·사무소장 또는 출장소장")
    assert fold("**①** 외국인이") == fold("① 외국인이")


def test_normalize_keeps_indent():
    assert normalize_text("  1\\. 첫째\r\n").startswith("  1")
