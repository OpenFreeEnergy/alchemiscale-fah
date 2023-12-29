"""
:mod:`alchemiscale_fah.cli` --- command line interface
======================================================

"""

import click


@click.group()
def cli():
    ...


@cli.command(
    name="generate-atom-counts",
    help=("Generate a series of atom counts for a range of Folding@Home projects, "
          "evently spaced by computational complexity"),
)
@click.option(
        "--lower",
        "-l",
        help="Lowest atom count to use for a project",
        type=int,
        required=True,
    )
@click.option(
        "--upper",
        "-u",
        help="Highest atom count to use for a project",
        type=int,
        required=True,
    )
@click.option(
        "--n-projects",
        "-p",
        help="Number of projects to create range for",
        type=int,
        required=True,
    )
@click.option(
        "--nonbonded-settings",
        "-n",
        help="Nonbonded settings that these projects will handle",
        type=click.Choice(['PME', 'NoCutoff']),
        required=True,
    )
def generate_atom_counts(lower, upper, n_projects, nonbonded_settings):  
    from .utils import generate_project_atom_counts
    
    counts = generate_project_atom_counts(lower, upper, n_projects, nonbonded_settings)
    click.echo(counts)


@cli.command(
    name="create-project",
    help="Create a new Folding@Home project on this work server",
)
@click.option(
        "--project-id",
        "-p",
        help="ID to use for the project",
        type=str,
        required=True,
    )
@click.option(
        "--core-id",
        "-i",
        help="ID of the core this project will utilize",
        type=str,
        required=True,
    )
@click.option(
        "--contact-email",
        "-e",
        help="Contact email for person responsible for the project",
        type=str,
        required=True,
    )
@click.option(
        "--n-atoms",
        "-a",
        help="Number of atoms project corresponds to",
        type=int,
        required=True,
    )
@click.option(
        "--nonbonded-settings",
        "-n",
        help="Nonbonded settings that these projects will handle",
        type=click.Choice(['PME', 'NoCutoff']),
        required=True,
    )
@click.option(
        "--ws-url",
        "-w",
        help="URL of the work server to create the project on",
        type=str,
        required=True,
    )
@click.option(
        "--certificate-file",
        "-c",
        help="TLS certificate to use for authenticating with API",
        type=str,
        required=True,
    )
@click.option(
        "--key-file",
        "-k",
        help="Private key to use for TLS responses",
        type=str,
        required=True,
    )
def create_project(project_id, core_id, contact_email, n_atoms,
                   nonbonded_settings, ws_url, certificate_file, key_file):
    from .compute.models import ProjectData
    from .compute.client import FahAdaptiveSamplingClient
    from .utils import NONBONDED_EFFORT, NonbondedSettings, assign_credit

    # assign credit based on effort function
    if isinstance(nonbonded_settings, str):
        try:
            nonbonded_settings = NonbondedSettings[nonbonded_settings]
        except KeyError:
            raise ValueError("Invalid NonbondedSettings given")

    effort_func = NONBONDED_EFFORT[nonbonded_settings]
    effort = effort_func(n_atoms)
    credit = assign_credit(effort)

    project_data = ProjectData(core_id=core_id,
                               contact=contact_email,
                               atoms=n_atoms,
                               credit=credit)

    fahc = FahAdaptiveSamplingClient(ws_url=ws_url,
                                     certificate_file=certificate_file,
                                     key_file=key_file)

    fahc.create_project(project_id, project_data)


@cli.group(help="Subcommands for compute services")
def compute():
    ...


@compute.command(
    name="fah-asynchronous",
    help="Start up a FahAsynchronousComputeService",
)
def fah_asynchronous():
    ...


@compute.command(
    name="initialize-state",
    help="Initialize statefile for FahAsynchronousComputeService",
)
def initialize_state():
    ...
