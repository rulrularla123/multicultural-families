# 자동 점검 공통 모듈 전달안

김민건 US-02 점검 흐름 연결용 입력·출력 제안이다. 팀 합의된 HTTP API를 추가하지 않는다.

## PDF 추출 (US-02)

`extract_pdf(file_name: str, data: bytes) -> ExtractionResult`

- 성공: `ok=True`, `pages: tuple[PageText, ...]`. PageText는 기존 식별정보 검사의 `file_name`, `page`(1부터), `text` 형식을 재사용한다.
- 실패: `ok=False`, pages는 빈 튜플. failure는 invalid_pdf, encrypted_pdf, no_text, extraction_error. 페이지가 특정되면 failed_page 반환.
- 한 페이지라도 텍스트가 없으면 전체 실패로 취급하는 보수적 제안이다. 빈 페이지 허용 여부는 팀 확인 필요. OCR은 하지 않는다.
- 호출자는 실패 시 LLM을 호출하지 않고 준비중 유지·자료 수정 안내를 담당한다. DB 저장·상태 변경은 이 모듈에 없다.
- 공통 모듈 검증 명령(backend/): `python -m unittest discover -s common_tests -v`. 기존 tests/ 인수·통합 테스트와 구분한다.
- 파서는 [pypdf 공식 텍스트 추출 문서](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)를 참고했다. 실제 개인정보·원본·추출 결과를 로그로 남기지 않는다.
