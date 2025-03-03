.. _user-guide:

##########
User Guide
##########

This document details the basic usage of the :py:class:`~alchemiscale.interface.client.AlchemiscaleClient` for evaluating :external+gufe:py:class:`~gufe.network.AlchemicalNetwork`\s using `Folding@Home`_.
It assumes that you already have a user identity on the target ``alchemiscale`` instance, with access to :py:class:`~alchemiscale.models.Scope`\s to submit :external+gufe:py:class:`~gufe.network.AlchemicalNetwork`\s to.

It also assumes the target ``alchemiscale`` instance has **alchemiscale-fah** present in its server environment, and at least one **alchemiscale-fah** compute service deployed to handle Folding\@Home-based :external+gufe:py:class:`~gufe.transformations.Transformation`\s.


.. _Folding@Home: https://foldingathome.org


************
Installation
************

Create a conda environment with the ``alchemiscale`` client using, e.g. `micromamba`_::

    $ micromamba create -n alchemiscale-client -c conda-forge alchemiscale-client


Once installed, activate the environment and install additional dependencies::

    $ micromamba activate alchemiscale-client
    $ micromamba install feflow>=0.1.2 plyvel

Finally, install ``alchemiscale-fah`` where ``<release-tag>`` corresponds to the GitHub tag from the release of **alchemiscale-fah** deployed on the target ``alchemiscale`` instance::

    $ pip install git+https://github.com/OpenFreeEnergy/alchemiscale-fah.git@<release-tag>

You may wish to install other packages into this environment, such as ``jupyterlab``.

.. _micromamba: https://github.com/mamba-org/micromamba-releases


******************************************************************
Creating an AlchemicalNetwork using a Folding\@Home-based Protocol
******************************************************************

**alchemiscale-fah** features :external+gufe:py:class:`~gufe.protocols.Protocol`\s derived from packages such as ``feflow``.
These take advantage of most of the components of these :external+gufe:py:class:`~gufe.protocols.Protocol`\s, but perform the compute-intensive simulation workloads using Folding\@Home instead.

To create an :external+gufe:py:class:`~gufe.network.AlchemicalNetwork`, review this notebook and apply the same approach to your systems of interest using a Folding\@Home-based :external+gufe:py:class:`~gufe.protocols.Protocol` like those listed below: `Preparing AlchemicalNetworks.ipynb`_

Currently, the following :external+gufe:py:class:`~gufe.protocols.Protocol`\s are available to users:

* :py:class:`alchemiscale_fah.protocols.feflow.nonequilbrium_cycling.FahNonEquilibriumCyclingProtocol`

Try each one out with default options for a start.
Below are notes on settings you may find more optimal for each, however.

.. _Preparing AlchemicalNetworks.ipynb: https://github.com/OpenFreeEnergy/ExampleNotebooks/blob/main/networks/Preparing%20AlchemicalNetworks.ipynb


``FahNonEquilibriumCyclingProtocol`` usage notes
================================================

For production use of this protocol, we recommend the default settings::

    >>> from alchemiscale_fah.protocols.feflow import FahNonEquilibriumCyclingProtocol

    >>> settings = NonEquilibriumCyclingProtocol.default_settings()

These default settings will perform non-equilibrium cycling with a total simulation time of 40 ns for each cycle, starting with 10 ns of equilibrium sampling in state A, 10 ns of nonequilibrium sampling from state A to B, 10 ns of equilibrium sampling in state B, and finally 10 ns of nonequilibrium sampling from state B to A.

We recommend that you stay close to these default values, but if you really need to adjust these run lengths, you can change the following options (assumes a 4 fs timestep)::

    >>> settings.integrator_settings.equilibrium_steps = 250000
    >>> settings.integrator_settings.nonequilibrium_steps = 250000

Note that if you change the above, you must also set the following; this tells the Folding\@Home ``openmm-core`` executable how many steps to perform, and must equal the full cycle steps to complete it::

    >>> settings.fah_settings.numSteps = (2 * settings.integrator_settings.equilibrium_steps +
                                          2 * settings.integrator_settings.nonequilibrium_steps)

A total of 100 cycles will be performed in parallel.
To adjust this number, change the following option to the desired count::

    >>> settings.num_cycles = 100

If a :external+gufe:py:class:`~gufe.transformations.Transformation` features charge changes, then consider setting the following::

    >>> settings.alchemical_settings.explicit_charge_correction = True

You may also want to set a newer **OpenFF** forcefield for any small molecules you simulate.
You can set this to the version you want with, e.g.::

    >>> settings.forcefield_settings.small_molecule_forcefield = 'openff-2.2.1'
