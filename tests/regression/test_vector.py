from firedrake import *
import pytest


@pytest.fixture
def f():
    mesh = UnitIntervalMesh(2)
    V = FunctionSpace(mesh, "CG", 1)
    f = Function(V)
    f.interpolate(Expression("1"))
    return f


def test_vector_array(f):
    v = f.vector()
    assert (v.array() == 1.0).all()


def test_vector_setitem(f):
    v = f.vector()
    v[:] = 2.0

    assert(v.array() == 2.0).all()


def test_vector_getitem(f):
    v = f.vector()
    assert v[0] == 1.0


def test_vector_len(f):
    v = f.vector()
    assert len(v) == f.dof_dset.size


def test_vector_returns_copy(f):
    v = f.vector()
    a = v.array()
    a[:] = 5.0
    assert v.array() is not a
    assert (v.array() == 1.0).all()
    assert (a == 5.0).all()


def test_vector_gather_works(f):
    f.interpolate(Expression("2"))
    v = f.vector()
    gathered = v.gather([0])
    assert len(gathered) == 1 and gathered[0] == 2.0


def test_axpy(f):
    f.interpolate(Expression("2"))
    v = f.vector()
    y = Vector(v)
    y[:] = 4

    v.axpy(3, y)

    assert (v.array() == 14.0).all()


def test_scale(f):
    f.interpolate(Expression("3"))
    v = f.vector()
    v._scale(7)

    assert (v.array() == 21.0).all()


@pytest.mark.parallel(nprocs=2)
def test_parallel_gather():
    from mpi4py import MPI
    mesh = UnitSquareMesh(2, 2)
    V = FunctionSpace(mesh, "CG", 1)
    f = Function(V)
    v = f.vector()
    rank = MPI.COMM_WORLD.rank
    v[:] = rank

    assert (f.dat.data_ro[:f.dof_dset.size] == rank).all()

    lsum = sum(v.array())
    lsum = MPI.COMM_WORLD.allreduce(lsum, op=MPI.SUM)
    gathered = v.gather()
    gsum = sum(gathered)
    assert lsum == gsum
    assert len(gathered) == v.size()

    gathered = v.gather([0])
    assert len(gathered) == 1 and gathered[0] == 0


if __name__ == '__main__':
    import os
    pytest.main(os.path.abspath(__file__))
