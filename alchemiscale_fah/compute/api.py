"""
:mod:`alchemiscale_fah.compute.api` --- mock F@H Work Server API for testing
============================================================================

"""


import os
from pathlib import Path

import plyvel
from fastapi import FastAPI, APIRouter, Body, Depends, HTTPException, status

from ..settings.fah_wsapi_settings import WSAPISettings, get_wsapi_settings


class WSStateDB:

    def __init__(self, state_dir: os.PathLike):
        self.db = plyvel.DB(state_dir, create_if_missing=True)

    def reset(self):
        ...

    def create_clone(self, project_id, run_id, clone_id):
        with self.db.write_batch(transaction=True) as wb:
            key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
            value = "READY"

            wb.put(key, value)

    def get_clone(self, project_id, run_id, clone_id):
        key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
        value = self.db.get(key).decode("utf-8")

    def finish_clone(self, project_id, run_id, clone_id):
        with self.db.write_batch(transaction=True) as wb:
            key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
            value = "FINISHED"

            wb.put(key, value)


def get_wsstatedb_depends(settings: WSAPISettings = Depends(get_wsapi_settings)) -> WSStateDB:
    return WSStateDB(settings.WSAPI_STATE_DIR)


def get_inputs_dir_depends(settings: WSAPISettings = Depends(get_wsapi_settings)) -> Path:
    return settings.WSAPI_INPUTS_DIR


def get_outputs_dir_depends(settings: WSAPISettings = Depends(get_wsapi_settings)) -> Path:
    return settings.WSAPI_OUTPUTS_DIR


app = FastAPI(title="FahWSAPI")


@app.put("/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/create")
def create_clone(
        project_id,
        run_id,
        clone_id,
        statedb: WSStateDB = Depends(get_wsstatedb_depends),
        ):
    # create clone instance in database
    statedb.create_clone(project_id, run_id, clone_id)


@app.get("/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}")
def get_clone(
        project_id,
        run_id,
        clone_id,
        statedb: WSStateDB = Depends(get_wsstatedb_depends),
        ):
    # return clone state information
    return statedb.get_clone(project_id, run_id, clone_id)


@app.put("/api/projects/{project_id}/files/RUN{run_id}/CLONE{clone_id}/{dest}")
def create_clone_file(
        project_id,
        run_id,
        clone_id,
        dest,
        inputs_dir: Path = Depends(get_inputs_dir_depends),
        ):
    # create clone files in inputs dir
    ...


# NOTE: this is not a real API endpoint on a work server, but is used by tests
# to simulate work completing
@app.put("/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/_finish")
def _finish_clone(
        project_id,
        run_id,
        clone_id,
        outputs_dir: Path = Depends(get_outputs_dir_depends),
        statedb: WSStateDB = Depends(get_wsstatedb_depends),
        ):
    # create results directory
    ...

    # create simulated result files
    ...

    # set finished state
    statedb.finish_clone(project_id, run_id, clone_id)
