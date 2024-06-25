"""Tests for compute services.

"""

import os
from pathlib import Path
import threading
import time

import pytest

from alchemiscale_fah.compute.client import FahAdaptiveSamplingClient
from alchemiscale_fah.compute.models import (
    ProjectData,
    JobData,
    FahProject,
    FahCoreType,
)
from alchemiscale_fah.compute.service import (
    FahAsynchronousComputeService,
    FahAsynchronousComputeServiceSettings,
)
from alchemiscale_fah.utils import NonbondedSettings
from alchemiscale_fah.protocols.feflow.nonequilibrium_cycling import (
    FahNonEquilibriumCyclingProtocol,
)


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


class TestFahAsynchronousComputeService:

    @pytest.fixture
    def service(self, n4js_preloaded, compute_client, tmpdir, fah_client_preloaded):
        fahc: FahAdaptiveSamplingClient = fah_client_preloaded
        with tmpdir.as_cwd():
            return FahAsynchronousComputeService(
                FahAsynchronousComputeServiceSettings(
                    api_url=compute_client.api_url,
                    identifier=compute_client.identifier,
                    key=compute_client.key,
                    name="test_compute_service",
                    shared_basedir=Path("shared").absolute(),
                    scratch_basedir=Path("scratch").absolute(),
                    heartbeat_interval=1,
                    sleep_interval=1,
                    protocols=[FahNonEquilibriumCyclingProtocol.__qualname__],
                    fah_as_url=fahc.as_url,
                    fah_ws_url=fahc.ws_url,
                    fah_certificate_file=fahc.certificate_file,
                    fah_key_file=fahc.key_file,
                    fah_csr_file=fahc.csr_file,
                    fah_client_verify=False,
                    fah_cert_update_interval=2,
                    index_dir=Path("./index/index_dir").absolute(),
                    obj_store=Path("./index/object_store").absolute(),
                    fah_project_ids=[90001],
                )
            )

    async def test_async_execute(
        self,
        n4js_preloaded,
        s3os_server_fresh,
        service,
        network_tyk2_solvent,
        scope_test,
    ):

        # get a Task to execute
        n4js = n4js_preloaded
        s3os = s3os_server_fresh
        network_sk = n4js.get_scoped_key(network_tyk2_solvent, scope_test)
        tq_sk = n4js.get_taskhub(network_sk)

        task_sks = n4js.get_taskhub_tasks(tq_sk)

        service.cycle_init()

        # try to execute this Task
        task_sk, protocoldagresultref_sk = await service.async_execute(task_sks[0])

        service.cycle_terminate()

        # examine object metadata
        protocoldagresultref = n4js.get_gufe(protocoldagresultref_sk)
        objs = list(s3os.resource.Bucket(s3os.bucket).objects.all())
        assert len(objs) == 1
        assert objs[0].key == os.path.join(s3os.prefix, protocoldagresultref.location)

        # check protocoldagresult
        pdr = s3os.pull_protocoldagresult(
            location=protocoldagresultref.location, ok=protocoldagresultref.ok
        )

        assert pdr.ok()

    async def test_async_cycle(self, n4js_preloaded, s3os_server_fresh, service):
        n4js = n4js_preloaded
        s3os = s3os_server_fresh

        q = """
        match (pdr:ProtocolDAGResultRef)
        return pdr
        """

        # preconditions
        protocoldagresultref = n4js.execute_query(q)
        assert not protocoldagresultref.records

        service.cycle_init()
        await service.async_cycle()
        service.cycle_terminate()

        # postconditions
        protocoldagresultref = n4js.execute_query(q)

        assert protocoldagresultref.records
        assert protocoldagresultref.records[0]["pdr"]["ok"] is True

        # check protocoldagresult
        pdr = s3os.pull_protocoldagresult(
            location=protocoldagresultref.records[0]["pdr"]["location"],
            ok=protocoldagresultref.records[0]["pdr"]["ok"],
        )

        assert pdr.ok()

        q = """
        match (t:Task {status: 'complete'})
        return t
        """

        results = n4js.execute_query(q)

        assert results.records

    def test_start(self, n4js_preloaded, s3os_server_fresh, service):
        n4js = n4js_preloaded
        s3os = s3os_server_fresh

        # start up service in a thread; will register itself
        service_thread = threading.Thread(target=service.start, daemon=True)
        service_thread.start()

        # give time for execution
        time.sleep(2)

        q = f"""
        match (csreg:ComputeServiceRegistration {{identifier: '{service.compute_service_id}'}})
        return csreg
        """
        csreg = n4js.execute_query(q).records[0]["csreg"]
        assert csreg["registered"] < csreg["heartbeat"]

        # stop the service
        service.stop()
        while True:
            if service_thread.is_alive():
                time.sleep(1)
            else:
                break

        q = """
        match (t:Task {status: 'complete'})
        return t
        """

        results = n4js.execute_query(q)
        assert results.records
