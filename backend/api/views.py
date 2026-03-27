import io
import uuid

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Chunk, FileObject, Project
from .tasks import ingest_fileobject
from .storage import ensure_bucket, get_minio_client, get_minio_config
from .embeddings import embed_8, to_vector_literal


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return JsonResponse({"ok": True})


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    return Response(
        {
            "name": "Nodex API",
            "endpoints": {
                "health": "/api/health/",
                "dev_login": "/api/auth/dev-login",
                "token_refresh": "/api/auth/token/refresh",
                "me": "/api/auth/me",
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_demo_project(request):
    """
    인증 붙이기 전 임시 엔드포인트.
    - Project 1개 + settings 파일 1개를 만들고
    - 청크/벡터를 즉시 저장한다.
    """
    user = request.user

    project = Project.objects.create(user=user, title="demo-project")
    content = "엘리온의 검 이름은 아르카디아다.\n엘리온은 냉소적인 말투를 쓴다."

    ensure_bucket()
    cfg = get_minio_config()
    client = get_minio_client()
    object_key = f"users/{user.id}/projects/{project.id}/files/{uuid.uuid4().hex}.txt"
    client.put_object(
        cfg.bucket,
        object_key,
        data=io.BytesIO(content.encode("utf-8")),
        length=len(content.encode("utf-8")),
        content_type="text/plain; charset=utf-8",
    )
    f = FileObject.objects.create(
        project=project,
        kind=FileObject.Kind.SETTINGS,
        relative_path="설정/인물/엘리온.txt",
        object_key=object_key,
        content_hash=FileObject.hash_content(content),
        index_status=FileObject.IndexStatus.READY,
    )

    Chunk.objects.create(
        project=project,
        file=f,
        chunk_index=0,
        content=content,
        embedding=embed_8(content),
    )

    return Response({"project_id": project.id, "file_id": f.id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_project(request):
    title = str(request.data.get("title") or "untitled")
    user = request.user
    project = Project.objects.create(user=user, title=title)
    return Response({"project_id": project.id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_text_file(request, project_id: int):
    """
    MVP: 텍스트를 body로 받아 MinIO 저장 + FileObject 생성.
    body: { relative_path, kind(settings|manuscript), content }
    """
    relative_path = str(request.data.get("relative_path") or "")
    kind = str(request.data.get("kind", FileObject.Kind.SETTINGS))
    content = str(request.data.get("content") or "")
    if not relative_path or not content:
        return Response(
            {"error": {"code": "INVALID_INPUT", "message": "relative_path/content required"}},
            status=400,
        )

    user = request.user
    project = Project.objects.get(id=int(project_id), user=user)

    ensure_bucket()
    cfg = get_minio_config()
    client = get_minio_client()
    object_key = f"users/{user.id}/projects/{project.id}/files/{uuid.uuid4().hex}.txt"
    data = content.encode("utf-8")
    client.put_object(
        cfg.bucket,
        object_key,
        data=io.BytesIO(data),
        length=len(data),
        content_type="text/plain; charset=utf-8",
    )

    f = FileObject.objects.create(
        project=project,
        kind=kind,
        relative_path=relative_path,
        object_key=object_key,
        content_hash=FileObject.hash_content(content),
        index_status=FileObject.IndexStatus.PENDING,
    )

    ingest_fileobject.apply_async(args=[f.id], queue="ingest")
    return Response({"file_id": f.id, "index_status": f.index_status})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def files_tree(request, project_id: int):
    user = request.user
    Project.objects.get(id=int(project_id), user=user)

    files = (
        FileObject.objects.filter(project_id=int(project_id))
        .order_by("relative_path")
        .values("id", "relative_path", "kind", "index_status")
    )
    return Response({"files": list(files)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_file_text(request, file_id: int):
    user = request.user

    f = FileObject.objects.select_related("project").get(id=int(file_id), project__user=user)
    ensure_bucket()
    cfg = get_minio_config()
    client = get_minio_client()
    obj = client.get_object(cfg.bucket, f.object_key)
    try:
        content = obj.read().decode("utf-8", errors="replace")
    finally:
        obj.close()
        obj.release_conn()
    return Response({"file_id": f.id, "relative_path": f.relative_path, "content": content})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rag_query(request):
    """
    MVP: pgvector 기반 유사도 조회(결정적 해시 임베딩).
    body: { project_id, query, top_k?, scope? }
    """
    project_id = int(request.data.get("project_id"))
    query = str(request.data.get("query") or "")
    top_k = int(request.data.get("top_k", 5))
    scope = request.data.get("scope", "settings_only")
    if not query:
        return Response(
            {"error": {"code": "INVALID_INPUT", "message": "query required"}},
            status=400,
        )

    # 소유권 검증
    Project.objects.get(id=project_id, user=request.user)

    qv = embed_8(query)
    qv_lit = to_vector_literal(qv)

    qs = Chunk.objects.filter(project_id=project_id)
    if scope == "settings_only":
        qs = qs.filter(file__kind=FileObject.Kind.SETTINGS)
    elif scope == "settings_plus_current_manuscript":
        # MVP에서는 manuscript 파일이 없으므로 pass (추후 구현)
        pass
    elif scope == "settings_plus_recent_manuscripts":
        pass

    # MVP: pgvector ORM helper 대신 raw SQL distance 정렬(L2 <->).
    # 추후: 코사인/inner product 및 인덱스(HNSW)로 최적화.
    qs = qs.extra(
        select={"distance": "embedding <-> (%s)::vector"},
        select_params=[qv_lit],
        order_by=["distance"],
    )[:top_k]

    results = []
    for c in qs:
        results.append(
            {
                "content": c.content,
                "source_path": c.file.relative_path,
                "file_id": c.file_id,
                "chunk_index": c.chunk_index,
            }
        )

    return Response({"results": results})

