# Nodex Studio (MVP Scaffold)

작가를 위한 로컬 AI 기반 집필 스튜디오의 **초기 스캐폴딩**입니다.

## 구성(현재)

- **nginx**: 단일 진입점(Reverse Proxy)
- **frontend**: Svelte(+Vite) 최소 스캐폴딩(3분할 화면 플레이스홀더)
- **backend**: Django/DRF 최소 스캐폴딩 + `pgvector` + `/api/health/`, `/api/rag/query`
- **db**: PostgreSQL + pgvector
- **redis**: Celery broker
- **minio**: 내부 오브젝트 스토리지(현재 외부 포트 미노출)
- **celery**: 워커 컨테이너(태스크는 다음 단계에서 확장)

## 실행(로컬/서버)

1) 환경변수 준비

- `.env.example`을 참고해 `.env`를 구성합니다.
- **절대** 실제 시크릿을 커밋하지 마세요.

2) 컨테이너 실행

```bash
docker compose up -d --build
```

3) 접속

- **Frontend**: `http://localhost:8188/`
- **Backend health**: `http://localhost:8188/api/health/`

## RAG MVP 테스트

현재는 “데모 데이터 부트스트랩 → RAG 쿼리”가 최소 동작합니다.

1) 데모 프로젝트/설정 파일 1개 생성

```bash
curl -X POST http://localhost:8188/api/demo/bootstrap/
```

응답 예:

```json
{"project_id": 3, "file_id": 3}
```

2) RAG 쿼리

```bash
curl -X POST http://localhost:8188/api/rag/query \
  -H 'Content-Type: application/json' \
  -d '{"project_id":3,"query":"엘리온 검 이름","top_k":3,"scope":"settings_only"}'
```

## 다음 단계

- 파일 업로드 → MinIO 저장 → Celery 색인(청크/임베딩) → pgvector upsert 연결
- 프로젝트/파일 트리 API(`files/tree`) + 프론트 트리 UI 연결
- WebLLM 로딩/폴백 + Gemini(프록시) + 쿼터/로그인(OAuth/JWT)

