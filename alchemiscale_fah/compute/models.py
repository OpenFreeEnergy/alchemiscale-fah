from enum import Enum, auto
from ipaddress import ip_address
from datetime import datetime

from pydantic import BaseModel, Field


class JobAction(Enum):
    create = auto()
    fail = auto()
    reset = auto()
    stop = auto()
    restart = auto()


class CompressionType(Enum):
    none = auto()
    bzip2 = auto()
    zlib = auto()
    gzip = auto()
    lz4 = auto()


class JobState(Enum):
    new = auto()
    ready = auto()
    assigned = auto()
    finished = auto()
    failed = auto()
    stopped = auto()
    held = auto()
    processing = auto()


class Email(BaseModel):
    domain: str
    user: str


class FahAdaptiveSamplingModel(BaseModel):
    ...


class ProjectData(FahAdaptiveSamplingModel):
    core_id: int = Field(
        ..., description="The core ID.  E.g. 0xa8."
    )
    contact: Email = Field(
        ..., description="The person responsible for the project."
    )
    runs: int = Field(
        ..., description="The number of runs."
    )
    clones: int = Field(
        ..., description="The number of clones."
    )
    gens: int = Field(
        ..., description="Maximum number of generations per job."
    )
    atoms: int = Field(
        ..., description="Approximate number of atoms in the simulations."
    )
    credit: int = Field(
        ..., description="The base credit awarded for the WU."
    )
    timeout: float = Field(
        ..., description="Days before the WU can be reassigned."
    )
    deadline: float = Field(
        ..., description="Days in which the WU can be returned for credit."
    )
    compression: CompressionType = Field(
        ..., description="Enable WU compression."
    )


class JobData(FahAdaptiveSamplingModel):
    project: int = Field(
        ..., description="The project ID."
    )
    run: int = Field(
        ..., description="The job run."
    )
    clone: int = Field(
        ..., description="The job clone."
    )
    gen: int = Field(
        ..., description="The latest job generation."
    )
    state: JobState = Field(
        ..., description="The current job state."
    )
    last: datetime = Field(
        ..., description="Last time the job state changed."
    ) 


class JobResults(FahAdaptiveSamplingModel):
    jobs: list[JobData] = Field(
        ..., description="List of jobs."
    )
    ts: datetime = Field(
        ..., description="Timestamp for these results."
    ) 


class FileData(FahAdaptiveSamplingModel):
    path: str = Field(
        ..., description="File path relative to the project, job or gen directory."
    )
    size: int = Field(
        ..., description="The file size in bytes."
    ) 
    modified: datetime = Field(
        ..., description="The file modification time."
    ) 


class ASWorkServerData(FahAdaptiveSamplingModel):
    max_assign_rate: float = Field(
        ..., description="The maximum assigns/sec allowed for this WS."
    )
    weight: float = Field(
        ..., description="The WS weight."
    ) 
    contraints: str = Field(
        ..., description="WS constraints as defined in the AS online help."
    ) 


class ASProjectData(FahAdaptiveSamplingModel):
    ws: ip_address = Field(
        ..., description="IP Address of the WS."
    )
    weight: float = Field(
        ..., description="The project weight."
    ) 
    contraints: str = Field(
        ..., description="Project constraints as defined in the AS online help."
    ) 
