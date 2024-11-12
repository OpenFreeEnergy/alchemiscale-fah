"""
:mod:`alchemiscale_fah.protocols.protocolunit` --- reusable ProtocolUnits for Folding@Home protocols
====================================================================================================

"""

import abc
from typing import List, Tuple, Optional, Any, Union
import asyncio
from dataclasses import dataclass
import datetime
import traceback

import numpy as np
import pandas as pd

from gufe.protocols.protocolunit import (
    ProtocolUnit,
    ProtocolUnitResult,
    ProtocolUnitFailure,
    Context,
)
from gufe.settings import Settings

from alchemiscale.models import ScopedKey
from feflow.utils.data import deserialize

from ..compute.client import FahAdaptiveSamplingClient
from ..compute.models import JobStateEnum, FahProject, FahRun, FahClone
from ..compute.index import FahComputeServiceIndex
from ..utils import NONBONDED_EFFORT, NonbondedSettings


class FahExecutionException(RuntimeError): ...


@dataclass
class FahContext(Context):
    fah_client: FahAdaptiveSamplingClient
    fah_projects: List[FahProject]
    transformation_sk: ScopedKey
    task_sk: ScopedKey
    index: FahComputeServiceIndex
    fah_poll_interval: int = 60
    encryption_public_key: Optional[str] = None


class FahSimulationUnit(ProtocolUnit):

    async def execute(
        self, *, context: Context, raise_error: bool = False, **inputs
    ) -> Union[ProtocolUnitResult, ProtocolUnitFailure]:
        """Given `ProtocolUnitResult` s from dependencies, execute this `ProtocolUnit`.

        Parameters
        ----------
        context : Context
            Execution context for this `ProtocolUnit`; includes e.g. ``shared``
            and ``scratch`` `Path` s.
        raise_error : bool
            If True, raise any errors instead of catching and returning a
            `ProtocolUnitFailure` default False
        **inputs
            Keyword arguments giving the named inputs to `_execute`.
            These can include `ProtocolUnitResult` objects from `ProtocolUnit`
            objects this unit is dependent on.

        """
        result: Union[ProtocolUnitResult, ProtocolUnitFailure]
        start = datetime.datetime.now()

        try:
            outputs = await self._execute(context, **inputs)
            result = ProtocolUnitResult(
                name=self.name,
                source_key=self.key,
                inputs=inputs,
                outputs=outputs,
                start_time=start,
                end_time=datetime.datetime.now(),
            )

        except KeyboardInterrupt:
            # if we "fail" due to a KeyboardInterrupt, we always want to raise
            raise
        except Exception as e:
            if raise_error:
                raise

            result = ProtocolUnitFailure(
                name=self._name,
                source_key=self.key,
                inputs=inputs,
                outputs=dict(),
                exception=(e.__class__.__qualname__, e.args),
                traceback=traceback.format_exc(),
                start_time=start,
                end_time=datetime.datetime.now(),
            )

        return result

    @abc.abstractmethod
    def _execute(self, ctx, *, state_a, state_b, mapping, settings, **inputs): ...


