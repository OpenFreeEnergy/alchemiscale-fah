"""
:mod:`alchemiscale_fah.compute.api` --- mock F@H Work Server API for testing
============================================================================

"""

import os
import shutil
from pathlib import Path
from importlib import resources
from typing import Annotated
import datetime
from contextlib import contextmanager

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

import plyvel
from starlette.responses import Response
from fastapi import FastAPI, APIRouter, Body, Depends, HTTPException, status, Request

from ..settings.fah_wsapi_settings import WSAPISettings, get_wsapi_settings
from .models import JobData, ProjectData


class WSStateDB:

    def __init__(self, state_dir: os.PathLike, server_id: int):
        self.state_dir = state_dir
        # self.db = plyvel.DB(str(state_dir.absolute()), create_if_missing=True)

        # with self.db.write_batch(transaction=True) as wb:
        #    wb.put("server-id", str(server_id).encode('utf-8'))

        self.server_id = server_id

    @contextmanager
    def db(self) -> plyvel.DB:
        """Context manager for a LevelDB transaction."""
        with plyvel.DB(str(self.state_dir.absolute()), create_if_missing=True) as db:
            yield db

    def reset(self):
        with self.db() as db:
            keys = [key for key, value in db]
            for key in keys:
                db.delete(key)

    def create_project(self, project_id, project_data: ProjectData):

        with self.db() as db:
            with db.write_batch(transaction=True) as wb:
                key = f"projects/{project_id}".encode("utf-8")
                value = project_data.json().encode("utf-8")

                wb.put(key, value)

    def get_project(self, project_id):

        key = f"projects/{project_id}".encode("utf-8")
        with self.db() as db:
            value = db.get(key).decode("utf-8")

        return ProjectData.parse_raw(value)

    def create_clone(self, project_id, run_id, clone_id):

        project_data = self.get_project(project_id)

        with self.db() as db:
            with db.write_batch(transaction=True) as wb:
                key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")

                value = (
                    JobData(
                        server=self.server_id,
                        core=project_data.core_id,
                        project=project_id,
                        run=run_id,
                        clone=clone_id,
                        gen=1,
                        state="READY",
                        last=datetime.datetime.utcnow(),
                    )
                    .json()
                    .encode("utf-8")
                )

                wb.put(key, value)

    def get_clone(self, project_id, run_id, clone_id):
        key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")
        with self.db() as db:
            value = db.get(key).decode("utf-8")

        return JobData.parse_raw(value)

    def finish_clone(self, project_id, run_id, clone_id):
        project_data = self.get_project(project_id)

        with self.db() as db:
            with db.write_batch(transaction=True) as wb:
                key = f"clones/{project_id}-{run_id}-{clone_id}".encode("utf-8")

                value = (
                    JobData(
                        server=self.server_id,
                        core=project_data.core_id,
                        project=project_id,
                        run=run_id,
                        clone=clone_id,
                        gen=1,
                        state="FINISHED",
                        last=datetime.datetime.utcnow(),
                    )
                    .json()
                    .encode("utf-8")
                )

                wb.put(key, value)


def get_wsstatedb_depends(
    settings: WSAPISettings = Depends(get_wsapi_settings),
) -> WSStateDB:
    return WSStateDB(settings.WSAPI_STATE_DIR, settings.WSAPI_SERVER_ID)


def get_tls_private_key_depends(
    settings: WSAPISettings = Depends(get_wsapi_settings),
) -> Path:

    # create a private key for this server
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    secrets_dir = settings.WSAPI_SECRETS_DIR
    secrets_dir.mkdir(parents=True, exist_ok=True)
    private_key_path = secrets_dir / "key.pem"

    with open(private_key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.BestAvailableEncryption(
                    b"passphrase"
                ),
            )
        )

    return private_key_path


def get_inputs_dir_depends(
    settings: WSAPISettings = Depends(get_wsapi_settings),
) -> Path:
    return settings.WSAPI_INPUTS_DIR


