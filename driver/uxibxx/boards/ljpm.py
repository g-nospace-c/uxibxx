from .._driver import UxibxxIoBoard
from .. import features
from ..usb_ids import USB_VIDPID_FOR_MODEL


MODEL_NAME = "UXIB-LJPM"


class UxibLjpm(
        UxibxxIoBoard,
        features.dio.DigitalIo,
        #features.i2c.ISquaredC,
        ):
    USB_VIDPIDS = {USB_VIDPID_FOR_MODEL[MODEL_NAME]}


_BoardModelDriverCls = UxibLjpm
