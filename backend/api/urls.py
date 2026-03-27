from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .auth_views import dev_login, google_callback, google_start, me
from .views import (
    api_root,
    create_demo_project,
    create_project,
    files_tree,
    get_file_text,
    health,
    rag_query,
    upload_text_file,
)

urlpatterns = [
    path("", api_root, name="api_root"),
    path("health/", health, name="health"),
    path("auth/dev-login", dev_login, name="dev_login"),
    path("auth/google/start", google_start, name="google_start"),
    path("auth/google/callback", google_callback, name="google_callback"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me", me, name="auth_me"),
    path("demo/bootstrap/", create_demo_project, name="demo_bootstrap"),
    path("projects/", create_project, name="create_project"),
    path("projects/<int:project_id>/files/upload_text", upload_text_file, name="upload_text_file"),
    path("projects/<int:project_id>/files/tree", files_tree, name="files_tree"),
    path("files/<int:file_id>", get_file_text, name="get_file_text"),
    path("rag/query", rag_query, name="rag_query"),
]

