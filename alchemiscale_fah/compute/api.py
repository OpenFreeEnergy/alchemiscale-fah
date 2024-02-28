"""
:mod:`alchemiscale_fah.compute.api` --- mock F@H Work Server API for testing
============================================================================

"""


import os
import shutil
from pathlib import Path
from importlib import resources

import plyvel
from fastapi import FastAPI, APIRouter, Body, Depends, HTTPException, status

from ..settings.fah_wsapi_settings import WSAPISettings, get_wsapi_settings
from .models import JobData, ProjectData


class WSStateDB:

    def __init__(
            self,
            state_dir: os.PathLike,
            server_id: int
            ):
        self.state_dir = state_dir
        self.db = plyvel.DB(str(state_dir.absolute()), create_if_missing=True)

        #with self.db.write_batch(transaction=True) as wb:
        #    wb.put("server-id", str(server_id).encode('utf-8'))

        self.server_id = server_id

    def reset(self):
        keys = [key for key, value in self.db]
        for key in keys:
            self.db.delete(key)

    def create_project(self, project_id, project_data: ProjectData):
        with self.db.write_batch(transaction=True) as wb:
            key = f"projects/{project_id}".encode("utf-8")
            value = project_data.json().encode('utf-8')

            wb.put(key, value)

    def get_project(self, project_id):

        key = f"projects/{project_id}".encode("utf-8")
        value = self.db.get(key).decode("utf-8")

        return ProjectData.parse_raw(value)

    def create_clone(self, project_id, run_id, clone_id):

        project_data = self.get_project(project_id)

        with self.db.write_batch(transaction=True) as wb:
            key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")

            value = JobData(
                    server=self.server_id, 
                    core=project_data.core_id, 
                    project=project_id, run=run_id,
                       clone=clone_id, gen=1, state="READY").json().encode('utf-8')

            wb.put(key, value)

    def get_clone(self, project_id, run_id, clone_id):
        key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
        value = self.db.get(key).decode("utf-8")
        
        return JobData.parse_raw(value)

    def finish_clone(self, project_id, run_id, clone_id):
        project_data = self.get_project(project_id)

        with self.db.write_batch(transaction=True) as wb:
            key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")

            value = JobData(
                    server=self.server_id, 
                    core=project_data.core_id, 
                    project=project_id, run=run_id,
                       clone=clone_id, gen=1, state="FINISHED").json().encode('utf-8')

            wb.put(key, value)


def get_wsstatedb_depends(settings: WSAPISettings = Depends(get_wsapi_settings)) -> WSStateDB:
    return WSStateDB(settings.WSAPI_STATE_DIR, settings.WSAPI_SERVER_ID)


def get_inputs_dir_depends(settings: WSAPISettings = Depends(get_wsapi_settings)) -> Path:
    return settings.WSAPI_INPUTS_DIR


def get_outputs_dir_depends(settings: WSAPISettings = Depends(get_wsapi_settings)) -> Path:
    return settings.WSAPI_OUTPUTS_DIR


app = FastAPI(title="FahWSAPI")


@app.get("/ping")
def _ping():
    return {"api": "FahWSAPI"}


@app.put("/reset")
def _reset(
        statedb: WSStateDB = Depends(get_wsstatedb_depends),
        inputs_dir: Path = Depends(get_inputs_dir_depends),
        outputs_dir: Path = Depends(get_outputs_dir_depends),
        ):
    statedb.reset()

    if inputs_dir.exists():
        shutil.rmtree(inputs_dir)

    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)


@app.put("/api/projects/{project_id}")
def create_project(
        project_id,
        project_data: ProjectData = Body(),
        statedb: WSStateDB = Depends(get_wsstatedb_depends),
        inputs_dir: Path = Depends(get_inputs_dir_depends),
        outputs_dir: Path = Depends(get_outputs_dir_depends),
        ):
    # create project instance in database
    statedb.create_project(project_id, project_data)

    # create project input and output dirs
    project_inputs = (inputs_dir / f"p{project_id}")
    project_inputs.mkdir(parents=True)
    (outputs_dir / f"PROJ{project_id}").mkdir(parents=True)

    # write projectdata to project.json (actually an XML file on a real WS)
    with open(project_inputs / 'project.json', 'w') as f:
        f.write(project_data.json())


@app.put("/api/projects/{project_id}/files/{dest}")
def create_project_file(
        project_id,
        dest,
        file_data: bytes = Body(),
        inputs_dir: Path = Depends(get_inputs_dir_depends),
        ):
    project_inputs = (inputs_dir / f"p{project_id}")
    dest_path = project_inputs.join(dest)
    
    # make parent directories if they don't exist
    dest_path.parent.mkdir(parents=True)

    with open(dest_path, 'wb') as f:
        f.write(file_data)


@app.get("/api/projects/{project_id}")
def get_project(
        project_id,
        statedb: WSStateDB = Depends(get_wsstatedb_depends),
        ) -> ProjectData:
    # return clone state information
    return statedb.get_project(project_id)


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
        ) -> JobData:
    # return clone state information
    return statedb.get_clone(project_id, run_id, clone_id)


# already serviced by create_project_file
#@app.put("/api/projects/{project_id}/files/RUN{run_id}/CLONE{clone_id}/{dest}")
#def create_clone_file(
#        project_id,
#        run_id,
#        clone_id,
#        dest,
#        file_data: bytes = Body(),
#        inputs_dir: Path = Depends(get_inputs_dir_depends),
#        ):
#    # create clone files in inputs dir
#    clone_inputs = (inputs_dir / f"p{project_id}")
#    dest_path = project_inputs.join(dest)
#    
#    # make parent directories if they don't exist
#    dest_path.parent.mkdir(parents=True)
#
#    with open(dest_path, 'wb') as f:
#        f.write(file_data)


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
    # create output directory
    clone_outputs = (outputs_dir / f"PROJ{project_id}/RUN{run_id}/CLONE{clone_id}")
    gen_outputs = clone_outputs / "results0"

    # create simulated output files
    globals_csv_output_path = gen_outputs / "globals.csv"
    globals_csv_path = resources.as_file(
            resources.files('alchemiscale_fah.tests.data').joinpath('globals.csv'))
    shutil.copy(globals_csv_path, globals_csv_output_path)

    # set finished state
    statedb.finish_clone(project_id, run_id, clone_id)
