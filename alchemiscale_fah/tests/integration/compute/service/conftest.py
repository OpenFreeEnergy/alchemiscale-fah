"""Components for standing up services for integration tests, including databases.

"""

## storage
### below from `py2neo.test.integration.conftest.py`

import os
from time import sleep
from copy import copy
from pathlib import Path
from collections import defaultdict

from grolt import Neo4jService, Neo4jDirectorySpec, docker
from grolt.security import install_self_signed_certificate
from pytest import fixture
from moto import mock_aws
from moto.server import ThreadedMotoServer
import uvicorn

from neo4j import GraphDatabase

from openff.units import unit
from alchemiscale.models import Scope
from alchemiscale.settings import Neo4jStoreSettings, S3ObjectStoreSettings
from alchemiscale.storage.statestore import Neo4jStore
from alchemiscale.storage.objectstore import S3ObjectStore, get_s3os
from alchemiscale.storage.models import ComputeServiceID

from alchemiscale.settings import get_base_api_settings
from alchemiscale.base.api import get_n4js_depends, get_s3os_depends
from alchemiscale.compute import api, client
from alchemiscale.storage.models import ComputeServiceID
from alchemiscale.security.auth import hash_key
from alchemiscale.security.models import CredentialedComputeIdentity, TokenData

from alchemiscale.tests.integration.compute.utils import get_compute_settings_override
from alchemiscale.tests.integration.utils import running_service

from alchemiscale_fah.protocols.feflow.nonequilibrium_cycling import (
    FahNonEqulibriumCyclingProtocol,
)
from alchemiscale_fah.tests.integration.compute.conftest import (
    generate_tyk2_solvent_network,
)

NEO4J_PROCESS = {}
NEO4J_VERSION = os.getenv("NEO4J_VERSION", "")


class DeploymentProfile(object):
    def __init__(self, release=None, topology=None, cert=None, schemes=None):
        self.release = release
        self.topology = topology  # "CE|EE-SI|EE-C3|EE-C3-R2"
        self.cert = cert
        self.schemes = schemes

    def __str__(self):
        server = "%s.%s %s" % (self.release[0], self.release[1], self.topology)
        if self.cert:
            server += " %s" % (self.cert,)
        schemes = " ".join(self.schemes)
        return "[%s]-[%s]" % (server, schemes)


class TestProfile:
    def __init__(self, deployment_profile=None, scheme=None):
        self.deployment_profile = deployment_profile
        self.scheme = scheme
        assert self.topology == "CE"

    def __str__(self):
        extra = "%s" % (self.topology,)
        if self.cert:
            extra += "; %s" % (self.cert,)
        bits = [
            "Neo4j/%s.%s (%s)" % (self.release[0], self.release[1], extra),
            "over",
            "'%s'" % self.scheme,
        ]
        return " ".join(bits)

    @property
    def release(self):
        return self.deployment_profile.release

    @property
    def topology(self):
        return self.deployment_profile.topology

    @property
    def cert(self):
        return self.deployment_profile.cert

    @property
    def release_str(self):
        return ".".join(map(str, self.release))

    def generate_uri(self, service_name=None):
        if self.cert == "full":
            raise NotImplementedError("Full certificates are not yet supported")
        elif self.cert == "ssc":
            certificates_dir = install_self_signed_certificate(self.release_str)
            dir_spec = Neo4jDirectorySpec(certificates_dir=certificates_dir)
        else:
            dir_spec = None
        with Neo4jService(
            name=service_name,
            image=self.release_str,
            auth=("neo4j", "password"),
            dir_spec=dir_spec,
            config={},
        ) as service:
            uris = [router.uri(self.scheme) for router in service.routers()]
            yield service, uris[0]


# TODO: test with full certificates
neo4j_deployment_profiles = [
    DeploymentProfile(release=(5, 16), topology="CE", schemes=["bolt"]),
]

if NEO4J_VERSION == "LATEST":
    neo4j_deployment_profiles = neo4j_deployment_profiles[:1]
elif NEO4J_VERSION == "4.x":
    neo4j_deployment_profiles = [
        profile for profile in neo4j_deployment_profiles if profile.release[0] == 4
    ]
elif NEO4J_VERSION == "4.4":
    neo4j_deployment_profiles = [
        profile for profile in neo4j_deployment_profiles if profile.release == (4, 4)
    ]


neo4j_test_profiles = [
    TestProfile(deployment_profile, scheme=scheme)
    for deployment_profile in neo4j_deployment_profiles
    for scheme in deployment_profile.schemes
]


@fixture(
    scope="session", params=neo4j_test_profiles, ids=list(map(str, neo4j_test_profiles))
)
def test_profile(request):
    test_profile = request.param
    yield test_profile


