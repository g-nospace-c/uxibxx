from .._driver import UxibxxIoBoard
from .. import features
from ..usb_ids import USB_VIDPID_FOR_MODEL


MODEL_NAME = "UXIB-DN12"


class UxibDn12(
        UxibxxIoBoard,
        features.dio.DigitalIo
        ):
    USB_VIDPIDS = {USB_VIDPID_FOR_MODEL[MODEL_NAME]}


_BoardModelDriverCls = UxibDn12
