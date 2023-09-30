from dataclasses import dataclass

from gufe.protocols.protocolunit import ProtocolUnit, Context

from ..compute.client import FahAdaptiveSamplingClient


@dataclass
class FahContext(Context):
    fah_client: FahAdaptiveSamplingClient


class FahSimulationUnit(ProtocolUnit):
    ...
    def _execute(self, ctx, *, state_a, state_b, mapping, settings, **inputs):
        return {}


class FahOpenMMSimulationUnit(FahSimulationUnit):
    async def _execute(self, ctx, *, state_a, state_b, mapping, settings, **inputs):
        ...

        # take serialized system, state, integrator from SetupUnit


        # pass to work server, create RUN/CLONE as appropriate


        # check for and await sleep results from work server


        # when results available, put them into useful form
        # may be a case where colocation of service on work server pretty
        # critical for performance

        # return results for consumption by ResultUnit

