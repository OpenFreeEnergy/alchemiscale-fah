from feflow.settings.nonequilibrium_cycling import NonEquilibriumCyclingSettings

from ...settings.fah_settings import FahOpenMMCoreSettings


class FahNonEquilibriumCyclingSettings(NonEquilibriumCyclingSettings):
    fah_settings: FahOpenMMCoreSettings
