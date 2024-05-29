"""
:mod:`alchemiscale_fah.compute.client` --- client for interacting with Folding@Home resources
=============================================================================================

"""

import os
from io import StringIO
import socket
from typing import Optional
from urllib.parse import urljoin, urlparse
from pathlib import Path
from datetime import datetime

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes

from .models import (
    ProjectData,
    ASCSR,
    ASWorkServerData,
    ASProjectData,
    JobData,
    JobResults,
    FileData,
)


class FahAdaptiveSamplingClient:
    """Client for interacting with a Folding@Home assignment and work server."""

    def __init__(
        self,
        as_url: Optional[str] = None,
        ws_url: Optional[str] = None,
        certificate_file: Optional[os.PathLike] = None,
        key_file: Optional[os.PathLike] = None,
        csr_file: Optional[os.PathLike] = None,
        verify: bool = True,
    ):
        """Create a new FahAdaptiveSamplingClient instance.

        Parameters
        ----------
        as_url
            URL of the assignment server to communicate with, if needed.
        ws_url
            URL of the work server to communicate with, if needed.
        certificate_file
            Path to the certificate file to use for authentication, in PEM
            format. Only needed for use with real FAH servers, not testing.
        key_file
            Path to the key file to use for encrypted communication, in PEM
            format. Only needed for use with real FAH servers, not testing.
        csr_file
            Path to the certificate signing request (CSR) file generated from
            private key, in PEM format. Only needed for use with real FAH
            servers, not testing. Required for refreshes of the
            `certificate_file` to be performed via API calls.

        """
        as_url = urlparse(as_url)
        ws_url = urlparse(ws_url)

        self.as_url = as_url.geturl()
        self.ws_url = ws_url.geturl()
        self.ws_ip_addr = socket.gethostbyname(ws_url.hostname)

        # self.certificate = (
        #    self.read_certificate(certificate_file) if certificate_file else None
        # )

        # if key_file is None:
        #    self.key = self.create_key()
        # else:
        #    self.key = self.read_key(key_file)

        self.certificate_file = certificate_file
        self.key_file = key_file
        self.csr_file = csr_file

        self.cert = (certificate_file, key_file)
        self.verify = verify

    @staticmethod
    def read_key(key_file):
        with open(key_file, "rb") as f:
            pem = f.read()

        return serialization.load_pem_private_key(pem, None, default_backend())

    @staticmethod
    def read_certificate(certificate_file):
        with open(certificate_file, "rb") as f:
            pem = f.read()

        return x509.load_pem_x509_certificate(pem, default_backend())

    @classmethod
    def create_key(cls):
        return rsa.generate_private_key(
            backend=default_backend(), public_exponent=65537, key_size=4096
        )

    @classmethod
    def write_key(cls, key, key_file):
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(key_file, "wb") as f:
            f.write(pem)

    @classmethod
    def generate_csr(cls, key, csr_file, email):
        """Generate certificate signing request (CSR) using private key.

        It is necessary to create a CSR and present this to an AS in order to
        receive a valid certificate. The CSR will be written in PEM format.

        Parameters
        ----------
        key
            RSA private key, as returned by `create_key` or `read_key`.
        csr_file
            Path in which to place CSR generated by this method.
        email
            Email address used to authenticate with the AS.

        """
        cn = x509.NameAttribute(NameOID.COMMON_NAME, email)
        csr = x509.CertificateSigningRequestBuilder()
        csr = csr.subject_name(x509.Name([cn]))
        csr = csr.sign(key, hashes.SHA256())

        with open(csr_file, "wb") as f:
            f.write(csr.public_bytes(serialization.Encoding.PEM))

    @staticmethod
    def read_csr_pem(csr_file):
        with open(csr_file, "r") as f:
            pem = f.read()

        return pem

    def _check_status(self, r):
        if r.status_code != 200:
            raise Exception("Request failed with %d: %s" % (r.status_code, r.text))

    def _get(self, api_url, endpoint, **params):
        url = urljoin(api_url, endpoint)
        r = requests.get(url, cert=self.cert, params=params, verify=self.verify)
        self._check_status(r)
        return r.json()

    def _put(self, api_url, endpoint, data=None):
        url = urljoin(api_url, endpoint)
        r = requests.put(url, json=data, cert=self.cert, verify=self.verify)
        self._check_status(r)

    def _post(self, api_url, endpoint, data=None):
        url = urljoin(api_url, endpoint)
        r = requests.post(url, json=data, cert=self.cert, verify=self.verify)
        self._check_status(r)
        return r.content

    def _delete(self, api_url, endpoint):
        url = urljoin(api_url, endpoint)
        r = requests.delete(url, cert=self.cert, verify=self.verify)
        self._check_status(r)

    def _upload(self, api_url, endpoint, filename):
        url = urljoin(api_url, endpoint)
        with open(filename, "rb") as f:
            r = requests.put(url, data=f, cert=self.cert, verify=self.verify)
            self._check_status(r)

    def _upload_bytes(self, api_url, endpoint, bytedata):
        url = urljoin(api_url, endpoint)
        r = requests.put(url, data=bytedata, cert=self.cert, verify=self.verify)
        self._check_status(r)

    def _download(self, api_url, endpoint, filename):
        url = urljoin(api_url, endpoint)
        r = requests.get(url, cert=self.cert, verify=self.verify, stream=True)
        self._check_status(r)

        os.makedirs(os.path.dirname(filename), exist_ok=True)

    def _download_bytes(self, api_url, endpoint):
        url = urljoin(api_url, endpoint)
        r = requests.get(url, cert=self.cert, verify=self.verify, stream=True)
        self._check_status(r)

        bytedata = r.raw.read(decode_content=True)
        r.close()

        return bytedata

    def as_update_certificate(self):
        as_csr = ASCSR(csr=self.read_csr_pem(self.csr_file))
        content = self._post(
                self.as_url,
                "/api/auth/csr",
                as_csr.dict(),
            )

        # overwrite certificate file with new certificate contents;
        # do this by writing to temp file, then do atomic move
        cert_file_tmp = Path(str(self.certificate_file.absolute()) + '.tmp')
        with open(cert_file_tmp, "wb") as f:
            f.write(content)

        os.rename(cert_file_tmp, self.certificate_file)


    def as_get_ws(self) -> ASWorkServerData:
        """Get work server attributes from assignment server."""
        return ASWorkServerData(**self._get(self.as_url, f"/api/ws/{self.ws_ip_addr}"))

    def as_set_ws(self, as_workserver_data: ASWorkServerData):
        """Set work server attributes on assignment server."""
        return self._put(
            self.as_url, f"/api/ws/{self.ws_ip_addr}", as_workserver_data.dict()
        )

    def as_get_project(self, project_id) -> ASProjectData:
        """Get project attributes on the assignment server."""
        return ASProjectData(
            **self._get(
                self.as_url,
                f"/api/ws/{self.ws_ip_addr}/projects/{project_id}",
            )
        )

    def as_set_project(self, project_id, weight, constraints):
        """Set project attributes on the assignment server."""

        as_project_data = ASProjectData(weight=weight, constraints=constraints)
        self._put(
            self.as_url,
            f"/api/ws/{self.ws_ip_addr}/projects/{project_id}",
            as_project_data.dict(),
        )

    def as_reset_project(self, project_id):
        """Set project attributes to default on the assignment server.

        Sets project weight to 0, drops all constraints.

        """
        as_project_data = ASProjectData(weight=0, constraints="")
        self._put(
            self.as_url,
            f"/api/ws/{self.ws_ip_addr}/projects/{project_id}",
            as_project_data.dict(),
        )

    def list_projects(self) -> dict[str, ProjectData]:
        return {
            key: ProjectData(**value)
            for key, value in self._get(self.ws_url, f"/api/projects").items()
        }

    def create_project(self, project_id, project_data: ProjectData):
        self._put(self.ws_url, f"/api/projects/{project_id}", project_data.dict())

    def update_project(self, project_id, project_data: ProjectData):
        self.create_project(project_id, project_data)

    def delete_project(self, project_id):
        self._delete(self.ws_url, f"/api/projects/{project_id}")

    def get_project(self, project_id) -> ProjectData:
        return ProjectData(**self._get(self.ws_url, f"/api/projects/{project_id}"))

    def list_project_files(self, project_id) -> list[FileData]:
        """Get a list of files associated with a project.

        Parameters
        ----------
        project_id
            ID of the project
        src
            File to download.
        dest
            Path to download file to.

        """
        return [
            FileData(**i)
            for i in self._get(
                self.ws_url,
                f"/api/projects/{project_id}/files",
            )
        ]

    def create_project_file(self, project_id, src: Path, dest: Path):
        """Upload a file to the PROJECT directory tree.

        Parameters
        ----------
        project_id
            ID of the project
        src
            File to upload.
        dest
            Path relative to PROJECT directory to upload to.

        """
        self._upload(
            self.ws_url,
            f"/api/projects/{project_id}/files/{dest}",
            src,
        )

    def create_project_file_from_bytes(self, project_id, bytedata: bytes, dest: Path):
        self._upload_bytes(
            self.ws_url,
            f"/api/projects/{project_id}/files/{dest}",
            bytedata,
        )

    def delete_project_file(self, project_id, path):
        """Delete a file from the PROJECT directory tree.

        Parameters
        ----------
        project_id
            ID of the project
        path
            File to delete.

        """
        self._delete(
            self.ws_url,
            f"/api/projects/{project_id}/files/{path}",
        )

    def get_project_file(self, project_id, src, dest):
        """Download a file from the PROJECT directory tree.

        Parameters
        ----------
        project_id
            ID of the project
        src
            File to download.
        dest
            Path to download file to.

        """
        self._download(self.ws_url, f"/api/projects/{project_id}/files/{src}", dest)

    def get_project_file_to_bytes(self, project_id, src):
        return self._download_bytes(
            self.ws_url, f"/api/projects/{project_id}/files/{src}"
        )

    def get_project_jobs(self, project_id, since: datetime = None) -> JobResults:
        """Get all active jobs for the project.

        Parameters
        ----------
        project_id
            ID of the project
        since
            If given, only include jobs that have been updated since this time.

        Returns
        -------
        JobResults

        """
        if since is not None:
            since = since.isoformat()

        return JobResults(
            **self._get(self.ws_url, f"/api/projects/{project_id}/jobs", since=since)
        )

    def create_run_file(self, project_id, run_id, src: Path, dest: Path):
        self._upload(
            self.ws_url,
            f"/api/projects/{project_id}/files/RUN{run_id}/{dest}",
            src,
        )

    def create_run_file_from_bytes(
        self, project_id, run_id, bytedata: bytes, dest: Path
    ):
        self._upload_bytes(
            self.ws_url,
            f"/api/projects/{project_id}/files/RUN{run_id}/{dest}",
            bytedata,
        )

    def get_run_file(self, project_id, run_id, src, dest):
        """Download a file from the given RUN directory tree.

         Parameters
         ----------
         project_id
             ID of the project
        run_id
             ID of the run
         src
             File to download.
         dest
             Path to download file to.

        """
        self._download(
            self.ws_url, f"/api/projects/{project_id}/files/RUN{run_id}/{src}", dest
        )

    def get_run_file_to_bytes(self, project_id, run_id, src):
        return self._download_bytes(
            self.ws_url, f"/api/projects/{project_id}/files/RUN{run_id}/{src}"
        )

    def delete_run_file(self, project_id, run_id, path: Path):
        self._delete(
            self.ws_url,
            f"/api/projects/{project_id}/files/RUN{run_id}/{path}",
        )

    def create_clone(self, project_id, run_id, clone_id):
        """Start a new CLONE for a given RUN."""

        # self._put(
        #    self.ws_url,
        #    f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/create",
        # )
        # self._put(
        #    self.ws_url,
        #    f"/api/projects/{project_id}/runs/{run_id}?clones=1"#&offset={clone_id}"
        # )

        self._put(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/create",
            data={"clones": int(clone_id) + 1},
        )

    def fail_clone(self, project_id, run_id, clone_id):
        """Fail a CLONE for a given RUN."""

        self._put(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/fail",
        )

    def reset_clone(self, project_id, run_id, clone_id):
        """Reset a CLONE for a given RUN."""

        self._put(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/reset",
        )

    def stop_clone(self, project_id, run_id, clone_id):
        """Stop a CLONE for a given RUN."""

        self._put(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/stop",
        )

    def restart_clone(self, project_id, run_id, clone_id):
        """Restart a CLONE for a given RUN."""

        self._put(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/restart",
        )

    def get_clone(self, project_id, run_id, clone_id) -> JobData:
        """Get state information for the given CLONE."""

        return JobData(
            **self._get(
                self.ws_url,
                f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}",
            )
        )

    def list_clone_files(self, project_id, run_id, clone_id) -> list[FileData]:
        return [
            FileData(**i)
            for i in self._get(
                self.ws_url,
                f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/files",
            )
        ]

    def create_clone_file(self, project_id, run_id, clone_id, src: Path, dest: Path):
        self._upload(
            self.ws_url,
            f"/api/projects/{project_id}/files/RUN{run_id}/CLONE{clone_id}/{dest}",
            src,
        )

    def create_clone_file_from_bytes(
        self, project_id, run_id, clone_id, bytedata: bytes, dest: Path
    ):
        self._upload_bytes(
            self.ws_url,
            f"/api/projects/{project_id}/files/RUN{run_id}/CLONE{clone_id}/{dest}",
            bytedata,
        )

    def get_clone_file(self, project_id, run_id, clone_id, src, dest):
        """Download a file from the given CLONE input directory tree.

        Parameters
        ----------
        project_id
            ID of the project.
        run_id
            ID of the run.
        clone_id
            ID of the clone.
        src
            File to download.
        dest
            Path to download file to.

        """
        self._download(
            self.ws_url,
            f"/api/projects/{project_id}/files/RUN{run_id}/CLONE{clone_id}/{src}",
            dest,
        )

    def get_clone_file_to_bytes(self, project_id, run_id, clone_id, src):
        return self._download_bytes(
            self.ws_url,
            f"/api/projects/{project_id}/files/RUN{run_id}/CLONE{clone_id}/{src}",
        )

    def create_clone_output_file(
        self, project_id, run_id, clone_id, src: Path, dest: Path
    ):
        self._upload(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/files/{dest}",
            src,
        )

    def get_clone_output_file_to_bytes(self, project_id, run_id, clone_id, src: Path):
        return self._download_bytes(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/files/{src}",
        )

    def list_gen_files(self, project_id, run_id, clone_id, gen_id) -> list[FileData]:
        return [
            FileData(**i)
            for i in self._get(
                self.ws_url,
                f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/gens/{gen_id}/files",
            )
        ]

    def get_gen_output_file_to_bytes(
        self, project_id, run_id, clone_id, gen_id, src: Path
    ):
        return self._download_bytes(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/gens/{gen_id}/files/{src}",
        )

    def _reset_mock_ws(self):
        """Only used for testing via mock ws"""
        self._put(self.ws_url, "/reset")

    def _finish_clone_mock_ws(self, project_id, run_id, clone_id):
        """Only used for testing via mock ws"""
        self._put(
            self.ws_url,
            f"/api/projects/{project_id}/runs/{run_id}/clones/{clone_id}/_finish",
        )
