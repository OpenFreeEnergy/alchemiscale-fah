import pytest



@pytest.fixture(scope=module)
def work_server_api():
    # create API service instance, but with exactly one thread to avoid
    # state race conditions for testing
    def get_s3os_override():
        return s3os_server

    overrides = copy(api.app.dependency_overrides)

    api.app.dependency_overrides[get_base_api_settings] = get_compute_settings_override
    api.app.dependency_overrides[get_s3os_depends] = get_s3os_override
    yield api.app
    api.app.dependency_overrides = overrides



def run_server(fastapi_app, settings):
    uvicorn.run(
        fastapi_app,
        host=settings.ALCHEMISCALE_COMPUTE_API_HOST,
        port=settings.ALCHEMISCALE_COMPUTE_API_PORT,
        log_level=settings.ALCHEMISCALE_COMPUTE_API_LOGLEVEL,
    )


@pytest.fixture(scope="module")
def uvicorn_server(compute_api):
    settings = get_compute_settings_override()
    with running_service(
        run_server,
        port=settings.ALCHEMISCALE_COMPUTE_API_PORT,
        args=(compute_api, settings),
    ):
        yield


@pytest.fixture(scope="module")
def compute_client(
    uvicorn_server,
    compute_identity,
    single_scoped_credentialed_compute,
    compute_service_id,
):
    return client.AlchemiscaleComputeClient(
        api_url="http://127.0.0.1:8000/",
        # use the identifier for the single-scoped user who should have access to some things
        identifier=single_scoped_credentialed_compute.identifier,
        # all the test users are based on compute_identity who use the same password
        key=compute_identity["key"],
    )


@pytest.fixture(scope=module)
def fah_adaptive_sampling_client():
    ...



