from app.generation.citations import align_citations


def test_renumbers_by_first_appearance_and_matches_marker():
    # 모델이 목록을 본문과 다른 순서로 준 경우: marker로 짝을 지어야 한다
    text = "신고 기한은 15일입니다 [2]. 서류는 계약서입니다 [1]."
    out, items = align_citations(text, [(1, "계약서 조문"), (2, "기한 조문")])
    assert out == "신고 기한은 15일입니다 [1]. 서류는 계약서입니다 [2]."
    assert items == ["기한 조문", "계약서 조문"]


def test_drops_unused_citations_and_orphan_markers():
    text = "답 [1][3]. 다른 문장 [4]."
    out, items = align_citations(text, [(1, "a"), (2, "안 씀"), (3, "c")])
    assert out == "답 [1][2]. 다른 문장."
    assert items == ["a", "c"]


def test_repeated_marker_keeps_one_entry():
    out, items = align_citations("A [1]. B [1]. C [2].", [(1, "x"), (1, "중복"), (2, "y")])
    assert out == "A [1]. B [1]. C [2]."
    assert items == ["x", "y"]
