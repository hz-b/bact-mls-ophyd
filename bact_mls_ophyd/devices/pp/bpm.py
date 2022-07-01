"""BPM preprocessed data
"""


from bact_bessyii_mls_ophyd.devices.utils.derived_signal_bpm import BPMWaveform

from ..raw.bpm import BPM as BPMR
from ophyd import Component as Cpt, Device, EpicsSignalRO
from ophyd.status import SubscriptionStatus, AndStatus


def read_orbit_data():
    import pandas as pd

    filename = "/opt/OPI/MapperApplications/Orbit/StandardUser.dat"

    df = pd.read_csv(
        filename,
        sep="\s+",
        header=None,
    )
    df.columns = ["name", "x_offset", "y_offset"]
    df = df.set_index("name")
    return df


def bpm_config_data():
    """

    Todo:
        make this hack a transparent access
        find appropriate way to store it
    """

    from PyML import mlsinit
    import pandas as pd
    import numpy as np

    columns = [
        "name",
        # x plane
        "read_x",
        "x_active",
        # y plane
        "read_y",
        "y_active",
        # infos
        "family",
        "num",
        "s",
        # index into the vector
        "idx",
        #
        "unknown_a",
        #
        "unknown_b",
        #
    ]

    mml_bpm_data = pd.DataFrame(
        index=columns, data=mlsinit.bpm, dtype=object
    ).T.set_index("name")

    # bpm_data = mml_bpm_data.reindex(columns=columns + ["offset_x", "offset_y"])
    ref_orbit = read_orbit_data()
    bpm_data = mml_bpm_data.merge(ref_orbit, left_index=True, right_index=True)
    bpm_data = bpm_data.infer_objects()
    return bpm_data


class BPM(BPMR, BPMWaveform):

    n_elements = 256
    n_valid_bpms = 32
    skip_unset_second_half = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.standardConfiguration()

    def standardConfiguration(self):
        """

        Todo:
            make this hack a transparent access
        """
        rec = bpm_config_data()

        indices = rec.idx.values - 1        
        self.configure(dict(names=rec.index.values, indices=indices, ))
        self.ds.put(rec.s.values)

        self.x.configure(dict(offset=rec.x_offset.values))
        self.y.configure(dict(offset=rec.y_offset.values))
        self.log.warning("Standard configuration executed")

    def trigger(self):
        def cb_r(success=False):
            self.log.debug(f"Finished raw data reading with success {success}")

        def cb_p(success=False):
            self.log.debug(f"Finished processed data reading with success {success}")
            
        stat_r = BPMR.trigger(self)
        stat_r.add_callback(cb_r)
        stat_p = BPMWaveform.trigger(self)
        stat_p.add_callback(cb_p)
        return AndStatus(stat_r, stat_p)

    # def discribe(self):
    #     d = BPMR.describe(self)
    #    d.update(BPMWaveform.describe(self))
    #    return d

    # def read(self):
    #    d = BPMR.read(self)
    #    d.update(BPMWaveform.read(self))
    #    return d
        
    
if __name__ == "__main__":
    # print("#--------")
    # print(bpm_config_data().dtypes)

    # print(mlsinit.bpm[0])
    # mlsinit.bpm
    # how to combine it with the BPM test of the raw type
    bpm = BPM("BPMZ1X003GP", name="bpm")
    if not bpm.connected:
        bpm.wait_for_connection()

    print(bpm.describe())
    stat = bpm.trigger()
    stat.wait(3)
    data = bpm.read()
    print("# ---- data")
    print(data)
    print("# ---- end data ")
