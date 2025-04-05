otters.model
====================

This module contains models. It's confusing because there are 2 types:
   - Simulations: such as Virtual Meter. These model the environement by simulating equipment and then having that equipment interact.
   - Models: These are mathematical models that simulate the environment like regressions or decision trees. These are extended from some other library to fit the needs of energy analysis 

Classes
-----------------
.. currentmodule:: otters.model

.. autosummary::
   :toctree: _autosummary
   :recursive:

   Regression
   VirtualMeter

