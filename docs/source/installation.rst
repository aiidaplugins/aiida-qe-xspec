============
Installation
============

.. _installation:requirements:

Requirements
============

To work with ``aiida-qe-xspec``, you should have:

* configured an AiiDA profile.
* QE code installed and configured in your AiiDA profile.

Please refer to the `documentation <https://aiida.readthedocs.io/projects/aiida-core/en/latest/intro/get_started.html>`_ of ``aiida-core`` for detailed instructions.


.. _installation:installation:

Installation
============


The recommended method of installation is to use the Python package manager |pip|_:

.. code-block:: console

    $ pip install aiida-qe-xspec

This will install the latest stable version that was released to PyPI.

To install the package from source, first clone the repository and then install using |pip|_:

.. code-block:: console

    $ git clone https://github.com/aiidalab/aiida-qe-xspec
    $ cd aiida-qe-xspec
    $ pip install -e .

The ``-e`` flag will install the package in editable mode, meaning that changes to the source code will be automatically picked up.


.. |pip| replace:: ``pip``
.. _pip: https://pip.pypa.io/en/stable/
