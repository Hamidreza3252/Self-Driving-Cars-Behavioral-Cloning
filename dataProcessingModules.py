import keras
import numpy as np
import cv2
import time


class DataGenerator4Classification(keras.utils.Sequence):
    def __init__(self, list_ids, labels, batch_size=32, dim=(32, 32, 3), n_channels=1, n_classes=10, shuffle=True):
        """

        Initialization:

        :param list_ids:
        :param labels:
        :param batch_size:
        :param dim:
        :param n_channels:
        :param n_classes:
        :param shuffle:
        """

        self.dim = dim
        self.batch_size = batch_size
        self.labels = labels
        self.list_ids = list_ids
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.shuffle = shuffle
        self.on_epoch_end()

        self.indexes = None
        self.shuffle = True

    def __len__(self):

        """
        Denotes the number of batches per epoch

        :return:
        """

        return int(np.floor(len(self.list_ids) / self.batch_size))

    def __getitem__(self, index):
        """

        Generate one batch of data

        :param index:
        :return:
        """

        # Generate indexes of the batch
        from_index = index * self.batch_size
        to_index = min(from_index + self.batch_size, len(self.labels))
        indexes = self.indexes[from_index:to_index]
        # indexes = self.indexes[index * self.batch_size:(index + 1) * self.batch_size]

        # Find list of IDs
        list_ids_temp = [self.list_ids[k] for k in indexes]

        # Generate data
        x_data, y_data = self.__data_generation(list_ids_temp)

        return x_data, y_data

    def on_epoch_end(self):
        """

        Updates indexes after each epoch

        :return:
        """

        self.indexes = np.arange(len(self.list_ids))

        if (self.shuffle == True):
            np.random.shuffle(self.indexes)

    def __data_generation(self, list_ids_temp):
        """

        Generates data containing batch_size samples # x_data : (n_samples, *dim, n_channels)

        :param list_ids_temp:
        :return:
        """

        # Initialization
        x_data = np.empty((self.batch_size, *self.dim, self.n_channels))
        y_data = np.empty((self.batch_size), dtype=int)

        # Generate data
        for i, id in enumerate(list_ids_temp):
            # Store sample
            x_data[i, ] = np.load("data/" + id + ".npy")

            # Store class
            y_data[i] = self.labels[id]

        return x_data, keras.utils.to_categorical(y_data, num_classes=self.n_classes)


# class DataGenerator4Regression(keras.utils.Sequence):
class DataGenerator4Regression(keras.utils.Sequence):

    def __init__(self, list_ids, values, batch_size=32, dims=(32, 32, 3), n_channels=1, shuffle=True, rescale_zero_mean=False, augment_data=False):
        """

        Initialization:

        :param list_ids:
        :param values:
        :param batch_size:
        :param dims:
        :param n_channels:
        :param shuffle:
        :param augment_data
        """

        # super().__init__(self)

        self.indexes = None
        self.shuffle = True
        self.augment_data = augment_data

        self.dims = dims
        self.batch_size = batch_size
        self.values = values
        self.list_ids = list_ids
        self.n_channels = n_channels
        self.shuffle = shuffle
        self.rescale_zero_mean = rescale_zero_mean

        self.on_epoch_end()

    def __len__(self):

        """
        Denotes the number of batches per epoch

        :return:
        """

        return int(np.floor(len(self.list_ids) / self.batch_size))

    @staticmethod
    def preprocess_rescale_zero_mean(x):
        y = x / 127.5
        y -= 1.0

        return y

        # y = x / 255.0
        # y -= 0.5
        # y *= 2.0

        # return y

    def __getitem__(self, index):
        """

        Generate one batch of data

        :param index:
        :return:
        """

        # Generate indexes of the batch
        # from_index = index * self.batch_size
        # to_index = min(from_index + self.batch_size, len(self.values))
        # indexes = self.indexes[from_index:to_index]
        indexes = self.indexes[index * self.batch_size:(index + 1) * self.batch_size]

        # Find list of IDs
        list_ids_temp = [self.list_ids[k] for k in indexes]

        # print("indexes.size", indexes.size)
        # print("list_ids_temp", list_ids_temp)

        # Generate data
        x_data, y_data = self.__data_generation(list_ids_temp)

        return x_data, y_data

    def on_epoch_end(self):
        """

        Updates indexes after each epoch

        :return:
        """

        self.indexes = np.arange(len(self.list_ids))

        if (self.shuffle == True):
            np.random.shuffle(self.indexes)

        # print("slepping for 30 secs to cool down...")
        # time.sleep(1*1*30)

    def __data_generation(self, list_ids_temp):
        """

        Generates data containing batch_size samples # x_data : (n_samples, *dim, n_channels)

        :param list_ids_temp:
        :return:
        """

        # Initialization
        # x_data = np.empty((self.batch_size, *self.dims, self.n_channels))
        # y_data = np.empty((self.batch_size), dtype=float)

        # x_data = np.empty((len(list_ids_temp), *self.dims, self.n_channels))

        batch_length = len(list_ids_temp)

        if (self.augment_data):
            x_data = np.empty((2 * batch_length, *self.dims), dtype=np.uint8)
            y_data = np.empty((2 * batch_length), dtype=np.float32)
        else:
            x_data = np.empty((batch_length, *self.dims), dtype=np.uint8)
            y_data = np.empty((batch_length), dtype=np.float32)

        # print(x_data.shape)

        # Generate data
        for i, id in enumerate(list_ids_temp):
            # Store sample
            # x_data[i, ] = np.load("data/" + id + ".npy")

            # x_data[i, ] = cv2.imread(id)[:, :, :, np.newaxis]

            # print(id)

            x_data[i] = cv2.imread(id)  # [:, :, :]
            x_data[i] = cv2.cvtColor(x_data[i], cv2.COLOR_BGR2RGB)

            # print(id)
            # print(self.values)

            y_data[i] = self.values[id]

            if (self.augment_data):
                x_data[i + batch_length] = cv2.flip(x_data[i], 1)
                y_data[i + batch_length] = y_data[i] * -1.0

        if (self.rescale_zero_mean):
            scaled_x_data = DataGenerator4Regression.preprocess_rescale_zero_mean(x_data)

            return scaled_x_data, y_data
        else:
            return x_data, y_data
