import ufl
import ufl.argument
from ufl.assertions import ufl_assert
from ufl.finiteelement import FiniteElementBase
from ufl.split_functions import split
from ufl.algorithms.analysis import extract_arguments
import core_types
import solving


class Argument(ufl.argument.Argument):
    """Representation of the argument to a form,"""
    def __init__(self, element, function_space, count=None):
        """
        :arg element: the :class:`ufl.element.FiniteElementBase` this
             argument corresponds to.
        :arg function_space: the :class:`.FunctionSpace` the argument
             corresponds to.
        :arg count: the number of the argument being constructed.

        .. note::

           an :class:`Argument` with a count of ``-2`` is used as a
           :class:`TestFunction`, with a count of ``-1`` it is used as
           a :class:`TrialFunction`.

        """
        super(Argument, self).__init__(element, count)
        self._function_space = function_space

    @property
    def cell_node_map(self):
        return self._function_space.cell_node_map

    @property
    def interior_facet_node_map(self):
        return self._function_space.interior_facet_node_map

    @property
    def exterior_facet_node_map(self):
        return self._function_space.exterior_facet_node_map

    def function_space(self):
        return self._function_space

    def make_dat(self):
        return self._function_space.make_dat()

    def reconstruct(self, element=None, function_space=None, count=None):
        if function_space is None or function_space == self._function_space:
            function_space = self._function_space
        if element is None or element == self._element:
            element = self._element
        if count is None or count == self._count:
            count = self._count
        if count is self._count and element is self._element:
            return self
        ufl_assert(isinstance(element, FiniteElementBase),
                   "Expecting an element, not %s" % element)
        ufl_assert(isinstance(count, int),
                   "Expecting an int, not %s" % count)
        ufl_assert(element.value_shape() == self._element.value_shape(),
                   "Cannot reconstruct an Argument with a different value shape.")
        return Argument(element, function_space, count)


class Action(object):
    """A representation of the action of a bilinear form on a coefficient.

    Because application of boundary conditions is not a right-action,
    we cannot use a :class:`ufl.Form` to represent the action in the
    presence of boundary conditions, since there is nowhere on the
    form to stash them.
    """
    def __init__(self, a, x, bcs=None):
        """
        :arg a: a bilinear form.
        :arg x: a :class:`Function`
        :kwarg bcs: optional boundary conditions (an iterable of
            :class:`DirichletBC`\s) to apply when computing the action
        """
        self._a = a
        self._x = x
        self._bcs = bcs

    def assemble(self, tensor=None):
        """Assemble this :class:`Action` to produce a :class:`Function`.

        :arg tensor: an optional :class:`Function` to place the result in."""
        if self._bcs is None:
            return solving.assemble(ufl.action(self._a, self._x),
                                    tensor=tensor)
        if tensor is None:
            out = core_types.Function(self._x)
        else:
            out = tensor
            out.assign(self._x)
        for bc in self._bcs:
            out.assign(0, subset=bc.node_set)
        out.assign(solving.assemble(ufl.action(self._a, out)))
        for bc in self._bcs:
            out.assign(self._x, subset=bc.node_set)
        return out


def TestFunction(function_space):
    """Build a test function on the specified function space.

    :arg function_space: the :class:`.FunctionSpaceBase` to build the test
         function on."""
    return Argument(function_space.ufl_element(), function_space, -2)


def TrialFunction(function_space):
    """Build a trial function on the specified function space.

    :arg function_space: the :class:`.FunctionSpaceBase` to build the trial
         function on."""
    return Argument(function_space.ufl_element(), function_space, -1)


def TestFunctions(function_space):
    """Return a tuple of test functions on the specified function space.

    :arg function_space: the :class:`.FunctionSpaceBase` to build the test
         functions on.

    This returns ``len(function_space)`` test functions, which, if the
    function space is a :class:`.MixedFunctionSpace`, are indexed
    appropriately.
    """
    return split(TestFunction(function_space))


def TrialFunctions(function_space):
    """Return a tuple of trial functions on the specified function space.

    :arg function_space: the :class:`.FunctionSpaceBase` to build the trial
         functions on.

    This returns ``len(function_space)`` trial functions, which, if the
    function space is a :class:`.MixedFunctionSpace`, are indexed
    appropriately.
    """
    return split(TrialFunction(function_space))


def derivative(form, u, du=None):
    """Compute the derivative of a form.

    Given a form, this computes its linearization with respect to the
    provided :class:`.Function`.  The resulting form has one
    additional :class:`Argument` in the same finite element space as
    the Function.

    :arg form: a :class:`ufl.Form` to compute the derivative of.
    :arg u: a :class:`.Function` to compute the derivative with
         respect to.
    :arg du: an optional :class:`Argument` to use as the replacement
         in the new form (constructed automatically if not provided).

    See also :func:`ufl.derivative`.
    """
    if du is None:
        if isinstance(u, core_types.Function):
            V = u.function_space()
            du = Argument(V.ufl_element(), V)
        else:
            raise RuntimeError("Can't compute derivative for form")
    return ufl.derivative(form, u, du)


def adjoint(form, reordered_arguments=None):
    """UFL form operator:
    Given a combined bilinear form, compute the adjoint form by
    changing the ordering (count) of the test and trial functions.

    By default, new Argument objects will be created with
    opposite ordering. However, if the adjoint form is to
    be added to other forms later, their arguments must match.
    In that case, the user must provide a tuple reordered_arguments=(u2,v2).
    """

    # ufl.adjoint creates new Arguments if no reordered_arguments is
    # given.  To avoid that, always pass reordered_arguments with
    # firedrake.Argument objects.
    if reordered_arguments is None:
        v, u = extract_arguments(form)
        reordered_arguments = (Argument(u.element(), u.function_space()),
                               Argument(v.element(), v.function_space()))
    return ufl.adjoint(form, reordered_arguments)


def CellSize(mesh):
    """A symbolic representation of the cell size of a mesh.

    :arg mesh: the mesh for which to calculate the cell size.
    """
    cell = mesh.ufl_cell()
    return 2.0 * cell.circumradius


def FacetNormal(mesh):
    """A symbolic representation of the facet normal on a cell in a mesh.

    :arg mesh: the mesh over which the normal should be represented.
    """
    return ufl.FacetNormal(mesh.ufl_cell())


def action(form, coefficient=None, bcs=None):
    """Given a bilinear form, return a :class:`ufl.Form` or
    :class:`Action` representing the action of `form` on a coefficient.

    :arg form: a bilinear form
    :arg coefficient: a :class:`Function` to act on.
    :arg bcs: optional boundary conditions to apply when computing the
        action.

    This returns a :class:`ufl.Form` if bcs is None, a :class:`Action`
    otherwise.
    """
    if bcs is None:
        return ufl.action(form, coefficient)
    return Action(form, coefficient, bcs=bcs)
