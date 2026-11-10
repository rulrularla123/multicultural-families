from app.retrieval.pipeline import MAX_SANCTION, ContextItem, add_sanctions

LAW = "출입국관리법"


def item(pid: str, score: float, source: str = "search") -> ContextItem:
    return ContextItem(pid, LAW, LAW, None, "law", pid, "본문", None, None, "in_force", score, source)


def test_sanction_replaces_lowest_scored_when_full():
    selected = [item(f"{LAW}:J{n}", 1.0 - n / 100) for n in range(30, 40)]
    out = add_sanctions(selected, [item(f"{LAW}:J98", 0.0, "sanction")], context_k=10)
    ids = [i.provision_id for i in out]
    assert len(out) == 10
    assert f"{LAW}:J98" in ids
    assert f"{LAW}:J39" not in ids  # 점수가 가장 낮은 조가 빠진다


def test_sanction_limit_and_no_duplicates():
    selected = [item(f"{LAW}:J36", 1.0), item(f"{LAW}:J98", 0.5)]
    extra = [item(f"{LAW}:J98", 0.0), item(f"{LAW}:J99", 0.0), item(f"{LAW}:J100", 0.0), item(f"{LAW}:J101", 0.0)]
    out = add_sanctions(selected, extra, context_k=10)
    ids = [i.provision_id for i in out]
    assert ids.count(f"{LAW}:J98") == 1
    assert len(ids) == 2 + MAX_SANCTION
