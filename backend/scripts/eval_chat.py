"""체류 질문 평가셋 실행기: 질문마다 인용 검증 통과율·숫자 검증·속도·비용을 기록한다.

실행 중인 서버(POST /api/v1/chat)를 부른다. 정답 여부는 자동으로 판정하지 않고, 사람이 채울 칸을 남긴다.

    .venv/bin/python scripts/eval_chat.py data/eval/cases.json --out eval-out/2026-11-10
    (서버 주소를 바꾸려면 --base http://127.0.0.1:8000)

결과: <out>/results.csv (사례별), <out>/summary.md (합계), <out>/answers.jsonl (응답 원문).
/health의 llm_fake가 참이면 결과 위에 "개발용 가짜 응답 — 품질 평가 아님"을 붙인다.
"""

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

FIELDS = [
    "id", "lang", "message", "http_status", "latency_s", "citations", "verified", "citation_pass_rate",
    "unverified_ids", "expected_provisions", "expected_hit", "number_checks", "numbers_not_found",
    "confidence", "needs_expert", "mentions_1345", "input_tokens", "output_tokens", "cost_usd", "error",
    "판정(정답/부분/오답)", "메모",
]


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise SystemExit("사례 id가 중복됨")
    for c in cases:
        if not 1 <= len(c["message"]) <= 1000:
            raise SystemExit(f"{c['id']}: 질문은 1~1,000자")
        if c.get("lang", "vi") not in ("vi", "ko"):
            raise SystemExit(f"{c['id']}: lang은 vi 또는 ko")
    return cases


def run_case(client: httpx.Client, case: dict) -> tuple[dict, dict | None]:
    row = {k: "" for k in FIELDS}
    row |= {"id": case["id"], "lang": case.get("lang", "vi"), "message": case["message"]}
    expected = case.get("expected_provisions") or []
    row["expected_provisions"] = " ".join(expected)
    started = time.perf_counter()
    try:
        r = client.post("/api/v1/chat", json={"message": case["message"], "lang": row["lang"]})
    except httpx.HTTPError as e:
        row |= {"http_status": "", "latency_s": round(time.perf_counter() - started, 2), "error": repr(e)}
        return row, None
    row["latency_s"] = round(time.perf_counter() - started, 2)
    row["http_status"] = r.status_code
    if r.status_code != 200:
        row["error"] = r.text[:300]
        return row, None
    body = r.json()
    cits = body.get("citations") or []
    verified = [c for c in cits if c.get("verified")]
    cited_ids = {c["provision_id"] for c in cits}
    numbers = body.get("number_checks") or []
    usage = body.get("usage") or {}
    row |= {
        "citations": len(cits),
        "verified": len(verified),
        "citation_pass_rate": round(len(verified) / len(cits), 3) if cits else "",
        "unverified_ids": " ".join(c["provision_id"] for c in cits if not c.get("verified")),
        "expected_hit": (f"{sum(e in cited_ids for e in expected)}/{len(expected)}" if expected else ""),
        "number_checks": len(numbers),
        "numbers_not_found": sum(n.get("status") == "not_found" for n in numbers),
        "confidence": body.get("confidence", ""),
        "needs_expert": body.get("needs_expert", ""),
        "mentions_1345": "1345" in json.dumps(body, ensure_ascii=False),
        "input_tokens": usage.get("input_tokens", ""),
        "output_tokens": usage.get("output_tokens", ""),
        "cost_usd": usage.get("cost_usd", ""),
    }
    return row, body


def summarize(rows: list[dict], health: dict, cases_path: Path) -> str:
    ok = [r for r in rows if r["http_status"] == 200]
    lat = sorted(r["latency_s"] for r in rows if r["latency_s"] != "")
    cits = sum(r["citations"] for r in ok)
    ver = sum(r["verified"] for r in ok)
    costs = [r["cost_usd"] for r in ok if r["cost_usd"] != ""]
    no_cite = [r["id"] for r in ok if r["citations"] == 0]
    lines = []
    if health.get("llm_fake"):
        lines += ["> **개발용 가짜 응답(LLM_FAKE) — 품질 평가 아님.** 도구 동작만 확인한 결과다.", ""]
    lines += [
        "# 체류 질문 평가 결과",
        "",
        f"- 사례 파일: `{cases_path}`",
        f"- 서버 상태: 법령 {health.get('documents')}개, 조문 {health.get('provisions')}개, "
        f"임베딩 {health.get('embedded')}개, llm_fake={health.get('llm_fake')}",
        "",
        "| 항목 | 값 |",
        "| --- | --- |",
        f"| 사례 수 | {len(rows)} (성공 {len(ok)}, 실패 {len(rows) - len(ok)}) |",
        f"| 인용 검증 통과율 | {ver}/{cits}" + (f" ({ver / cits:.1%})" if cits else "") + " |",
        f"| 인용 없는 답변 | {len(no_cite)}건 {' '.join(no_cite)} |",
        f"| 숫자 검증 실패 | {sum(r['numbers_not_found'] for r in ok)}건 |",
        f"| 전문가 상담 표시 | {sum(r['needs_expert'] is True for r in ok)}건 |",
        f"| 응답 시간 중앙값 / 최대 | {statistics.median(lat):.2f}초 / {lat[-1]:.2f}초 |" if lat else "| 응답 시간 | - |",
        f"| 비용 합계 | ${sum(costs):.4f} ({len(costs)}건 집계) |" if costs else "| 비용 합계 | 기록 없음 |",
        "",
        "정답 여부(오답 수)는 `results.csv`의 판정 칸을 사람이 원문과 대조해 채운 뒤 센다.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cases", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--timeout", type=float, default=120)
    args = p.parse_args(argv)

    cases = load_cases(args.cases)
    args.out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=args.base, timeout=args.timeout) as client:
        health = client.get("/health").json()
        rows = []
        with (args.out / "answers.jsonl").open("w", encoding="utf-8") as raw:
            for case in cases:
                row, body = run_case(client, case)
                rows.append(row)
                raw.write(json.dumps({"id": case["id"], "response": body}, ensure_ascii=False, default=str) + "\n")
                print(f"{row['id']}: HTTP {row['http_status']} {row['latency_s']}초 "
                      f"인용 {row['verified']}/{row['citations']}", file=sys.stderr)
    with (args.out / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    (args.out / "summary.md").write_text(summarize(rows, health, args.cases), encoding="utf-8")
    print((args.out / "summary.md").read_text(encoding="utf-8"))
    return 0 if all(r["http_status"] == 200 for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
