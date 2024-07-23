import pytest
import math

import numpy as np

from alchemiscale_fah import utils


@pytest.mark.parametrize(
    "n_atoms, lower, upper, effort_func, n_atoms_res",
    [
        (20, 10, 100, lambda x: x**2, 20),
        (5, 10, 100, lambda x: x**2, 10),
        (150, 10, 100, lambda x: x**2, 100),
        (30, 10, 100, lambda x: x * np.log(x), 30),
        (110, 10, 100, lambda x: x * np.log(x), 100),
        (20, 10, 100, lambda x: x**3, 20),
    ],
)
def test_get_atom_count(n_atoms, lower, upper, effort_func, n_atoms_res):
    target_effort = effort_func(n_atoms)
    n_atoms_ = utils.get_atom_count(target_effort, effort_func, lower, upper)

    assert math.isclose(n_atoms_res, n_atoms_)


@pytest.mark.parametrize(
    "lower, upper, n_projects, nonbonded_settings",
    [
        (10**3, 10**5, 10, utils.NonbondedSettings.PME),
        (10**3, 10**5, 10, utils.NonbondedSettings.NoCutoff),
    ],
)
def test_generate_project_atom_counts(lower, upper, n_projects, nonbonded_settings):
    project_atom_counts = utils.generate_project_atom_counts(
        lower, upper, n_projects, nonbonded_settings
    )

    # check that if we calculate effort for each of these atom counts, we get evenly-spaced values
    effort_func = utils.NONBONDED_EFFORT[nonbonded_settings]

    project_efforts = list(map(effort_func, project_atom_counts))
    expected_project_efforts = np.linspace(
        effort_func(lower), effort_func(upper), n_projects
    )

    assert np.isclose(project_efforts, expected_project_efforts, rtol=1e-3).all()
