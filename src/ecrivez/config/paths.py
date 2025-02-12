from xdg import (
    xdg_cache_home as cache,
    xdg_data_home as data,
    xdg_runtime_dir as runtime,
    xdg_config_home as config,
)
from pydantic import BaseModel, Field
from pathlib import Path


class DefaultsBaseDir(BaseModel, strict=True):
    xdg_cache: Path = Field(cache(), description="Cache directory")
    xdg_data: Path = Field(data(), description="Data directory")
    xdg_runtime: Path = Field(runtime(), description="Runtime directory")
    xdg_config: Path = Field(config(), description="Configuration directory")
    config


class DefaultsAppPaths(BaseModel, strict=True):
    cache_dir: Path = Field(cache() / "ecrivez", description="Cache directory")
    data_dir: Path = Field(data() / "ecrivez", description="Data directory")
    runtime_dir: Path = Field(runtime() / "ecrivez", description="Runtime directory")
    config_dir: Path = Field(
        config() / "ecrivez", description="Configuration directory"
    )


class Paths(DefaultsBaseDir, DefaultsAppPaths):
    def __init__(self):
        super().__init__()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def read_config(self):
        pass
