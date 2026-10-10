from agents.applications.advertising.persistence.factory import create_persistence_store


def test_memory_store_path_remains_an_in_memory_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_AGENT_DATABASE_URL", raising=False)
    monkeypatch.delenv("AD_AGENT_DB_BACKEND", raising=False)
    store = create_persistence_store(sqlite_path=":memory:")
    try:
        assert store._db_path == ":memory:"
    finally:
        store.close()


def test_default_store_lives_in_deployment_cwd_not_in_the_package(
    tmp_path, monkeypatch
):
    for name in ("AD_AGENT_DATABASE_URL", "AD_AGENT_DB_BACKEND", "AD_AGENT_DB_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    store = create_persistence_store()
    try:
        assert store._db_path == str(tmp_path / "ad_agent.db")
    finally:
        store.close()
