"""
:mod:`alchemiscale_fah.compute.service` --- compute services for FEC execution via Folding@Home
===============================================================================================

"""
import os
import asyncio
import gc
from typing import Union, Optional, List, Dict, Tuple
from pathlib import Path
from uuid import uuid4
import threading
import time
import logging
import shutil

from alchemiscale.models import Scope, ScopedKey
from alchemiscale.storage.models import Task, TaskHub, ComputeServiceID
from alchemiscale.compute.client import AlchemiscaleComputeClient
from alchemiscale.compute.service import SynchronousComputeService, InterruptableSleep, SleepInterrupted

from .settings import FAHSynchronousComputeServiceSettings
from .client import FahWorkServerClient


class FahAsynchronousComputeService(SynchronousComputeService):
    """An asynchronous compute service for utilizing a Folding@Home work server.

    """

    def __init__(self, settings: FAHSynchronousComputeServiceSettings):
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

        self.fah_client = FahWorkServerClient(...)

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

    def _refresh_heartbeat_thread(self):
        if self.heartbeat_thread is None:
            self.heartbeat_thread = threading.Thread(target=self.heartbeat, daemon=True)
            self.heartbeat_thread.start()

        # check that heartbeat is still alive; if not, resurrect it
        elif not self.heartbeat_thread.is_alive():
            self.heartbeat_thread = threading.Thread(
                target=self.heartbeat, daemon=True
            )
            self.heartbeat_thread.start()

    async def execute_DAG(self, protocoldag):
        ...

    async def async_execute(self, task: ScopedKey) -> ScopedKey:
        """Executes given Task.

        Returns ScopedKey of ProtocolDAGResultRef following push to database.

        """
        # obtain a ProtocolDAG from the task
        self.logger.info("Creating ProtocolDAG from '%s'...", task)
        protocoldag, transformation, extends = self.task_to_protocoldag(task)
        self.logger.info(
            "Created '%s' from '%s' performing '%s'",
            protocoldag,
            task,
            transformation.protocol,
        )

        # execute the task; this looks the same whether the ProtocolDAG is a
        # success or failure

        shared = self.shared_basedir / str(protocoldag.key)
        shared.mkdir()
        scratch = self.scratch_basedir / str(protocoldag.key)
        scratch.mkdir()

        self.logger.info("Executing '%s'...", protocoldag)
        try:
            # TODO need a custom `execute_DAG` here that feeds appropriate info
            # (via context?), such as the fah client, to units that interact with F@H
            protocoldagresult = await execute_DAG(
                protocoldag,
                shared_basedir=shared,
                scratch_basedir=scratch,
                keep_scratch=self.keep_scratch,
                raise_error=False,
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

    async def async_cycle(self, max_tasks: Optional[int] = None, max_time: Optional[int] = None):
        self._check_max_tasks(max_tasks)
        self._check_max_time(max_time)

        # claim as many tasks as we are allowed to at once
        # TODO: only want to claim tasks that correspond to FAH protocols
        # claim tasks from the compute API
        self.logger.info("Claiming tasks")
        task_sks: List[ScopedKey] = self.client.claim_tasks(self.claim_limit)

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

            done, pending = await asyncio.wait(async_tasks,
                                               return_when=asyncio.FIRST_COMPLETED)

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
            task_sks: List[ScopedKey] = self.client.claim_tasks()
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
        # add ComputeServiceRegistration
        self.logger.info("Starting up service '%s'", self.name)
        self._register()
        self.logger.info(
            "Registered service with registration '%s'", str(self.compute_service_id)
        )

        # start up heartbeat thread
        self._refresh_heartbeat_thread()

        # stop conditions will use these
        self._tasks_counter = 0
        self._start_time = time.time()

        # TODO: add running count of successes/failures, log to output
        try:
            self.logger.info("Starting main loop")
            while not self._stop:

                # refresh heartbeat in case it died
                self._refresh_heartbeat_thread()

                # perform continuous cycle until available tasks exhausted
                asyncio.run(self.async_cycle(max_tasks, max_time))

                # force a garbage collection to avoid consuming too much memory
                gc.collect()
        except KeyboardInterrupt:
            self.logger.info("Caught SIGINT/Keyboard interrupt.")
        except SleepInterrupted:
            self.logger.info("Service stopping.")
        finally:
            # remove ComputeServiceRegistration, drop all claims
            self._deregister()
            self.logger.info(
                "Deregistered service with registration '%s'",
                str(self.compute_service_id),
            )


