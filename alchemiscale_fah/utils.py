
from typing import Callable
from enum import Enum

import numpy as np
from scipy.optimize import minimize_scalar


class NonbondedSettings(Enum):
    PME = "PME"
    NoCutoff = "NoCutoff"


def effort_nlogn(n):
    return n * np.log(n)


def effort_n2(n):
    return n ** 2


NONBONDED_EFFORT = {
        NonbondedSettings.PME: effort_nlogn,
        NonbondedSettings.NoCutoff: effort_n2,
        }


def get_atom_count(target_effort: float, effort_func: Callable, lower: int, upper: int) -> int:
    """Given a target effort and effort function, get the atom count associated
    with it.

    The effort function must take number of atoms as its only parameter. This
    function performs a scalar minimization to identify the number of atoms
    that yield the target effort, bounded by `lower` and `upper`. This allows
    the effort function to be arbitrarily complex, and perhaps not analytically
    sovable for the number of atoms.

    Parameters
    ----------
    target_effort
        Computational complexity for which we want the number of atoms, as
        would be obtained from `effort_func`.
    effort_func
        The function mapping number of atoms to computational complexity.
    lower
        The lowest atom count to consider in minimizing `effort_func`.
    upper
        The highest atom count to consider in minimizing `effort_func`.

    Returns
    -------
    atom_count
        Atom count corresponding to `target_effort`, within bounds `lower` and
        `upper`.

    """
    def f(n):
        return np.abs(effort_func(n) - target_effort)
    return round(minimize_scalar(f, bounds=(lower, upper), method='bounded').x)


def generate_project_atom_counts(lower: int, upper: int, n_projects: int,
                                 nonbonded_settings: NonbondedSettings) -> list[int]:
    """Generate a list of atom counts, evenly spaced in computational effort.

    This function is useful for seeding a range of Folding@Home PROJECTs with
    a range of atom counts that can be used effectivley with 

    Parameters
    ----------
    lower
        The lowest atom count to feature in the output list.
    upper
        The highest number of atoms to feature in the output list.
    n_projects
        The total number of atom counts to feature in the output list.
    nonbonded_settings
        The `NonbondedSettings` that the projects will be used for; this
        determines the function for computational effort given atom count.

    Returns
    -------
    atom_counts
        List of `n_projects` atom counts between `lower` and `upper` (inclusive).

    """
    if isinstance(nonbonded_settings, str):
        try:
            nonbonded_settings = NonbondedSettings[nonbonded_settings]
        except KeyError:
            raise ValueError("Invalid NonbondedSettings given")

    effort_func = NONBONDED_EFFORT[nonbonded_settings]

    #match nonbonded_settings:
    #    case NonbondedSettings.PME | 'PME':
    #        effort_func = effort_nlogn
    #    case NonbondedSettings.NoCutoff | 'NoCutoff':
    #        effort_func = effort_n2
    #    case _:
    #        raise ValueError("Invalid NonbondedSettings given")


    project_efforts = np.linspace(effort_func(lower), effort_func(upper), n_projects)

    project_atom_counts = []
    for project_effort in project_efforts:
        project_atom_counts.append(get_atom_count(project_effort, effort_func, lower, upper))

    return project_atom_counts


# TODO: figure this one out
# at the very least need some kind of scaling factor for our effort as a
# function of n to points credit
def assign_credit(effort):
    return effort
