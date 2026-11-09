from app.generation.numbers import check_numbers, extract_numbers


def test_extract_korean_and_vietnamese_units():
    got = {(c.unit, tuple(c.values)) for c in extract_numbers("14일 이내, 3 năm, 100 triệu won, 1억원, 6 tháng")}
    assert got == {("days", (14.0,)), ("years", (3.0,)), ("krw", (100_000_000.0,)), ("months", (6.0,))}


def test_number_check_against_provision():
    src = [("출입국관리법:J36", "체류지를 변경한 날부터 15일 이내에 전입신고를 하여야 한다.")]
    ok, bad = check_numbers("Trong vòng 15 ngày (15일 이내). Không phải 14 ngày.", src)[:2]
    assert ok.status == "verified" and ok.provision_id == "출입국관리법:J36"
    assert bad.status == "not_found" and bad.missing == [14]
