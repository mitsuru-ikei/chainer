import ctypes
import numpy

from chainer import cuda
from chainer import function
from chainer.utils import type_check

if cuda.cudnn_enabled:
    cudnn = cuda.cudnn
    libcudnn = cudnn.cudnn
    _algorithm = libcudnn.CUDNN_SOFTMAX_ACCURATE
    _mode = libcudnn.CUDNN_SOFTMAX_MODE_INSTANCE


class Softmax(function.Function):

    """Softmax activation function."""

    def __init__(self, use_cudnn=True):
        self.use_cudnn = use_cudnn

    def check_type_forward(self, in_types):
        type_check.expect(in_types.size() == 1)
        x_type, = in_types

        type_check.expect(
            x_type.dtype == numpy.float32,
            x_type.ndim == 2,
        )

    def check_type_backward(self, in_types, out_types):
        type_check.expect(
            in_types.size() == 1,
            out_types.size() == 1,
        )
        x_type, = in_types
        y_type, = out_types

        type_check.expect(
            y_type.ndim == 2,

            y_type.shape[0] == x_type.shape[0],
            y_type.shape[1] == x_type.shape[1],
        )

    def forward_cpu(self, x):
        self.y = x[0] - numpy.amax(x[0], axis=1, keepdims=True)
        numpy.exp(self.y, out=self.y)
        self.y /= self.y.sum(axis=1, keepdims=True)
        return self.y,

    def forward_gpu(self, x):
        y = cuda.empty_like(x[0])
        if cuda.cudnn_enabled and self.use_cudnn:
            handle = cudnn.get_handle()
            x_mat = x[0].reshape(x[0].shape[0], -1, 1, 1)
            desc = cudnn.create_tensor_descriptor(x_mat)
            libcudnn.softmaxForward(
                handle, _algorithm, _mode, ctypes.c_float(1), desc.value,
                x[0].data.ptr, ctypes.c_float(0), desc.value, y.data.ptr)
            self.y = y
        else:
            maxes = cuda.empty((x[0].shape[0],), dtype=numpy.float32)
            c = x[0].shape[1]
            cuda.elementwise(
                ['maxes', 'x', 'c'],
                '''
                   const float* row = &x[i * c];
                   float maxval = row[0];
                   for (int j = 1; j < c; ++j) {
                     if (maxval < row[j]) {
                       maxval = row[j];
                     }
                   }
                   maxes[i] = maxval;
                ''', 'softmax_rowmax')(maxes, x[0], c)
            cuda.elementwise(
                ['y', 'x', 'maxes', 'c'],
                'y[i] = __expf(x[i] - maxes[i / c])',
                'softmax_exp')(y, x[0], maxes, c)
            coeff = maxes  # reuse memory
            cuda.elementwise(
                ['coeff', 'y', 'c'],
                '''
                   const float* row = &y[i * c];
                   float sum = 0;
                   for (int j = 0; j < c; ++j) {
                     sum += row[j];
                   }
                   coeff[i] = 1 / sum;
                ''', 'softmax_invrowsum')(coeff, y, c)
            cuda.elementwise(
                ['y', 'coeff', 'c'], 'y[i] *= coeff[i / c]',
                'softmax_rowmul')(y, coeff, c)
            self.y = y

        return y,

    def backward_cpu(self, x, gy):
        gx = self.y * gy[0]
        sumdx = gx.sum(axis=1, keepdims=True)
        gx -= self.y * sumdx
        return gx,

    def backward_gpu(self, x, gy):
        if cuda.cudnn_enabled and self.use_cudnn:
            handle = cudnn.get_handle()
            gx = cuda.empty_like(x[0])
            x_mat = x[0].reshape(x[0].shape[0], -1, 1, 1)
            desc = cudnn.create_tensor_descriptor(x_mat)
            libcudnn.softmaxBackward(
                handle, _algorithm, _mode, ctypes.c_float(1), desc.value,
                self.y.data.ptr, desc.value, gy[0].data.ptr, ctypes.c_float(0),
                desc.value, gx.data.ptr)
        else:
            gx = self.y * gy[0]
            c = gx.shape[1]
            sum_ydy = cuda.empty((gx.shape[0],), dtype=numpy.float32)
            cuda.elementwise(
                ['sum_ydy', 'ydy', 'c'],
                '''
                   const float* row = &ydy[i * c];
                   float sum = 0;
                   for (int j = 0; j < c; ++j) {
                     sum += row[j];
                   }
                   sum_ydy[i] = sum;
                ''', 'softmax_bwd_sum_ydy')(sum_ydy, gx, c)
            cuda.elementwise(
                ['gx', 'y', 'sum_ydy', 'c'],
                'gx[i] -= y[i] * sum_ydy[i / c]',
                'softmax_bwd_diff')(gx, self.y, sum_ydy, c)

        return gx,


def softmax(x, use_cudnn=True):
    """Channelwise softmax function.

    This function only accepts a two dimensional input array, and computes its
    softmax along the second axis. For each index :math:`i, j` of the input
    matrix :math:`x`, it computes
    :math:`f_{ij}(x)={\\exp(x_{ij}) \\over \\sum_j \\exp(x_{ij})}`.

    Args:
        x (~chainer.Variable): Input variable.
        use_cudnn (bool): If True and CuDNN is enabled, then this function uses
            CuDNN as the core implementation.

    Returns:
        ~chainer.Variable: Output variable.

    """
    return Softmax(use_cudnn)(x)
