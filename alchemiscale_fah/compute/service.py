"""
:mod:`alchemiscale_fah.compute.service` --- compute services for FEC execution via Folding@Home
===============================================================================================

"""

import os
import asyncio
import gc
import json
from typing import Union, Optional, List, Dict, Tuple
from pathlib import Path
from uuid import uuid4
import threading
import time
import logging
import shutil
from concurrent.futures import ProcessPoolExecutor

from gufe.tokenization import GufeKey, JSON_HANDLER
from gufe.protocols.protocoldag import (
    ProtocolDAG,
    ProtocolDAGResult,
    _pu_to_pur,
    Context,
)
from gufe.protocols.protocolunit import ProtocolUnit, ProtocolUnitResult

from alchemiscale.models import Scope, ScopedKey
from alchemiscale.storage.models import Task, TaskHub, ComputeServiceID
from alchemiscale.compute.client import AlchemiscaleComputeClient
from alchemiscale.compute.service import (
    SynchronousComputeService,
    InterruptableSleep,
    SleepInterrupted,
)
from alchemiscale.keyedchain import KeyedChain

from .models import FahProject
from .settings import FahAsynchronousComputeServiceSettings
from .client import FahAdaptiveSamplingClient
from .index import FahComputeServiceIndex
from ..protocols.protocolunit import FahSimulationUnit, FahContext

# NOTE: if we don't do this, it appears that our RDKit mols won't keep their
# properties on being pickled with a ProcessPoolExecutor, despite our efforts to avoid this;
# this is important for retaining partial charges
from rdkit import Chem

Chem.SetDefaultPickleProperties(Chem.PropertyPickleOptions.AllProps)


