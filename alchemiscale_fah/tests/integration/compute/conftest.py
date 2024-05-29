import os
from copy import copy

import pytest
import uvicorn

from gufe import ChemicalSystem, Transformation, AlchemicalNetwork, SmallMoleculeComponent, LigandAtomMapping
from alchemiscale.tests.integration.utils import running_service
from openfe_benchmarks import tyk2

from alchemiscale_fah.compute import api, client
from alchemiscale_fah.compute.api import WSStateDB
from alchemiscale_fah.settings.fah_wsapi_settings import WSAPISettings
from alchemiscale_fah.tests.integration.compute.utils import get_wsapi_settings_override


@pytest.fixture(scope="module")
def work_server_api(tmpdir_factory):
    with tmpdir_factory.mktemp("wsapi_state").as_cwd():

        overrides = copy(api.app.dependency_overrides)

        api.app.dependency_overrides[api.get_wsapi_settings] = (
            get_wsapi_settings_override
        )

        yield api.app, get_wsapi_settings_override()

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
    ws_api, settings = work_server_api
    with running_service(
        run_server,
        port=settings.WSAPI_PORT,
        args=(ws_api, settings),
    ):
        yield


@pytest.fixture(scope="function")
def fah_adaptive_sampling_client(
    uvicorn_server,
):
    fahasc = client.FahAdaptiveSamplingClient(
        as_url="http://127.0.0.1:8001/",
        ws_url="http://127.0.0.1:8001/",
        verify=False,
    )
    yield fahasc

    fahasc._reset_mock_ws()


def generate_tyk2_solvent_network(protocol):
    tyk2s = tyk2.get_system()

    solvent_network = []
    for mapping in tyk2s.ligand_network.edges:

        # apply formal charges to avoid long charging times in test suite
        ligand_A = mapping.componentA.to_openff()
        ligand_A.assign_partial_charges('gasteiger')
        ligand_A = SmallMoleculeComponent.from_openff(ligand_A, name=ligand_A.name)

        ligand_B = mapping.componentB.to_openff()
        ligand_B.assign_partial_charges('gasteiger')
        ligand_B = SmallMoleculeComponent.from_openff(ligand_B, name=ligand_B.name)

        mapping_ = LigandAtomMapping(componentA=ligand_A,
                                     componentB=ligand_B,
                                     componentA_to_componentB=mapping.componentA_to_componentB,
                                     annotations=mapping.annotations)

        solvent_transformation = Transformation(
            stateA=ChemicalSystem(
                components={
                    "ligand": ligand_A,
                    "solvent": tyk2s.solvent_component,
                },
                name=f"{ligand_A.name}_water",
            ),
            stateB=ChemicalSystem(
                components={
                    "ligand": ligand_B,
                    "solvent": tyk2s.solvent_component,
                },
                name=f"{ligand_B.name}_water",
            ),
            mapping={"ligand": mapping_},
            protocol=protocol,
            name=f"{ligand_A.name}_to_{ligand_B.name}_solvent",
        )

        solvent_network.append(solvent_transformation)

    return AlchemicalNetwork(edges=solvent_network, name="tyk2_solvent")


#def generate_tyk2_complex_network(protocol):
#    tyk2s = tyk2.get_system()
#
#    complex_network = []
#    for mapping in tyk2s.ligand_network.edges:
#        complex_transformation = Transformation(
#            stateA=ChemicalSystem(
#                components={
#                    "protein": tyk2s.protein_component,
#                    "ligand": mapping.componentA,
#                    "solvent": tyk2s.solvent_component,
#                },
#                name=f"{mapping.componentA.name}_complex",
#            ),
#            stateB=ChemicalSystem(
#                components={
#                    "protein": tyk2s.protein_component,
#                    "ligand": mapping.componentB,
#                    "solvent": tyk2s.solvent_component,
#                },
#                name=f"{mapping.componentB.name}_complex",
#            ),
#            mapping={"ligand": mapping},
#            protocol=protocol,
#            name=f"{mapping.componentA.name}_to_{mapping.componentB.name}_complex",
#        )
#
#        complex_network.append(complex_transformation)
#
#    return AlchemicalNetwork(edges=complex_network, name="tyk2_complex")
