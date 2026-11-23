"""적재 CLI

  python -m ingest fetch [법령 …]                  # legalize-kr에서 법령 마크다운 받기 (기본: 체류 관련 4개 법령)
  python -m ingest check data/laws                 # DB 없이 파싱·관계 추출 결과만 확인
  python -m ingest load data/laws [--samples]      # 문서·조문·청크 적재 + 관계 재구성
  python -m ingest summarize --lang vi             # 한국어 요약 → NMT 베트남어 번역 (+ 이후 embed)
  python -m ingest embed                           # 임베딩이 없는 청크 임베딩
  python -m ingest all data/laws [--samples]       # load → summarize(vi) → embed
  python -m ingest review <문서ID> --by 이름 [--note 메모] [--unset]  # 사람 검토 기록
  python -m ingest review --list                   # 검토/미검토 현황
  python -m ingest versions [--strict]             # 적재한 판이 지금 시행 중인 최신 판인지 확인·저장
  python -m ingest sync [data/laws] [--dry-run]    # 확인 후 새 판이 시행 중인 법령만 받기·재적재·요약·임베딩
"""

import argparse
import asyncio
import logging
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from ingest.loader import discover


def cmd_check(args) -> None:
    from ingest.parsers.structure import parse_law
    from ingest.pipeline import doc_metas, source_provisions
    from ingest.relations.resolver import resolve_edges

    docs = discover(Path(args.root), include_samples=args.samples)
    provisions = []
    rows_doc, rows_rel = [], []
    for raw in docs:
        m = raw.meta
        parsed = parse_law(raw.text, raw.id, m["title_ko"])
        levels = Counter(n.level for n in parsed.nodes())
        print(f"■ {raw.id}  {m['title_ko']}  (시행 {m['effective_from']}, {m['status']})")
        print(f"  조 {levels['jo']} · 항 {levels['hang']} · 호 {levels['ho']} · 목 {levels['mok']} · 장 {levels['jang']}")
        for w in parsed.warnings:
            print(f"  ⚠ {w}")
        rows_doc.append(SimpleNamespace(id=raw.id, doc_type=m["doc_type"], title_ko=m["title_ko"],
                                        short_names=m["short_names"]))
        rows_rel += [SimpleNamespace(src_doc=raw.id, dst_doc=g, rel="GUIDES") for g in m["guides"]]
        rows = [SimpleNamespace(id=n.id, document_id=raw.id, jo_id=(n.jo().id if n.jo() else None),
                                parent_id=n.parent.id if n.parent else None, level=n.level, heading=n.heading,
                                text_ko=n.text) for n in parsed.nodes()]
        provisions.extend(source_provisions(rows))

    edges, unresolved = resolve_edges(provisions, doc_metas(rows_doc, rows_rel), {p.id for p in provisions})
    print(f"\n관계 {len(edges)}개: {dict(Counter(e.rel for e in edges))}")
    for e in edges[: args.show]:
        print(f"  {e.src_id} -[{e.rel}]-> {e.dst_id}   «{e.evidence}»")
    print(f"미해결 참조 {len(unresolved)}개: {dict(Counter(u.reason.split(':')[0] for u in unresolved))}")
    for u in unresolved[: args.show]:
        print(f"  {u.src_id}: {u.reason}   «{u.evidence}»")


async def _review(session, args) -> None:
    from ingest import pipeline

    if args.list or not args.doc_id:
        docs = await pipeline.list_reviews(session)
        done = [d for d in docs if d.reviewed]
        print(f"검토 완료 {len(done)} · 미검토 {len(docs) - len(done)} (샘플 제외 {len(docs)}건)")
        for d in docs:
            mark = "✔" if d.reviewed else "·"
            who = f"  {d.reviewed_by} {d.reviewed_at:%Y-%m-%d}" if d.reviewed and d.reviewed_at else ""
            note = f"  «{d.review_note}»" if d.review_note else ""
            print(f"  {mark} {d.id}  {d.title_ko[:60]}{who}{note}")
        return
    if not args.unset and not args.by:
        raise SystemExit("--by 이름을 지정하세요")
    try:
        d = await pipeline.set_review(session, args.doc_id, args.by, args.note, unset=args.unset)
    except LookupError as e:
        raise SystemExit(str(e)) from None
    state = f"검토 완료 ({d.reviewed_by}, {d.reviewed_at:%Y-%m-%d %H:%M})" if d.reviewed else "검토 해제"
    print(f"{d.id}: {state}")


VERSION_LABEL = {
    "current": "최신 판",
    "upcoming": "최신 판 (시행 예정 개정 있음)",
    "outdated": "새 판이 시행 중 → fetch·load 필요",
    "unknown": "확인 못 함",
}


async def _versions(session, args) -> None:
    from app.core.lang import today_kr
    from ingest import pipeline

    results = await pipeline.check_versions(session, today_kr())
    for r in results:
        extra = f"  시행 예정 {r.upcoming_effective_from} (MST {r.upcoming_mst})" if r.upcoming_mst else ""
        reason = f"  «{r.reason}»" if r.reason else ""
        print(f"  [{r.status}] {r.document_id}: {VERSION_LABEL[r.status]} · {r.source}{extra}{reason}")
    outdated = [r for r in results if r.status == "outdated"]
    unknown = [r for r in results if r.status == "unknown"]
    print(f"확인 {len(results)}건 · 새 판 시행 중 {len(outdated)} · 확인 못 함 {len(unknown)}")
    if args.strict and (outdated or unknown):
        raise SystemExit(1)


