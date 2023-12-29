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

    def select_project(self, fah_projects: List[FahProject], settings: Settings):
        ...
        # TODO: need to also examine nonbonded settings for project selection

    def generate_core_file(self, settings: Settings):
        """Generate a core file from the Protocol's settings."""
        ...
        #TODO for options set to `None`, don't include in core file

    def place_run_files(self):
        ...

    def place_clone_files(
        self, 
        core_file: Path,
        system_file: Path,
        state_file: Path,
        integrator_file: Path):
        ...

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
            # create core file from settings
            core_file = self.generate_core_file(settings)

            # select PROJECT to use for execution
            project_id = self.select_project(ctx.fah_projects, settings)

            # get PROJECT RUNs; select next RUN id
            run_id = ctx.index.get_project_run_next(project_id)

            # create RUN for this Transformation, CLONE for this Task
            ctx.fah_client.create_run_file(project_id, run_id)
            self.place_clone_files(
                    core_file,
                    system_file,
                    state_file,
                    integrator_file
            )

            ctx.index.set_run(FahRun(transformation_key=str(ctx.transformation_sk.gufe_key)))

        # if we got PROJECT and RUN IDs, but no CLONE ID, it means this Task
        # has never been seen before on this work server, but the
        # Transformation has; we use the existing PROJECT and RUN but create a
        # new CLONE
        elif clone_id is None:
            ...

        # if we got PROJECT, RUN, and CLONE IDs, then this Task has been seen
        # before on this work server; we use the results if they exist
        else:
            ...
            

        # get RUN Transformation

        # pass to work server, create RUN/CLONE as appropriate
        run_id = ctx.fah_client.create_run(
            project_id, core_file, system_file, state_file, integrator_file
        )
        ctx.fah_client.start_run_clone(project_id, run_id, 0)

        while True:
            # check for and await sleep results from work server
            jobdata = ctx.fah_client.get_run_clone(project_id, run_id, 0)

            if jobdata.state == JobStateEnum.finished:
                break
            elif jobdata.state == JobStateEnum.failed:
                raise FahExecutionException(
                    "Consecutive failed or faulty WUs exceeded the "
                    f"maximum for RUN {run_id} in PROJECT {project_id}"
                )

            else:
                await asyncio.sleep(ctx.fah_poll_sleep)

        # when results available, put them into useful form
        # may be a case where colocation of service on work server pretty
        # critical for performance; prefer not to pull large files out of host
        # will be very dependent on what `openmm-core` outputs;
        # can influence this if it's putting things out in an obtuse or incomplete form

        # return results for consumption by ResultUnit
