import sys
import threading
import time
from typing import Sequence

from ophyd import (
    Component as Cpt,
    Device,
    EpicsSignal,
    EpicsSignalRO,
    Kind,
    PVPositionerPC,
    Signal,
)

from ophyd.device import DynamicDeviceComponent as DDC
from ophyd.status import AndStatus, SubscriptionStatus, Status

from bact_mls_ophyd.devices.pp.power_converter import MultiplexerPowerConverter
from bact_mls_ophyd.devices.pp.selected_multiplexer import MultiplexerSelector
from bact_bessyii_mls_ophyd.devices.utils.reached_setpoint import ReachedSetpointEPS
from bact_mls_ophyd.devices.pp.quadrupoles import quad_names
t_super = PVPositionerPC
t_super = ReachedSetpointEPS

_muxer_off = "Mux OFF"
_request_off = "Off"

_t_super = PVPositionerPC


class MultiplexerPCWrapper(Device):
    pcs = DDC(
        {
            name: (EpicsSignal, ":" + name, dict(put_complete=True))
            for name in quad_names
        },
        doc="the multiplexer power converter selector pvs",
        default_read_attrs=(),
    )

    def get_element_names(self) -> Sequence[str]:
        """
        Returns:
            the names of the elements the multiplexer can connect to
        """
        return self.pcs.component_names
