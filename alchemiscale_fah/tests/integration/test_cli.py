import pytest
from click.testing import CliRunner


import time
import yaml
import multiprocessing
from datetime import datetime, timedelta

from alchemiscale.cli import cli as alchemiscale_cli
from alchemiscale_fah.cli import cli
from alchemiscale_fah.compute.client import FahAdaptiveSamplingClient
from alchemiscale_fah.utils import NonbondedSettings
from alchemiscale_fah.compute.models import ProjectData, FahProject, FahCoreType

from alchemiscale.tests.integration.utils import running_service
from alchemiscale.models import Scope
from alchemiscale.security.models import (
    CredentialedUserIdentity,
    CredentialedComputeIdentity,
)
from alchemiscale.security.auth import hash_key, authenticate, AuthenticationError


def test_create_project(fah_adaptive_sampling_client):
    fahc: FahAdaptiveSamplingClient = fah_adaptive_sampling_client

    project_id = "90001"
    n_atoms = 1000

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "create-project",
            "--project-id",
            project_id,
            "--core-id",
            "0x23",
            "--core-type",
            "openmm",
            "--contact-email",
            "lol@no.int",
            "--n-atoms",
            n_atoms,
            "--nonbonded-settings",
            "PME",
            "--ws-url",
            fahc.ws_url,
        ],
    )

    assert result.exit_code == 0

    project_data_ = fahc.get_project(project_id)
    assert project_data_.atoms == n_atoms


def test_generate_atom_counts():

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "generate-atom-counts",
            "--lower",
            10**3,
            "--upper",
            10**5,
            "--n-projects",
            10,
            "--nonbonded-settings",
            "PME",
        ],
    )

    assert result.exit_code == 0


@pytest.fixture(scope="function")
def fah_client_preloaded(fah_adaptive_sampling_client):
    client: FahAdaptiveSamplingClient = fah_adaptive_sampling_client
    project_id = 90001
    n_atoms = 10000
    nonbonded_settings = NonbondedSettings["PME"]

    project_data = ProjectData(
        core_id=0x23,
        contact="lol@no.int",
        atoms=n_atoms,
        credit=5000,
    )

    client.create_project(project_id, project_data)

    fah_project = FahProject(
        project_id=project_id,
        n_atoms=n_atoms,
        nonbonded_settings=nonbonded_settings,
        core_type=FahCoreType["openmm"],
    )
    client.create_project_file_from_bytes(
        project_id, fah_project.json().encode("utf-8"), "alchemiscale-project.txt"
    )

    return client


@pytest.fixture
def compute_api_args():
    workers = 2
    host = "127.0.0.1"
    port = 50100
    command = ["compute", "api"]
    api_opts = ["--workers", workers, "--host", host, "--port", port]
    db_opts = [
        "--url",
        "bolt://localhost:7687",
        "--user",
        "neo4j",
        "--password",
        "password",
    ]
    s3_opts = [
        "--access-key-id",
        "test-key-id",
        "--secret-access-key",
        "test-key",
        "--session-token",
        "test-session-token",
        "--s3-bucket",
        "test-bucket",
        "--s3-prefix",
        "test-prefix",
        "--default-region",
        "us-east-1",
    ]
    jwt_opts = []  # leaving empty, we have default behavior for these

    return host, port, (command + api_opts + db_opts + s3_opts + jwt_opts)


@pytest.fixture
def compute_service_config(compute_api_args, fah_client_preloaded):
    host, port, _ = compute_api_args
    fahc: FahAdaptiveSamplingClient = fah_client_preloaded

    config = {
        "init": {
            "api_url": f"http://{host}:{port}",
            "identifier": "test-compute-user",
            "key": "test-comute-user-key",
            "name": "test-compute-service",
            "shared_basedir": "./shared",
            "scratch_basedir": "./scratch",
            "loglevel": "INFO",
            "fah_as_url": fahc.as_url,
            "fah_ws_url": fahc.ws_url,
            "fah_certificate_file": fahc.certificate_file,
            "fah_key_file": fahc.key_file,
            "fah_client_verify": False,
            "fah_cert_update_interval": None,
            "index_dir": "./index/index_dir",
            "obj_store": "./index/object_store",
            "fah_project_ids": [90001],
        },
        "start": {"max_time": None},
    }

    return config


def test_compute_fahasynchronous(
    n4js_fresh, s3os, compute_api_args, compute_service_config, tmpdir
):
    host, port, args = compute_api_args
    n4js = n4js_fresh

    # create compute identity; add all scope access
    identity = CredentialedComputeIdentity(
        identifier=compute_service_config["init"]["identifier"],
        hashed_key=hash_key(compute_service_config["init"]["key"]),
    )

    n4js.create_credentialed_entity(identity)
    n4js.add_scope(identity.identifier, CredentialedComputeIdentity, Scope())

    # start up compute API
    runner = CliRunner()
    with running_service(runner.invoke, port, (alchemiscale_cli, args)):
        # start up compute service
        with tmpdir.as_cwd():
            command = ["compute", "fah-asynchronous"]
            opts = ["--config-file", "config.yaml"]

            with open("config.yaml", "w") as f:
                yaml.dump(compute_service_config, f)

            multiprocessing.set_start_method("fork", force=True)
            proc = multiprocessing.Process(
                target=runner.invoke, args=(cli, command + opts), daemon=True
            )
            proc.start()

            q = f"""
            match (csreg:ComputeServiceRegistration)
            where csreg.identifier =~ "{compute_service_config['init']['name']}.*"
            return csreg
            """
            while True:
                csreg = n4js.execute_query(q)

                if not csreg.records:
                    time.sleep(1)
                else:
                    break

            assert csreg.records[0]["csreg"][
                "registered"
            ] > datetime.utcnow() - timedelta(seconds=30)

            proc.terminate()
            proc.join()
