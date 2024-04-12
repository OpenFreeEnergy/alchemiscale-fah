import pytest
from typing import Any


from alchemiscale_fah.protocols.protocolunit import FahOpenMMSimulationUnit, FahContext


class DummyFahOpenMMSimulationUnit(FahOpenMMSimulationUnit):

    # TODO: make a simpler version of this for testing
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



class TestFahOpenMMSimulationUnit:

    @pytest.fixture
    def testunit(self):
        return DummyFahOpenMMSimulationUnit()

    def test_select_project(self): ...

    def test_generate_core_settings_file(self): ...

    def test_execute(self, tmpdir): ...
