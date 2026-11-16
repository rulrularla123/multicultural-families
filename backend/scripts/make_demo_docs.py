"""시연용 가상 안내문 DOCX를 만든다. 실제 기관 문서·개인정보가 아니다.

demo-extension-supplement-notice.docx는 시연 때 직접 올리는 서류다. 식별정보 마스킹을 보여 주려고
형식만 맞춘 가짜 번호(등록번호·여권번호·전화번호)를 넣었다. 실제 사람의 번호가 아니다.

    python scripts/make_demo_docs.py   → data/demo/*.docx
"""

from pathlib import Path

from docx import Document

OUT = Path(__file__).resolve().parents[1] / "data" / "demo"

DOCS = {
    "demo-extension-supplement-notice.docx": (
        "체류기간 연장허가 신청 서류 보완 요청 (가상 시연용)",
        [
            "이 문서는 서비스 시연을 위한 가상 문서입니다. 기관명·사람·번호는 모두 지어낸 것입니다.",
            "발신: 가상 출입국·외국인사무소 체류관리과",
            "수신: 응우옌 티 란 (가상 인물)",
            "외국인등록번호: 950312-6000001 / 여권번호: M00000001 / 연락처: 010-0000-0001",
            "1. 신청 내용: 결혼이민(F-6-1) 체류기간 연장허가 신청 (접수일 2026. 11. 10.)",
            "2. 현재 체류기간 만료일: 2026. 12. 5.",
            "3. 보완 요청 사유: 제출하신 서류 중 아래 서류가 빠져 있어 심사를 진행할 수 없습니다.",
            "  가. 배우자의 혼인관계증명서(상세) 1부",
            "  나. 체류지 입증서류(임대차계약서 사본 등) 1부",
            "4. 보완 기한: 2026. 11. 27.까지 방문 또는 하이코리아 전자민원으로 제출하십시오.",
            "5. 기한 안에 보완하지 않으면 제출된 서류만으로 심사하며, 연장이 허가되지 않을 수 있습니다. "
            "허가되지 않으면 출국기한을 정하여 통지합니다.",
            "6. 수수료: 체류기간 연장허가 수수료 3만원은 접수 시 이미 납부되었습니다.",
            "7. 그 밖에: 체류지가 바뀐 경우 전입한 날부터 15일 이내에 체류지 변경신고를 하여야 합니다.",
            "8. 문의: 외국인종합안내센터 ☎1345 (베트남어 상담 가능)",
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
