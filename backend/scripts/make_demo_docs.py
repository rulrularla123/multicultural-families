"""시연용 가상 안내문 DOCX를 만든다. 실제 기관 문서·개인정보가 아니다.

    python scripts/make_demo_docs.py   → data/demo/*.docx
"""

from pathlib import Path

from docx import Document

OUT = Path(__file__).resolve().parents[1] / "data" / "demo"

DOCS = {
    "sample-extension-guide.docx": (
        "체류기간 연장허가 신청 안내 (예시)",
        [
            "이 문서는 서비스 시연을 위한 가상 안내문이며 실제 기관이 발급한 문서가 아닙니다.",
            "1. 대상: 결혼이민(F-6-1) 체류자격으로 체류 중인 외국인",
            "2. 체류기간 만료일: 2026. 12. 20.",
            "3. 신청 기한: 체류기간이 끝나기 전까지 연장허가를 신청하여야 합니다. 만료일이 지난 뒤에 신청하면 체류기간 초과로 범칙금이 부과될 수 있습니다.",
            "4. 제출 서류: 통합신청서, 여권, 외국인등록증, 수수료, 혼인관계증명서(배우자 기준), 체류지 입증서류, 배우자의 신원보증서",
            "5. 추가 확인: 부부가 함께 살고 있는지, 가족을 부양할 소득이 있는지 확인할 수 있습니다. 필요하면 추가 서류를 요청합니다.",
            "6. 신청 방법: 하이코리아에서 방문 예약 후 관할 출입국·외국인관서를 방문하거나 전자민원으로 신청합니다.",
            "7. 문의: 외국인종합안내센터 ☎1345 (베트남어 상담 가능)",
        ],
    ),
    "sample-address-change-notice.docx": (
        "체류지 변경신고 안내 (예시)",
        [
            "이 문서는 서비스 시연을 위한 가상 안내문이며 실제 기관이 발급한 문서가 아닙니다.",
            "1. 외국인등록을 한 사람이 체류지를 변경한 때에는 새로운 체류지로 전입한 날부터 15일 이내에 전입신고를 하여야 합니다.",
            "2. 신고 장소: 새 체류지의 시·군·구 또는 읍·면·동 주민센터, 관할 출입국·외국인관서",
            "3. 준비물: 외국인등록증, 체류지 입증서류(임대차계약서 등)",
            "4. 기한 안에 신고하지 않으면 과태료가 부과될 수 있습니다.",
            "5. 문의: 외국인종합안내센터 ☎1345",
        ],
    ),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (title, paras) in DOCS.items():
        doc = Document()
        doc.add_heading(title, level=1)
        for p in paras:
            doc.add_paragraph(p)
        doc.save(OUT / name)
        print(OUT / name)


if __name__ == "__main__":
    main()
