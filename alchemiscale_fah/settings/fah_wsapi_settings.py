"""
:mod:`alchemiscale.settings.fah_wsapi_settings` --- settings for mock WS API
============================================================================

"""

import pathlib
from functools import lru_cache

from pydantic import BaseSettings


class FrozenSettings(BaseSettings):
    class Config:
        frozen = True


class WSAPISettings(FrozenSettings):
    """Automatically populates settings from environment variables where they
    match; case-insensitive.

    """

    WSAPI_SERVER_ID: int

    WSAPI_STATE_DIR: pathlib.Path
    WSAPI_SECRETS_DIR: pathlib.Path
    WSAPI_INPUTS_DIR: pathlib.Path
    WSAPI_OUTPUTS_DIR: pathlib.Path

    WSAPI_HOST: str = "127.0.0.1"
    WSAPI_PORT: int = 80
    WSAPI_LOGLEVEL: str = "info"


@lru_cache()
def get_wsapi_settings():
    return WSAPISettings()
