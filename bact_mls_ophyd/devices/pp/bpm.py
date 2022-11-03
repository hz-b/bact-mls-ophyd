"""BPM preprocessed data
"""
import numpy as np

# from bact_bessyii_mls_ophyd.devices.utils.derived_signal_bpm import BPMWaveform
from bact_bessyii_mls_ophyd.devices.process.bpm_packed_data import packed_data_to_named_array
from ..raw.bpm import BPM as BPMR
from .bpmElem import BpmElementList, BpmElemPlane, BpmElem
import functools
from ophyd import Component as Cpt, Device, EpicsSignalRO, Signal, Kind
from ophyd.status import SubscriptionStatus, AndStatus


def read_orbit_data():
    from pyml import mls_data
    return mls_data.bpm_offsets()


@functools.lru_cache(maxsize=1)
def bpm_config_data():
    """

    Todo:
        make this hack a transparent access
        find appropriate way to store it
    """

    from pyml import mlsinit
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


class BPM(BPMR):
    """
    This is the model for a BPM class which specifies a BPM inside a machine.
    A BPM is
    TODO: write a description of the model class in details.
    """

    # List of member attributes for a BPM

    n_elements = 256
    """
        TODO: Provide such a comment to each member attribute of all classes.
        default value of the n_element
        @Member n_elements: this is the number of bpms inside a machine
        todo: rewrite this comment after discussing with Pierre
    """

    #  @Member n_valid_bpms out of n_elements these are only active....
    #  todo: why set this on the model level?
    n_valid_bpms = 32
    skip_unset_second_half = False

    #  @Member ds: it is a signal componenet and it does .....
    #  A componenet is a descriptor representing a device component (or signal)
    ds = Cpt(Signal, name="ds", value=np.nan, )  # kind=Kind.config
    #  @Member indices a signal which determines the index .... what is inside indices
    indices = Cpt(Signal, name="indices", value=np.nan, kind=Kind.config)
    names = Cpt(Signal, name="names", value=np.nan, kind=Kind.config)

    #  a constructor for BPM
    #  **kwargs / **args...  passed an unspecified number of arguments to to the constructor.
    #  We should know what are we passing to a constructor, todo don't we?

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.standardConfiguration()

    # member function standardConfiguration
    #  todo: explain what we should be doing in this function
    def standardConfiguration(self):
        """

        Todo:
            make this hack a transparent access
        """
        #  todo: rec = recievable... or?
        rec = bpm_config_data()
        self.ds.put(rec.s.values)
        indices = rec.idx.values - 1
        self.configure(dict(names=rec.index.values, indices=indices, ))
        return

    #
    def splitPackedData(self, data_dic):
        """
        @Params: data_dict: data dictionary in a ... format
        this method will split the packed data into ...
        """
        pd = data_dic[self.name + '_packed_data']
        timestamp = pd["timestamp"]
        r = packed_data_to_named_array(pd["value"], n_elements=self.n_elements, indices=self.indices.get())
        d2 = {self.name + "_" + key: dict(value=r[key], timestamp=timestamp) for key, val in r.dtype.descr}
        return d2

    @functools.lru_cache(maxsize=1)
    def dataForDescribe(self):
        return self.splitPackedData(self.read())

    def describe(self):
        data = super().describe()
        signal_name = self.name + "_packed_data"
        bpm_data = {self.name + "_elem_data": BpmElementList().describe_dict()}
        data.update(bpm_data)
        del data[signal_name]
        return data

    def read(self):
        data = super().read()
        bpm_element_list = BpmElementList()
        n_channels = 8
        signal_name = self.name + "_packed_data"
        bpm_packed_data_chunks = np.transpose(np.reshape(data[signal_name]['value'], (n_channels, -1)))
        for chunk in bpm_packed_data_chunks:
            bpm_elem_plane_x = BpmElemPlane(chunk[0], chunk[1])
            bpm_elem_plane_y = BpmElemPlane(chunk[2], chunk[3])
            bpm_elem = BpmElem(bpm_elem_plane_x, bpm_elem_plane_y, chunk[4], chunk[5], chunk[6], chunk[7])
            bpm_element_list.add_bpm_elem(bpm_elem)
        bpm_data = {self.name + "_elem_data": bpm_element_list.to_dict(data['bpm_packed_data']['timestamp'])}
        data.update(bpm_data)
        del data[signal_name]
        return data


if __name__ == "__main__":
    # print("#--------")
    # print(bpm_config_data().dtypes)

    # print(mlsinit.bpm[0])
    # mlsinit.bpm
    # how to combine it with the BPM test of the raw type
    bpm = BPM("BPMZ1X003GP", name="bpm")
    if not bpm.connected:
        bpm.wait_for_connection()
    stat = bpm.trigger()
    stat.wait(3)
    data = bpm.read()
    print("# ---- data")
    print(data)
    print("# ---- end data ")
