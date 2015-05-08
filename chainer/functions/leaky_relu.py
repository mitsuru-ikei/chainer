import numpy
from chainer import cuda, Function

class LeakyReLU(Function):
    """Leaky rectifier unit."""

    def __init__(self, slope=0.2):
        self.slope = slope

    def forward_cpu(self, x):
        y = x[0].copy()
        y[x[0] < 0] *= self.slope
        return y,

    def forward_gpu(self, x):
        y = cuda.empty_like(x[0])
        self._kern()(y, x[0], x[0], self.slope)
        return y,

    def backward_cpu(self, x, gy):
        gx = gy[0].copy()
        gx[x[0] < 0] *= self.slope
        return gx,

    def backward_gpu(self, x, gy):
        gx = cuda.empty_like(x[0])
        self._kern()(gx, x[0], gy[0], self.slope)
        return gx,

    @staticmethod
    def _kern():
        return cuda.elementwise(
            'float* y, const float* cond, const float* x, float slope',
            'y[i] = cond[i] >= 0 ? x[i] : slope * x[i]', 'lrelu')

def leaky_relu(x, slope=0.2):
    return LeakyReLU(slope)(x)
