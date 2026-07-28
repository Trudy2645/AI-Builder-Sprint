# Commit Strategy

## 커밋 메시지 형식

```text
<type>[(scope)]: <short summary>
```

- `feat`: 새 기능
- `fix`: 버그 수정
- `docs`: 문서 변경
- `style`: 기능 변화 없는 형식·스타일 변경
- `refactor`: 리팩터링
- `test`: 테스트
- `build`: 빌드 변경
- `ci`: CI 설정 변경
- `perf`: 성능 개선
- `chore`: 그 밖의 작업

하나의 커밋에는 하나의 논리적 변경만 담고, 요약은 50자 이내로 작성합니다.

## 예시

- `feat(auth): 구글 OAuth 로그인 추가`
- `fix(api): 사용자 조회 오류 처리`
- `docs: README 실행 방법 추가`
