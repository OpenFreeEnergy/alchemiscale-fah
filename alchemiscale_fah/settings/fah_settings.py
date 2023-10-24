from pydantic import Field
from gufe.settings import Settings


class FahCoreSettings(Settings):
    ...

    numSteps: int = Field(2500000, description="Total number of steps for FahSimulationUnit; aim to keep execution to just a few hours.")
    xtcFreq: int = Field(250000, description="Number of steps to wait before writing a snapshot to the XTC trajectory file; 10 - 40 snapshots usually sufficient.")
