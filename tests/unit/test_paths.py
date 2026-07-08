"""Unit tests for backend.shared.paths."""

from pathlib import Path


class TestProjectRoot:
    def test_returns_path_to_repo_root(self):
        from backend.shared.paths import project_root
        root = project_root()
        assert isinstance(root, Path)
        assert root.exists()
        assert (root / "backend").is_dir()
        assert (root / "services").is_dir()

    def test_root_has_dotenv_sentinel(self):
        from backend.shared.paths import project_root
        root = project_root()
        assert (root / ".env").exists() or (root / ".env.example").exists()


class TestInfraSql:
    def test_returns_directory_when_no_schema(self):
        from backend.shared.paths import infra_sql
        path = infra_sql()
        assert path.is_dir()
        assert path.name == "sql"
        assert path.parent.name == "infra"

    def test_appends_schema_name(self):
        from backend.shared.paths import infra_sql
        path = infra_sql("energy")
        assert path.name == "energy_schema.sql"
        assert path.parent.name == "sql"


class TestServiceDir:
    def test_returns_correct_path(self):
        from backend.shared.paths import service_dir
        path = service_dir("energy-service")
        assert path.is_dir()
        assert path.name == "energy-service"
        assert path.parent.name == "services"

    def test_raises_for_nonexistent_service(self):
        from backend.shared.paths import service_dir
        path = service_dir("nonexistent-service")
        assert not path.exists()
