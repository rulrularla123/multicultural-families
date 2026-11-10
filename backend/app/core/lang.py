"""응답 언어와 사용자 노출 문구. 기본은 베트남어, 한국어도 지원한다 (질문은 어떤 언어로 해도 된다)."""

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

Lang = Literal["vi", "ko"]
SUPPORTED: tuple[Lang, ...] = ("vi", "ko")
DEFAULT_LANG: Lang = "vi"

KR_TZ = ZoneInfo("Asia/Seoul")


def today_kr() -> date:
    """법령 효력 기준일. 서버가 UTC여도 한국 날짜 기준으로 판단한다."""
    return datetime.now(KR_TZ).date()


LANG_NAME: dict[Lang, str] = {"vi": "Vietnamese (Tiếng Việt)", "ko": "Korean (한국어)"}

MESSAGES: dict[str, dict[Lang, str]] = {
    "disclaimer": {
        "vi": "Đây là thông tin pháp luật, không phải tư vấn pháp lý hay quyết định cho phép lưu trú. "
              "Hãy hỏi Trung tâm tư vấn người nước ngoài (☎ 1345) trước khi quyết định việc quan trọng.",
        "ko": "법률 정보이며 법률 자문이나 체류 허가가 아닙니다. 중요한 결정 전에는 외국인종합안내센터(☎ 1345)에 문의하세요.",
    },
    "no_results": {
        "vi": "Chúng tôi không tìm thấy điều luật liên quan. Hãy mô tả tình huống cụ thể hơn, "
              "hoặc gọi Trung tâm tư vấn người nước ngoài (☎ 1345).",
        "ko": "관련 조문을 찾지 못했습니다. 상황을 조금 더 자세히 적어 주시거나 외국인종합안내센터(☎ 1345)에 문의하세요.",
    },
    "smalltalk": {
        "vi": "Xin chào! Tôi trả lời câu hỏi về cư trú tại Hàn Quốc (gia hạn lưu trú, đăng ký người nước ngoài, "
              "khai báo nơi ở, nhập quốc tịch…) dựa trên điều luật. Bạn muốn hỏi gì?",
        "ko": "안녕하세요! 체류기간 연장, 외국인등록, 체류지 변경신고, 귀화 같은 한국 체류 질문에 법령 조문을 근거로 답해 드려요. "
              "무엇이 궁금하세요?",
    },
    "unclear": {
        "vi": "Bạn có thể nói rõ hơn tình huống của mình không? Ví dụ: tư cách lưu trú hiện tại, việc bạn cần làm, thời hạn.",
        "ko": "어떤 상황인지 조금 더 알려 주시겠어요? 예를 들어 지금 체류자격, 하려는 일, 기한 같은 것을 적어 주시면 찾아볼게요.",
    },
    "example.1": {"vi": "Tôi phải gia hạn visa F-6 trước khi nào?", "ko": "체류기간 연장은 언제까지 신청해야 하나요?"},
    "example.2": {"vi": "Chuyển nhà thì phải khai báo trong mấy ngày?", "ko": "이사하면 며칠 안에 신고해야 하나요?"},
    "example.3": {"vi": "Điều kiện nhập quốc tịch cho người kết hôn di trú là gì?", "ko": "결혼이민자 귀화 요건이 뭔가요?"},
    "low_confidence": {
        "vi": "Căn cứ pháp lý tìm được chưa đủ để trả lời chắc chắn. Nên hỏi thêm chuyên gia hoặc ☎ 1345.",
        "ko": "찾은 근거가 확실히 답하기에 부족합니다. 전문가나 외국인종합안내센터(☎ 1345)에 확인하세요.",
    },
    "stage.rewriting": {"vi": "Đang hiểu câu hỏi", "ko": "질문 이해하는 중"},
    "stage.searching": {"vi": "Đang tìm luật xuất nhập cảnh, lưu trú", "ko": "출입국·체류 법령 찾는 중"},
    "stage.expanding": {"vi": "Đang xem điều luật liên quan", "ko": "관련 조문 확인하는 중"},
    "stage.generating": {"vi": "Đang viết câu trả lời", "ko": "답변 쓰는 중"},
    "stage.verifying": {"vi": "Đang kiểm tra căn cứ", "ko": "근거 확인하는 중"},
    "analysis_failed": {
        "vi": "Có lỗi khi phân tích. Hãy thử lại.",
        "ko": "분석 중 문제가 생겼습니다. 다시 시도해 주세요.",
    },
}


def t(key: str, lang: Lang = DEFAULT_LANG) -> str:
    return MESSAGES[key][lang]
