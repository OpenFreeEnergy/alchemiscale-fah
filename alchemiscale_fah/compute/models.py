from enum import Enum, auto
from typing import Optional
from ipaddress import IPv4Address
from datetime import datetime

from pydantic import BaseModel, Field, validator

from alchemiscale.models import ScopedKey


# FahAdaptiveSamplingClient models


class CompressionTypeEnum(Enum):
    NONE = "NONE"
    BZIP2 = "BZIP2"
    ZLIB = "ZLIB"
    GZIP = "GZIP"
    LZ4 = "LZ4"


class JobStateEnum(Enum):
    NEW = "NEW"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    HELD = "HELD"
    PROCESSING = "PROCESSING"


class FahAdaptiveSamplingModel(BaseModel):
    class Config:
        use_enum_values = True


class ProjectData(FahAdaptiveSamplingModel):
    core_id: str = Field(..., description="The core ID.  E.g. 0xa8.")
    contact: str = Field(
        ..., description="Email of the person responsible for the project."
    )
    runs: int = Field(0, description="The number of runs.")
    clones: int = Field(0, description="The number of clones.")
    gens: int = Field(1, description="Maximum number of generations per job.")
    atoms: int = Field(
        ..., description="Approximate number of atoms in the simulations."
    )
    credit: int = Field(..., description="The base credit awarded for the WU.")
    timeout: float = Field(86400.0, description="Days before the WU can be reassigned.")
    deadline: float = Field(
        172800.0, description="Days in which the WU can be returned for credit."
    )
    compression: CompressionTypeEnum = Field(
        CompressionTypeEnum.ZLIB, description="Enable WU compression."
    )

    # @validator('core_id', pre=True, always=True)
    # def validate_core_id(cls, v, values, **kwargs):
    #    return int(v, 16) if isinstance(v, str) else v

    # TODO: add validator to preconvert emails from strings
    # TODO: add validator to handle compression case insensitive


class JobData(FahAdaptiveSamplingModel):
    server: int = Field(..., description="ID for work server that executed this job.")
    core: Optional[int] = Field(None, description="ID for core that executed this job.")
    project: int = Field(..., description="The project ID.")
    run: int = Field(..., description="The job run.")
    clone: int = Field(..., description="The job clone.")
    gen: int = Field(..., description="The latest job generation.")
    state: JobStateEnum = Field(..., description="The current job state.")
    last: Optional[datetime] = Field(
        None, description="Last time the job state changed."
    )
    retries: Optional[int] = Field(
        None, description="Number of times the job has been retried."
    )
    assigns: Optional[int] = Field(
        None, description="Number of times the job has been assigned."
    )
    progress: Optional[int] = Field(None, description="Job progress.")


class JobResults(FahAdaptiveSamplingModel):
    jobs: list[JobData] = Field(..., description="List of jobs.")
    ts: datetime = Field(..., description="Timestamp for these results.")


class FileData(FahAdaptiveSamplingModel):
    path: str = Field(
        ..., description="File path relative to the project, job or gen directory."
    )
    size: int = Field(..., description="The file size in bytes.")
    modified: datetime = Field(..., description="The file modification time.")


class ASCSR(FahAdaptiveSamplingModel):
    csr: str = Field(..., description="Certificate Signing Request in PEM format")

class ASCertificate(FahAdaptiveSamplingModel):
    certificate: str = Field(..., description="New client certificate in PEM format")
    as_cert: str = Field(..., description="AS certificate in PEM format")

class ASWorkServerData(FahAdaptiveSamplingModel):
    max_assign_rate: float = Field(
        ..., description="The maximum assigns/sec allowed for this WS."
    )
    weight: float = Field(..., description="The WS weight.")
    contraints: str = Field(
        ..., description="WS constraints as defined in the AS online help."
    )


class ASProjectData(FahAdaptiveSamplingModel):
    ws: IPv4Address = Field(..., description="IP Address of the WS.")
    weight: float = Field(..., description="The project weight.")
    contraints: str = Field(
        ..., description="Project constraints as defined in the AS online help."
    )


# FahAsynchronousComputeService models


# TODO: documentation and enum for nonbonded_settings
class FahProject(BaseModel):
    project_id: str
    n_atoms: int
    nonbonded_settings: str


class FahRun(BaseModel):
    project_id: str
    run_id: str
    transformation_key: str


class FahClone(BaseModel):
    project_id: str
    run_id: str
    clone_id: str
    task_sk: ScopedKey