@fixture(scope="session")
def neo4j_service_and_uri(test_profile):
    for service, uri in test_profile.generate_uri("py2neo"):
        yield service, uri

    # prune all docker volumes left behind
    docker.volumes.prune()
    return


@fixture(scope="session")
def uri(neo4j_service_and_uri):
    _, uri = neo4j_service_and_uri
    return uri


# TODO: this should be pulling from the defined profile
@fixture(scope="session")
def graph(uri):
    return GraphDatabase.driver(
        uri,
        auth=("neo4j", "password"),
    )


## data
### below specific to alchemiscale


@fixture(scope="module")
def n4js(graph):
    return Neo4jStore(graph)


@fixture
def n4js_fresh(graph):
    n4js = Neo4jStore(graph)

    n4js.reset()
    n4js.initialize()

    return n4js


@fixture(scope="module")
def s3objectstore_settings():
    os.environ["AWS_ACCESS_KEY_ID"] = "test-key-id"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test-key"
    os.environ["AWS_SESSION_TOKEN"] = "test-session-token"
    os.environ["AWS_S3_BUCKET"] = "test-bucket"
    os.environ["AWS_S3_PREFIX"] = "test-prefix"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    return S3ObjectStoreSettings()


@fixture(scope="module")
def s3os_server(s3objectstore_settings):
    server = ThreadedMotoServer()
    server.start()

    s3os = get_s3os(s3objectstore_settings, endpoint_url="http://127.0.0.1:5000")
    s3os.initialize()

    yield s3os

    server.stop()


@fixture
def s3os_server_fresh(s3os_server):
    s3os_server.reset()
    s3os_server.initialize()

    return s3os_server


@fixture(scope="module")
def s3os(s3objectstore_settings):
    with mock_aws():
        s3os = get_s3os(s3objectstore_settings)
        s3os.initialize()

        yield s3os


@fixture(scope="module")
def scope_test():
    """Primary scope for individual tests"""
    return Scope(org="test_org", campaign="test_campaign", project="test_project")


@fixture(scope="module")
def compute_service_id():
    return ComputeServiceID("compute-service-123")


# compute API

@fixture(scope="module")
def compute_api(s3os_server):
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


@fixture(scope="module")
def uvicorn_server(compute_api):
    settings = get_compute_settings_override()
    with running_service(
        run_server,
        port=settings.ALCHEMISCALE_COMPUTE_API_PORT,
        args=(compute_api, settings),
    ):
        yield


@fixture(scope="module")
def compute_identity():
    return dict(identifier="test-compute-identity", key="strong passphrase lol")


@fixture(scope="module")
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


## preloaded alchemiscale

@fixture(scope="module")
def network_tyk2_solvent():

    settings = FahNonEqulibriumCyclingProtocol.default_settings()
    settings.thermo_settings.pressure = 1.0 * unit.bar
    settings.platform = "CPU"

    # lowering sampling by 10x for demo purposes
    settings.eq_steps = 25000
    settings.neq_steps = 25000

    settings.fah_settings.numSteps = 250000
    settings.fah_settings.xtcFreq = 25000

    protocol = FahNonEqulibriumCyclingProtocol(settings)

    return generate_tyk2_solvent_network(protocol)


@fixture(scope="module")
def transformation(network_tyk2_solvent):
    return sorted(list(network_tyk2_solvent.edges))[0]


@fixture(scope="module")
def compute_identity_prepped(compute_identity):
    return {
        "identifier": compute_identity["identifier"],
        "hashed_key": hash_key(compute_identity["key"]),
    }


@fixture(scope="module")
def single_scoped_credentialed_compute(compute_identity_prepped, scope_test):
    identity = copy(compute_identity_prepped)
    identity["identifier"] = identity["identifier"] + "-a"

    compute = CredentialedComputeIdentity(
        **identity, scopes=[scope_test]
    )  # Ensure list
    return compute


@fixture
def n4js_preloaded(
    n4js_fresh,
    network_tyk2_solvent,
    transformation,
    scope_test,
    single_scoped_credentialed_compute,
):
    n4js: Neo4jStore = n4js_fresh

    # set starting contents for many of the tests in this module
    sk, th_sk, _ = n4js.assemble_network(network_tyk2_solvent, scope_test)

    # spawn tasks
    task_sks = list()
    trans_sk = n4js.get_scoped_key(transformation, scope_test)

    extends = None
    for i in range(3):
        extends = n4js.create_task(trans_sk, extends=extends)
        task_sks.append(extends)

    # add tasks from each transformation selected to each task hubs
    n4js.action_tasks(task_sks[0:1], th_sk)

    # create compute identities
    n4js.create_credentialed_entity(single_scoped_credentialed_compute)

    return n4js
