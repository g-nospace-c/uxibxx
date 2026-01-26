.. currentmodule:: uxibxx

``uxibxx`` module
=================

Board driver classes
--------------------
The helper classmethods on :class:`UxibxxIoBoard` will automatically dispatch
to the appropriate subclass according to the identity reported by the hardware,
or you can use the subclasses directly.

.. autoclass:: uxibxx.UxibxxIoBoard
   :members: \
      __init__, list_connected_devices, open_first_device, \
      from_serial_portname, board_model, board_id
   :member-order: bysource

Board driver classes
--------------------
.. autoclass:: uxibxx.UxibDn12
   :show-inheritance: True

.. autoclass:: uxibxx.UxibShf4
   :show-inheritance: True

.. autoclass:: uxibxx.UxibLjpm
   :show-inheritance: True

Feature set classes
-------------------
These are mixins for specific types of functionality. Refer to the relevant
board class to see what is supported.

.. autoclass:: uxibxx.features.dio.DigitalIo
   :members:

.. autoclass:: uxibxx.features.flow.FlowMeasurement
   :members:

.. autoclass:: uxibxx.features.leak.LeakDetector
   :members:



Data classes
------------
.. autoclass:: uxibxx.types.LeakDetectorResult
.. autoclass:: uxibxx.types.FlowRateHistoryResult
.. autoclass:: uxibxx.types.VolMeasurementResult
.. autoclass:: uxibxx.types.VolMeasurementResults

Enums
-----
.. autoclass:: uxibxx.UxibxxIoBoard.IoDirection
   :members:

Exceptions
----------
.. autoclass:: uxibxx.UxibxxIoBoard.UxibxxIoBoardError
.. autoclass:: uxibxx.UxibxxIoBoard.DeviceNotFound
   :show-inheritance: True
.. autoclass:: uxibxx.UxibxxIoBoard.IdMismatch
   :show-inheritance: True
.. autoclass:: uxibxx.UxibxxIoBoard.InvalidTerminalNo
   :show-inheritance: True
.. autoclass:: uxibxx.UxibxxIoBoard.Unsupported
   :show-inheritance: True
.. autoclass:: uxibxx.UxibxxIoBoard.RemoteError
   :show-inheritance: True
.. autoclass:: uxibxx.UxibxxIoBoard.ResponseTimeout
   :show-inheritance: True
.. autoclass:: uxibxx.UxibxxIoBoard.BadResponse
   :show-inheritance: True

Usage examples
--------------

Digital I/O
^^^^^^^^^^^
.. literalinclude:: usage_example_dio.py
   :language: python

Flow measurement
^^^^^^^^^^^^^^^^
.. literalinclude:: usage_example_flow.py
   :language: python

Liquid spill sensor
^^^^^^^^^^^^^^^^^^^
.. literalinclude:: usage_example_leak.py
   :language: python
