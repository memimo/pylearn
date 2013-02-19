import os, gc
import warnings
try:
    import tables
except ImportError:
    warnings.warn("Couldn't import tables, so far SVHN is "
            "only supported with PyTables")
import numpy
from theano import config
from pylearn2.datasets import dense_design_matrix
from pylearn2.utils.serial import load
from pylearn2.utils.string_utils import preprocess

class SVHN(dense_design_matrix.DenseDesignMatrixPyTables):

    mapper = {'train': 0, 'test': 1, 'extra': 2, 'train_all' : 3, 'splitted_train' : 4, 'valid' : 5}
    def __init__(self, which_set, path = None, center = False, scale = False,
            start = None, stop = None, axes=('b', 0, 1, 'c')):
        """
        Only for faster access there is a copy of hdf5 file in PYLEARN2_DATA_PATH
        but it mean to be only readable. If you wish to modify the data, you should pass
        a local copy to the path argument.
        """

        assert which_set in self.mapper.keys()
        self.args = locals()

        if path is None:
            path = '${PYLEARN2_DATA_PATH}/SVHN/format2/'
            mode = 'r'
            make_new = True
        else:
            mode = 'r+'
            make_new = False

        if mode == 'r' and (scale or center or (start != None) or (stop != None)):
            raise ValueError("Only for speed there is a copy of hdf5 "+\
                    "file in PYLEARN2_DATA_PATH but it meant to be only "+\
                    "readable. If you wish to modify the data, you should "+\
                    "pass a local copy to the path argument.")

        # load data
        path = preprocess(path)
        file_n = "{}{}_32x32.h5".format(path + "h5/", which_set)
        if os.path.isfile(file_n):
            make_new = False
        # if hdf5 file does not exist make them
        if make_new:
            self.make_data(which_set, path)

        self.h5file = tables.openFile(file_n, mode = mode)
        data = self.h5file.getNode('/', "Data")

        if start != None or stop != None:
            self.h5file, data = self.resize(self.h5file, start, stop)

        # rescale or center if permitted
        if center and scale:
            data.X[:] -= 127.5
            data.X[:] /= 127.5
        elif center:
            data.X[:] -= 127.5
        elif scale:
            data.X[:] /= 255.

        view_converter = dense_design_matrix.DefaultViewConverter((32, 32, 3), axes)
        super(SVHN, self).__init__(X = data.X, y = data.y, view_converter = view_converter)
        self.h5file.flush()

    @staticmethod
    def make_data(which_set, path):

        sizes = {'train': 73257, 'test': 26032, 'extra': 531131, 'train_all': 604388, 'splitted_train' : 598388, 'valid' : 6000}
        image_size = 32*32*3
        h_file_n = "{}{}_32x32.h5".format(path + "h5/", which_set)
        h5file, node = SVHN.init_hdf5(h_file_n, ([sizes[which_set], image_size], [sizes[which_set], 10]))

        path = path + "npy/"
        if which_set in ['train', 'test', 'valid']:
            if which_set == 'valid':
                path += 'split/'
            data_x = SVHN.load_data("{}{}_32x32_x.npy".format(path, which_set))
            data_y = SVHN.load_data("{}{}_32x32_y.npy".format(path, which_set), True)

            index = slice(0, sizes[which_set])
            SVHN.fill_hdf5(h5file, node, (data_x, data_y), index)
            assert numpy.array_equal(data_x, node.X[:])
            assert numpy.array_equal(data_y, node.y[:])
        elif which_set in ['splitted_train', 'valid']:
            for i in xrange(6):
                print 'loading {}/6'.format(i)
                # if the file is not closed/reopend the process goes into I/O zombie state
                if i > 0:
                    h5file = tables.openFile(h_file_n, mode = 'a')
                    node = h5file.getNode('/', "Data")
                data_x = SVHN.load_data("{}split/{}_32x32_x_{}.npy".format(path, 'train', i))
                data_y = SVHN.load_data("{}split/{}_32x32_y_{}.npy".format(path, 'train', i), True)
                index = slice(100000*i, 100000*i + data_x.shape[0])
                SVHN.fill_hdf5(h5file, node, (data_x, data_y), index)
                h5file.close()
                del data_x, data_y
                gc.collect()
        elif which_set in ['train_all', 'extra']:
            for i in xrange(6):
                print 'loading {}/6'.format(i)
                # if the file is not closed/reopend the process goes into I/O zombie state
                if i > 0:
                    h5file = tables.openFile(h_file_n, mode = 'a')
                    node = h5file.getNode('/', "Data")
                data_x = SVHN.load_data("{}{}_32x32_x_{}.npy".format(path, 'extra', i))
                data_y = SVHN.load_data("{}{}_32x32_y_{}.npy".format(path, 'extra', i), True)
                index = slice(100000*i, 100000*i + data_x.shape[0])
                SVHN.fill_hdf5(h5file, node, (data_x, data_y), index)
                h5file.close()
                del data_x, data_y
                gc.collect()

        if which_set == 'train_all':
            h5file = tables.openFile(h_file_n, mode = 'a')
            node = h5file.getNode('/', "Data")
            # add train data on top
            data_x = SVHN.load_data("{}{}_32x32_x.npy".format(path, 'train'))
            data_y = SVHN.load_data("{}{}_32x32_y.npy".format(path, 'train'), True)
            index = slice(sizes['extra'], sizes['extra'] + sizes['train'])
            SVHN.fill_hdf5(h5file, node, (data_x, data_y), index)

        h5file.close()

    @staticmethod
    def load_data(path, target = False):
        data = load(path)
        if not target:
            data = numpy.cast[config.floatX](data)
            data =  numpy.transpose(data, axes = [3, 2, 0 , 1])
            return data.reshape((data.shape[0], 32 * 32 * 3))
        else:
            # TODO assuming one_hot as default for now
            one_hot = numpy.zeros((data.shape[0], 10), dtype = config.floatX)
            for i in xrange(data.shape[0]):
                one_hot[i, data[i] -1] = 1.
            return one_hot

