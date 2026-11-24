from datetime import date

import httpx
import pytest

from ingest.sources import legalize_kr


@pytest.mark.parametrize(("failure", "reason"), [
    ("latest", "500"),
    ("timeout", "요청 시간 초과"),
    ("commits", "503"),
    ("revision", "502"),
])
def test_fetch_skips_failed_family_and_preserves_existing_files(tmp_path, monkeypatch, caplog, failure, reason):
    failed = "실패법"
    healthy = "후속법"
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith(f"/main/kr/{failed}/법률.md"):
            return httpx.Response(200, text="수집 중 받은 새 원문")
        if request.url.path.endswith(f"/main/kr/{failed}/시행령.md"):
            if failure == "latest":
                return httpx.Response(500)
            if failure == "timeout":
                raise httpx.ReadTimeout(reason, request=request)
            return httpx.Response(200, text="시행일자: 2027-01-01\n")
        if request.url.path.endswith("/commits"):
            if failure == "commits":
                return httpx.Response(503)
            return httpx.Response(200, json=[{"sha": "new"}, {"sha": "old"}])
        if request.url.path.endswith(f"/old/kr/{failed}/시행령.md"):
            return httpx.Response(502)
        if request.url.path.endswith(f"/main/kr/{healthy}/법률.md"):
            return httpx.Response(200, text="후속 법령 원문")
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(legalize_kr.httpx, "Client", lambda **kwargs: client)
    existing = tmp_path / failed / "법률.md"
    existing.parent.mkdir()
    existing.write_text("기존 원문", encoding="utf-8")

    written = legalize_kr.fetch([failed, healthy], tmp_path, today=date(2026, 11, 24))

    healthy_path = tmp_path / healthy / "법률.md"
    assert written == [healthy_path]
    assert healthy_path.read_text(encoding="utf-8") == "후속 법령 원문"
    assert existing.read_text(encoding="utf-8") == "기존 원문"
    assert not any(path.endswith(f"/main/kr/{failed}/시행규칙.md") for path in requests)
    warnings = caplog.messages
    assert len(warnings) == 1
    assert failed in warnings[0] and reason in warnings[0]
