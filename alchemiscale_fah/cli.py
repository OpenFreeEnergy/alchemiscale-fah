"""
:mod:`alchemiscale_fah.cli` --- command line interface
======================================================

"""

import click
import signal
import yaml


@click.group()
def cli(): ...


@cli.command(
    name="generate-atom-counts",
    help=(
        "Generate a series of atom counts for a range of Folding@Home projects, "
        "evently spaced by computational complexity"
    ),
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
    type=click.Choice(["PME", "NoCutoff"]),
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
    "--core-type",
    "-t",
    help="The type of core this project will use.",
    type=click.Choice(["openmm", "gromacs"]),
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
    type=click.Choice(["PME", "NoCutoff"]),
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
    help="TLS certificate to use for authenticating with API; required for real deployments",
    type=str,
    required=False,
)
@click.option(
    "--key-file",
    "-k",
    help="Private key to use for TLS responses; required for real deployments",
    type=str,
    required=False,
)
def create_project(
    project_id,
    core_id,
    core_type,
    contact_email,
    n_atoms,
    nonbonded_settings,
    ws_url,
    certificate_file,
    key_file,
):
    from .compute.models import ProjectData, FahProject, FahCoreType
    from .compute.client import FahAdaptiveSamplingClient
    from .compute.index import FahComputeServiceIndex
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

    project_data = ProjectData(
        core_id=core_id, contact=contact_email, atoms=n_atoms, credit=credit
    )

    fahc = FahAdaptiveSamplingClient(
        ws_url=ws_url, certificate_file=certificate_file, key_file=key_file
    )

    fahc.create_project(project_id, project_data)

    # create entry in index for this PROJECT
    fah_project = FahProject(
        project_id=project_id,
        n_atoms=n_atoms,
        nonbonded_settings=nonbonded_settings,
        core_type=FahCoreType[core_type],
        core_id=core_id,
    )

    # add file to PROJECT dir that can be used to rebuild index
    fahc.create_project_file_from_bytes(
        project_id, fah_project.json().encode("utf-8"), "alchemiscale-project.txt"
    )

    click.echo(f"Created FAH PROJECT {project_id}")


@cli.command(
    name="create-key-file",
    help=(
        "Generate a new private key used for TLS responses; required for real deployments."
    ),
)
@click.option(
    "--key-file",
    "-k",
    help="Path to write key to",
    type=str,
    required=True,
)
def create_key_file(
    key_file,
):
    from .compute.client import FahAdaptiveSamplingClient

    key = FahAdaptiveSamplingClient.create_key()
    FahAdaptiveSamplingClient.write_key(key, key_file)

    click.echo(f"Created new private key at {key_file}")


@cli.command(
    name="create-csr-file",
    help=(
        "Generate a new certificate signing request (CSR) using private key; required for real deployments."
    ),
)
@click.option(
    "--key-file",
    "-k",
    help="Private key to use for TLS responses; required for real deployments",
    type=str,
    required=True,
)
@click.option(
    "--csr-file",
    "-r",
    help="Path to write CSR to",
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
def create_csr_file(
    key_file,
    csr_file,
    contact_email,
):
    from .compute.client import FahAdaptiveSamplingClient

    key = FahAdaptiveSamplingClient.read_key(key_file)
    FahAdaptiveSamplingClient.generate_csr(key, csr_file, contact_email)

    click.echo(f"Created new CSR at {csr_file}")


@cli.group(help="Subcommands for compute services")
def compute(): ...


@compute.command(
    name="fah-asynchronous",
    help="Start up a FahAsynchronousComputeService",
)
@click.option(
    "--config-file",
    "-c",
    type=click.File(),
    help="YAML-based configuration file giving the settings for this service",
    required=True,
)
def fah_asynchronous(config_file):
    from alchemiscale.models import Scope
    from alchemiscale_fah.compute.service import FahAsynchronousComputeService
    from alchemiscale_fah.compute.settings import FahAsynchronousComputeServiceSettings

    params = yaml.safe_load(config_file)

    params_init = params.get("init", {})
    params_start = params.get("start", {})

    if "scopes" in params_init:
        params_init["scopes"] = [
            Scope.from_str(scope) for scope in params_init["scopes"]
        ]

    service = FahAsynchronousComputeService(
        FahAsynchronousComputeServiceSettings(**params_init)
    )

    # add signal handling
    for signame in {"SIGHUP", "SIGINT", "SIGTERM"}:

        def stop(*args, **kwargs):
            service.stop()
            raise KeyboardInterrupt()

        signal.signal(getattr(signal, signame), stop)

    try:
        service.start(**params_start)
    except KeyboardInterrupt:
        pass
