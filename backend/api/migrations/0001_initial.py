from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import pgvector.django


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS vector;"),
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="FileObject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("settings", "settings"), ("manuscript", "manuscript")], default="settings", max_length=20)),
                ("relative_path", models.CharField(max_length=500)),
                ("content_hash", models.CharField(max_length=64)),
                ("index_status", models.CharField(choices=[("pending", "pending"), ("ready", "ready"), ("failed", "failed")], default="pending", max_length=20)),
                ("last_error", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="api.project")),
            ],
        ),
        migrations.CreateModel(
            name="Chunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.IntegerField()),
                ("content", models.TextField()),
                ("embedding", pgvector.django.VectorField(dimensions=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("file", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="api.fileobject")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="api.project")),
            ],
            options={
                "unique_together": {("file", "chunk_index")},
            },
        ),
    ]

