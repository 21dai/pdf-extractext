"""Unit tests for app.config.settings.

The .env file is shared between the application and docker-compose, so it holds
variables that are not application settings. Loading it must never break the
app: these tests pin that contract.
"""

from pathlib import Path

from app.config.settings import Settings

ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"


def test_settings_loads_the_committed_env_example():
    """Test copying .env.example to .env does not break application startup."""
    settings = Settings(_env_file=ENV_EXAMPLE)

    assert settings.app_name
    assert settings.app_version
    assert settings.database_name


def test_settings_ignores_variables_that_are_not_application_settings(tmp_path):
    """Test build-time variables in the .env are ignored instead of rejected."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_NAME=PDF Extract API\nIMAGE_TAG=1.0.0\nCOMPOSE_PROJECT_NAME=docker\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "PDF Extract API"
    assert not hasattr(settings, "image_tag")
