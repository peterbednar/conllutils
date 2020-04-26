import os
import pytest
import numpy as np

from conllutils.pipeline import pipe

def _data_filename(name):
    return os.path.join(os.path.dirname(__file__), name)

@pytest.fixture
def data1():
    return _data_filename("data1.conllu")
@pytest.fixture
def data2():
    return _data_filename("data2.conllu")
@pytest.fixture
def data3():
    return _data_filename("data3.conllu")
@pytest.fixture
def data4():
    return _data_filename("data4.conllu")
@pytest.fixture
def data5():
    return _data_filename("data5.conllu")

def test_hdf5(data3, tmp_path):
    index = pipe().read_conllu(data3).create_index()
    instances1 = pipe().read_conllu(data3).to_instance(index).collect()

    filename = tmp_path / 'data.hdf5'
    pipe(instances1).write_file(filename, 'hdf5')
    instances2 = pipe().read_file(filename, 'hdf5').collect()

    for ins1, ins2 in zip(instances1, instances2):
        equal_instance(ins1, ins2)

def equal_instance(ins1, ins2):
    assert ins1.metadata == ins2.metadata
    assert ins1.keys() == ins2.keys()

    for field in ins1.keys():
        assert np.array_equal(ins1[field], ins2[field])

if __name__ == "__main__":
    pass
