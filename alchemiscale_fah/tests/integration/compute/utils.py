from pathlib import Path

from alchemiscale_fah.settings.fah_wsapi_settings import WSAPISettings


def get_wsapi_settings_override():
    # settings overrides for test suite
    return WSAPISettings(
        WSAPI_SERVER_ID=123456789,
        WSAPI_STATE_DIR=Path("ws_state").absolute(),
        WSAPI_INPUTS_DIR=Path("ws_inputs").absolute(),
        WSAPI_OUTPUTS_DIR=Path("ws_outputs").absolute(),
        WSAPI_HOST="127.0.0.1",
        WSAPI_PORT=8000,
    )
