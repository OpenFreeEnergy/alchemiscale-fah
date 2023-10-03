"""
:mod:`alchemiscale_fah.protocols.feflow.nonequilibrium_cycling` --- non-equilibrium cycling protocol for Folding@Home
=====================================================================================================================

"""

from feflow.protocols.nonequilibrium_cycling import NonEquilibriumCyclingProtocol

from ..protocolunit import FahOpenMMSimulationUnit


class FahNonEqulibriumCyclingProtocol(NonEquilibriumCyclingProtocol):
    _simulation_unit = FahOpenMMSimulationUnit
