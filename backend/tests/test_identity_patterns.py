import pytest

from app.common.identity_patterns import IdentityKind, find_kinds, mask


@pytest.mark.parametrize("text, kind", [
    ("등록번호 900101-5123456", IdentityKind.REGISTRATION),
    ("9001015123456", IdentityKind.REGISTRATION),
    ("여권 M12345678", IdentityKind.PASSPORT),
    ("연락처 010-1234-5678", IdentityKind.MOBILE_PHONE),
    ("01012345678", IdentityKind.MOBILE_PHONE),
])
def test_detects(text, kind):
    assert find_kinds(text) == [kind]


@pytest.mark.parametrize("text", ["2026-11-09", "제25조제1항", "F-6-1 체류자격", "02-123-4567", "900101-9123456"])
def test_ignores_non_identifiers(text):
    assert find_kinds(text) == []


def test_mask_removes_values():
    masked, n = mask("번호 900101-5123456, 여권 M12345678, 010 1234 5678")
    assert n == 3
    assert "5123456" not in masked and "M12345678" not in masked and "1234" not in masked
    assert "[등록번호 가림]" in masked
