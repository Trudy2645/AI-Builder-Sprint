# AI 변경 이력

## 2026-08-03

- 문서 처리 시간을 줄이기 위해 Document Parse와 Information Extract 요청을 병렬 실행하도록 변경했다.
- 한 작업만 실패한 경우 성공 결과를 재사용하고 실패한 작업만 재시도하도록 Extract 원시 결과 체크포인트를 추가했다.
- 체크포인트는 비공개 AI artifact Storage에 저장하며 경로, schema version, SHA-256 hash만 job metadata에 기록한다.
- Parse·Extract 실패 조합과 병렬 실행을 포함한 전체 백엔드 테스트를 검증했다.
