"""
:mod:`alchemiscale_fah.compute.service` --- compute services for FEC execution via Folding@Home
===============================================================================================

"""
import os
from typing import Union, Optional, List, Dict, Tuple
from pathlib import Path
from uuid import uuid4
import time
import logging

from alchemiscale.models import Scope, ScopedKey
from alchemiscale.storage.models import Task, TaskHub, ComputeServiceID
from alchemiscale.compute.client import AlchemiscaleComputeClient
from alchemiscale.compute.service import SynchronousComputeService, InterruptableSleep

from .settings import FAHSynchronousComputeServiceSettings
from .client import FahWorkServerClient


class FahSynchronousComputeService(SynchronousComputeService):
    """Fully synchronous compute service for utilizing a Folding@Home work server.

    This service is intended for use as a reference implementation, and for
    testing/debugging protocols.

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
