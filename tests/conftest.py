"""
Root conftest for the Weidr test suite.

IMPORTANT: The env vars below must be set at module load time — before any app
module is imported — because both `app_info_cache` and `config` are module-level
singletons instantiated on first import. Any nested conftest.py files must
mirror this same module-level assignment for the same reason.
"""

import atexit
import os
import shutil
import tempfile

# Bootstrap a safe temporary location so that the singletons created during
# initial import never touch the real cache or config files.
_bootstrap_tmp = tempfile.mkdtemp(prefix="weidr_tests_")
os.environ.setdefault("WEIDR_CACHE_DIR", os.path.join(_bootstrap_tmp, "cache"))
os.environ.setdefault("WEIDR_CONFIGS_DIR", os.path.join(_bootstrap_tmp, "configs"))
os.makedirs(os.environ["WEIDR_CACHE_DIR"], exist_ok=True)
os.makedirs(os.environ["WEIDR_CONFIGS_DIR"], exist_ok=True)
_src_example = os.path.join(os.path.dirname(__file__), "configs", "config_example.json")
shutil.copy(_src_example, os.path.join(os.environ["WEIDR_CONFIGS_DIR"], "config.json"))
atexit.register(shutil.rmtree, _bootstrap_tmp, True)

import pytest


@pytest.fixture(autouse=True)
def isolated_singletons(tmp_path, monkeypatch):
    """Re-initialise the app_info_cache and config singletons for each test,
    pointing at a fresh per-test temp directory. No production files are touched."""
    cache_dir = tmp_path / "cache"
    configs_dir = tmp_path / "configs"
    cache_dir.mkdir()
    configs_dir.mkdir()
    shutil.copy(_src_example, configs_dir / "config.json")

    monkeypatch.setenv("WEIDR_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("WEIDR_CONFIGS_DIR", str(configs_dir))

    import utils.app_info_cache as aic
    import utils.config as cfg

    monkeypatch.setattr(aic, "app_info_cache", aic.AppInfoCache())

    # Silence startup log spam; patch before instantiation so __init__ skips the print.
    monkeypatch.setattr(cfg.Config, "print_config_settings", lambda self: None)
    monkeypatch.setattr(cfg, "config", cfg.Config())
