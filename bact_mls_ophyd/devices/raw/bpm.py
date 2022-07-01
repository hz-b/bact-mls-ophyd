"""
"""
from ophyd import Component as Cpt, Device, EpicsSignalRO, Kind, Signal
from ophyd.status import SubscriptionStatus

class BPM(Device):
    packed_data = Cpt(EpicsSignalRO, ":rdBufBpm")
    count = Cpt(EpicsSignalRO, ":count")
    timeout = Cpt(Signal, name="timeout", value=3, kind=Kind.config)
    
    def trigger(self):
        def cb(**kwargs):
            """new data here"""
            return True
        
        timeout = self.timeout.get()
        return SubscriptionStatus(self.packed_data, cb, run=False, timeout=timeout)
    

def test_bpm():
    """pytest compatible
    """
    
    bpm = BPM("BPMZ1X003GP", name="bpm")
    if not bpm.connected:
        bpm.wait_for_connection()
        
    stat = bpm.trigger()
    stat.wait(3)
    data = bpm.read()
    bpm_data = data["bpm_packed_data"]["value"]
    
if __name__ == "__main__":
    test_bpm()
