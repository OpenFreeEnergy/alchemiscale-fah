"""
:mod:`alchemiscale_fah.protocols.protocolunit` --- reusable ProtocolUnits for Folding@Home protocols
====================================================================================================

"""

from typing import List, Tuple, Optional
import asyncio
from dataclasses import dataclass

from gufe.protocols.protocolunit import ProtocolUnit, Context
from gufe.settings import Settings
from alchemiscale.models import ScopedKey
from feflow.utils.data import deserialize

from ..compute.client import FahAdaptiveSamplingClient
from ..compute.models import JobStateEnum, FahProject, FahRun, FahClone
from ..compute.index import FahComputeServiceIndex


class FahExecutionException(RuntimeError):
    ...


@dataclass
class FahContext(Context):
    fah_client: FahAdaptiveSamplingClient
    fah_poll_sleep: 60
    fah_projects: list[FahProject]
    project_run_clone: Tuple[Optional[str], Optional[str], Optional[str]]
    transformation_sk: ScopedKey
    task_sk: ScopedKey
    index: FahComputeServiceIndex


class FahSimulationUnit(ProtocolUnit):
    ...

    def _execute(self, ctx, *, state_a, state_b, mapping, settings, **inputs):
        return {}


class FahOpenMMSimulationUnit(FahSimulationUnit):
    def select_project(
        self, n_atoms: int, fah_projects: List[FahProject], settings: Settings
    ):
        """Select the PROJECT with the nearest effort to the given Transformation.

        "Effort" is a function of the number of atoms in the system and the
        nonbonded settings in use.

        """

        nonbonded_settings = settings.system_settings.nonbonded_method

        # get only PROJECTs with matching nonbonded settings
        eligible_projects = [
            fah_project
            for fah_project in fah_projects
            if fah_project.nonbonded_settings == nonbonded_settings
        ]

        # get efforts for each project, select project with closest effort to
        # this Transformation
        ...

    def generate_core_file(self, settings: Settings):
        """Generate a core file from the Protocol's settings."""
        ...
        # TODO for options set to `None`, don't include in core file

    async def _execute(self, ctx: FahContext, *, setup, settings, **inputs):
        # take serialized system, state, integrator from SetupUnit
        system_file = setup.outputs["system"]
        state_file = setup.outputs["state"]
        integrator_file = setup.outputs["integrator"]

        # read in system; count atoms
        system = deserialize(system_file)
        n_atoms = system.getNumParticles()

        project_id, run_id, clone_id = ctx.project_run_clone

        # if we haven't been assigned PROJECT and RUN IDs, then we need to
        # choose a PROJECT for this Transformation and create a RUN for it;
        # also need to create a CLONE for this Task
        if project_id is None and run_id is None:
            # select PROJECT to use for execution
            project_id = self.select_project(ctx.fah_projects, settings)

            # get next available RUN id
            run_id = ctx.index.get_project_run_next(project_id)

            # create RUN for this Transformation
            ctx.fah_client.create_run_file_from_bytes(
                project_id,
                run_id,
                str(ctx.transformation_sk.gufe_key).encode("utf-8"),
                "alchemiscale-transformation.txt",
            )
            ctx.index.set_transformation(
                ctx.transformation_sk.gufe_key, project_id, run_id
            )

        # if we got PROJECT and RUN IDs, but no CLONE ID, it means this Task
        # has never been seen before on this work server, but the
        # Transformation has; we use the existing PROJECT and RUN but create a
        # new CLONE
        if clone_id is None:
            # create core file from settings
            core_file = self.generate_core_file(settings)

            # get next available CLONE id
            run_id = ctx.index.get_run_clone_next(project_id, run_id)

            # create CLONE for this Task
            ctx.fah_client.create_clone_file_from_bytes(
                project_id,
                run_id,
                clone_id,
                str(ctx.task_sk).encode("utf-8"),
                "alchemiscale-task.txt",
            )
            for filepath in (core_file, system_file, state_file, integrator_file):
                ctx.fah_client.create_clone_file(
                    project_id, run_id, clone_id, filepath, filepath.name
                )
            ctx.index.set_task(ctx.task_sk, project_id, run_id, clone_id)
            ctx.fah_client.create_clone(project_id, run_id, clone_id)

        while True:
            # check for and await sleep results from work server
            jobdata = ctx.fah_client.get_clone(project_id, run_id, clone_id)

            if jobdata.state == JobStateEnum.finished:
                break
            elif jobdata.state == JobStateEnum.failed:
                raise FahExecutionException(
                    "Consecutive failed or faulty WUs exceeded the "
                    f"maximum for RUN {run_id} in PROJECT {project_id}"
                )

            else:
                await asyncio.sleep(ctx.fah_poll_sleep)

        # read in results from `globals.csv`

        # return results for consumption by ResultUnit
