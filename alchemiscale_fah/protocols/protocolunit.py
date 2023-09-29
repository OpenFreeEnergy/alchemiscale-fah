from gufe.protocols.protocolunit import ProtocolUnit


class FahProtocolUnit(ProtocolUnit):
    ...


class FahOpenMMProtocolUnit(FahProtocolUnit):
    async def _execute(self, ctx, *, state_a, state_b, mapping, settings, **inputs):
        ...
