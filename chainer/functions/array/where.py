import numpy

from chainer import cuda
from chainer import function
from chainer.utils import type_check


class Where(function.Function):

    def check_type_forward(self, in_types):
        type_check.expect(in_types.size() == 3)
        c_type, x_type, y_type = in_types

        type_check.expect(
            c_type.dtype == numpy.bool_,
            x_type.dtype == y_type.dtype,
            x_type.shape == c_type.shape,
            y_type.shape == c_type.shape,
        )

    def forward(self, inputs):
        xp = cuda.get_array_module(*inputs)
        condition, x, y = inputs
        return xp.where(condition, x, y),

    def backward(self, inputs, grads):
        xp = cuda.get_array_module(*inputs)
        condition, x, y = inputs
        zeros = xp.zeros((), dtype=grads.dtype)
        gx = xp.where(condition, grads, zeros)
        gy = xp.where(~condition, grads, zeros)
        return gx, gy


def where(condition, x, y):
    return Where()(condition, x, y)
