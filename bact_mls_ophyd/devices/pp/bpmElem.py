from dataclasses import dataclass


@dataclass
class BpmElementList:
    def __init__(self):
        self.bpmElemList = []

    def addBpmElem(self, bpmElem):
        self.bpmElemList.append(bpmElem)

    def toDict(self):
        pass
    def unDict(self):
        pass


@dataclass
class BpmElemPlane:
    def __init__(self, pos_raw, rms_raw):
        self.pos_raw = pos_raw
        self.rms_raw = rms_raw

    pos_raw: int
    rms_raw: int



@dataclass
class BpmElem():
    def __init__(self, bpmElemPlaneX, bpmElemPlaneY, intensity_z, intensity_s, stat, gain_raw):
        self.x = bpmElemPlaneX
        self.y = bpmElemPlaneY
        self.intensity_z = intensity_z
        self.intensity_s = intensity_s
        self.stat = stat
        self.gain_raw = gain_raw

    x: BpmElemPlane
    y: BpmElemPlane
    intensity_z: int
    intensity_s: int
    stat: int
    gain_raw: int
