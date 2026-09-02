"""demo_data seeding — the pieces the app actually reads back."""

from pathlib import Path

import pytest
from sqlalchemy import text


def test_remove_existing_deletes_the_full_pyturso_sidecar_set(tmp_path):
    """A stale -changes queue beside a plain SQLite file is exactly the state
    config._remove_replica_files() exists to avoid."""
    from demo_data import _remove_existing

    base = tmp_path / "demo.db"
    suffixes = ("", "-shm", "-wal", "-info", "-changes", "-wal-revert")
    for suffix in suffixes:
        Path(f"{base}{suffix}").write_text("x")

    _remove_existing(base, force=True)

    assert [s for s in suffixes if Path(f"{base}{s}").exists()] == []


def test_remove_existing_without_force_refuses(tmp_path):
    from demo_data import _remove_existing

    base = tmp_path / "demo.db"
    base.write_text("x")
    with pytest.raises(FileExistsError):
        _remove_existing(base, force=False)
    assert base.exists()


def test_industry_index_is_seeded_where_build_costs_reads_it(tmp_path, monkeypatch):
    """industry_index moved from buildcost.db to the local-only cache DB.

    Seeding it into buildcost.db left demo mode raising "No manufacturing
    cost index found" for every system, so seed and read must agree on the
    file.
    """
    from sqlalchemy import create_engine

    import repositories.build_cost_repo as repo

    cache_db = tmp_path / "streamlit_cache.db"
    repo._cache_engine.cache_clear()
    monkeypatch.setattr(repo, "_CACHE_DB", cache_db)
    monkeypatch.setattr(
        repo, "_cache_engine", lambda: create_engine(f"sqlite:///{cache_db}")
    )

    from demo_data import _seed_industry_index_cache

    _seed_industry_index_cache()

    assert cache_db.exists()
    assert repo._get_manufacturing_cost_index_impl(30000240) == pytest.approx(0.045)
    assert repo._get_manufacturing_cost_index_impl(30002029) == pytest.approx(0.052)


def test_seed_build_cost_db_holds_rigs_and_structures_only(tmp_path):
    """The shared buildcost replica carries rigs/structures; industry_index is
    a per-viewer ESI cache and must not be seeded into it."""
    from sqlalchemy import create_engine

    from demo_data import _seed_build_cost_db

    path = tmp_path / "buildcost.db"
    _seed_build_cost_db(path)

    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM rigs")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM structures")).scalar() == 2
        assert conn.execute(text("SELECT count(*) FROM industry_index")).scalar() == 0
    engine.dispose()
