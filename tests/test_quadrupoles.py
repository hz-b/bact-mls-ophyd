from bact_mls_ophyd.devices.pp.quadrupoles import QuadrupolesCollection
import pytest


def create_quad_collection():
    return QuadrupolesCollection(name="qc")


def test020_quadrupole_create():
    create_quad_collection()


@pytest.mark.skip
def test020_quadrupole_load():
    qc = create_quad_collection()
    if not qc.connected:
        qc.wait_for_connection()

    print(qc.read())
