"""
:mod:`alchemiscale_fah.protocols.feflow.nonequilibrium_cycling` --- non-equilibrium cycling protocol for Folding@Home
=====================================================================================================================

"""

from typing import Any
from io import BytesIO

import numpy as np
import pandas as pd

from gufe.settings import Settings

from openff.units import unit
from feflow.protocols.nonequilibrium_cycling import NonEquilibriumCyclingProtocol

from ..protocolunit import FahOpenMMSimulationUnit, FahContext
from ...settings.fah_settings import FahOpenMMCoreSettings


class FahNonEquilibriumCyclingSimulationUnit(FahOpenMMSimulationUnit):
    """A SimulationUnit for performing and returning results from executing
    nonequilibrium cycling via OpenMM on Folding@Home.

    """

    @staticmethod
    def _is_header_line(line: bytes) -> bool:
        """
        Determine if the specified line is a globals.csv header line

        Parameters
        ----------
        line : str
            The line to evaluate

        Returns
        -------
        is_header_line : bool
            If True, `line` is a header line

        """
        return "kT" in line.decode("utf-8")

    def _get_last_header_line(self, csv_content: bytes) -> int:
        """
        Return the line index of the last occurrence of the globals.csv header
        in order to filter out erroneously repeated headers

        Parameters
        ----------
        path : str
            The path to the globals.csv file

        Returns
        -------
        index : int
            The index of the last header line
        """
        with BytesIO(csv_content) as f:
            lines = f.readlines()
        header_lines = [i for i, line in enumerate(lines) if self._is_header_line(line)]
        if not header_lines:
            raise ValueError(f"Missing header in CSV content")
        return header_lines[-1]

    def postprocess_globals(
        self, globals_csv_content: bytes, ctx: FahContext
    ) -> dict[str, Any]:

        # TODO: Because of a known bug in core22 0.0.11,
        # globals.csv can have duplicate headers or duplicate records
        # if the core is paused and resumed.
        # https://github.com/FoldingAtHome/openmm-core/issues/281

        # Start with the last header entry (due to aforementioned bug)
        header_line_number = self._get_last_header_line(globals_csv_content)

        with BytesIO(globals_csv_content) as f:
            df = pd.read_csv(f, header=header_line_number)

        df = df[["lambda", "protocol_work"]]

        forward_works = []
        reverse_works = []

        prev_lambda = None
        prev_work = None
        mode = None
        for i, row in df.iterrows():
            if prev_lambda is None:
                prev_lambda = row["lambda"]
                prev_work = row["protocol_work"]
                continue

            if np.isclose(row["lambda"], prev_lambda) and np.isclose(prev_lambda, 0):
                mode = "A"
            elif (row["lambda"] - prev_lambda) > 0:
                if mode == "A":
                    forward_works.append(prev_work)
                mode = "A->B"
                forward_works.append(row["protocol_work"])
            elif np.isclose(row["lambda"], prev_lambda) and np.isclose(prev_lambda, 1):
                mode = "B"
            elif (row["lambda"] - prev_lambda) < 0:
                if mode == "B":
                    reverse_works.append(prev_work)
                mode = "B->A"
                reverse_works.append(row["protocol_work"])

            prev_lambda = row["lambda"]
            prev_work = row["protocol_work"]

        forward_work_path = ctx.shared / f"forward_{self.name}.npy"
        reverse_work_path = ctx.shared / f"reverse_{self.name}.npy"
        with open(forward_work_path, "wb") as out_file:
            np.save(out_file, forward_works)
        with open(reverse_work_path, "wb") as out_file:
            np.save(out_file, reverse_works)

        return {
            "forward_work": forward_work_path,
            "reverse_work": reverse_work_path,
        }


# TODO: add validators to inputs to ensure good behavior on Folding@Home
class FahNonEquilibriumCyclingProtocol(NonEquilibriumCyclingProtocol):
    _simulation_unit = FahNonEquilibriumCyclingSimulationUnit

    def __init__(self, settings: Settings):
        super().__init__(settings)

    @classmethod
    def _default_settings(cls):
        from .settings import FahNonEquilibriumCyclingSettings
        from gufe.settings import OpenMMSystemGeneratorFFSettings, ThermoSettings
        from openfe.protocols.openmm_utils.omm_settings import (
            SystemSettings,
            SolvationSettings,
        )
        from openfe.protocols.openmm_rfe.equil_rfe_settings import AlchemicalSettings

        return FahNonEquilibriumCyclingSettings(
            forcefield_settings=OpenMMSystemGeneratorFFSettings(),
            thermo_settings=ThermoSettings(temperature=300 * unit.kelvin),
            system_settings=SystemSettings(),
            solvation_settings=SolvationSettings(),
            alchemical_settings=AlchemicalSettings(),
            fah_settings=FahOpenMMCoreSettings(),
        )
