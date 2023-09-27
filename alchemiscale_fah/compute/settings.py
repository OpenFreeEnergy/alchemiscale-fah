import os
from typing import Union, Optional, List, Dict, Tuple
from pydantic import BaseModel

from alchemiscale.models import Scope, ScopedKey


class FAHSynchronousComputeServiceSettings(BaseModel):
    api_url: str
    identifier: str
    key: str
    name: str
    shared_basedir: os.PathLike
    scratch_basedir: os.PathLike
    keep_shared: bool = False
    keep_scratch: bool = False
    sleep_interval: int = 30
    heartbeat_interval: int = 300
    scopes: Optional[List[Scope]] = None
    claim_limit: int = 1
    loglevel = "WARN"
    logfile: Optional[os.PathLike] = None
    client_max_retries = (5,)
    client_retry_base_seconds = 2.0
    client_retry_max_seconds = 60.0
    client_verify = True


"""
        Parameters
        ----------
        api_url
            URL of the compute API to execute Tasks for.
        identifier
            Identifier for the compute identity used for authentication.
        key
            Credential for the compute identity used for authentication.
        name
            The name to give this compute service; used for Task provenance, so
            typically set to a distinct value to distinguish different compute
            resources, e.g. different hosts or HPC clusters.
        shared_basedir
            Filesystem path to use for `ProtocolDAG` `shared` space.
        scratch_basedir
            Filesystem path to use for `ProtocolUnit` `scratch` space.
        keep_shared
            If True, don't remove shared directories for `ProtocolDAG`s after
            completion.
        keep_scratch
            If True, don't remove scratch directories for `ProtocolUnit`s after
            completion.
        sleep_interval
            Time in seconds to sleep if no Tasks claimed from compute API.
        heartbeat_interval
            Frequency at which to send heartbeats to compute API.
        scopes
            Scopes to limit Task claiming to; defaults to all Scopes accessible
            by compute identity.
        claim_limit
            Maximum number of Tasks to claim at a time from a TaskHub.
        loglevel
            The loglevel at which to report; see the :mod:`logging` docs for
            available levels.
        logfile
            Path to file for logging output; if not set, logging will only go
            to STDOUT.
        client_max_retries
            Maximum number of times to retry a request. In the case the API
            service is unresponsive an expoenential backoff is applied with
            retries until this number is reached. If set to -1, retries will
            continue indefinitely until success.
        client_retry_base_seconds
            The base number of seconds to use for exponential backoff.
            Must be greater than 1.0.
        client_retry_max_seconds
            Maximum number of seconds to sleep between retries; avoids runaway
            exponential backoff while allowing for many retries.
        client_verify
            Whether to verify SSL certificate presented by the API server.
"""