def get_outputs_dir_depends(
    settings: WSAPISettings = Depends(get_wsapi_settings),
) -> Path:
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


@app.post("/api/auth/csr")
def as_update_certificate(
    private_key_file: Path = Depends(get_tls_private_key_depends),
):
    # create self-signed cert from private key
    with open(private_key_file, "rb") as f:
        pem = f.read()

    key = serialization.load_pem_private_key(pem, b"passphrase", default_backend())

    # subject and issuer are always the same.
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Davis"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OMSF"),
            x509.NameAttribute(NameOID.COMMON_NAME, "omsf.io"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            # Our certificate will be valid for 10 days
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=10)
        )
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
            # Sign our certificate with our private key
        )
        .sign(key, hashes.SHA256())
    )

    return Response(cert.public_bytes(serialization.Encoding.PEM))


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
    project_inputs = inputs_dir / f"p{project_id}"
    project_inputs.mkdir(parents=True, exist_ok=True)
    (outputs_dir / f"PROJ{project_id}").mkdir(parents=True, exist_ok=True)

    # write projectdata to project.json (actually an XML file on a real WS)
    with open(project_inputs / "project.json", "w") as f:
        f.write(project_data.json())


@app.put("/api/projects/{project_id}/files/{dest}")
async def create_project_file(
    project_id,
    dest,
    file_data: Request,
    inputs_dir: Path = Depends(get_inputs_dir_depends),
):
    data = await file_data.body()
    project_inputs = inputs_dir / f"p{project_id}"
    dest_path = project_inputs.joinpath(dest)

    # make parent directories if they don't exist
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, "wb") as f:
        f.write(data)


@app.get("/api/projects/{project_id}/files/{src}")
def get_project_file(
    project_id,
    src,
    inputs_dir: Path = Depends(get_inputs_dir_depends),
) -> bytes:
    project_inputs = inputs_dir / f"p{project_id}"
    src_path = project_inputs.joinpath(src)

    with open(src_path, "rb") as f:
        file_data = f.read()

    return Response(file_data)


@app.get("/api/projects/{project_id}")
def get_project(
    project_id,
    statedb: WSStateDB = Depends(get_wsstatedb_depends),
) -> ProjectData:
    # return clone state information
    return statedb.get_project(project_id)


@app.put("/api/projects/{project_id}/files/RUN{run_id}/{dest}")
async def create_run_file(
    project_id,
    run_id,
    dest,
    file_data: Request,
    inputs_dir: Path = Depends(get_inputs_dir_depends),
):
    data = await file_data.body()
    run_inputs = inputs_dir / f"p{project_id}/RUN{run_id}"
    dest_path = run_inputs.joinpath(dest)

    # make parent directories if they don't exist
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, "wb") as f:
        f.write(data)


@app.get("/api/projects/{project_id}/files/RUN{run_id}/{src}")
def get_run_file(
    project_id,
    run_id,
    src,
    inputs_dir: Path = Depends(get_inputs_dir_depends),
) -> bytes:
    run_inputs = inputs_dir / f"p{project_id}/RUN{run_id}"
    src_path = run_inputs.joinpath(src)

    with open(src_path, "rb") as f:
        file_data = f.read()

    return Response(file_data)


@app.put("/api/projects/{project_id}/runs/{run_id}/create")
def create_clone(
    project_id,
    run_id,
    *,
    clones: int = Body(embed=True),
    statedb: WSStateDB = Depends(get_wsstatedb_depends),
):
    # create clone instance in database
    statedb.create_clone(project_id, run_id, clones - 1)


