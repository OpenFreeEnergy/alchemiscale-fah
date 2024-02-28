import os
from copy import copy

import pytest
import uvicorn

from alchemiscale.tests.integration.utils import running_service

from alchemiscale_fah.compute import api, client
from alchemiscale_fah.compute.api import WSStateDB
from alchemiscale_fah.settings.fah_wsapi_settings import WSAPISettings
from alchemiscale_fah.tests.integration.compute.utils import get_wsapi_settings_override


# @pytest.fixture(scope="module")
# def wsapi_settings(tmpdir_factory):
#    with tmpdir_factory.mktemp("wsapi_state").as_cwd():
#        os.environ["WSAPI_STATE_DIR"] = 'ws_state'
#        os.environ["WSAPI_INPUTS_DIR"] = 'ws_inputs'
#        os.environ["WSAPI_OUTPUTS_DIR"] = 'ws_outputs'
#
#    return WSAPISettings()


@pytest.fixture(scope="module")
def work_server_api(tmpdir_factory):
    # def get_wsstatedb_override():
    #    return api.WSStateDB(wsapi_settings.WSAPI_STATE_DIR)

    # def get_inputs_dir_override():
    #    return wsapi_settings.WSAPI_INPUTS_DIR

    # def get_outputs_dir_override():
    #    return wsapi_settings.WSAPI_OUTPUTS_DIR
    with tmpdir_factory.mktemp("wsapi_state").as_cwd():

        overrides = copy(api.app.dependency_overrides)

        api.app.dependency_overrides[api.get_wsapi_settings] = (
            get_wsapi_settings_override
        )
        # api.app.dependency_overrides[api.get_wsstatedb_depends] = get_inputs_dir_override
        # api.app.dependency_overrides[api.get_inputs_dir_depends] = get_inputs_dir_override
        # api.app.dependency_overrides[api.get_outputs_dir_depends] = get_outputs_dir_override
        yield api.app
        api.app.dependency_overrides = overrides


def run_server(fastapi_app, settings):
    # create API service instance, but with exactly one thread to avoid
    # potential state race conditions for testing
    uvicorn.run(
        fastapi_app,
        host=settings.WSAPI_HOST,
        port=settings.WSAPI_PORT,
        log_level=settings.WSAPI_LOGLEVEL,
    )


@pytest.fixture(scope="module")
def uvicorn_server(work_server_api):
    settings = get_wsapi_settings_override()
    with running_service(
        run_server,
        port=settings.WSAPI_PORT,
        args=(work_server_api, settings),
    ):
        yield


@pytest.fixture(scope="function")
def fah_adaptive_sampling_client(
    uvicorn_server,
):
    fahasc = client.FahAdaptiveSamplingClient(
        ws_url="http://127.0.0.1:8000/",
        verify=False,
    )
    yield fahasc

    fahasc._reset_mock_ws()


# @pytest.fixture(scope='function')
# def ws_statedb():
#    settings = get_wsapi_settings_override()
#
#    yield None
#
#    ws_statedb = WSStateDB(settings.WSAPI_STATE_DIR, settings.WSAPI_SERVER_ID)
#    ws_statedb.reset()
