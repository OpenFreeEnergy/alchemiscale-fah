"""
:mod:`alchemiscale_fah.compute.index` --- compute service index interface
=========================================================================

"""

import os
import plyvel
import json
from typing import List, Tuple, Optional
from pathlib import Path

from gufe.tokenization import GufeKey, JSON_HANDLER, GufeTokenizable
from gufe.protocols.protocoldag import ProtocolDAG
from alchemiscale.models import ScopedKey
from alchemiscale.utils import keyed_dicts_to_gufe, gufe_to_keyed_dicts

from .models import FahProject, FahRun, FahClone


class FahComputeServiceIndex:
    """Persistent index interface for FahComputeServices"""

    def __init__(
        self, index_file: os.PathLike, obj_store: Optional[os.PathLike] = None
    ):
        self.db = plyvel.DB(index_file, create_if_missing=True)

        # self.projects = self.db.prefixed_db(b"projects/")
        # self.runs = self.db.prefixed_db(b"runs/")
        # self.clones = self.db.prefixed_db(b"clones/")

        # self.transformations = self.db.prefixed_db(b"transformations/")
        # self.tasks = self.db.prefixed_db(b"tasks/")

        self.obj_store = Path(obj_store).absolute()
        os.makedirs(obj_store, exist_ok=True)

    def set_project(self, project_id: str, fah_project: FahProject):
        """Set the metadata for the given PROJECT."""
        key = f"projects/{project_id}".encode("utf-8")
        value = fah_project.json().encode("utf-8")

        self.db.put(key, value)

    def get_project(self, project_id: str) -> FahProject:
        """Get metadata for the given PROJECT."""
        key = f"projects/{project_id}".encode("utf-8")
        value = self.db.get(key).decode("utf-8")

        if value is not None:
            value = FahProject.parse_raw(value)

        return value

    def get_project_run_next(self, project_id: str) -> FahProject:
        """Get next available RUN id for the given PROJECT."""
        prefix = f"runs/{project_id}-".encode("utf-8")
        run_ids = sorted(
            [
                int(key.split("-")[-1])
                for key in self.db.iterator(prefix=prefix, include_value=False)
            ]
        )

        return str(run_ids[-1] + 1)

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
        value = self.db.get(key).decode("utf-8")

        if value is not None:
            value = FahRun.parse_raw(value)

        return value

    def get_run_clone_next(self, project_id: str, run_id: str) -> FahRun:
        """Get metadata for the given RUN."""
        prefix = f"clones/{project_id}-{run_id}-".encode("utf-8")
        run_ids = sorted(
            [
                int(key.split("-")[-1])
                for key in self.db.iterator(prefix=prefix, include_value=False)
            ]
        )

        return str(run_ids[-1] + 1)

    def set_clone(
        self, project_id: str, run_id: str, clone_id: str, fah_clone: FahClone
    ):
        """Set the metadata for the given CLONE.

        Also sets the metadata for the corresponding Task.

        """
        with self.db.write_batch(transaction=True) as wb:
            key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
            value = fah_clone.json().encode("utf-8")

            wb.put(key, value)

            key = f"tasks/{fah_clone.task_sk}".encode("utf-8")
            value = f"{project_id}-{run_id}-{clone_id}".encode("utf-8")

            wb.put(key, value)

    def get_clone(self, project_id: str, run_id: str, clone_id: str) -> FahClone:
        """Get metadata for the given CLONE."""
        key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
        value = self.db.get(key).decode("utf-8")

        if value is not None:
            value = FahClone.parse_raw(value)

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
        value = self.db.get(key).decode("utf-8")

        if value is not None:
            value = value.split("-")
        else:
            value = (None, None)

        return value

    def set_task(self, task: ScopedKey, project_id: str, run_id: str, clone_id: str):
        """Set the PROJECT, RUN, and CLONE used for the given Task.

        Also sets the metadata for the corresponding CLONE.

        """
        with self.db.write_batch(transaction=True) as wb:
            key = f"tasks/{task}".encode("utf-8")
            value = f"{project_id}-{run_id}-{clone_id}".encode("utf-8")

            wb.put(key, value)

            key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
            value = (
                FahClone(
                    project_id=project_id,
                    run_id=run_id,
                    clone_id=clone_id,
                    task_sk=task,
                )
                .json()
                .encode("utf-8")
            )

            wb.put(key, value)

    def get_task(
        self, task: ScopedKey
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get the PROJECT, RUN, and CLONE used for the given Task, already present."""
        key = f"tasks/{task}".encode("utf-8")
        value = self.db.get(key).decode("utf-8")

        if value is not None:
            value = value.split("-")
        else:
            value = (None, None, None)

        return value

    def set_task_protocoldag(self, task: ScopedKey, protocoldag: ProtocolDAG) -> Path:
        """Set the ProtocolDAG for the given Task."""
        # TODO: add zstandard compression
        protocoldag_path = self.obj_store / "tasks" / str(task) / "protocoldag.json"
        protocoldag_path.parent.mkdir(parents=True, exist_ok=True)

        with open(protocoldag_path, "w") as f:
            json.dump(gufe_to_keyed_dicts(protocoldag), f, cls=JSON_HANDLER.encoder)

        return protocoldag_path

    def get_task_protocoldag(self, task: ScopedKey) -> ProtocolDAG:
        """Get the ProtocolDAG for the given Task."""
        # TODO: add zstandard compression
        protocoldag_path = self.obj_store / "tasks" / str(task) / "protocoldag.json"

        with open(protocoldag_path, "r") as f:
            protocoldag = keyed_dicts_to_gufe(json.load(f, cls=JSON_HANDLER.decoder))

        return protocoldag
