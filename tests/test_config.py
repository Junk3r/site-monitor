from site_monitor.config import loader


def test_profile_is_loaded_from_the_ignored_file(monkeypatch, tmp_path):

    path = tmp_path / "profile.yaml"

    path.write_text(
        "candidate: |\n"
        "  Candidate profile:\n"
        "  - Account Manager\n"
        "scale: |\n"
        "  Score meaning:\n"
        "  1-10: fit\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(loader, "PROFILE_PATH", path)

    profile = loader.load_profile()

    assert "Account Manager" in profile["candidate"]

    assert "1-10: fit" in profile["scale"]


def test_missing_profile_falls_back_to_the_example(monkeypatch, tmp_path):
    """Без своего profile.yaml берётся шаблон — работать продолжаем,
    но с предупреждением в логе."""

    monkeypatch.setattr(
        loader,
        "PROFILE_PATH",
        tmp_path / "does-not-exist.yaml",
    )

    profile = loader.load_profile()

    assert profile["candidate"].strip()


def test_the_example_is_not_a_copy_of_the_real_profile():
    """Шаблон коммитится в публичный репозиторий. Ловим ровно ту ошибку,
    которая всё сломает: свой профиль, сохранённый поверх шаблона.

    Перечислять здесь настоящие личные данные нельзя — тест сам лежит
    в репозитории и утёк бы вместо профиля."""

    example = loader.PROFILE_EXAMPLE_PATH.read_text(encoding="utf-8")

    if not loader.PROFILE_PATH.exists():
        return

    real = loader.PROFILE_PATH.read_text(encoding="utf-8")

    assert example.strip() != real.strip()


def test_profile_yaml_is_not_tracked_by_git():

    gitignore = (
        loader.PROJECT_ROOT / ".gitignore"
    ).read_text(encoding="utf-8")

    assert "site_monitor/config/profile.yaml" in gitignore
