from bact_bessyii_mls_ophyd.devices.utils.power_converters_as_multiplexer import (
    ScaledPowerConverter,
    SelectedPowerConverter,
    MultiplexerSetMixin,
)

from ophyd.areadetector.base import ad_group
from ophyd import Component as Cpt, Device, Kind, Signal
from ophyd.device import DynamicDeviceComponent as DDC

def load_quad_names():
    import numpy as np
    from importlib.resources import files

    module_name = __name__.split('.')[0]
    archiver_config_file = files(module_name).joinpath("data/quadrupole_names.txt")

    quad_q1 = np.loadtxt(archiver_config_file, dtype="U40").tolist()
    quad_q2 = [name.replace("Q1", "Q2") for name in quad_q1]
    quad_q3 = [name.replace("Q1", "Q3") for name in quad_q1]
    quad_names = quad_q1 + quad_q2 + quad_q3
    return quad_names


quad_names = load_quad_names()

class QuadrupolesCollection(Device, MultiplexerSetMixin):
    """

    Todo:
        Belongs to the multiplexer
    """

    power_converters = DDC(
        ad_group(ScaledPowerConverter, [(name, name) for name in quad_names], kind=Kind.normal, lazy=False),
        doc="all quadrupoles ",
        default_read_attrs=(),
    )

    power_converter_names = Cpt(
        Signal, name="quad_names", value=quad_names, kind=Kind.config
    )

    sel = Cpt(SelectedPowerConverter, name="sel_pc")

    _default_config_attrs = ("quad_names",)
    _default_read_attrs = ("sel",)


