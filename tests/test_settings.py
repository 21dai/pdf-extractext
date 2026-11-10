"""Unit tests for app.config.settings.

The .env file is shared between the application and docker-compose, so it holds
variables that are not application settings. Loading it must never break the
app: these tests pin that contract.
"""

import tomllib
from pathlib import Path

import app
from app.config.settings import Settings

ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"
PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_settings_loads_the_committed_env_example():
    """Test copying .env.example to .env does not break application startup."""
    settings = Settings(_env_file=ENV_EXAMPLE)

    assert settings.app_name
    assert settings.app_version


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


def test_the_version_is_declared_only_once():
    """Test the package does not declare a second version of its own.

    `app/__init__.py` declaraba su propio `__version__`, que quedo en 1.4.0
    mientras el paquete iba en 2.0.1: dos declaraciones que se desincronizan
    sin avisar. La version vive en la configuracion y en `pyproject.toml`.
    """
    assert not hasattr(app, "__version__")
    assert not hasattr(app, "__author__")


def test_the_version_of_the_settings_is_the_one_of_the_package():
    """Test the declared version and the one of the package do not diverge."""
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]

    assert Settings.model_fields["app_version"].default == version
    assert Settings(_env_file=ENV_EXAMPLE).app_version == version
