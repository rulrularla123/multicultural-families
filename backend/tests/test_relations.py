from ingest.relations.patterns import AliasIndex, DocContext, extract_local_refs, extract_refs
from ingest.relations.resolver import DocMeta, SourceProvision, resolve_edges, target_id

ALIASES = AliasIndex({"출입국관리법": "출입국관리법", "국적법": "국적법"})
LAW = DocContext("출입국관리법")
DECREE = DocContext("출입국관리법시행령", parent_law="출입국관리법")
RULE = DocContext("출입국관리법시행규칙", parent_law="출입국관리법", parent_decree="출입국관리법시행령")


def refs(text, ctx=LAW):
    return [(r.target_doc, r.jo, r.hang, r.ho, r.mok) for r in extract_refs(text, ctx, ALIASES)]


def test_same_document_reference():
    assert refs("제46조제1항 각 호의 어느 하나") == [(None, "46", "1", None, None)]
    assert refs("제4조제1항제3호가목") == [(None, "4", "1", "3", "가")]
    assert refs("제93조의2, 제93조의3") == [(None, "93-2", None, None, None), (None, "93-3", None, None, None)]


def test_range():
    assert [r[1] for r in refs("제94조부터 제96조까지")] == ["94", "95", "96"]


def test_external_and_same_law():
    out = refs("「국적법」 제6조제2항 및 같은 법 제7조")
    assert out == [("국적법", "6", "2", None, None), ("국적법", "7", None, None, None)]
    assert refs("「형법」 제127조 및 제129조부터 제130조까지") == [
        ("?형법", "127", None, None, None), ("?형법", "129", None, None, None), ("?형법", "130", None, None, None),
    ]


def test_parent_law_and_decree():
    assert refs("법 제25조에 따른 체류기간 연장허가", DECREE) == [("출입국관리법", "25", None, None, None)]
    assert refs("영 제31조제1항", RULE) == [("출입국관리법시행령", "31", "1", None, None)]
    assert refs("이 영 제2조", DECREE) == [(None, "2", None, None, None)]


def test_local_refs():
    assert extract_local_refs("제1항에 따른 허가") == [("1", None, "제1항")]
    assert extract_local_refs("같은 조 제3항제2호") == [("3", "2", "같은 조 제3항제2호")]


def test_target_falls_back_to_article():
    known = {"출입국관리법:J25", "출입국관리법:J25:H1"}
    assert target_id("출입국관리법", "25", "1", "3", None, known) == "출입국관리법:J25:H1"
    assert target_id("출입국관리법", "25", "2", None, None, known) == "출입국관리법:J25"
    assert target_id("출입국관리법", "99", None, None, None, known) is None


def test_resolve_guides_and_unresolved():
    docs = [DocMeta("출입국관리법", "출입국관리법", ()),
            DocMeta("출입국관리법시행령", "출입국관리법 시행령", (), parent_law="출입국관리법")]
    known = {"출입국관리법:J25", "출입국관리법시행령:J31", "출입국관리법시행령:J31:H1"}
    provs = [SourceProvision("출입국관리법시행령:J31:H1", "출입국관리법시행령", "출입국관리법시행령:J31",
                             "법 제25조에 따른 연장허가와 「형법」 제1조")]
    edges, unresolved = resolve_edges(provs, docs, known)
    assert [(e.dst_id, e.rel) for e in edges] == [("출입국관리법:J25", "GUIDES")]
    assert unresolved[0].reason == "대상 법령 미적재: 형법"