@app.get("/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}")
def get_clone(
    project_id,
    run_id,
    clone_id,
    outputs_dir: Path = Depends(get_outputs_dir_depends),
    statedb: WSStateDB = Depends(get_wsstatedb_depends),
) -> JobData:

    # get clone state information
    jobdata = statedb.get_clone(project_id, run_id, clone_id)

    # if enough time has passed (3 seconds), then set the job as complete,
    # then return again
    if (datetime.datetime.utcnow() - jobdata.last).total_seconds() > 3:
        _finish_clone(project_id, run_id, clone_id, outputs_dir, statedb)

    # return new clone state information
    return statedb.get_clone(project_id, run_id, clone_id)


@app.put("/api/projects/{project_id}/files/RUN{run_id}/CLONE{clone_id}/{dest}")
async def create_clone_file(
    project_id,
    run_id,
    clone_id,
    dest,
    file_data: Request,
    inputs_dir: Path = Depends(get_inputs_dir_depends),
):
    data = await file_data.body()
    clone_inputs = inputs_dir / f"p{project_id}/RUN{run_id}/CLONE{clone_id}"
    dest_path = clone_inputs.joinpath(dest)

    # make parent directories if they don't exist
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, "wb") as f:
        f.write(data)


@app.get("/api/projects/{project_id}/files/RUN{run_id}/CLONE{clone_id}/{src}")
def get_clone_file(
    project_id,
    run_id,
    clone_id,
    src,
    inputs_dir: Path = Depends(get_inputs_dir_depends),
) -> bytes:
    clone_inputs = inputs_dir / f"p{project_id}/RUN{run_id}/CLONE{clone_id}"
    src_path = clone_inputs.joinpath(src)

    with open(src_path, "rb") as f:
        file_data = f.read()

    return Response(file_data)


@app.get("/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/files/{src}")
def get_clone_output_file(
    project_id,
    run_id,
    clone_id,
    src,
    outputs_dir: Path = Depends(get_outputs_dir_depends),
) -> bytes:
    clone_outputs = outputs_dir / f"PROJ{project_id}/RUN{run_id}/CLONE{clone_id}"
    gen_outputs = clone_outputs / "results0"
    src_path = gen_outputs.joinpath(src)

    with open(src_path, "rb") as f:
        file_data = f.read()

    return Response(file_data)


@app.get(
    "/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/gens/{gen_id}/files/{src}"
)
def get_gen_output_file(
    project_id,
    run_id,
    clone_id,
    gen_id,
    src,
    outputs_dir: Path = Depends(get_outputs_dir_depends),
) -> bytes:
    clone_outputs = outputs_dir / f"PROJ{project_id}/RUN{run_id}/CLONE{clone_id}"
    gen_outputs = clone_outputs / f"results{gen_id}"
    src_path = gen_outputs.joinpath(src)

    with open(src_path, "rb") as f:
        file_data = f.read()

    return Response(file_data)


# NOTE: this is not a real API endpoint on a work server, but is used by tests
# to simulate work completing
@app.put("/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/_finish")
def finish_clone(
    project_id,
    run_id,
    clone_id,
    outputs_dir: Path = Depends(get_outputs_dir_depends),
    statedb: WSStateDB = Depends(get_wsstatedb_depends),
):
    _finish_clone(project_id, run_id, clone_id, outputs_dir, statedb)


def _finish_clone(
    project_id,
    run_id,
    clone_id,
    outputs_dir: Path,
    statedb: WSStateDB,
):
    # create output directory
    clone_outputs = outputs_dir / f"PROJ{project_id}/RUN{run_id}/CLONE{clone_id}"
    gen_outputs = clone_outputs / "results0"

    gen_outputs.mkdir(parents=True, exist_ok=True)

    # create simulated output files
    globals_csv_output_path = gen_outputs / "globals.csv"
    with resources.as_file(
        resources.files("alchemiscale_fah.tests.data").joinpath("globals.csv")
    ) as globals_csv_path:
        shutil.copy(globals_csv_path, globals_csv_output_path)

    with open(gen_outputs / "science.log", "w") as f:
        f.write("Science!")

    # set finished state
    statedb.finish_clone(project_id, run_id, clone_id)