class FahAsynchronousComputeService(SynchronousComputeService):
    """An asynchronous compute service for utilizing a Folding@Home work server."""

    def __init__(self, settings: FahAsynchronousComputeServiceSettings):
        """Create a `FAHSynchronousComputeService` instance."""
        self.settings = settings

        self.api_url = self.settings.api_url
        self.name = self.settings.name
        self.sleep_interval = self.settings.sleep_interval
        self.heartbeat_interval = self.settings.heartbeat_interval
        self.claim_limit = self.settings.claim_limit

        self.client = AlchemiscaleComputeClient(
            self.settings.api_url,
            self.settings.identifier,
            self.settings.key,
            max_retries=self.settings.client_max_retries,
            retry_base_seconds=self.settings.client_retry_base_seconds,
            retry_max_seconds=self.settings.client_retry_max_seconds,
            verify=self.settings.client_verify,
        )

        self.fah_project_ids = self.settings.fah_project_ids

        self.index_dir = Path(self.settings.index_dir).absolute()
        self.obj_store = Path(self.settings.obj_store).absolute()

        self.fah_client = FahAdaptiveSamplingClient(
            as_url=self.settings.fah_as_url,
            ws_url=self.settings.fah_ws_url,
            certificate_file=self.settings.fah_certificate_file,
            key_file=self.settings.fah_key_file,
            csr_file=self.settings.fah_csr_file,
            verify=self.settings.fah_client_verify,
        )

        # get PROJECT data from metadata files in each PROJECT
        self.fah_projects = [
            FahProject.parse_raw(
                self.fah_client.get_project_file_to_bytes(
                    p, "alchemiscale-project.txt"
                ).decode("utf-8")
            )
            for p in self.fah_project_ids
        ]

        self.fah_cert_update_interval = settings.fah_cert_update_interval

        if self.settings.scopes is None:
            self.scopes = [Scope()]
        else:
            self.scopes = self.settings.scopes

        self.shared_basedir = Path(self.settings.shared_basedir).absolute()
        self.shared_basedir.mkdir(exist_ok=True)
        self.keep_shared = self.settings.keep_shared

        self.scratch_basedir = Path(self.settings.scratch_basedir).absolute()
        self.scratch_basedir.mkdir(exist_ok=True)
        self.keep_scratch = self.settings.keep_scratch

        self.compute_service_id = ComputeServiceID(f"{self.name}-{uuid4()}")

        self.int_sleep = InterruptableSleep()

        self._stop = False

        # logging
        extra = {"compute_service_id": str(self.compute_service_id)}
        logger = logging.getLogger("AlchemiscaleSynchronousComputeService")
        logger.setLevel(self.settings.loglevel)

        formatter = logging.Formatter(
            "[%(asctime)s] [%(compute_service_id)s] [%(levelname)s] %(message)s"
        )
        formatter.converter = time.gmtime  # use utc time for logging timestamps

        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)

        if self.settings.logfile is not None:
            fh = logging.FileHandler(self.settings.logfile)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

        self.logger = logging.LoggerAdapter(logger, extra)

        self.heartbeat_thread = None
        self.fah_cert_update_thread = None

    def update_fah_cert(self):
        """Start up the FAH cert update, sleeping for `self.fah_cert_update_interval`"""
        while True:
            if self._stop:
                break
            self.fah_client.as_update_certificate()
            time.sleep(self.fah_cert_update_interval)

    def _refresh_heartbeat_thread(self):
        if self.heartbeat_thread is None:
            self.heartbeat_thread = threading.Thread(target=self.heartbeat, daemon=True)
            self.heartbeat_thread.start()

        # check that heartbeat is still alive; if not, resurrect it
        elif not self.heartbeat_thread.is_alive():
            self.heartbeat_thread = threading.Thread(target=self.heartbeat, daemon=True)
            self.heartbeat_thread.start()

    def _refresh_cert_update_thread(self):
        if self.fah_cert_update_thread is None:
            self.fah_cert_update_thread = threading.Thread(
                target=self.update_fah_cert, daemon=True
            )
            self.fah_cert_update_thread.start()

        # check that heartbeat is still alive; if not, resurrect it
        elif not self.fah_cert_update_thread.is_alive():
            self.fah_cert_update_thread = threading.Thread(
                target=self.update_fah_cert, daemon=True
            )
            self.fah_cert_update_thread.start()

    async def async_execute(self, task: ScopedKey) -> ScopedKey:
        """Executes given Task.

        Returns ScopedKey of ProtocolDAGResultRef following push to database.

        """
        # check if Task seen before, serialized ProtocolDAG present
        # use that ProtocolDAG instead and feed to `execute_DAG`
        project_id, run_id, clone_id = self.index.get_task(task)

        if project_id is not None:
            protocoldag = self.index.get_task_protocoldag(task)
        else:
            # check if we have seen this Transformation before
            # get PROJECT, RUN if so
            tf_sk = self.client.get_task_transformation(task)
            project_id, run_id = self.index.get_transformation(tf_sk.gufe_key)
            clone_id = None

            # obtain a ProtocolDAG from the task
            self.logger.info("Creating ProtocolDAG from '%s'...", task)
            protocoldag, transformation, extends = self.task_to_protocoldag(task)
            self.logger.info(
                "Created '%s' from '%s' performing '%s'",
                protocoldag,
                task,
                transformation.protocol,
            )
            self.index.set_task_protocoldag(task, protocoldag)

        # execute the task; this looks the same whether the ProtocolDAG is a
        # success or failure

        shared = self.shared_basedir / str(protocoldag.key)
        shared.mkdir()
        scratch = self.scratch_basedir / str(protocoldag.key)
        scratch.mkdir()

        self.logger.info("Executing '%s'...", protocoldag)
        try:
            # use a custom `execute_DAG` here that feeds appropriate components
            # via context, such as the FahAdaptiveSamplingClient, to units that
            # interact with FAH
            protocoldagresult = await execute_DAG(
                protocoldag,
                shared_basedir=shared,
                scratch_basedir=scratch,
                keep_scratch=self.keep_scratch,
                raise_error=False,
                n_retries=self.settings.n_retries,
                pool=self._pool,
                fah_client=self.fah_client,
                fah_projects=self.fah_projects,
                project_run_clone=(project_id, run_id, clone_id),
                transformation_sk=tf_sk,
                task_sk=task,
                index=self.index,
            )
        finally:
            if not self.keep_shared:
                shutil.rmtree(shared)

            if not self.keep_scratch:
                shutil.rmtree(scratch)

        if protocoldagresult.ok():
            self.logger.info("'%s' -> '%s' : SUCCESS", protocoldag, protocoldagresult)
        else:
            for failure in protocoldagresult.protocol_unit_failures:
                self.logger.info(
                    "'%s' -> '%s' : FAILURE :: '%s' : %s",
                    protocoldag,
                    protocoldagresult,
                    failure,
                    failure.exception,
                )

        # push the result (or failure) back to the compute API
        result_sk = self.push_result(task, protocoldagresult)
        self.logger.info("Pushed result `%s'", protocoldagresult)

        return task, result_sk

    async def async_cycle(
        self, max_tasks: Optional[int] = None, max_time: Optional[int] = None
    ):
        self._check_max_tasks(max_tasks)
        self._check_max_time(max_time)

        # claim as many tasks as we are allowed to at once
        # TODO: only want to claim tasks that correspond to FAH protocols
        # claim tasks from the compute API
        self.logger.info("Claiming tasks")
        task_sks: List[ScopedKey] = self.client.claim_tasks(
            scopes=self.scopes,
            compute_service_id=self.compute_service_id,
            count=self.claim_limit,
            protocols=self.settings.protocols,
        )

        # if no tasks claimed, sleep and return
        if all([task_sk is None for task_sk in task_sks]):
            self.logger.info(
                "No tasks claimed; sleeping for %d seconds", self.sleep_interval
            )
            await asyncio.sleep(self.sleep_interval)
            return []

        # otherwise, process tasks
        self.logger.info("Executing tasks...")

        # as we execute tasks, claim new ones and execute them too until
        # we have exhausted what's available
        async_tasks = []
        for task_sk in task_sks:
            self.logger.info("Executing task '%s'...", task_sk)
            async_tasks.append(asyncio.create_task(self.async_execute(task_sk)))

        result_sks = []
        while len(async_tasks) > 0:
            self.logger.info("Currently running tasks: '%d'...", len(async_tasks))
            self._check_max_tasks(max_tasks)
            self._check_max_time(max_time)

            # refresh heartbeat in case it died
            self._refresh_heartbeat_thread()

            # if cert update thread died, restart it
            if self.fah_cert_update_interval is not None:
                self._refresh_cert_update_thread()

            done, pending = await asyncio.wait(
                async_tasks, return_when=asyncio.FIRST_COMPLETED
            )

            # remove any completed tasks from running list
            for async_task in done:
                task_sk, result_sk = await async_task
                self.logger.info("Finished task '%s'", task_sk)

                if max_tasks is not None:
                    self._tasks_counter += 1

                result_sks.append(result_sk)
                async_tasks.remove(async_task)

            # attempt to claim a new task, add to execution
            self.logger.info("Attempting to claim an additional task")
            task_sks: List[ScopedKey] = self.client.claim_tasks(
                scopes=self.scopes,
                compute_service_id=self.compute_service_id,
                count=self.claim_limit,
                protocols=self.settings.protocols,
            )

            if all([task_sk is None for task_sk in task_sks]):
                self.logger.info("No new task claimed")

            for task_sk in task_sks:
                self.logger.info("Executing task '%s'...", task_sk)
                async_tasks.append(asyncio.create_task(self.async_execute(task_sk)))

        return result_sks

    def start(self, max_tasks: Optional[int] = None, max_time: Optional[int] = None):
        """Start the service.

        Limits to the maximum number of executed tasks or seconds to run for
        can be set. The first maximum to be hit will trigger the service to
        exit.

        Parameters
        ----------
        max_tasks
            Max number of Tasks to execute before exiting.
            If `None`, the service will have no task limit.
        max_time
            Max number of seconds to run before exiting.
            If `None`, the service will have no time limit.

        """
        self.cycle_init()

        # TODO: add running count of successes/failures, log to output
        try:
            self.logger.info("Starting main loop")
            while not self._stop:
                # refresh heartbeat in case it died
                self._refresh_heartbeat_thread()

                # if cert update thread died, restart it
                if self.fah_cert_update_interval is not None:
                    self._refresh_cert_update_thread()

                # perform continuous cycle until available tasks exhausted
                asyncio.run(self.async_cycle(max_tasks, max_time))

                # force a garbage collection to avoid consuming too much memory
                gc.collect()
        except KeyboardInterrupt:
            self.logger.info("Caught SIGINT/Keyboard interrupt.")
        except SleepInterrupted:
            self.logger.info("Service stopping.")
        finally:
            self.cycle_terminate()

    def cycle_init(self):
        # add ComputeServiceRegistration
        self.logger.info("Starting up service '%s'", self.name)
        self._register()
        self.logger.info(
            "Registered service with registration '%s'", str(self.compute_service_id)
        )

        # start up heartbeat thread
        self._refresh_heartbeat_thread()

        # set up automatic cert refreshes, if desired
        if self.fah_cert_update_interval is not None:
            self._refresh_cert_update_thread()

        # stop conditions will use these
        self._tasks_counter = 0
        self._start_time = time.time()

        # create process pool
        self._pool = ProcessPoolExecutor()

        # open index
        self.index = FahComputeServiceIndex(self.index_dir, self.obj_store)

        # update index with PROJECT information
        for p in self.fah_projects:
            self.index.set_project(p.project_id, p)

    def cycle_terminate(self):
        # setting this ensures heartbeat also stops
        self._stop = True
        # remove ComputeServiceRegistration, drop all claims
        self._deregister()

        # close index
        self.index.db.close()

        self.logger.info(
            "Deregistered service with registration '%s'",
            str(self.compute_service_id),
        )
        self._pool.shutdown(cancel_futures=True)