async def _sync(session, args) -> None:
    from app.core.lang import today_kr
    from ingest import pipeline

    r = await pipeline.sync_versions(session, Path(args.root), today_kr(), dry_run=args.dry_run)
    for c in r["checked"]:
        print(f"  [{c.status}] {c.document_id}: {VERSION_LABEL[c.status]} · {c.source}")
    if r["reindexed"]:
        print(f"요약·임베딩 새로 만듦: {', '.join(r['reindexed'])} (요약 {r['summarized']}개 · 임베딩 {r['embedded']}개)")
    if r["pending_reindex"]:
        print(f"요약·임베딩 대기: {', '.join(r['pending_reindex'])} (LLM_FAKE=true. 실제 키로 다시 실행하면 채움)")
    if not r["changed"]:
        print("새 판이 시행 중인 법령이 없습니다.")
    elif args.dry_run:
        print(f"새 판 시행 중 {len(r['changed'])}건 (--dry-run이라 받지 않음): {', '.join(r['changed'])}")
    else:
        print(f"새 판 시행 중 {len(r['changed'])}건 → 재적재 {len(r['reloaded'])}건: {', '.join(r['reloaded']) or '없음'}")
        if r["still_outdated"]:
            print(f"아직 옛 판: {', '.join(r['still_outdated'])} (legalize-kr에 새 판이 아직 반영되지 않았을 수 있음)")
    if args.strict and (r["still_outdated"] or any(c.status == "unknown" for c in r["checked"])):
        raise SystemExit(1)


async def _run(args) -> None:
    from app.core.db import SessionLocal
    from ingest import pipeline

    async with SessionLocal() as session:
        if args.cmd == "review":
            await _review(session, args)
            return
        if args.cmd == "versions":
            await _versions(session, args)
            return
        if args.cmd == "sync":
            await _sync(session, args)
            return
        if args.cmd in ("load", "all"):
            docs = discover(Path(args.root), include_samples=args.samples)
            await pipeline.load_documents(session, docs, force=args.force)
            await pipeline.rebuild_relations(session)
        if args.cmd == "relations":
            await pipeline.rebuild_relations(session)
        if args.cmd == "summarize" or (args.cmd == "all" and not args.no_summary):
            await pipeline.summarize_missing(session, lang=getattr(args, "lang", "vi"))
        if args.cmd in ("embed", "all", "summarize"):
            await pipeline.embed_missing(session)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="python -m ingest")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fetch", help="legalize-kr에서 법령 받기")
    s.add_argument("laws", nargs="*")
    s.add_argument("--out", default="data/laws")
    for name in ("check", "load", "all"):
        s = sub.add_parser(name)
        s.add_argument("root", nargs="?", default="data/laws")
        s.add_argument("--samples", action="store_true", help="'_'로 시작하는 샘플 폴더도 포함")
        if name == "check":
            s.add_argument("--show", type=int, default=30)
        else:
            s.add_argument("--force", action="store_true", help="원문이 같아도 다시 적재")
        if name == "all":
            s.add_argument("--no-summary", action="store_true")
    sub.add_parser("relations")
    sub.add_parser("embed")
    s = sub.add_parser("summarize")
    s.add_argument("--lang", default="vi", choices=["vi", "ko"])
    s = sub.add_parser("review", help="법령 문서 사람 검토 기록")
    s.add_argument("doc_id", nargs="?")
    s.add_argument("--by", help="검토자 이름")
    s.add_argument("--note")
    s.add_argument("--unset", action="store_true", help="검토 기록 해제")
    s.add_argument("--list", action="store_true", help="검토 현황 목록")
    s = sub.add_parser("versions", help="적재한 법령이 최신 판인지 확인 (LAW_GO_KR_OC가 있으면 국가법령정보센터 기준)")
    s.add_argument("--strict", action="store_true", help="새 판이 시행 중이거나 확인하지 못한 법령이 있으면 종료 코드 1")
    s = sub.add_parser("sync", help="최신 판 확인 → 바뀐 법령만 받기·재적재·요약·임베딩")
    s.add_argument("root", nargs="?", default="data/laws")
    s.add_argument("--dry-run", action="store_true", help="확인만 하고 받지 않음")
    s.add_argument("--strict", action="store_true", help="동기화 뒤에도 옛 판이거나 확인하지 못한 법령이 있으면 종료 코드 1")

    args = p.parse_args()
    if args.cmd == "fetch":
        from ingest.sources.legalize_kr import DEFAULT_LAWS, fetch

        written = fetch(args.laws or DEFAULT_LAWS, Path(args.out))
        print(f"{len(written)}개 파일 저장 → {args.out}")
    elif args.cmd == "check":
        cmd_check(args)
    else:
        asyncio.run(_run(args))


if __name__ == "__main__":
    main()
