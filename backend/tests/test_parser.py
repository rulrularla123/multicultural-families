from ingest.loader import load_file
from ingest.parsers.structure import parse_law

SAMPLE = """# 예시법

## 제1장 총칙

##### 제1조 (목적)

이 법은 예시를 정한다.

##### 제10조의2 (특칙)

**①** 첫째 항이다. <개정 2020.6.9>

**②** 다음 각 호의 어느 하나에 해당하는 경우:

  1\\. 첫째 호
  2의2\\. 가지 호
    가\\. 첫째 목
    나\\. 둘째 목

##### 제11조

삭제 <2022.12.13>

## 부칙

##### 제1조 (시행일)

이 법은 공포한 날부터 시행한다.
"""


def test_parse_levels_and_ids():
    doc = parse_law(SAMPLE, "예시법", "예시법")
    ids = [n.id for n in doc.nodes()]
    assert "예시법:C1" in ids
    assert "예시법:J10-2:H2:O2-2:M나" in ids
    assert [j.number for j in doc.jos()] == ["1", "10의2", "11"]  # 부칙은 읽지 않는다
    assert doc.warnings == ["누락된 조 번호: [2, 3, 4, 5, 6, 7, 8, 9]"]


def test_render_and_path():
    doc = parse_law(SAMPLE, "예시법", "예시법")
    jo = next(j for j in doc.jos() if j.number == "10의2")
    text = jo.render()
    assert text.startswith("제10조의2(특칙)")
    assert "② 다음 각 호" in text and "2의2. 가지 호" in text and "가. 첫째 목" in text
    mok = next(n for n in doc.nodes() if n.id.endswith(":M가"))
    assert mok.path("예시법") == "예시법 › 제1장 총칙 › 제10조의2(특칙) › 제2항 › 제2호의2 › 가목"


def test_deleted_article():
    doc = parse_law(SAMPLE, "예시법", "예시법")
    assert next(j for j in doc.jos() if j.number == "11").deleted


def test_real_immigration_act(laws_dir):
    raw = load_file(laws_dir / "출입국관리법" / "법률.md")
    assert raw.id == "출입국관리법" and raw.meta["doc_type"] == "law"
    doc = parse_law(raw.text, raw.id, raw.meta["title_ko"])
    by_id = {n.id: n for n in doc.nodes()}
    assert "체류기간 연장허가" in by_id["출입국관리법:J25"].heading
    assert "출입국관리법:J25-2:H1:O4" in by_id
    assert len(doc.jos()) > 150


def test_all_loaded_laws_parse(laws_dir):
    for path in sorted(laws_dir.glob("*/*.md")):
        raw = load_file(path)
        doc = parse_law(raw.text, raw.id, raw.meta["title_ko"])
        assert doc.jos(), path
        assert raw.meta["status"] == "in_force", path
