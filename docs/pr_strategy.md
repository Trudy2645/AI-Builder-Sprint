# Pull Request Strategy

## PR 작성 규칙

- PR 대상은 항상 `main`입니다.
- 제목은 `<type>: <summary>` 형식으로 작성합니다. 예: `feat: 계약서 업로드 화면 추가`
- 하나의 PR에는 하나의 논리적 변경만 담습니다.
- 본문에는 변경 목적, 주요 변경 사항, 테스트 방법, 관련 Issue를 작성합니다.
- PR 작성자를 assignee로 지정하고, 다른 팀원을 reviewer로 지정합니다.

## 리뷰 및 병합

- 리뷰어는 기능 동작, 코드 가독성, 테스트 여부를 확인하고 구체적인 의견을 남깁니다.
- 수정 요청을 받은 작성자는 반영 여부를 댓글로 공유합니다.
- 2명 이상의 승인 후 PR 작성자가 병합합니다.
- 병합 방식은 **Squash and merge**를 사용합니다.
- 병합 후 작업 브랜치를 삭제합니다.

## PR 후 최신화

```bash
git switch main
git pull origin main
```
