from pathlib import Path
from typing import Union, Optional, List, Dict, Tuple
from pydantic import BaseModel, Field

from alchemiscale.models import Scope, ScopedKey
from alchemiscale.compute.settings import ComputeServiceSettings


class FahAsynchronousComputeServiceSettings(ComputeServiceSettings):
    """Settings schema for a FahSynchronousComputeService."""

    fah_as_url: str = Field(
        ...,
        description="URL of the FAH assignment server to use.",
    )
    fah_ws_url: str = Field(
        ...,
        description="URL of the FAH work server to use.",
    )
    fah_certificate_file: Optional[Path] = Field(
        None,
        description="Path to the TLS certificate to use for authentication with FAH servers; required for real deployments.",
    )
    fah_key_file: Optional[Path] = Field(
        None,
        description="Path to the RSA private key used for TLS communication with FAH servers; required for real deployments.",
    )
    fah_csr_file: Optional[Path] = Field(
        None,
        description="Path to the certificate signing request (CSR) file generated from private key, in PEM format. Only needed for use with real FAH servers, not testing. Required for refreshes of the `certificate_file` to be performed via API calls.",
    )
    fah_client_verify: bool = Field(
        True,
        description="Whether to verify SSL certificate presented by the FAH server.",
    )
    fah_cert_update_interval: Optional[int] = Field(
        86400,
        description="Interval in seconds to update the certificate used to authenticate with FAH servers; set to `None` to disable automatic cert renewal.",
    )
    index_dir: Path = Field(
        ...,
        description="Path to leveldb index dir used by the service to track its state.",
    )
    obj_store: Path = Field(
        ...,
        description="Path to object store directory for larger objects, such as ProtocolDAGs.",
    )
    fah_project_ids: List[int] = Field(
        ...,
        description="List of FAH PROJECT ids that this compute service should use for executing compute.",
    )
    fah_poll_interval: int = Field(
        60,
        description="Frequency in seconds between polls of FAH WS API for completed jobs.",
    )
