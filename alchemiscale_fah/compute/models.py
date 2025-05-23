from typing import Optional
from ipaddress import IPv4Address
from datetime import datetime
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    NonNegativeInt,
    PositiveInt,
    PositiveFloat,
)

from alchemiscale.models import ScopedKey
from ..utils import NonbondedSettings


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
    core_id: str = Field(
        ..., description="The core ID in hex (base 16) format.  E.g. 0xa8."
    )
    contact: str = Field(
        ..., description="Email of the person responsible for the project."
    )
    runs: NonNegativeInt = Field(0, description="The number of runs.")
    clones: NonNegativeInt = Field(0, description="The number of clones.")
    gens: PositiveInt = Field(1, description="Maximum number of generations per job.")
    atoms: PositiveInt = Field(
        ..., description="Approximate number of atoms in the simulations."
    )
    credit: PositiveInt = Field(..., description="The base credit awarded for the WU.")
    timeout: PositiveInt = Field(
        86400, description="Seconds before the WU can be reassigned."
    )
    deadline: PositiveInt = Field(
        172800, description="Seconds in which the WU can be returned for credit."
    )
    compression: CompressionTypeEnum = Field(
        CompressionTypeEnum.ZLIB,
        description="Enable WU compression.",
        validate_default=True,
    )

    @field_validator("core_id", mode="before")
    def validate_core_id(cls, v, values, **kwargs):
        if not v[:2] == "0x":
            raise ValueError("`core_id` must be given in hex format, e.g. 0xa8")
        try:
            int(v, 16)
        except:
            raise ValueError("`core_id` must be given in hex format, e.g. 0xa8")

        return v

    @field_validator("timeout", mode="before")
    def validate_timeout(cls, v, values, **kwargs):
        if v < 300:
            raise ValueError(
                "`timeout` must not be less than 300; it will be interpreted as days if so"
            )

        return v

    @field_validator("deadline", mode="before")
    def validate_deadline(cls, v, values, **kwargs):
        if v < 300:
            raise ValueError(
                "`deadline` must not be less than 300; it will be interpreted as days if so"
            )

        return v

    # TODO: add validator to preconvert emails from strings
    # TODO: add validator to handle compression case insensitive


class JobData(FahAdaptiveSamplingModel):
    server: int = Field(..., description="ID for work server that executed this job.")
    core: Optional[int] = Field(
        None, description="ID for core that executed this job, as base-10 integer."
    )
    project: NonNegativeInt = Field(..., description="The project ID.")
    run: NonNegativeInt = Field(..., description="The job run.")
    clone: NonNegativeInt = Field(..., description="The job clone.")
    gen: NonNegativeInt = Field(..., description="The latest job generation.")
    state: JobStateEnum = Field(..., description="The current job state.")
    last: Optional[datetime] = Field(
        None, description="Last time the job state changed."
    )
    retries: Optional[NonNegativeInt] = Field(
        None, description="Number of times the job has been retried."
    )
    assigns: Optional[NonNegativeInt] = Field(
        None, description="Number of times the job has been assigned."
    )
    progress: Optional[NonNegativeInt] = Field(None, description="Job progress.")

    @field_validator("core", mode="before")
    def validate_core(cls, v, values, **kwargs):
        if isinstance(v, str):
            if v[:2] == "0x":
                return int(v, 16)
            else:
                return int(v)
        else:
            return v


class JobResults(FahAdaptiveSamplingModel):
    jobs: list[JobData] = Field(..., description="List of jobs.")
    ts: datetime = Field(..., description="Timestamp for these results.")


class FileData(FahAdaptiveSamplingModel):
    path: str = Field(
        ..., description="File path relative to the project, job or gen directory."
    )
    size: NonNegativeInt = Field(..., description="The file size in bytes.")
    modified: datetime = Field(..., description="The file modification time.")


class ASCSR(FahAdaptiveSamplingModel):
    csr: str = Field(..., description="Certificate Signing Request in PEM format")


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


class FahCoreType(Enum):
    openmm = "openmm"
    gromacs = "gromacs"


# TODO: documentation
class FahProject(BaseModel):
    project_id: NonNegativeInt
    n_atoms: PositiveInt
    nonbonded_settings: NonbondedSettings
    core_type: FahCoreType
    core_id: str = Field(
        ..., description="The core ID in hex (base 16) format.  E.g. 0xa8."
    )


class FahRun(BaseModel):
    project_id: NonNegativeInt
    run_id: NonNegativeInt
    transformation_key: str


class FahClone(BaseModel):
    project_id: NonNegativeInt
    run_id: NonNegativeInt
    clone_id: NonNegativeInt
    task_sk: ScopedKey
    protocolunit_key: str
