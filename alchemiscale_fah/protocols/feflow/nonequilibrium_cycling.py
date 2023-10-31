"""
:mod:`alchemiscale_fah.protocols.feflow.nonequilibrium_cycling` --- non-equilibrium cycling protocol for Folding@Home
=====================================================================================================================

"""

from gufe.settings import Settings

from openff.units import unit
from feflow.protocols.nonequilibrium_cycling import NonEquilibriumCyclingProtocol

from ..protocolunit import FahOpenMMSimulationUnit
from ...settings.fah_settings import FahOpenMMCoreSettings


class FahNonEqulibriumCyclingProtocol(NonEquilibriumCyclingProtocol):
    _simulation_unit = FahOpenMMSimulationUnit

    def __init__(self, settings: Settings):
        super().__init__(settings)

    @classmethod
    def _default_settings(cls):
        from .settings import FahNonEquilibriumCyclingSettings
        from gufe.settings import OpenMMSystemGeneratorFFSettings, ThermoSettings
        from openfe.protocols.openmm_utils.omm_settings import SystemSettings, SolvationSettings
        from openfe.protocols.openmm_rfe.equil_rfe_settings import AlchemicalSettings
        return FahNonEquilibriumCyclingSettings(
            forcefield_settings=OpenMMSystemGeneratorFFSettings(),
            thermo_settings=ThermoSettings(temperature=300 * unit.kelvin),
            system_settings=SystemSettings(),
            solvation_settings=SolvationSettings(),
            alchemical_settings=AlchemicalSettings(),
            fah_settings=FahOpenMMCoreSettings()
        )