def execute_unit(unit, params):
    return (
        KeyedChain(json.loads(unit, cls=JSON_HANDLER.decoder))
        .to_gufe()
        .execute(**params)
    )


async def execute_DAG(
    protocoldag: ProtocolDAG,
    *,
    shared_basedir: Path,
    scratch_basedir: Path,
    keep_shared: bool = False,
    keep_scratch: bool = False,
    raise_error: bool = True,
    n_retries: int = 0,
    pool: ProcessPoolExecutor,
    fah_client: FahAdaptiveSamplingClient,
    fah_projects: List[FahProject],
    project_run_clone: Tuple[Optional[str], Optional[str], Optional[str]] = (
        None,
        None,
        None,
    ),
    transformation_sk: ScopedKey,
    task_sk: ScopedKey,
    index: FahComputeServiceIndex,
    encryption_public_key: Optional[str] = None,
) -> ProtocolDAGResult:
    """
    Locally execute a full :class:`ProtocolDAG` in serial and in-process.

    Parameters
    ----------
    protocoldag : ProtocolDAG
        The :class:``ProtocolDAG`` to execute.
    shared_basedir : Path
        Filesystem path to use for shared space that persists across whole DAG
        execution. Used by a `ProtocolUnit` to pass file contents to dependent
        class:``ProtocolUnit`` instances.
    scratch_basedir : Path
        Filesystem path to use for `ProtocolUnit` `scratch` space.
    keep_shared : bool
        If True, don't remove shared directories for `ProtocolUnit`s after
        the `ProtocolDAG` is executed.
    keep_scratch : bool
        If True, don't remove scratch directories for a `ProtocolUnit` after
        it is executed.
    raise_error : bool
        If True, raise an exception if a ProtocolUnit fails, default True
        if False, any exceptions will be stored as `ProtocolUnitFailure`
        objects inside the returned `ProtocolDAGResult`
    n_retries : int
        the number of times to attempt, default 0, i.e. try once and only once

    pool

    fah_client

    fah_projects

    project_run_clone

    transformation_sk

    task_sk

    index

    encryption_public_key

    Returns
    -------
    ProtocolDAGResult
        The result of executing the `ProtocolDAG`.

    """
    loop = asyncio.get_running_loop()

    if n_retries < 0:
        raise ValueError("Must give positive number of retries")

    # iterate in DAG order
    results: dict[GufeKey, ProtocolUnitResult] = {}
    all_results = []  # successes AND failures
    shared_paths = []
    for unit in protocoldag.protocol_units:
        # for each unit, check that results already exist; if so, use these
        # and skip forward
        result = index.get_protocolunit_result(unit.key)

        if result is not None:
            results[unit.key] = result
            all_results.append(result)
        else:

            # translate each `ProtocolUnit` in input into corresponding
            # `ProtocolUnitResult`
            inputs = _pu_to_pur(unit.inputs, results)

            attempt = 0
            while attempt <= n_retries:
                shared = shared_basedir / f"shared_{str(unit.key)}_attempt_{attempt}"

                # if we partially executed a ProtocolUnit, but didn't complete it,
                # start with a fresh shared directory
                if shared.exists():
                    shutil.rmtree(shared)

                shared_paths.append(shared)
                shared.mkdir()

                scratch = scratch_basedir / f"scratch_{str(unit.key)}_attempt_{attempt}"

                # if we partially executed a ProtocolUnit, but didn't complete it,
                # start with a fresh scratch directory
                if scratch.exists():
                    shutil.rmtree(scratch)

                scratch.mkdir()

                context = Context(shared=shared, scratch=scratch)

                fah_context = FahContext(
                    shared=shared,
                    scratch=scratch,
                    fah_client=fah_client,
                    fah_projects=fah_projects,
                    project_run_clone=project_run_clone,
                    transformation_sk=transformation_sk,
                    task_sk=task_sk,
                    index=index,
                    encryption_public_key=encryption_public_key,
                )

                params = dict(context=context, raise_error=raise_error, **inputs)
                fah_params = dict(
                    context=fah_context, raise_error=raise_error, **inputs
                )

                # if this is a FahProtocolUnit, then we await its execution in-process
                if isinstance(unit, FahSimulationUnit):
                    result = await unit.execute(**fah_params)
                else:
                    # otherwise, execute with process pool, allowing CPU bound
                    # units to parallelize across multiple tasks being executed
                    # at once

                    # TODO instead of immediately `await`ing here, we could build
                    # up a task for each ProtocolUnit whose deps are satisfied, and
                    # only proceed with additional ones as their deps are satisfied;
                    # would require restructuring this whole method around that
                    # approach, in particular handling retries
                    result = await loop.run_in_executor(
                        pool,
                        execute_unit,
                        json.dumps(
                            KeyedChain.gufe_to_keyed_chain_rep(unit),
                            cls=JSON_HANDLER.encoder,
                        ),
                        params,
                    )

                all_results.append(result)

                if not keep_scratch:
                    shutil.rmtree(scratch)

                if result.ok():
                    # attach result to this `ProtocolUnit`
                    results[unit.key] = result

                    # hold on to ProtocolUnitResult so the DAG can be replayed if needed
                    index.set_protocolunit_result(unit.key, result)

                    break
                attempt += 1

        if not result.ok():
            break

    if not keep_shared:
        for shared_path in shared_paths:
            shutil.rmtree(shared_path)

    # clean up protocoldagresults from index object state store
    for unit in protocoldag.protocol_units:
        index.del_protocolunit_result(unit.key)

    return ProtocolDAGResult(
        name=protocoldag.name,
        protocol_units=protocoldag.protocol_units,
        protocol_unit_results=all_results,
        transformation_key=protocoldag.transformation_key,
        extends_key=protocoldag.extends_key,
    )
