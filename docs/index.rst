.. alchemiscale-fah documentation master file, created by
   sphinx-quickstart on Wed Feb 26 17:04:07 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

#######################################################################
high-throughput alchemical free energy execution...on Folding\@Home
#######################################################################

**alchemiscale-fah** provides deployable components for using `Folding@Home`_ work servers as compute sources for an `alchemiscale`_ server instance, enabling "planetary-scale" distributed compute for :external+gufe:py:class:`~gufe.network.AlchemicalNetwork` evaluation.
It also features :external+gufe:py:class:`~gufe.protocols.Protocol`\s that take advantage of these components.

For users: see the :ref:`user-guide` for details on how to make use of Folding\@Home-based :external+gufe:py:class:`~gufe.protocols.Protocol`\s.

For instructions on how to deploy an **alchemiscale-fah** compute service to a Folding\@Home work server, see :ref:`deployment` and :ref:`compute`.


.. note::
   This software is in beta and under active development. It is used for production purposes by early-adopters, but its API is still rapidly evolving.



.. _alchemiscale: https://alchemiscale.org
.. _Folding@Home: https://foldingathome.org


.. toctree::
   :maxdepth: 1
   :caption: Contents:


   ./user_guide
   ./deployment
   ./compute
   ./operations
   ./api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
