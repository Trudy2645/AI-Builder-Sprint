# BusanLink RAG ingestion

이 디렉터리는 공식 근거, 승인 템플릿, 승인 판례의 재현 가능한 manifest만 보관한다.
PDF 원본과 API key, Vector Store ID는 Git에 포함하지 않는다.

Vector Store는 다음 세 개를 서로 분리한다.

- `official_contract_knowledge`: 검수 완료된 법령·표준약관
- `busan_link_templates`: 팀 승인 템플릿
- `case_reference`: 승인 판례 참고자료

`downloaded_sources.json`의 공식 자료 10건은 hash 검증과 운영자 검수를 완료했다.
`status=reviewed`, `approved_by`, `approved_at`이 없는 공식 자료는 ingestion command가 거절한다.
`pending_source_verification` 자료와 사용자 계약서는 대상이 아니다.

```bash
cd backend
.venv/bin/python -m app.cli.ingest_knowledge \
  --manifest ../rag/manifests/template_sources.json \
  --source-root /absolute/path/to/rag \
  --corpus approved_templates \
  --approved-by 00000000-0000-0000-0000-000000000000
```

명령은 PDF 크기와 SHA-256을 검증하고 private `rag-knowledge` Storage snapshot,
Upstage Files, 해당 Vector Store, PostgreSQL registry 순서로 연결한다. 동일 hash는 재업로드하지
않으며 provider 임시 URL은 저장하지 않는다.

Upstage가 유효한 장문 PDF를 직접 index하지 못한 경우에만 `--retry-failed
--provider-text-derivative`를 함께 사용한다. immutable 원본 PDF를 바꾸지 않고 페이지 마커가
포함된 검색 파생물을 만들며 파생물 hash와 retry mode를 DB metadata에 기록한다.
