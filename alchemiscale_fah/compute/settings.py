import os
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
    fah_certificate_file: os.PathLike = Field(
        ...,
        description="Path to the TLS certificate to use for authentication with FAH servers",
    )
    fah_key_file: os.PathLike = Field(
        ...,
        description="Path to the RSA private key used for TLS communication with FAH servers.",
    )
    fah_client_verify: bool = Field(
        True,
        description="Whether to verify SSL certificate presented by the FAH server.",
    )

    index_file: os.PathLike = Field(
        ...,
        description="Path to leveldb index file used by the service to track its state.",
    )
    obj_store: os.PathLike = Field(
        ...,
        description="Path to object store directory for larger objects, such as ProtocolDAGs.",
    )
