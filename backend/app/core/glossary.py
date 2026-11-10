"""베트남어 → 한국 출입국·체류 법령 용어 대역 사전.

질의 재작성 프롬프트에 넣어서 베트남어(또는 다른 언어) 질문이 한국 법령 용어로 검색되게 한다.
"""

TERMS: list[tuple[str, str]] = [
    # 체류자격·체류기간
    ("thị thực kết hôn / visa F-6 (kết hôn di trú)", "결혼이민(F-6) 체류자격"),
    ("tư cách lưu trú", "체류자격"),
    ("gia hạn thời gian lưu trú", "체류기간 연장허가"),
    ("thời hạn lưu trú hết hạn / quá hạn", "체류기간 만료 / 체류기간 초과"),
    ("thay đổi tư cách lưu trú", "체류자격 변경허가"),
    ("cấp tư cách lưu trú (cho con sinh ở Hàn Quốc)", "체류자격 부여"),
    ("hoạt động ngoài tư cách lưu trú / làm thêm", "체류자격 외 활동허가"),
    ("thay đổi, bổ sung nơi làm việc", "근무처의 변경·추가"),
    ("thường trú / visa F-5", "영주자격(F-5)"),
    # 등록·신고
    ("đăng ký người nước ngoài", "외국인등록"),
    ("thẻ đăng ký người nước ngoài (thẻ cư trú)", "외국인등록증"),
    ("khai báo thay đổi nơi cư trú / chuyển nhà", "체류지 변경신고"),
    ("khai báo thay đổi thông tin đăng ký (hộ chiếu mới)", "외국인등록사항 변경신고"),
    ("thời hạn khai báo (trong vòng 14 ngày / 15 ngày)", "신고 기한"),
    # 혼인·가족
    ("vợ/chồng là người Hàn Quốc", "국민의 배우자"),
    ("ly hôn / ly thân", "이혼 / 별거"),
    ("chồng/vợ mất tích, bị bạo hành gia đình", "배우자의 사망·실종, 가정폭력"),
    ("nuôi con chưa thành niên", "미성년 자녀 양육"),
    ("gia đình đa văn hóa", "다문화가족"),
    ("người nhập cư theo diện kết hôn", "결혼이민자"),
    ("chương trình hội nhập xã hội (KIIP)", "사회통합프로그램"),
    ("bảo lãnh / người bảo lãnh", "신원보증 / 신원보증인"),
    # 출국·제재
    ("xuất cảnh / tái nhập cảnh", "출국 / 재입국허가"),
    ("lệnh trục xuất / buộc xuất cảnh", "강제퇴거 / 출국명령"),
    ("phạt tiền (vi phạm hành chính)", "과태료 / 범칙금"),
    ("cấm nhập cảnh", "입국금지"),
    # 국적
    ("nhập quốc tịch Hàn Quốc", "귀화허가"),
    ("nhập quốc tịch giản lược (diện kết hôn)", "간이귀화"),
    ("thi nhập quốc tịch / phỏng vấn", "귀화 필기시험 / 면접심사"),
    # 서류·절차
    ("giấy chứng nhận quan hệ hôn nhân", "혼인관계증명서"),
    ("giấy chứng nhận quan hệ gia đình", "가족관계증명서"),
    ("giấy xác nhận cư trú", "주민등록등본"),
    ("chứng minh thu nhập / khả năng tài chính", "소득 요건 / 재정능력 입증서류"),
    ("hồ sơ xin phép / đơn đề nghị", "신청서 / 제출서류"),
    ("lệ phí", "수수료"),
    ("Cục xuất nhập cảnh địa phương", "지방출입국·외국인관서"),
]


def glossary_text() -> str:
    return "\n".join(f"- {vi} → {ko}" for vi, ko in TERMS)
