"""
:mod:`alchemiscale_fah.protocols.protocolunit` --- reusable ProtocolUnits for Folding@Home protocols
====================================================================================================

"""

import asyncio
from dataclasses import dataclass

from gufe.protocols.protocolunit import ProtocolUnit, Context
from gufe.settings import Settings
from feflow.utils.data import deserialize

from ..compute.client import FahAdaptiveSamplingClient
from ..compute.models import JobStateEnum


class FahExecutionException(RuntimeError):
    ...


@dataclass
class FahContext(Context):
    fah_client: FahAdaptiveSamplingClient
    fah_poll_sleep: 60


class FahSimulationUnit(ProtocolUnit):
    ...

    def _execute(self, ctx, *, state_a, state_b, mapping, settings, **inputs):
        return {}


class FahOpenMMSimulationUnit(FahSimulationUnit):
    def generate_core_file(settings: Settings):
        """Generate a core file from the Protocol's settings."""
        ...

        #TODO for options set to `None`, don't include in core file

    async def _execute(self, ctx: FahContext, *, setup, settings, **inputs):
        # take serialized system, state, integrator from SetupUnit
        system_file = setup.outputs["system"]
        state_file = setup.outputs["state"]
        integrator_file = setup.outputs["integrator"]

        # read in system; count atoms
        system = deserialize(system_file)
        n_atoms = system.getNumParticles()

        # check projects available from work server
        # compare number of atoms to that of this system
        available_projects = ctx.fah_client.list_projects()

        # sort projects in atom count order
        # TODO: NEED TO CHOOSE AN ALGORITHMIC APPROACH TO SPAWNING NEW PROJECTS AS NEEDED
        for project_id, project_data in sorted(
            available_projects.items(), key=lambda item: item[1].atoms
        ):
            ...
            project_id

        # TODO: need to store some kind of state allowing compute service to go
        # down and come back up, resuming activity if it picks up a task it
        # was working on previously

        # create core file from settings
        core_file = self.generate_core_file(settings)

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
