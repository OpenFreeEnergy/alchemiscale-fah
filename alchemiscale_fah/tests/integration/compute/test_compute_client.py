"""Tests for FahAdaptiveSamplingClient.

"""

import pytest

from alchemiscale_fah.compute.client import FahAdaptiveSamplingClient
from alchemiscale_fah.compute.models import ProjectData, JobData


class TestFahAdaptiveSamplingClient:

    def test_create_project(self, fah_adaptive_sampling_client):
        client: FahAdaptiveSamplingClient = fah_adaptive_sampling_client

        project_id = "90001"

        project_data = ProjectData(
            core_id=0x23,
            contact="lol@no.int",
            atoms=10000,
            credit=5000,
        )

        client.create_project(project_id, project_data)

        project_data_ = client.get_project(project_id)

        assert project_data == project_data_

    def test_create_project_file_from_bytes(self, fah_adaptive_sampling_client): ...

    def test_create_clone(self, fah_adaptive_sampling_client):
        client: FahAdaptiveSamplingClient = fah_adaptive_sampling_client

        project_id = "90001"
        run_id = "0"
        clone_id = "0"

        project_data = ProjectData(
            core_id=0x23,
            contact="lol@no.int",
            atoms=10000,
            credit=5000,
        )

        client.create_project(project_id, project_data)

        client.create_clone(project_id, run_id, clone_id)

        assert client

    def test_get_clone(self): ...

    def test_create_clone_file(self): ...

    def test_create_clone_file_from_bytes(self): ...

    def test_get_clone_output_file_to_bytes(self): ...
