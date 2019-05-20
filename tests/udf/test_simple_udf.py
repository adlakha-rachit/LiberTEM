import numpy as np
import pytest

from libertem.common.buffers import BufferWrapper
from libertem.udf import UDF
from utils import MemoryDataSet, _mk_random


class PixelsumUDF(UDF):
    def get_result_buffers(self):
        return {
            'pixelsum': BufferWrapper(
                kind="nav", dtype="float32"
            )
        }

    def process_frame(self, frame):
        self.results.pixelsum[:] = np.sum(frame)


def test_sum_frames(lt_ctx):
    """
    Test sum over the pixels for 2-dimensional dataset

    Parameters
    ----------
    lt_ctx
        Context class for loading dataset and creating jobs on them

    """
    data = _mk_random(size=(16, 16, 16, 16), dtype="float32")
    dataset = MemoryDataSet(data=data, tileshape=(1, 16, 16),
                            num_partitions=2, sig_dims=2)

    pixelsum = PixelsumUDF()
    res = lt_ctx.run_udf(dataset=dataset, udf=pixelsum)
    assert 'pixelsum' in res
    print(data.shape, res['pixelsum'].data.shape)
    assert np.allclose(res['pixelsum'].data, np.sum(data, axis=(2, 3)))


def test_3d_ds(lt_ctx):
    """
    Test sum over the pixels for 3-dimensional dataset

    Parameters
    ----------
    lt_ctx
        Context class for loading dataset and creating jobs on them
    """
    data = _mk_random(size=(16 * 16, 16, 16), dtype="float32")
    dataset = MemoryDataSet(data=data, tileshape=(1, 16, 16),
                            num_partitions=2, sig_dims=2)

    pixelsum = PixelsumUDF()
    res = lt_ctx.run_udf(dataset=dataset, udf=pixelsum)
    assert 'pixelsum' in res
    print(data.shape, res['pixelsum'].data.shape)
    assert np.allclose(res['pixelsum'].data, np.sum(data, axis=(1, 2)))


def test_kind_single(lt_ctx):
    """
    Test buffer type kind='single'

    Parameters
    ----------
    lt_ctx
        Context class for loading dataset and creating jobs on them
    """
    data = _mk_random(size=(16, 16, 16, 16), dtype="float32")
    dataset = MemoryDataSet(data=data, tileshape=(2, 16, 16),
                            num_partitions=2, sig_dims=2)

    class CounterUDF(UDF):
        def get_result_buffers(self):
            return {
                'counter': BufferWrapper(
                    kind="single", dtype="uint32"
                )
            }

        def process_frame(self, frame):
            self.results.counter += 1

        def merge(self, dest, src):
            dest['counter'][:] += src['counter']

    counter = CounterUDF()
    res = lt_ctx.run_udf(dataset=dataset, udf=counter)
    assert 'counter' in res
    assert res['counter'].data.shape == (1,)
    assert res['counter'].data == 16 * 16


def test_bad_merge(lt_ctx):
    """
    Test bad example of updating buffer
    """
    data = _mk_random(size=(16 * 16, 16, 16), dtype="float32")
    dataset = MemoryDataSet(data=data, tileshape=(1, 16, 16),
                            num_partitions=2, sig_dims=2)

    class BadmergeUDF(UDF):
        def get_result_buffers(self):
            return {
                'pixelsum': BufferWrapper(
                    kind="nav", dtype="float32"
                )
            }

        def process_frame(self, frame):
            self.results.pixelsum[:] = np.sum(frame)

        def merge(self, dest, src):
            # bad, because it just sets a key in dest, it doesn't copy over the data to dest
            dest['pixelsum'] = src['pixelsum']

    with pytest.raises(TypeError):
        bm = BadmergeUDF()
        lt_ctx.run_udf(dataset=dataset, udf=bm)


def test_extra_dimension_shape(lt_ctx):
    """
    Test sum over the pixels for 2-dimensional dataset

    Parameters
    ----------
    lt_ctx
        Context class for loading dataset and creating jobs on them

    """
    data = _mk_random(size=(16, 16, 16, 16), dtype="float32")
    dataset = MemoryDataSet(data=data, tileshape=(1, 16, 16),
                            num_partitions=2, sig_dims=2)

    class ExtraShapeUDF(UDF):
        def get_result_buffers(self):
            return {
                'test': BufferWrapper(
                    kind="nav", extra_shape=(2,), dtype="float32"
                )
            }

        def process_frame(self, frame):
            self.results.test[:] = (1, 2)

    extra = ExtraShapeUDF()
    res = lt_ctx.run_udf(dataset=dataset, udf=extra)

    print(data.shape, res['test'].data.shape)
    assert res['test'].data.shape == tuple(dataset.shape.nav) + (2,)
    assert np.allclose(res['test'].data[0, 0], (1, 2))


def test_roi_1(lt_ctx):
    data = _mk_random(size=(16, 16, 16, 16), dtype="float32")
    dataset = MemoryDataSet(data=data, tileshape=(3, 16, 16),
                            num_partitions=4, sig_dims=2)
    mask = np.random.choice([True, False], size=(16, 16))

    def my_buffers():
        return {
            'pixelsum': BufferWrapper(
                kind="nav", dtype="float32"
            )
        }

    def my_frame_fn(frame, pixelsum):
        pixelsum[:] = np.sum(frame)

    pixelsum = PixelsumUDF()
    res = lt_ctx.run_udf(dataset=dataset, udf=pixelsum, roi=mask)
    assert 'pixelsum' in res
    print(data.shape, res['pixelsum'].data.shape)
    expected = np.sum(data[mask, ...], axis=(-1, -2))
    assert np.allclose(res['pixelsum'].raw_data, expected)


def test_roi_all_zeros(lt_ctx):
    data = _mk_random(size=(16, 16, 16, 16), dtype="float32")
    dataset = MemoryDataSet(data=data, tileshape=(3, 16, 16),
                            num_partitions=16, sig_dims=2)
    mask = np.zeros(data.shape[:2], dtype=bool)

    pixelsum = PixelsumUDF()
    res = lt_ctx.run_udf(dataset=dataset, udf=pixelsum, roi=mask)
    assert 'pixelsum' in res
    print(data.shape, res['pixelsum'].data.shape)
    expected = np.sum(data[mask, ...], axis=(-1, -2))
    assert np.allclose(res['pixelsum'].raw_data, expected)


def test_roi_some_zeros(lt_ctx):
    data = _mk_random(size=(16, 16, 16, 16), dtype="float32")
    dataset = MemoryDataSet(data=data, tileshape=(3, 16, 16),
                            num_partitions=16, sig_dims=2)
    mask = np.zeros(data.shape[:2], dtype=bool)
    mask[0] = True

    pixelsum = PixelsumUDF()
    res = lt_ctx.run_udf(dataset=dataset, udf=pixelsum, roi=mask)
    assert 'pixelsum' in res
    print(data.shape, res['pixelsum'].data.shape)
    expected = np.sum(data[mask, ...], axis=(-1, -2))
    assert np.allclose(res['pixelsum'].raw_data, expected)
