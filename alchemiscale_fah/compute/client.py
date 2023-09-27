#!/usr/bin/env python3

import os
import requests
from typing import Optional
from urllib.parse import urljoin

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes


# project_data = dict(
#    core_id=0x22,
#    gens=25000,
#    atoms=288449,
#    credit=56,
#    timeout=0.002,
#    deadline=0.005,
# )


class FahAdaptiveSamplingClient:
    def __init__(
        self,
        as_api_url: str,
        ws_api_url: str,
        ws_ip_addr: str,
        certificate_file: os.PathLike = "api-certificate.pem",
        key_file: os.PathLike = "api-private.pem",
        verify: bool = True,
    ):
        self.as_api_url = as_api_url
        self.ws_api_url = ws_api_url
        self.ws_ip_addr = ws_ip_addr

        self.certificate = self.read_certificate(certificate_file)

        if key_file is None:
            self.key = self.create_key()
        else:
            self.key = self.read_key(key_file)

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
    def create_key():
        return rsa.generate_private_key(
            backend=default_backend(), public_exponent=65537, key_size=4096
        )

    @classmethod
    def write_key(key, key_file):
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(key_file, "wb") as f:
            f.write(pem)

    @classmethod
    def generate_csr(key, csr_file):
        """Generate certificate signing request (CSR) using private key.

        It is necessary to create a CSR and present this to an AS in order to
        receive a valid certificate. The CSR will be written in PEM format.

        """
        cn = x509.NameAttribute(NameOID.COMMON_NAME, "joe@example.com")
        csr = x509.CertificateSigningRequestBuilder()
        csr = csr.subject_name(x509.Name([cn]))
        csr = csr.sign(key, hashes.SHA256())

        with open(csr_file, "wb") as f:
            f.write(csr.public_bytes(serialization.Encoding.PEM))

    def _check_status(self, r):
        if r.status_code != 200:
            raise Exception("Request failed with %d: %s" % (r.status_code, r.text))

    def _get(self, api_url, endpoint, **params):
        url = urljoin(api_url, endpoint)
        r = requests.get(url, cert=self.cert, params=params, verify=self.verify)
        self._check_status(r)
        return r.json()

    def _put(self, api_url, endpoint, **data):
        url = urljoin(api_url, endpoint)
        r = requests.put(url, json=data, cert=self.cert, verify=self.verify)
        self._check_status(r)

    def _delete(self, api_url, endpoint):
        url = urljoin(api_url, endpoint)
        r = requests.delete(url, cert=self.cert, verify=self.verify)
        self._check_status(r)

    def _upload(self, api_url, endpoint, filename):
        url = urljoin(api_url, endpoint)
        with open(filename, "rb") as f:
            r = requests.put(url, data=f, cert=self.cert, verify=self.verify)
            self._check_status(r)

    def _download(self, api_url, endpoint, filename):
        url = urljoin(api_url, endpoint)
        r = requests.get(url, cert=self.cert, verify=self.verify, stream=True)
        self._check_status(r)

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        r.close()

    def as_get_ws(self):
        """Get work server attributes from assignment server."""
        return self._get(self.as_api_url, f"/ws/{self.ws_ip_addr}")

    def as_set_ws(self, as_workserver_data):
        """Set work server attributes on assignment server."""
        return self._put(
            self.as_api_url, f"/ws/{self.ws_ip_addr}", **as_workserver_data
        )

    def as_get_project(self, project_id):
        """Set project attributes on the assignment server."""
        self._gut(
            self.as_api_url,
            f"/ws/{self.ws_ip_addr}/projects/{project_id}",
        )

    def as_set_project(self, project_id, weight, constraints):
        """Set project attributes on the assignment server."""
        self._put(
            self.as_api_url,
            f"/ws/{self.ws_ip_addr}/projects/{project_id}",
            weight=weight,
            constraints=constraints,
        )

    def as_reset_project(self, project_id):
        """Set project attributes to default on the assignment server.

        Sets project weight to 0, drops all constraints.

        """
        self._put(
            self.as_api_url,
            f"/ws/{self.ws_ip_addr}/projects/{project_id}",
            weight=0,
            constraints="",
        )

    def create_project(self, project_id, project_data):
        self._put(self.ws_api_url, f"/projects/{project_id}", **project_data)

    def delete_project(self, project_id):
        self._delete(self.ws_api_url, f"/projects/{project_id}")

    def start_run(self, project_id, run_id, clones=0):
        """Start a new run."""
        self._put(
            self.ws_api_url,
            f"/projects/{project_id}/runs/{run_id}/create",
            clones=clones,
        )

    def upload_project_files(self, project_id):
        files = "core.xml integrator.xml.bz2 state.xml.bz2 system.xml.bz2".split()

        for name in files:
            self._upload(self.ws_api_url, f"/projects/{project_id}/files/{name}", name)

    def get_project(self, project_id):
        return self._get(self.ws_api_url, f"/projects/{project_id}")

    def get_job_files(self, project_id, run_id, clone_id):
        return self._get(
            self.ws_api_url,
            f"/projects/{project_id}/runs/{run_id}/clones/{clone_id}/files",
        )

    def get_xtcs(self, project_id, run_id, clone_id):
        data = self._get(
            self.ws_api_url,
            f"/projects/{project_id}/runs/{run_id}/clones/{clone_id}/files",
        )

        for info in data:
            if info["path"].endswith(".xtc"):
                self._download(
                    self.ws_api_url,
                    f"/projects/{project_id}/runs/{run_id}/clones/{clone_id}/files/{info['path']}",
                    info["path"],
                )