class FahOpenMMSimulationUnit(FahSimulationUnit):
    """A SimulationUnit that uses the Folding@Home OpenMM core to execute its
    system, state, and integrator.

    """

    @staticmethod
    def select_project(
        n_atoms: int, fah_projects: List[FahProject], settings: Settings
    ) -> FahProject:
        """Select the PROJECT with the nearest effort to the given Transformation.

        "Effort" is a function of the number of atoms in the system and the
        nonbonded settings in use.

        """
        nonbonded_settings = NonbondedSettings[
            settings.forcefield_settings.nonbonded_method
        ]

        # get only PROJECTs with matching nonbonded settings
        eligible_projects = [
            fah_project
            for fah_project in fah_projects
            if fah_project.nonbonded_settings == nonbonded_settings
        ]

        # get efforts for each project, select project with closest effort to
        # this Transformation
        effort_func = NONBONDED_EFFORT[nonbonded_settings]
        effort = effort_func(n_atoms)

        project_efforts = np.array(
            [effort_func(fah_project.n_atoms) for fah_project in eligible_projects]
        )

        selected_project = eligible_projects[np.abs(project_efforts - effort).argmin()]

        return selected_project

    @staticmethod
    def generate_core_settings_file(settings: Settings):
        """Generate a core settings XML file from the Protocol's settings.

        Settings that are set to `None` are not included in XML output.

        Returns
        -------
        xml_str
            XML content of the core settings file.

        """
        xml_str = '<?xml version="1.0" ?>'
        xml_str += "<config>"

        for key, value in settings.fah_settings:
            if value is not None:
                xml_str += f"<{key}>{value}</{key}>"

        xml_str += "</config>"

        return xml_str

    @abc.abstractmethod
    def postprocess_globals(
        self, globals_csv_content: bytes, ctx: FahContext
    ) -> dict[str, Any]: ...

    async def _execute(self, ctx: FahContext, *, protocol, setup, **inputs):
        # take serialized system, state, integrator from SetupUnit
        system_file = setup.outputs["system"]
        state_file = setup.outputs["state"]
        integrator_file = setup.outputs["integrator"]

        # identify if this Task-ProtocolUnit has an existing PROJECT,RUN,CLONE
        # associated with it
        project_id, run_id, clone_id = ctx.index.get_task_protocolunit(
            ctx.task_sk, self.key
        )

        # if we have never seen this Task-ProtocolUnit, then
        if not all((project_id, run_id, clone_id)):
            # identify if the Transformation corresponding to this ProtocolUnit
            # has an existing PROJECT,RUN associated with it
            project_id, run_id = ctx.index.get_transformation(
                ctx.transformation_sk.gufe_key
            )

        # if we haven't been assigned PROJECT and RUN IDs, then we need to
        # choose a PROJECT for this Transformation and create a RUN for it;
        # also need to create a CLONE for this Task-ProtocolUnit
        if project_id is None and run_id is None:

            # read in system; count atoms
            system = deserialize(system_file)
            n_atoms = system.getNumParticles()

            # select PROJECT to use for execution
            project_id = self.select_project(
                n_atoms, ctx.fah_projects, protocol.settings
            ).project_id

            # get next available RUN id
            run_id = ctx.index.get_project_run_next(project_id)

            # if we are beyond the highest possible RUN id, then halt
            if run_id > 65535:
                raise KeyboardInterrupt(f"Exhausted RUN ids for PROJECT {project_id}")

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

        # if we got PROJECT and RUN IDs, but no CLONE ID, it means this Task-ProtocolUnit
        # has never been seen before on this work server, but the
        # Transformation has; we use the existing PROJECT and RUN but create a
        # new CLONE
        if clone_id is None:
            # create core file from settings
            core_file_content = self.generate_core_settings_file(protocol.settings)

            # get next available CLONE id
            clone_id = ctx.index.get_run_clone_next(project_id, run_id)

            # if we are beyond the highest possible CLONE id, then halt
            if clone_id > 65535:
                raise KeyboardInterrupt(
                    f"Exhausted CLONE ids for PROJECT {project_id}, RUN {run_id}"
                )

            # create CLONE for this Task
            ctx.fah_client.create_clone_file_from_bytes(
                project_id,
                run_id,
                clone_id,
                str(ctx.task_sk).encode("utf-8"),
                "alchemiscale-task.txt",
            )
            ctx.fah_client.create_clone_file_from_bytes(
                project_id,
                run_id,
                clone_id,
                str(self.key).encode("utf-8"),
                "alchemiscale-protocolunit.txt",
            )

            # TODO: add encryption of files here if enabled as a setting on the
            # service use configured public key
            if ctx.encryption_public_key:
                raise NotImplementedError("Encryption support not yet implemented.")

            else:
                ctx.fah_client.create_clone_file_from_bytes(
                    project_id,
                    run_id,
                    clone_id,
                    str(core_file_content).encode("utf-8"),
                    "core.xml",
                )

                for filepath in (system_file, state_file, integrator_file):
                    ctx.fah_client.create_clone_file(
                        project_id, run_id, clone_id, filepath, filepath.name
                    )

            ctx.index.set_task_protocolunit(
                ctx.task_sk, self.key, project_id, run_id, clone_id
            )
            ctx.fah_client.create_clone(project_id, run_id, clone_id)
        else:
            # if we have a CLONE ID, it means that we have seen this
            # Task-ProtocolUnit before; we check its status, and if it is in a
            # failed state, then we restart it
            jobdata = ctx.fah_client.get_clone(project_id, run_id, clone_id)

            if JobStateEnum[jobdata.state] is JobStateEnum.FAILED:
                ctx.fah_client.restart_clone(project_id, run_id, clone_id)

        while True:
            # check for and await sleep results from work server
            jobdata = ctx.fah_client.get_clone(project_id, run_id, clone_id)

            if JobStateEnum[jobdata.state] is JobStateEnum.FINISHED:
                break
            elif JobStateEnum[jobdata.state] is JobStateEnum.FAILED:
                raise FahExecutionException(
                    "Consecutive failed or faulty WUs exceeded the "
                    f"maximum for RUN {run_id} in PROJECT {project_id}"
                )

            else:
                await asyncio.sleep(ctx.fah_poll_interval)

        # read in results from `globals.csv`
        globals_csv = ctx.fah_client.get_gen_output_file_to_bytes(
            project_id,
            run_id,
            clone_id,
            0,
            protocol.settings.fah_settings.globalVarFilename,
        )

        outputs = self.postprocess_globals(globals_csv, ctx)

        # read in science log
        science_log = ctx.fah_client.get_gen_output_file_to_bytes(
            project_id, run_id, clone_id, 0, "science.log"
        )

        science_log_path = ctx.shared / "science.log"
        with open(ctx.shared / "science.log", "wb") as f:
            f.write(science_log)

        outputs.update({"log": science_log_path})

        return outputs
