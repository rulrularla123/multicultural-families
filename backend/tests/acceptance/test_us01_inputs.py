"""US-01 경계값 입력 fixture 자체 점검.

생성 API 테스트는 API.md 항목 1(경로·필드 이름·오류 형식) 합의 뒤에 추가한다.
여기서는 입력이 인수 조건의 값과 정확히 맞는지만 확인한다. DB를 쓰지 않는다.
"""
PDF_SIGNATURE = b"%PDF-"


def test_us01_pdf_at_limit_is_exactly_10485760_bytes(pdf_at_limit):
    name, content, _ = pdf_at_limit
    assert name.endswith(".pdf")
    assert len(content) == 10_485_760
    assert content.startswith(PDF_SIGNATURE)


def test_us01_pdf_over_limit_is_exactly_10485761_bytes(pdf_over_limit):
    _, content, _ = pdf_over_limit
    assert len(content) == 10_485_761
    assert content.startswith(PDF_SIGNATURE)


def test_us01_fake_pdf_has_pdf_extension_but_no_signature(fake_pdf):
    name, content, _ = fake_pdf
    assert name.endswith(".pdf")
    assert not content.startswith(PDF_SIGNATURE)


def test_us01_non_pdf_extension_file(non_pdf_extension):
    name, _, _ = non_pdf_extension
    assert not name.endswith(".pdf")


def test_us01_file_count_bundles_have_0_1_5_6_files(pdf_files):
    assert [len(pdf_files(n)) for n in (0, 1, 5, 6)] == [0, 1, 5, 6]
    assert all(content.startswith(PDF_SIGNATURE) for _, content, _ in pdf_files(6))


def test_us01_situation_lengths_are_1_1000_1001_characters(situations):
    assert {n: len(s) for n, s in situations.items()} == {1: 1, 1000: 1000, 1001: 1001}
    # 공백·줄바꿈이 없어 세는 방법을 정하기 전에도 길이가 같다.
    assert not any(c.isspace() for c in situations[1001])


def test_us01_counted_situations_count_spaces_but_not_newlines(counted_situations):
    def count(s):
        return len(s.replace("\n", ""))

    assert {k: count(s) for k, s in counted_situations.items()} == {
        "1000_with_spaces": 1000, "1001_with_spaces": 1001, "1000_plus_newlines": 1000,
    }
    assert len(counted_situations["1000_plus_newlines"]) == 1002


def test_us01_blank_situations_contain_only_whitespace(blank_situations):
    assert all(s.strip() == "" for s in blank_situations)
    assert any("\n" in s for s in blank_situations)
