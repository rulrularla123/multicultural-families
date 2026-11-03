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


## LLM 클라이언트 (US-02)

`await check_documents(request: CheckInput, transport: Transport, timeout=60) -> Analysis`

- CheckInput: situation, document_texts(문자열 튜플), support_type(F-6-1), criteria(기준 입력 튜플). CriterionInput은 criterion_id, body, source, checked_on(date). 이는 DB 모델이 아닌 전송용 제안이다. 버전·작업 ID는 서버가 별도로 보존한다.
- 계정 ID·작업 ID·PDF 바이너리·파일명·반려 사유를 입력 필드로 받지 않는다. 전송 직전 모든 전송 문자열의 기존 식별정보 패턴을 재검사한다. 식별정보 외 실명·주소·이메일 등의 완전 검출을 보장하지 않는다. 서버 호출자는 검사를 통과한 모의 자료만 전달해야 한다.
- Analysis: cautions, possible_omissions, additional_documents. 각 항목은 text, criterion_id(문자열 또는 null). 근거가 없거나 요청 기준에 없는 ID면 null로 정규화하며 `item.needs_confirmation`이 True다. 출처·기준일은 호출자가 등록 기준에서 조회해 붙인다.
- CheckClientError.code: identifying_input, invalid_input, timeout, transport_error, invalid_response. 입력값·키·응답 원문을 예외 메시지나 로그에 넣지 않는다.
- MockTransport: success, error, delay(기본 61초), invalid. timeout은 0 초과 60 이하로 테스트에서 줄일 수 있다. 테스트는 60초를 실제로 기다리지 않고 같은 취소 경로를 짧은 제한으로 확인한다.
- GeminiTransport: api_key와 model을 명시적으로 주입해야 한다. 기본 모델·환경변수 읽기·실제 키 연결은 없다. httpx REST 어댑터이며 실제 Gemini 호출은 미검증이다.
- DB 잠금 밖에서 호출하고, 저장 직전 상태·점검 작업 ID·상황·서류·기준 버전을 다시 검사하는 일은 김민건 US-02 담당이다. 이 클라이언트는 상태 변경·승인·결과 공개를 하지 않는다.
- 참고: [Gemini generateContent](https://ai.google.dev/api/generate-content), [구조화 출력](https://ai.google.dev/gemini-api/docs/structured-output). 모델 지원 여부·결제는 실제 키 연결 전에 확인한다.

미합의 항목: 내부 응답 필드 이름과 기준 ID 타입은 연결 전 김민건과 맞춘다. HTTP 경로·API.md·DB 모델은 이 작업에서 수정하지 않는다.
