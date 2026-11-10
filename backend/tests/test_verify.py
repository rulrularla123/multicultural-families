from app.generation.verify import ProvisionInfo, check_citation, normalize_provision_id, quote_in_text

TEXT = "① 외국인이 체류기간을 초과하여 계속 체류하려면 대통령령으로 정하는 바에 따라 체류기간이 끝나기 전에 법무부장관의 체류기간 연장허가를 받아야 한다."


def test_normalize_ids():
    assert normalize_provision_id("출입국관리법:제25조제1항") == "출입국관리법:J25:H1"
    assert normalize_provision_id("출입국관리법:J10의2") == "출입국관리법:J10-2"
    assert normalize_provision_id("[출입국관리법:J25:H1]") == "출입국관리법:J25:H1"


def test_quote_with_ellipsis():
    assert quote_in_text("체류기간이 끝나기 전에 … 연장허가를 받아야 한다", TEXT)
    assert not quote_in_text("체류기간이 끝난 후에", TEXT)


def test_check_citation():
    info = ProvisionInfo("출입국관리법:J25:H1", TEXT, "출입국관리법:J25", TEXT, True)
    assert check_citation("출입국관리법:J25:H1", "연장허가를 받아야 한다", info).ok
    assert check_citation("출입국관리법:J25:H1", "없는 문장", info).reason
    assert not check_citation("없는:J1", "x", None).ok
