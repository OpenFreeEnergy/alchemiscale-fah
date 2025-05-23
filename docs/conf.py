# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'alchemiscale-fah'
copyright = '2025, alchemiscale developers'
author = 'alchemiscale developers'
release = '0.1.2'

import sys
import os
import sphinx_rtd_theme

sys.path.insert(0, os.path.abspath("."))

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "myst_nb",
]

numfig = True

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

autodoc_mock_imports = [
    "async_lru",
    "boto3",
    "click",
    "fastapi",
    "gufe",
    "httpx",
    "jose",
    "networkx",
    "numpy",
    "py2neo",
    "pydantic",
    "pydantic_settings",
    "starlette",
    "yaml",
    "plyvel",
]

intersphinx_mapping = {
    "gufe": ("https://gufe.readthedocs.io/en/latest/", None),
    "openfe": ("https://docs.openfree.energy/en/stable/", None),
    "alchemiscale": ("https://docs.alchemiscale.org/en/stable/", None),
    "python": ("https://docs.python.org/3", None),
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]


# -- Options for MystNB ------------------------------------------------------

myst_url_schemes = [
    "http",
    "https",
]

myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "html_image",
    "smartquotes",
    "replacements",
]

myst_heading_anchors = 2

# Never execute notebooks
# Output is stored in the notebook itself
# Remember `Widgets -> Save Notebook Widget State` in the notebook.
# See: https://myst-nb.readthedocs.io/en/latest/computation/execute.html
nb_execution_mode = "off"
