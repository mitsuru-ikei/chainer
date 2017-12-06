import numpy

import chainer
from chainer import variable


available = False

try:
    from dnn import cosim
    import dnn._dnn
    from dnn._dnn import mdarray
    from dnn._dnn import IntVector
    from dnn._dnn import MdarrayVector
    from dnn._dnn import batchNormalizationF32
    from dnn._dnn import Relu_Py_F32
    from dnn._dnn import conv_param_t, Convolution2D_Py_F32
    from dnn._dnn import pooling_param_t, Pooling2D_Py_F32
    from dnn._dnn import Concat_Py_F32
    from dnn._dnn import linear_param_t, Linear_Py_F32
    from dnn._dnn import lrn_param_t, LocalResponseNormalization_Py_F32
    from dnn._dnn import Dropout_F32
    available = True
except Exception as ex:
    print('*** CPU acceleration is disabled: %s' % ex)

    class mdarray(object):
        pass


def is_enabled():
    # Check whether ideep installed

    return available


def all_ready(inputs, check_with_ndim):
    if not is_enabled():
        return False
    _inputs = [x.data if isinstance(x, variable.Variable)
               else x for x in inputs]

    # Check with ideep supported dimension of input data
    valid_ndim = False
    for ndim in check_with_ndim:
        valid_ndim = valid_ndim or _inputs[0].ndim == ndim

    if check_with_ndim and not valid_ndim:
        return False

    if isinstance(_inputs[0], mdarray):
        return True
    # Check whether ideep configured and used correctly
    elif isinstance(_inputs[0], numpy.ndarray):
        _should_use_ideep = True

        for x in _inputs:
            _should_use_ideep = _should_use_ideep and \
                                 x.dtype == numpy.dtype('float32')
        if _should_use_ideep:
            _should_use_ideep = _should_use_ideep and \
                                 chainer.should_use_ideep('>=auto')
        if not _should_use_ideep:
            return False
    # cuda.ndarray
    else:
        return False

    return True


# ----------------------------------------------------------------------
# ideepy mdarray allocation
# ---------------------------------------------------------------------
data = 'd' #data array
weight = 'w' #weight array
def array(x, itype=data):
    if isinstance(x, numpy.ndarray):
        if x.flags.contiguous is False:
            x = numpy.ascontiguousarray(x)
        return mdarray(x, itype)
    else:
        return x


def to_mdarray(xs):
    ys = ()
    for x in xs:
        ys += array(x),
    return ys


def to_ia(arr):
    if not is_enabled():
        raise Exception ( "ideepy is not installed coorectly" )
    return array(arr, itype=weight)