class SVHN_Light(dense_design_matrix.DenseDesignMatrix):

    mapper = {'train': 0, 'test': 1, 'valid' : 2}
    def __init__(self, which_set, center = False, scale = False, start = None,
            stop = None, one_hot = False, axes=('b', 0, 1, 'c')):
        """
        This class load data as numpy array on memory
        """

        assert which_set in self.mapper.keys()
        self.args = locals()

        path = preprocess('${PYLEARN2_DATA_PATH}/SVHN/format2/')
        data_x, data_y = self.load_data(which_set, path, one_hot)
        data_x = numpy.cast[config.floatX](data_x)
        data_x =  numpy.transpose(data_x, axes = [3, 2, 0 , 1])
        data_x = data_x.reshape((data_x.shape[0], 32 * 32 * 3))

        if one_hot:
            one_hot = numpy.zeros((data_y.shape[0], 10), dtype = config.floatX)
            for i in xrange(data_y.shape[0]):
                one_hot[i, data_y[i] -1] = 1.
            data_y = one_hot
        else:
            data_y = data_y.reshape(data_y.shape[0])


        if start is not None:
            assert start >= 0
            if stop is None:
                stop = -1
            else:
                assert stop > start
            data_x = data_x[start:stop,:]
            data_y = data_y[start:stop,:]


        # rescale or center if permitted
        if center and scale:
            data_x -= 127.5
            data_x /= 127.5
        elif center:
            data_x -= 127.5
        elif scale:
            data_x /= 255.


        view_converter = dense_design_matrix.DefaultViewConverter((32, 32, 3), axes)
        super(SVHN_Light, self).__init__(X = data_x, y = data_y, view_converter = view_converter)


    @staticmethod
    def load_data(which_set, path, one_hot = False, rng = None):

        if rng is None:
            rng = numpy.random.RandomState(322)

        path = preprocess('${PYLEARN2_DATA_PATH}/SVHN/format2/')
        if which_set == 'valid':
            # Load balanced number of samples of each class from the extra
            data = load(path + 'extra_32x32.mat')
            valid_index = []
            for i in xrange(1, 11):
                index = numpy.nonzero(data['y'] == i)[0]
                index.flags.writeable = 1
                rng.random.shuffle(index)
                valid_index.append(index[:600])

            valid_index = numpy.concatenate(valid_index)
            rng.random.shuffle(valid_index)
            data_x = data['X'][:,:,:,valid_index]
            data_y = data['y'][valid_index,:]
            del data
            gc.collect()

            return data_x, data_y
        else:
            data = load("{}{}_32x32.mat".format(path, which_set))
            return data['X'], data['y']


