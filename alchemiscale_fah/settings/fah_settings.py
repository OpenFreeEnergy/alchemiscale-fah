from typing import Optional, Union

from pydantic import Field
from gufe.settings import Settings


class FahOpenMMCoreSettings(Settings):
    # required
    numSteps: int = Field(
        2500000,
        description="Total number of steps for FahSimulationUnit; aim to keep execution to just a few hours.",
    )
    xtcFreq: int = Field(
        250000,
        description="Number of steps to wait before writing a snapshot to the XTC trajectory file; 10 - 40 snapshots usually sufficient.",
    )

    # optional
    ## intervals
    checkpointFreq: int = Field(
        -5,
        description="Interval at which checkpoint is to be written (default: -5 [5%])",
    )
    viewerFreq: int = Field(
        -1, "Interval at which JSON viewer frame is to be written (default: -1 [1%])"
    )
    globalVarFreq: int = Field(
        2500, "Interval at which global variables are to be written"
    )

    ## other
    maxRetriesFromLastCheckpoint: int = Field(
        2,
        "Specify the maximum number of retries from the last checkpoint (optional, default: 2)",
    )
    precision: str = Field(
        "single",
        "Specify the OpenMM OpenCL platform precision [mixed, single, double] (optional, default: single)",
    )
    xtcMinAtom: Optional[int] = Field(
        None,
        "If specified, this is the minimum atom index returned in the XTC file (optional)",
    )
    xtcMaxAtom: int = Field(
        None,
        "If specified, this is the maximum atom index returned in the XTC file (optional)",
    )
    xtcAtoms: Optional[Union[str, list[int]]] = Field(
        None, "If specified, solute will ensure no water is stored (optional)"
    )
    trrFreq: int = Field(
        0,
        "Specify the interval with which TRR frames are written (optional, default: 0, i.e., not saving TRR file)",
    )
    trrMinAtom: Optional[int] = Field(
        None,
        "If specified, this is the minimum atom index returned in the TRR file (optional)",
    )
    trrMaxAtom: int = Field(
        None,
        "If specified, this is the maximum atom index returned in the XTC file (optional)",
    )
    trrAtoms: Optional[Union[str, list[int]]] = Field(
        None, "If specified, solute will ensure no water is stored (optional)"
    )
    saveForcesInTrr: Optional[int] = Field(
        None,
        "If 1 and trrFreq is nonzero, forces will be stored. The frame and atom indices mirror the settings for TRR coordinates (optional)",
    )
    forceTolerance: float = Field(
        5.0,
        "Force tolerance for triggering Bad State errors (kJ/mol/nm) (optional, default: 5 kJ/mol/nm)",
    )
    energyTolerance: float = Field(
        10.0,
        "Energy tolerance for triggering Bad State errors (kJ/mol) (optional, default: 10 kJ/mol)",
    )
    DisablePmeStream: int = Field(
        1,
        "Either disable (1) or enable (0) separate PME stream (default: 1); warning, setting 0 may cause failures on some cards",
    )
    globalVarFilename: str = Field(
        "globals.csv", "File to write global variables to (default: globals.csv)"
    )
    disableCheckpointStateTests: int = (
        0,
        "If 1, will disable checkpoint State tests; 0 will perform State tests (default: 0)",
    )
