"""
:mod:`alchemiscale_fah.compute.index` --- compute service index interface
=========================================================================

"""

import os
import plyvel
import json
import shutil
from typing import List, Tuple, Optional
from pathlib import Path

from gufe.tokenization import GufeKey, JSON_HANDLER, GufeTokenizable
from gufe.protocols.protocoldag import ProtocolDAG
from gufe.protocols.protocolunit import ProtocolUnitResult
from alchemiscale.models import ScopedKey
from alchemiscale.keyedchain import KeyedChain

from .models import FahProject, FahRun, FahClone


class FahComputeServiceIndex:
    """Persistent index interface for FahComputeServices"""

    def __init__(self, index_dir: os.PathLike, obj_store: Optional[os.PathLike] = None):
        self.index_dir = Path(index_dir).absolute()
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.db = plyvel.DB(str(self.index_dir), create_if_missing=True)

        # self.projects = self.db.prefixed_db(b"projects/")
        # self.runs = self.db.prefixed_db(b"runs/")
        # self.clones = self.db.prefixed_db(b"clones/")

        # self.transformations = self.db.prefixed_db(b"transformations/")
        # self.tasks = self.db.prefixed_db(b"tasks/")

        self.obj_store = Path(obj_store).absolute()
        self.obj_store.mkdir(parents=True, exist_ok=True)

    def set_project(self, project_id: str, fah_project: FahProject):
        """Set the metadata for the given PROJECT."""
        key = f"projects/{project_id}".encode("utf-8")
        value = fah_project.json().encode("utf-8")

        self.db.put(key, value)

    def get_project(self, project_id: str) -> FahProject:
        """Get metadata for the given PROJECT."""
        key = f"projects/{project_id}".encode("utf-8")
        value = self.db.get(key)

        if value is not None:
            value = FahProject.parse_raw(value.decode("utf-8"))

        return value

    def get_project_run_next(self, project_id: str) -> FahProject:
        """Get next available RUN id for the given PROJECT."""
        prefix = f"runs/{project_id}-".encode("utf-8")
        run_ids = sorted(
            [
                int(key.decode("utf-8").split("-")[-1])
                for key in self.db.iterator(prefix=prefix, include_value=False)
            ]
        )

        if run_ids:
            return str(run_ids[-1] + 1)
        else:
            return "0"

    def set_run(self, project_id: str, run_id: str, fah_run: FahRun):
        """Set the metadata for the given RUN.

        Also sets the metadata for the corresponding Transformation.

        """
        with self.db.write_batch(transaction=True) as wb:
            key = f"runs/{project_id}-{run_id}".encode("utf-8")
            value = fah_run.json().encode("utf-8")

            wb.put(key, value)

            key = f"transformations/{fah_run.transformation}".encode("utf-8")
            value = f"{project_id}-{run_id}".encode("utf-8")

            wb.put(key, value)

    def get_run(self, project_id: str, run_id: str) -> FahRun:
        """Get metadata for the given RUN."""
        key = f"runs/{project_id}-{run_id}".encode("utf-8")
        value = self.db.get(key)

        if value is not None:
            value = FahRun.parse_raw(value.decode("utf-8"))

        return value

    def get_run_clone_next(self, project_id: str, run_id: str) -> FahRun:
        """Get next available CLONE id for the given RUN."""
        prefix = f"clones/{project_id}-{run_id}-".encode("utf-8")
        clone_ids = sorted(
            [
                int(key.decode("utf-8").split("-")[-1])
                for key in self.db.iterator(prefix=prefix, include_value=False)
            ]
        )

        if clone_ids:
            return str(clone_ids[-1] + 1)
        else:
            return "0"

    def set_clone(
        self, project_id: str, run_id: str, clone_id: str, fah_clone: FahClone
    ):
        """Set the metadata for the given CLONE.

        Also sets the metadata for the corresponding Task-ProtocolUnit.

        """
        with self.db.write_batch(transaction=True) as wb:
            key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
            value = fah_clone.json().encode("utf-8")

            wb.put(key, value)

            key = f"tasks/{fah_clone.task_sk}/protocolunits/{fah_clone.protocolunit_key}".encode(
                "utf-8"
            )
            value = f"{project_id}-{run_id}-{clone_id}".encode("utf-8")

            wb.put(key, value)

    def get_clone(self, project_id: str, run_id: str, clone_id: str) -> FahClone:
        """Get metadata for the given CLONE."""
        key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
        value = self.db.get(key)

        if value is not None:
            value = FahClone.parse_raw(value.decode("utf-8"))

        return value

    def set_transformation(self, transformation: GufeKey, project_id: str, run_id: str):
        """Set the PROJECT and RUN used for the given Transformation.

        Also sets the metadata for the corresponding RUN.

        """
        with self.db.write_batch(transaction=True) as wb:
            key = f"transformations/{transformation}".encode("utf-8")
            value = f"{project_id}-{run_id}".encode("utf-8")

            wb.put(key, value)

            key = f"runs/{project_id}-{run_id}".encode("utf-8")
            value = (
                FahRun(
                    project_id=project_id,
                    run_id=run_id,
                    transformation_key=str(transformation),
                )
                .json()
                .encode("utf-8")
            )

            wb.put(key, value)

    def get_transformation(
        self, transformation: GufeKey
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get the PROJECT and RUN used for the given Transformation, if already present."""
        key = f"transformations/{transformation}".encode("utf-8")
        value = self.db.get(key)

        if value is not None:
            value = value.decode("utf-8").split("-")
        else:
            value = (None, None)

        return value

    def set_task_protocolunit(
        self,
        task: ScopedKey,
        protocolunit: GufeKey,
        project_id: str,
        run_id: str,
        clone_id: str,
    ):
        """Set the PROJECT, RUN, and CLONE used for the given Task-ProtocolUnit.

        Also sets the metadata for the corresponding CLONE.

        """
        with self.db.write_batch(transaction=True) as wb:
            key = f"tasks/{task}/protocolunits/{protocolunit}".encode("utf-8")
            value = f"{project_id}-{run_id}-{clone_id}".encode("utf-8")

            wb.put(key, value)

            key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
            value = (
                FahClone(
                    project_id=project_id,
                    run_id=run_id,
                    clone_id=clone_id,
                    task_sk=task,
                    protocolunit_key=str(protocolunit),
                )
                .json()
                .encode("utf-8")
            )

            wb.put(key, value)

    def get_task_protocolunit(
        self,
        task: ScopedKey,
        protocolunit: GufeKey,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get the PROJECT, RUN, and CLONE used for the given Task-ProtocolUnit, if already present."""
        key = f"tasks/{task}/protocolunits/{protocolunit}".encode("utf-8")
        value = self.db.get(key)

        if value is not None:
            value = value.decode("utf-8").split("-")
        else:
            value = (None, None, None)

        return value

    def set_task_protocoldag(self, task: ScopedKey, protocoldag: ProtocolDAG) -> Path:
        """Set the ProtocolDAG for the given Task."""
        # TODO: add zstandard compression
        protocoldag_path = self.obj_store / "tasks" / str(task) / "protocoldag.json"
        protocoldag_path.parent.mkdir(parents=True, exist_ok=True)

        with open(protocoldag_path, "w") as f:
            json.dump(
                KeyedChain.gufe_to_keyed_chain_rep(protocoldag),
                f,
                cls=JSON_HANDLER.encoder,
            )

        return protocoldag_path

    def get_task_protocoldag(self, task: ScopedKey) -> Optional[ProtocolDAG]:
        """Get the ProtocolDAG for the given Task."""
        # TODO: add zstandard compression
        protocoldag_path = self.obj_store / "tasks" / str(task) / "protocoldag.json"

        if not protocoldag_path.exists():
            return None

        with open(protocoldag_path, "r") as f:
            protocoldag = KeyedChain(json.load(f, cls=JSON_HANDLER.decoder)).to_gufe()

        return protocoldag

    def set_protocolunit_result(
        self, protocolunit: GufeKey, protocolunitresult: ProtocolUnitResult
    ) -> Path:
        protocolunitresult_path = (
            self.obj_store
            / "protocolunitresults"
            / str(protocolunit)
            / "protocolunitresult.json"
        )
        protocolunitresult_path.parent.mkdir(parents=True, exist_ok=True)

        with open(protocolunitresult_path, "w") as f:
            json.dump(
                KeyedChain.gufe_to_keyed_chain_rep(protocolunitresult),
                f,
                cls=JSON_HANDLER.encoder,
            )

        return protocolunitresult_path

    def get_protocolunit_result(
        self, protocolunit: GufeKey
    ) -> Optional[ProtocolUnitResult]:
        protocolunitresult_path = (
            self.obj_store
            / "protocolunitresults"
            / str(protocolunit)
            / "protocolunitresult.json"
        )

        if not protocolunitresult_path.exists():
            return None

        with open(protocolunitresult_path, "r") as f:
            protocolunitresult = KeyedChain(
                json.load(f, cls=JSON_HANDLER.decoder)
            ).to_gufe()

        return protocolunitresult

    def del_protocolunit_result(self, protocolunit: GufeKey):
        protocolunit_path = self.obj_store / "protocolunitresults" / str(protocolunit)

        if not protocolunit_path.exists():
            return None

        shutil.rmtree(protocolunit_path)
