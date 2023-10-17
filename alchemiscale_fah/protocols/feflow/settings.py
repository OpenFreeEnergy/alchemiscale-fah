from feflow.settings.nonequilibrium_cycling import NonEquilibriumCyclingSettings

from ...settings.fah_settings import FahCoreSettings


class FahNonEquilibriumCyclingSettings(NonEquilibriumCyclingSettings):

    fah_settings: FahCoreSettings
