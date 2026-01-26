from .._driver import UxibxxIoBoard
from .. import features
from ..usb_ids import USB_VIDPID_FOR_MODEL


MODEL_NAME = "UXIB-SHF4"


class UxibShf4(
        UxibxxIoBoard,
        features.dio.DigitalIo,
        #features.i2c.ISquaredC,
        features.flow.FlowMeasurement,
        features.leak.LeakDetector,
        ):
    USB_VIDPIDS = {USB_VIDPID_FOR_MODEL[MODEL_NAME]}


_BoardModelDriverCls = UxibShf4
