"""Tests for FahNonEquilibriumCyclingProtocol."""

import pytest
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

from alchemiscale.models import ScopedKey
from gufe.tokenization import GufeKey
from openff.units import unit

from alchemiscale_fah.compute.models import ProjectData, FahProject, FahCoreType
from alchemiscale_fah.compute.client import FahAdaptiveSamplingClient
from alchemiscale_fah.compute.service import execute_DAG
from alchemiscale_fah.compute.index import FahComputeServiceIndex
from alchemiscale_fah.protocols.feflow.nonequilibrium_cycling import (
    FahNonEquilibriumCyclingProtocol,
)

from alchemiscale_fah.tests.integration.conftest import (
    generate_tyk2_solvent_network,
)


@pytest.fixture(scope="function")
def fah_client_preloaded(fah_adaptive_sampling_client):
    client: FahAdaptiveSamplingClient = fah_adaptive_sampling_client
    project_id = 90001

    project_data = ProjectData(
        core_id="0x23",
        contact="lol@no.int",
        atoms=10000,
        credit=5000,
    )

    client.create_project(project_id, project_data)

    return client


class TestFahNonEquilibriumCyclingSimulationUnit: ...


class TestFahNonEquilibriumCyclingProtocol:

    async def test_dag_execute(self, fah_client_preloaded, transformation):
        client: FahAdaptiveSamplingClient = fah_client_preloaded

        protocoldag = transformation.create()

        shared_basedir = Path("./shared")
        shared_basedir.mkdir(exist_ok=True)

        scratch_basedir = Path("./scratch")
        scratch_basedir.mkdir(exist_ok=True)

        shared = shared_basedir / str(protocoldag.key)
        shared.mkdir(exist_ok=True)
        scratch = scratch_basedir / str(protocoldag.key)
        scratch.mkdir(exist_ok=True)

        pool = ProcessPoolExecutor()

        fah_project = FahProject(
            project_id="90001",
            n_atoms=10000,
            nonbonded_settings="PME",
            core_type=FahCoreType["openmm"],
            core_id="0x23",
        )

        t_sk = ScopedKey(
            gufe_key=transformation.key,
            org="test_org",
            campaign="test_campaign",
            project="test_project",
        )
        task_sk = ScopedKey(
            gufe_key=GufeKey("Task-12345"),
            org="test_org",
            campaign="test_campaign",
            project="test_project",
        )

        index = FahComputeServiceIndex(
            Path("./index/index_dir"), Path("./index/object_store")
        )

        # execute DAG; "work server" will "finish" a simulation unit after a
        # preset amount of time
        pdr = await execute_DAG(
            protocoldag,
            shared_basedir=shared,
            scratch_basedir=scratch,
            keep_scratch=True,
            pool=pool,
            fah_client=client,
            fah_projects=[fah_project],
            fah_poll_interval=1,
            transformation_sk=t_sk,
            task_sk=task_sk,
            index=index,
        )

        assert pdr.ok()
