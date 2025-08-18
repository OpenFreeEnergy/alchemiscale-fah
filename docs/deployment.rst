.. _deployment:

##########
Deployment
##########

Deploying an **alchemiscale-fah** compute service requires at least the following to be in place:

* an **alchemiscale** server
* a **Folding\@Home** (FAH) work server

The compute service mediates the interaction between these two systems by:

1. Pulling computational tasks from the **alchemiscale** server
2. Submitting and awaiting molecular dynamics simulations to **Folding\@Home** via the work server
3. Collecting results and returning them to the **alchemiscale** server


*************
Prerequisites
*************

Before deploying the compute service, ensure the infrastructure you are deploying to has:

1. **Network Access**
   
   * HTTPS connectivity to your **alchemiscale** server
   * HTTPS connectivity to a FAH Assignment Server (e.g. ``https://assign1.foldingathome.org``)
   * HTTPS connectivity to your FAH work server

2. **Infrastructure**
   
   * Local filesystem space for object storage, indexes, and temporary files
   * Sufficient computational resources for process pool workers

Also ensure that you have:
   
* Valid compute identity and key for the **alchemiscale** server you are using
* Email address registered with **Folding\@Home** for certificate generation

Because a compute service can only make use of a single FAH work server,
it often makes sense to deploy the compute service to the work server itself.
Consider this as a default choice unless you have reason to deploy the service elsewhere.

************
Installation
************

Create a conda environment with the ``alchemiscale`` client using, e.g. `micromamba`_::

    $ micromamba create -n alchemiscale-compute-fah -c conda-forge alchemiscale-compute


Once installed, activate the environment and install additional dependencies::

    $ micromamba activate alchemiscale-compute-fah
    $ micromamba install feflow>=0.1.2 plyvel

Finally, install ``alchemiscale-fah`` where ``<release-tag>`` corresponds to the GitHub tag from the release of **alchemiscale-fah** deployed on the target ``alchemiscale`` instance::

    $ pip install git+https://github.com/OpenFreeEnergy/alchemiscale-fah.git@<release-tag>

.. _micromamba: https://github.com/mamba-org/micromamba-releases


.. note:: 

   It is possible to deploy the compute service in other ways, such as via Docker,
   and to other types of infrastructure, such as a container orchestrator.
   Instructions for how to do this are outside the scope of this document.


********************
Deployment directory
********************

We recommend creating a directory you wish to use for the service's configuration and index.
For example::

    $ mkdir alchemiscale-fah && cd alchemiscale-fah

The rest of this guide assumes you are using such a directory.


*******************
Certificate setup
*******************

Authentication with **Folding\@Home** requires TLS client certificates.
The compute service can manage these automatically once in place.

We recommend placing the necessary files in a single place, such as::

    $ mkdir auth

Generating certificates
=======================

Create the required certificate files using the **alchemiscale-fah** CLI:

1. **Generate RSA Private Key**::

    alchemiscale-fah create-key-file --key-file ./auth/fah-key.pem

2. **Generate Certificate Signing Request (CSR)**::

    alchemiscale-fah create-csr-file \
        --key-file ./auth/fah-key.pem \
        --csr-file ./auth/fah-csr.pem \
        --contact-email "<your-email>@<domain>"

3. **Obtain Certificate**
   
   Log in to the web interface of the assignment server you intend to use,
   and click "Certificate" in the top bar.
   Copy and paste the CSR file content into the text box, and click "Submit CSR".
   Place the certificate you receive in the same directory alongside the key and CSR as ``fah-cert.pem``.

   This certificate has a lifetime of 1 month.
   The compute service will handle refreshes of the certificate automatically via the Assignment Server API.


The ``auth`` directory should now have the following contents::

    $ ls ./auth
    fah-key.pem
    fah-csr.pem
    fah-cert.pem


*************************
Work server configuration
*************************

In order for the work server to handle requests properly from the compute service,
add the following content to ``/etc/fah-work/config.xml`` inside the ``<config>`` section::

      <core type="0x26">
       <gens v="1"/>
        <create-command v="/bin/true"/>
        <send>
          $home/RUN$run/CLONE$clone/core.xml
          $home/RUN$run/CLONE$clone/system.xml.bz2
          $home/RUN$run/CLONE$clone/integrator.xml.bz2
          $home/RUN$run/CLONE$clone/state.xml.bz2
        </send>
        <next-gen-command>
          rm -f $results/checkpointIntegrator.xml.bz2
          rm -f $results/checkpointState.xml.bz2
          dos2unix $results/science.log
        </next-gen-command>
      </core>

This will by default apply to any and all PROJECTs that use ``openmm-core`` ``0x26``.
You can choose a newer core version, such as ``0x27``, if you prefer.

Restart the work server to apply this new configuration with::

    $ systemctl restart fah-work.service 


*******************
FAH PROJECT setup
*******************

**Folding\@Home** PROJECTs must be created and configured before the compute service can use them.

You *must* choose your PROJECT id(s) from an allocation assigned to you in `this list`_.

The PROJECT creation process automatically:

* Estimates credits based on atom count and computational complexity
* Creates the PROJECT on the work server, which registers it with the FAH assignment server(s)
* Creates an ``alchemiscale-project.txt`` file in the PROJECT directory on the work server, including configuration relevant for **alchemiscale** compute service


.. _this list: https://docs.foldingathome.org/project-numbers.html

Project Creation
================

Create FAH projects using the **alchemiscale-fah** CLI::

    alchemiscale-fah create-project \
        --project-id <project-id> \
        --core-id 0x26 \
        --core-type openmm \
        --contact-email "<your-email>@<domain>" \
        --n-atoms 25000 \
        --nonbonded-settings PME \
        --ws-url https://<your-work-server>.foldingathome.org \
        --certificate-file ./auth/fah-cert.pem \
        --key-file ./auth/fah-key.pem

Project Configuration Parameters
===============================

* **project-id**: Unique integer identifier for the FAH project
* **core-id**: Computational core to use (in hexadecimal, e.g., ``0x26`` for ``openmm-core`` 26)
* **core-type**: Type of simulation engine (``openmm`` or ``gromacs``)
* **contact-email**: Contact email for the project
* **n-atoms**: Expected number of atoms for credit calculation
* **nonbonded-settings**: Nonbonded calculation method (``PME`` or ``NoCutoff``)

Generating Atom Counts
======================

To create multiple PROJECTs with varying computational complexity, you can generate appropriate atom counts with::

    alchemiscale-fah generate-atom-counts \
        --lower 1000 \
        --upper 50000 \
        --n-projects 10 \
        --nonbonded-settings PME

This returns a series of atom counts with evenly-spaced computational effort estimates.

PROJECT constraints
===================

After creating your PROJECTs,
log in to the web interface of the assignment server and set your new PROJECTs to use a unique ``ProjectKey`` in their constraints::

    ProjectKey=<unique number>

You will use this in your :ref:`testing of these PROJECTs <project_testing>` further below.
Also, set the weight of each PROJECT to 0.01 to ensure generated jobs can be picked up by clients targeting the ``ProjectKey``.

****************************
Service configuration
****************************

The ``FahAsynchronousComputeService`` requires a YAML configuration file specifying both initialization and runtime parameters.

Configuration File Structure
=============================

Copy the configuration file for the release of **alchemiscale-fah** you are deploying from here::

    https://raw.githubusercontent.com/OpenFreeEnergy/alchemiscale-fah/refs/tags/<release-tag>/devtools/configs/fah-asynchronous-compute-settings.yaml

and place it into ``config.yaml``.

Required Configuration Parameters
=================================

**alchemiscale connection:**

* ``api_url``: URL of the **alchemiscale** compute API
* ``identifier``: Your compute identity identifier  
* ``key``: Authentication credential for the compute identity
* ``name``: Human-readable name for this service instance

**protocol filtering**

* ``protocols``: List of ``Protocol`` class names to filter for; important to only include FAH-based protocols

**filesystem paths:**

* ``shared_basedir``: Shared directory for ``ProtocolDAG`` execution
* ``scratch_basedir``: Scratch directory for ``ProtocolDAG`` execution
* ``index_dir``: Directory for LevelDB index storage
* ``obj_store``: Directory for object storage

**FAH server connection:**

* ``fah_as_url``: FAH Assignment Server URL (e.g. ``https://assign1.foldingathome.org``)
* ``fah_ws_url``: Your FAH work server URL
* ``fah_certificate_file``: Path to TLS certificate file
* ``fah_key_file``: Path to RSA private key file
* ``fah_csr_file``: Path to certificate signing request file

**project configuration:**

* ``fah_project_ids``: List of FAH project IDs this service should use
* ``fah_core_ids_supported``: List of supported core IDs (in hex format)

Optional Configuration Parameters
=================================

**Service Tuning:**

* ``fah_poll_interval``: Seconds between polling for completed jobs (default: 60)
* ``fah_cert_update_interval``: Certificate renewal interval in seconds (default: 86400)
* ``max_processpool_workers``: Maximum number of worker processes (default: ``null`` will equal CPU count on host)
* ``claim_limit``: Maximum tasks to claim at once (default: 1)
* ``sleep_interval``: Sleep time when no tasks available (default: 30)
* ``heartbeat_interval``: Heartbeat frequency in seconds (default: 300)

**Development Options:**

* ``fah_client_verify``: Enable SSL certificate verification (default: True)
* ``keep_shared``: Retain shared directories after completion (default: False)
* ``keep_scratch``: Retain scratch directories after completion (default: False)
* ``loglevel``: Logging level (``DEBUG``, ``INFO``, ``WARN``, ``ERROR``)

****************************
Service startup
****************************

Start the compute service using the **alchemiscale-fah** CLI.

Basic Startup
=============

Start the service with your configuration file::

    alchemiscale-fah compute fah-asynchronous --config-file config.yaml

The service will:

1. **Initialize**: Load configuration and validate parameters
2. **Authenticate**: Connect to **alchemiscale** server and verify credentials  
3. **Certificate Check**: Verify or renew FAH certificates if needed
4. **Project Validation**: Confirm access to specified FAH projects
5. **Storage Setup**: Initialize local index and object store directories
6. **Start Processing**: Begin polling for tasks and managing execution

.. note:: If running the service on a remote machine,
   you will want to ensure the process remains active after logout or disconnection.
   You can do this through a variety of means,
   including running it within a ``tmux``,
   creating a ``systemd`` unit and starting it up as a system service,
   or through disowning the process.
   These choices are outside the scope of this document.


Service Management
==================

**Graceful Shutdown:**

The service handles ``SIGTERM`` and ``SIGINT`` signals for clean shutdown::

    # Stop the service gracefully
    kill -TERM <service_pid>

**Resource Cleanup:**

By default, the service cleans up temporary directories. To retain them for debugging::

    init:
      keep_shared: True
      keep_scratch: True

**Log Management:**

Configure logging for operational monitoring::

    init:
      loglevel: "INFO"  # or DEBUG, WARN, ERROR
      logfile: "./alchemiscale-fah.log"

Note that if writing to a log file, no file rotation is performed.
The file will grow monotonically and without bound on its own for a long-running service.


.. _project_testing:

***************
PROJECT testing
***************

With the service running,
the FAH PROJECTs it uses will need to be run through INTERNAL and BETA testing before enabling them for full **Folding\@Home**.
