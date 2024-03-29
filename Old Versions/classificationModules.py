import cv2
import numpy as np
import glob
from sklearn import preprocessing
import tensorflow as tf
import re
import os
from datetime import datetime
import sys
import shutil
from sklearn.preprocessing import LabelBinarizer
import matplotlib.pyplot as plt
import math
from sklearn import metrics


class Cnn:

    def __init__(self):
        # self.n_classes = 0

        self.label_names = {}
        self.label_ids = []
        self.lb = None

    def init_model(self, label_names, label_ids):
        # self.n_classes = len(label_names)
        # self.label_names = label_names[:]
        self.label_ids = label_ids[:]

        self.label_names = {}
        for label_name, label_id in zip(label_names, label_ids):
            self.label_names[label_id] = label_name

        self.lb = preprocessing.LabelBinarizer()
        self.lb.fit(range(0, len(label_ids)))

    def resize_img(file_name, new_file_name, new_size):
        img = cv2.imread(file_name)
        resized_img = cv2.resize(img, dsize=(54, 140), interpolation=cv2.INTER_CUBIC)

    def get_list_of_image_files(imgs_dir):
        # return glob.glob('SampleRaw/*.txt')
        # return glob.glob('SampleRaw/Lift A - CH12 Data - Breakdown/*.txt')
        return glob.glob(imgs_dir)

    @staticmethod
    def whiten_images_zca(raw_norm_images, processed_images, batch_size=1000, epsilon=0.1):
        print("- pre-processing raw images and applying ZCA to whiten them... started")

        original_image_shape = (raw_norm_images.shape[1], raw_norm_images.shape[2], raw_norm_images.shape[3])

        w_images = raw_norm_images.reshape(raw_norm_images.shape[0], raw_norm_images.shape[1] * raw_norm_images.shape[2] * raw_norm_images.shape[3])
        raw_norm_images_mean = w_images.mean(axis=0)

        for start in range(0, raw_norm_images.shape[0], batch_size):
            end = min(start + batch_size, raw_norm_images.shape[0])

            # working images, a temporary variable to process images
            w_images = raw_norm_images[start:end, :, :, :]
            w_images = w_images.reshape(w_images.shape[0], w_images.shape[1] * w_images.shape[2] * w_images.shape[3])

            # print(w_images.shape)
            # print(w_images.mean(axis=0).shape)

            # w_images = w_images - w_images.mean(axis=0)
            w_images = w_images - raw_norm_images_mean
            # print(w_images.mean(axis=0))

            w_images_cov = np.cov(w_images, rowvar=True)
            w_images_cov_u, w_images_cov_s, w_images_cov_v = np.linalg.svd(w_images_cov)
            # print(w_images_cov_u.shape, w_images_cov_s.shape)

            w_images_zca = w_images_cov_u.dot(np.diag(1.0 / np.sqrt(w_images_cov_s + epsilon))).dot(w_images_cov_u.T).dot(w_images)
            processed_images[start:end, :, :, :] = np.reshape(Cnn.rescale_zca(w_images_zca), (w_images_zca.shape[0], original_image_shape[0],
                                                                                              original_image_shape[1], original_image_shape[2]))

            print("  in progress... {0:>0.0f}% ".format(start * 100 / raw_norm_images.shape[0], ""), end="\r")

        print("  completed! {0:>10}".format(""))

    @staticmethod
    def whiten_images_self_mean(in_norm_images, batch_size=1000, width_offset=0, height_offset=0, epsilon=0.0, verbose=True):

        if(verbose):
            print("- pre-processing raw images and applying self-mean correction to whiten them... started")

        original_image_shape = (in_norm_images.shape[1], in_norm_images.shape[2], in_norm_images.shape[3])
        processed_images = np.zeros_like(in_norm_images).astype(np.uint8)

        for start in range(0, in_norm_images.shape[0], batch_size):
            end = min(start + batch_size, in_norm_images.shape[0])

            w_images = in_norm_images[start:end]
            w_images_cropped = np.zeros_like(w_images)
            w_images_cropped[:, height_offset:original_image_shape[0]-height_offset, width_offset:original_image_shape[1]-width_offset, :] = \
                w_images[:, height_offset:original_image_shape[0]-height_offset, width_offset:original_image_shape[1]-width_offset, :]

            w_images_cropped = np.reshape(w_images_cropped,
                                          (end-start, original_image_shape[0] * original_image_shape[1] * original_image_shape[2]))

            if(epsilon != 0.0):
                # noise_matrices = np.random.uniform(low=0.0, high=0.1, size=(end-start, original_image_shape[0] * original_image_shape[1] * original_image_shape[2])) * epsilon
                w_images_cropped += np.random.uniform(low=0.0, high=1.0, size=(end-start, original_image_shape[0] * original_image_shape[1] * original_image_shape[2])) * epsilon

            processed_w_images = Cnn.standardize(w_images_cropped)

            image_data_mins = processed_w_images.min(axis=1)[:, None].astype(float)
            image_data_maxs = processed_w_images.max(axis=1)[:, None].astype(float)

            output_range_max = 1.0
            output_range_min = 0.0

            image_data_range_diffs = image_data_maxs - image_data_mins
            processed_w_images = np.clip((((processed_w_images - image_data_mins) * output_range_max / image_data_range_diffs + output_range_min)), 0.0, 1.0)

            # print(normalized_image_data.shape)
            # print(normalized_image_data.min(axis=1))
            # print(normalized_image_data.max(axis=1))

            # original_images = x_train_raw_data[start_index:end_index]

            processed_images[start:end, :, :, :] = np.reshape((processed_w_images * 255).astype(np.uint8),
                                                              (end-start, original_image_shape[0], original_image_shape[1], original_image_shape[2]))

            if(verbose):
                print("  in progress... {0:>0.0f}% ".format(start * 100 / in_norm_images.shape[0], ""), end="\r")

        if (verbose):
            print("  completed! {0:>10}".format(""))

        return processed_images

    @staticmethod
    def augment_data(in_norm_images, in_label_ids, epsilon=0.1):
        '''

        :param in_norm_images: normalized features, 0.0 ... 1.0
        :param in_label_ids:
        :param epsilon:
        :return: out_norm_images, out_label_ids, features_counts
        '''

        unique_label_ids = np.unique(in_label_ids)
        # original_image_shape = (in_norm_images.shape[1], in_norm_images.shape[2], in_norm_images.shape[3])

        features_counts = np.asanyarray([(np.where(in_label_ids == label_id))[0].size for label_id in unique_label_ids])
        # print("features count before augmentation:", features_counts)
        min_features_counts = min(features_counts)
        # max_features_counts = max(features_counts)

        # features_counts = max_features_counts - features_counts

        total_augmented_features = None
        total_augmented_label_ids = None

        # batch_size = 1000

        # augmented_features = np.zeros((min_features_counts, in_norm_images.shape[1], in_norm_images.shape[2], in_norm_images.shape[3])).astype(np.uint8)

        for i_label, label_id in enumerate(unique_label_ids):
            # feature_count = features_counts[i_label]

            index_locators = (in_label_ids == label_id)
            augmented_labels = np.ones(min_features_counts) * label_id
            augmented_features = in_norm_images[index_locators, :, :, :][:min_features_counts]

            augmented_features += np.random.uniform(low=0.0, high=1.0, size=(augmented_features.shape[0], augmented_features.shape[1],
                                                                             augmented_features.shape[2], augmented_features.shape[3])) * epsilon

            augmented_features = np.clip(augmented_features, 0.0, 1.0)

            if (total_augmented_features is None):
                total_augmented_features = augmented_features
            else:
                total_augmented_features = np.append(total_augmented_features, augmented_features, axis=0)

            if (total_augmented_label_ids is None):
                total_augmented_label_ids = augmented_labels
            else:
                total_augmented_label_ids = np.append(total_augmented_label_ids, augmented_labels, axis=0)

        # augmented_norm_features = Cnn.normalize(total_augmented_features, approach="scale")

        # out_norm_images = np.append(in_norm_images, augmented_norm_features, axis=0)

        out_norm_images = np.append(in_norm_images, total_augmented_features, axis=0)
        out_label_ids = np.append(in_label_ids, total_augmented_label_ids, axis=0)

        features_counts = [(np.where(out_label_ids == label_id))[0].size for label_id in unique_label_ids]
        # print("features count after augmentation:", features_counts)

        arg_sort_indices = np.argsort(out_label_ids)
        out_norm_images = out_norm_images[arg_sort_indices]
        out_label_ids = out_label_ids[arg_sort_indices]

        return (out_norm_images, out_label_ids, features_counts)

    @staticmethod
    def center(in_vectors):
        out_vectors = in_vectors - np.mean(in_vectors, axis=1)[:, None].astype(float)
        return out_vectors

    @staticmethod
    def standardize(in_vectors):
        out_vectors = Cnn.center(in_vectors) / np.std(in_vectors, axis=1)[:, None].astype(float)
        return out_vectors

    @staticmethod
    def get_features_of_types(in_features, in_label_ids, filter_label_ids):
        # unique_label_ids = np.unique(in_label_ids)

        out_features = np.empty((1, in_features.shape[1], in_features.shape[2], in_features.shape[3]))
        # out_features = np.array([])
        out_label_ids = np.array([])

        for i_label, label_id in enumerate(filter_label_ids):
            # feature_count = features_counts[i_label]

            index_locators = (in_label_ids == label_id)

            out_label_ids = np.append(out_label_ids, in_label_ids[index_locators])
            out_features = np.append(out_features, in_features[index_locators, :, :, :], axis=0)

        out_features = out_features[1:]
        features_counts = np.asanyarray([(np.where(out_label_ids == label_id))[0].size for label_id in filter_label_ids])

        return (out_features, out_label_ids, features_counts)

    @staticmethod
    def select_equally_sized_data_sets(in_features, in_label_ids, n_classes, unique_label_ids, features_counts):
        if (unique_label_ids is None):
            unique_label_ids = np.unique(in_label_ids)

        if(features_counts is None):
            features_counts = [(np.where(in_label_ids == label_id))[0].size for label_id in unique_label_ids]

        new_feature_count = np.min(features_counts)
        selected_features = np.zeros((new_feature_count * n_classes,
                                      in_features.shape[1], in_features.shape[2], in_features.shape[3]))
        selected_labels = np.zeros((new_feature_count * n_classes))

        from_feature_count = 0

        for i_label, label_id in enumerate(unique_label_ids):
            to_feature_count = from_feature_count + new_feature_count

            selected_features[i_label * new_feature_count:(i_label + 1) * new_feature_count, :, :, :] = \
                in_features[from_feature_count:to_feature_count, :, :, :]

            selected_labels[i_label * new_feature_count:(i_label + 1) * new_feature_count] = \
                in_label_ids[from_feature_count:to_feature_count]

            from_feature_count += features_counts[i_label]

        new_features_counts = [(np.where(selected_labels == label_id))[0].size for label_id in unique_label_ids]

        return (selected_features, selected_labels, new_features_counts)

    @staticmethod
    def output_feature_map(tf_image_input, tf_input_ph, tf_activation, tf_session, activation_min=-1, activation_max=-1, plt_num=1):
        """
        :param tf_image_input: the test image being fed into the network to produce the feature maps
        :param tf_input_ph: tensorflow place-holder for CNN layer to fed into
        :param tf_activation: should be a tf variable name used during your training procedure that represents
            the calculated state of a specific weight layer
        :param activation_min / max: can be used to view the activation contrast in more detail,
            by default matplot sets min and max to the actual min and max values of the output
        :param plt_num: used to plot out multiple different weight feature map sets on the same block,
            just extend the plt number for each new feature map entry
        """
        # Here make sure to preprocess your image_input in a way your network expects
        # with size, normalization, ect if needed
        # image_input =
        # Note: x should be the same name as your network's tensorflow data placeholder variable
        # If you get an error tf_activation is not defined it may be having trouble accessing the variable from inside a function

        activation = tf_activation.eval(session=tf_session, feed_dict={tf_input_ph: tf_image_input})
        featuremaps = activation.shape[3]
        plt.figure(plt_num, figsize=(10, 10))

        for featuremap in range(featuremaps):
            plt.subplot(6, 8, featuremap + 1)  # sets the number of feature maps to show on each row and column
            plt.title('FeatureMap ' + str(featuremap), fontsize=5)  # displays the feature map number
            if activation_min != -1 & activation_max != -1:
                plt.imshow(activation[0, :, :, featuremap], interpolation="nearest", vmin=activation_min, vmax=activation_max, cmap="gray")
            elif activation_max != -1:
                plt.imshow(activation[0, :, :, featuremap], interpolation="nearest", vmax=activation_max, cmap="gray")
            elif activation_min != -1:
                plt.imshow(activation[0, :, :, featuremap], interpolation="nearest", vmin=activation_min, cmap="gray")
            else:
                plt.imshow(activation[0, :, :, featuremap], interpolation="nearest", cmap="gray")

    @staticmethod
    def read_and_resize_images(file_count=-1, skip_file_count=0, images_dir="", specific_file_name="", target_img_size=128, keep_aspect_ratio=True, **kwargs):
        """Read the raw data in a file or all files in the raw data directory and estimate velocity, considering all missing data

        returns:
            a list containing all image objects created
        """

        images = []

        if (file_count == 0):
            return images

        if (specific_file_name == ""):
            list_of_image_files = CnnModules.get_list_of_image_files(images_dir + "*.jpg")
            # list_of_image_files = sorted(list_of_image_files,
            #                            key=lambda x: Lift_Utils.extract_lift_name_and_timestamp(x)[1])

            # list_of_image_files = [x for x in list_of_image_files if x != ""]
        else:
            list_of_image_files = [specific_file_name]

        save_resized_iamges = kwargs["save_resized_iamges"] if("save_resized_iamges" in kwargs) else False
        resized_iamges_dir = kwargs["resized_iamges_dir"] if(save_resized_iamges) else ""

        # print("Reading {} image files...".format(len(list_of_image_files) if (file_count < 0) else min(len(list_of_image_files), file_count)))

        if (file_count != -1):
            file_count += skip_file_count

        for i, file_name in enumerate(list_of_image_files[skip_file_count:], start=skip_file_count):
            # file_name = 'SampleRaw\CH11-(2018, 7, 19, 4, 8, 43, 44, 196).txt'

            # if(i < 5 or i > 5):
            #    continue

            directory, file_name_only = os.path.split(file_name)
            file_name_only = file_name_only[:-4]

            # print("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -")
            # print("{}) {}".format(i, file_name))

            try:
                img = cv2.imread(file_name)

                if(keep_aspect_ratio):
                    img_dimensions = np.asarray(img.shape[:2])

                    target_img_dimensions = np.asarray([target_img_size, target_img_size])
                    img_resize_ratios = target_img_dimensions / img_dimensions
                    min_img_ratio = min(np.min(img_resize_ratios), 1.0)

                    new_img = np.zeros(shape=(target_img_size, target_img_size, 3))

                    # if(np.any(img_resize_ratios < 1.0)):
                    resized_img_dimensions = (img_dimensions * min_img_ratio + 0.5).astype(int)

                    resized_img = cv2.resize(img, dsize=(resized_img_dimensions[1], resized_img_dimensions[0]), interpolation=cv2.INTER_CUBIC)
                    width_gap = int((target_img_size - resized_img_dimensions[0]) // 2.0)
                    height_gap = int((target_img_size - resized_img_dimensions[1]) // 2.0)
                    new_img[width_gap:width_gap + resized_img_dimensions[0], height_gap:height_gap + resized_img_dimensions[1]] = resized_img
                else:
                    new_img = cv2.resize(img, dsize=(target_img_size, target_img_size), interpolation=cv2.INTER_CUBIC)

                if(save_resized_iamges):
                    if(resized_iamges_dir != ""):
                        directory = resized_iamges_dir

                    resized_file_name = directory + file_name_only + "-resized.jpg"
                    cv2.imwrite(resized_file_name, new_img)

                images.append(new_img)
            except Exception as exception:
                print("An error occurred while processing image file {0:} and it was ignored.".format(file_name))

            if (i == file_count - 1):
                break

        return images

    #@staticmethod
    def display_images(self, features, encoded_label_ids, normalized=True):

        max_count = 50

        assert (len(features) == len(encoded_label_ids)), "len(features) <> len(labels)"
        assert (len(features) < max_count and len(encoded_label_ids) < max_count), "len of features must be < {0:d}".format(max_count)

        label_ids = self.lb.inverse_transform(np.asanyarray(encoded_label_ids))

        # label_binarizer = LabelBinarizer()
        # label_binarizer.fit(range(self.n_classes))
        # label_ids = label_binarizer.inverse_transform(np.array(labels))

        # print("Label IDs:", label_ids)whiten_images

        fig, axes = plt.subplots(nrows=len(features), ncols=1)
        fig.set_figheight(5 + len(features))
        fig.set_figwidth(10)
        fig.tight_layout()
        fig.suptitle("Display sample images", fontsize=10, y=1.02)

        for image_i, (feature, label_id) in enumerate(zip(features, label_ids)):
            label_name = self.label_names[label_id]
            axis = axes[image_i]

            # rectified_feature = (feature * 255.0).astype(int)

            if(normalized):
                axis.imshow((feature * 255).astype(np.uint8))
            else:
                axis.imshow(feature)

            axis.set_title(str(image_i) + ": " + label_name)
            axis.set_axis_off()

    @staticmethod
    def batch_features_labels(features, labels, batch_size):
        """
        Split features and labels into batches
        """

        for start in range(0, len(features), batch_size):
            end = min(start + batch_size, len(features))
            yield np.asarray(features[start:end]), np.asarray(labels[start:end])

    @staticmethod
    def normalize(x, output_range_min=0.0, output_range_max=1.0, image_data_min=0.0, image_data_max=255.0, approach="scale"):
        """
        Normalize a list of sample image data in the range of 0 to 1
        : x: List of image data.  The image shape is (32, 32, 3)
        : return: Numpy array of normalize data
        """

        output_range_diff = output_range_max - output_range_min

        if(approach == "scale"):
            image_data_range_diff = image_data_max - image_data_min
            offset = 0
        elif(approach == "offset-scale"):
            image_data_range_diff = (image_data_max - image_data_min) // 2
            offset = (image_data_max + image_data_min) // 2
        else:
            raise Exception("Approach is wrong or missing")

        # print("image_data_range_diff", image_data_range_diff)
        # print("offset", offset)

        normalized_image_data = output_range_min + (x - image_data_min - offset) * output_range_diff / image_data_range_diff

        return normalized_image_data

    @staticmethod
    def denormalize(x, approach="scale"):
        """
        Normalize a list of sample image data in the range of 0 to 1
        : x: List of image data.  The image shape is (32, 32, 3)
        : return: Numpy array of normalize data
        """

        if(approach == "scale"):
            return (x * 255).astype(np.uint8)
        elif(approach == "offset-scale"):
            return (x * 127 + 127).astype(np.uint8)
        else:
            raise Exception("Approach is wrong or missing")

        return None

    @staticmethod
    def rescale_zca(x_zca):
        batches_min_values = np.min(x_zca, axis=1)[:, None].astype(float)
        batches_max_values = np.max(x_zca, axis=1)[:, None].astype(float)

        return ((x_zca - batches_min_values) / (batches_max_values - batches_min_values) * 255).astype(np.uint8)

    def one_hot_encode(self, x):
        """
        One hot encode a list of sample labels. Return a one-hot encoded vector for each label.
        : x: List of sample Labels
        : return: Numpy array of one-hot encoded labels
        """

        return self.lb.transform(x)

    @staticmethod
    def one_hot_encode_2d(x, label_binarizer):
        """
        One hot encode a list of sample labels. Return a one-hot encoded vector for each label.
        : x: List of sample Labels
        : return: Numpy array of one-hot encoded labels
        """

        return np.asarray([[1, 0] if(x_i == 0) else [0, 1] for x_i in x])

    @staticmethod
    def neural_net_image_input(image_shape):
        """
        Return a Tensor for a batch of image input
        : image_shape: Shape of the images
        : return: Tensor for image input.
        """
        x = tf.placeholder(dtype=tf.float32, shape=[None, image_shape[0], image_shape[1], image_shape[2]], name="x")

        return x

    @staticmethod
    def neural_net_label_input(n_classes):
        """
        Return a Tensor for a batch of label input
        : n_classes: Number of classes
        : return: Tensor for label input.
        """
        y = tf.placeholder(dtype=tf.float32, shape=[None, n_classes], name="y")

        return y

    @staticmethod
    def neural_net_keep_prob_input():
        """
        Return a Tensor for keep probability
        : return: Tensor for keep probability.
        """

        keep_prob = tf.placeholder(dtype=tf.float32, name="keep_prob")

        return keep_prob

    @staticmethod
    def conv2d_maxpool(x_tensor, conv_num_outputs, conv_ksize, conv_strides, pool_ksize, pool_strides, wieghts_name="", layer_name="",
                       batch_normalizer=None):
        """
        Apply convolution then max pooling to x_tensor
        :param x_tensor: TensorFlow Tensor
        :param conv_num_outputs: Number of outputs for the convolutional layer
        :param conv_ksize: kernal size 2-D Tuple for the convolutional layer
        :param conv_strides: Stride 2-D Tuple for convolution
        :param pool_ksize: kernal size 2-D Tuple for pool
        :param pool_strides: Stride 2-D Tuple for pool
        : return: A tensor that represents convolution and max pooling of x_tensor
        """

        # conv_layer = tf.nn.conv2d(input, weight, strides, padding)

        print("conv2d_maxpool... Start")
        print("Checking inputs dimensions...")
        print("conv_ksize:", conv_ksize)
        print("conv_num_outputs:", conv_num_outputs)
        # print(x_tensor)

        input_depth = x_tensor.get_shape().as_list()[3]

        # weight = tf.Variable(tf.truncated_normal([filter_size_height, filter_size_width, color_channels, k_output]))
        # bias = tf.Variable(tf.zeros(k_output))
        # [batch, height, width, channels]

        # truncated_normal(shape, mean=0.0, stddev=1.0, dtype=tf.float32, seed=None, name=None)

        weights = tf.Variable(tf.truncated_normal(shape=[conv_ksize[0], conv_ksize[1], input_depth, conv_num_outputs], mean=0.0, stddev=0.05), name=wieghts_name)
        biases = tf.Variable(tf.zeros(conv_num_outputs))
        conv_strides = (1, conv_strides[0], conv_strides[1], 1)
        pool_ksize = (1, pool_ksize[0], pool_ksize[1], 1)
        pool_strides = (1, pool_strides[0], pool_strides[1], 1)

        print("Checking strides dimensions...")
        print("conv_strides:", conv_strides)
        print("pool_ksize:", pool_ksize)
        print("pool_strides", pool_strides)

        conv_layer = tf.nn.conv2d(x_tensor, weights, conv_strides, "VALID") + biases

        # conv_layer = tf.nn.bias_add(conv_layer, biases, name=layer_name)

        if(batch_normalizer):
            print("batch_normalizer:", batch_normalizer)

            conv_layer = batch_normalizer(conv_layer)

        conv_layer = tf.nn.relu(conv_layer)
        # conv_layer = tf.nn.tanh(conv_layer)
        # conv_layer = tf.nn.leaky_relu(conv_layer)
        conv_layer = tf.nn.max_pool(conv_layer, ksize=pool_ksize, strides=pool_strides, padding="VALID", name=layer_name)

        # H1: conv_layer = tf.nn.max_pool(conv_layer, ksize=pool_ksize, strides=pool_strides, padding='SAME')

        print("conv_layer:", conv_layer.shape)
        print("conv2d_maxpool... End")
        print("")

        return conv_layer

    @staticmethod
    def conv2d_avg_pool(x_tensor, conv_num_outputs, conv_ksize, conv_strides, pool_ksize, pool_strides):
        """
        Apply convolution then max pooling to x_tensor
        :param x_tensor: TensorFlow Tensor
        :param conv_num_outputs: Number of outputs for the convolutional layer
        :param conv_ksize: kernal size 2-D Tuple for the convolutional layer
        :param conv_strides: Stride 2-D Tuple for convolution
        :param pool_ksize: kernal size 2-D Tuple for pool
        :param pool_strides: Stride 2-D Tuple for pool
        : return: A tensor that represents convolution and max pooling of x_tensor
        """

        # conv_layer = tf.nn.conv2d(input, weight, strides, padding)

        print("conv2d_avg_pool... Start")
        print("Cheking inputs dimensions... ")
        print('conv_ksize: ', conv_ksize)
        print('conv_num_outputs: ', conv_num_outputs)
        # print(x_tensor)

        input_depth = x_tensor.get_shape().as_list()[3]

        # weight = tf.Variable(tf.truncated_normal([filter_size_height, filter_size_width, color_channels, k_output]))
        # bias = tf.Variable(tf.zeros(k_output))
        # [batch, height, width, channels]

        """
        truncated_normal(
        shape,
        mean=0.0,
        stddev=1.0,
        dtype=tf.float32,
        seed=None,
        name=None
        )
        """

        weights = tf.Variable(tf.truncated_normal(shape=[conv_ksize[0], conv_ksize[1], input_depth, conv_num_outputs], mean=0.0, stddev=0.05))
        biases = tf.Variable(tf.zeros(conv_num_outputs))
        conv_strides = (1, conv_strides[0], conv_strides[1], 1)
        pool_ksize = (1, pool_ksize[0], pool_ksize[1], 1)
        pool_strides = (1, pool_strides[0], pool_strides[1], 1)

        print("Cheking strides dimensions... ")
        print('conv_strides: ', conv_strides)
        print('pool_ksize: ', pool_ksize)
        print('pool_strides', pool_strides)

        conv_layer = tf.nn.conv2d(x_tensor, weights, conv_strides, "SAME")
        conv_layer = tf.nn.bias_add(conv_layer, biases)
        conv_layer = tf.nn.avg_pool(conv_layer, ksize=pool_ksize, strides=pool_strides, padding="SAME")
        conv_layer = tf.nn.relu(conv_layer)

        # H1: conv_layer = tf.nn.max_pool(conv_layer, ksize=pool_ksize, strides=pool_strides, padding='SAME')

        print("conv2d_avg_pool... End")
        print("")
        return conv_layer

    @staticmethod
    def flatten(x_tensor):
        """
        Flatten x_tensor to (Batch Size, Flattened Image Size)
        : x_tensor: A tensor of size (Batch Size, ...), where ... are the image dimensions.
        : return: A tensor of size (Batch Size, Flattened Image Size).
        """

        # print(x_tensor)

        output_tensor = tf.contrib.layers.flatten(x_tensor)

        # print(output_tensor)

        return output_tensor

    @staticmethod
    def fully_conn(x_tensor, num_outputs):
        """
        Apply a fully connected layer to x_tensor using weight and bias
        : x_tensor: A 2-D tensor where the first dimension is batch size.
        : num_outputs: The number of output that the new tensor should be.
        : return: A 2-D tensor where the second dimension is num_outputs.
        """

        """
        fully_connected(
        inputs,
        num_outputs,
        activation_fn=tf.nn.relu,
        normalizer_fn=None,
        normalizer_params=None,
        weights_initializer=initializers.xavier_initializer(),
        weights_regularizer=None,
        biases_initializer=tf.zeros_initializer(),
        biases_regularizer=None,
        reuse=None,
        variables_collections=None,
        outputs_collections=None,
        trainable=True,
        scope=None
        )
        """

        output_tensor = tf.contrib.layers.fully_connected(x_tensor, num_outputs, activation_fn=tf.nn.relu)

        return output_tensor

    @staticmethod
    def output(x_tensor, num_outputs):
        """
        Apply a output layer to x_tensor using weight and bias
        : x_tensor: A 2-D tensor where the first dimension is batch size.
        : num_outputs: The number of output that the new tensor should be.
        : return: A 2-D tensor where the second dimension is num_outputs.
        """

        output_tensor = tf.contrib.layers.fully_connected(x_tensor, num_outputs, activation_fn=None)
        # output_tensor = tf.contrib.layers.fully_connected(x_tensor, num_outputs, activation_fn=tf.nn.sigmoid)

        return output_tensor

    @staticmethod
    def train_neural_network(session, x_tf_ph, y_tf_ph, keep_prob_tf_ph, optimizer, keep_probability, feature_batch, label_batch):
        """
        Optimize the session on a batch of images and labels
        : session: Current TensorFlow session
        : optimizer: TensorFlow optimizer function
        : keep_probability: keep probability
        : feature_batch: Batch of Numpy image data
        : label_batch: Batch of Numpy label data
        """
        # batch_size.shape  ->  (128, 32, 32, 3)
        # label_batch.shape  ->  (128, 10)

        session.run(optimizer, feed_dict={x_tf_ph: feature_batch, y_tf_ph: label_batch, keep_prob_tf_ph: keep_probability})

    @staticmethod
    def print_stats(session, x_tf_ph, y_tf_ph, keep_prob_tf_ph, feature_batch, label_batch, val_images, val_labels, cost, accuracy, prefix_text=""):
        """
        Print information about loss and validation accuracy
        : session: Current TensorFlow session
        : feature_batch: Batch of Numpy image data
        : label_batch: Batch of Numpy label data
        : cost: TensorFlow cost function
        : accuracy: TensorFlow accuracy function
        """

        # print(cost)
        # print(accuracy)

        # correct_prediction = tf.equal(tf.argmax(valid_labels, 1), tf.argmax(label_batch, 1))

        test_cost = session.run(cost, feed_dict={x_tf_ph: feature_batch, y_tf_ph: label_batch, keep_prob_tf_ph: 1.0})
        valid_accuracy = session.run(accuracy, feed_dict={x_tf_ph: val_images, y_tf_ph: val_labels, keep_prob_tf_ph: 1.0})

        print(prefix_text + "Test Cost: {0:0.4f}   ---   Valid Accuracy: {1:0.4f}".format(test_cost, valid_accuracy), end="\r")

        return (test_cost, valid_accuracy)
        # print('Test Accuracy: {}'.format(test_accuracy))

    @staticmethod
    def _load_label_names():
        """
        Load the label names from file
        """
        raise NotImplementedError("deprecated method")

    def display_image_predictions(self, features, encoded_label_ids, predicted_label_ids, max_top_count=0):

        # self.label_names = {}

        label_ids = self.lb.inverse_transform(np.asanyarray(encoded_label_ids))

        fig, axes = plt.subplots(nrows=len(features), ncols=2)
        fig.set_figheight(15)
        fig.set_figwidth(18)
        fig.tight_layout()
        fig.suptitle("Top Softmax Predictions", fontsize=20, y=1.1)

        # max_label_count = min(pred_indicies.size, max_top_count)

        n_classes = min(len(self.label_names), max_top_count)
        margin = 0.05
        ind = np.arange(n_classes)
        width = (1. - 2. * margin) / n_classes

        for image_i, (feature, label_id, pred_indicies, pred_values) in enumerate(zip(features, label_ids, predicted_label_ids.indices, predicted_label_ids.values)):
            pred_label_names = [self.label_names[pred_i] for pred_i in pred_indicies]
            pred_label_name = pred_label_names[np.argmax(pred_values)]

            label_name = self.label_names[label_id]

            # rectified_feature = (feature * 255.0).astype(int)

            axis = axes[image_i]

            axis[0].imshow((feature * 255).astype(np.uint8))
            # axes[0].imshow((feature * 127 + 127).astype(np.uint8))
            axis[0].set_title(label_name)
            axis[0].set_axis_off()

            axis[1].barh(ind + margin, pred_values[::-1][-n_classes:], width)
            axis[1].set_yticks(ind + margin)
            axis[1].set_yticklabels(pred_label_names[:n_classes][::-1])
            # axis[1].set_yticklabels(pred_label_name)
            axis[1].set_title("predicted: " + pred_label_name)
            axis[1].set_xticks([0, 0.5, 1.0])

            # print(pred_label_names[:max_label_count][::-1])

        # return pred_values, pred_label_names

    @staticmethod
    def evaluate_roc_curve(test_labels, predicted_y_probabilities):

        fpr, tpr, _ = metrics.roc_curve(test_labels, predicted_y_probabilities)
        auc = metrics.roc_auc_score(test_labels, predicted_y_probabilities)

        return fpr, tpr, auc

    @staticmethod
    def plot_roc_curve(test_labels, predicted_y_probabilities, **kwargs):

        title = kwargs["title"] if("title" in kwargs) else ""
        legend_title = kwargs["legend_title"] if("legend_title" in kwargs) else "data-1, auc"

        fpr, tpr, _ = metrics.roc_curve(test_labels, predicted_y_probabilities)
        auc = metrics.roc_auc_score(test_labels, predicted_y_probabilities)

        fig, axis = plt.subplots()

        axis.plot(fpr, tpr, label=legend_title + "={0:0.5f}".format(auc))
        axis.legend(loc=4, fontsize="x-large")
        axis.set_title(title, fontsize="x-large")

        gridlines = axis.get_xgridlines() + axis.get_ygridlines()
        ticklabels = axis.get_xticklabels() + axis.get_yticklabels()

        for line in gridlines:
            line.set_linestyle("-.")

        for label in ticklabels:
            label.set_color("b")
            label.set_fontsize(13)

        axis.set_xlabel("FPR", fontsize="x-large")
        axis.set_ylabel("TPR", fontsize="x-large")

        axis.grid(b=True, which="both", alpha=1.0)

        fig.set_figheight(6)
        fig.set_figwidth(10)
        fig.tight_layout()

        plt.show()

        return fpr, tpr, auc

    @staticmethod
    def plot_evaluated_roc_curves(fprs, tprs, acus, legend_titles, **kwargs):

        title = kwargs["title"] if("title" in kwargs) else ""

        if(len(legend_titles) != len(fprs)):
            raise Exception("list lengths mismatch")

        fig, axis = plt.subplots()

        for i, fpr, tpr, auc, legend_title in zip(range(len(fprs)), fprs, tprs, acus, legend_titles):
            axis.plot(fpr, tpr, label=legend_title + "={0:0.5f}".format(auc))
            axis.legend(loc=4, fontsize="x-large")

        axis.set_title(title, fontsize="x-large")

        gridlines = axis.get_xgridlines() + axis.get_ygridlines()
        ticklabels = axis.get_xticklabels() + axis.get_yticklabels()

        for line in gridlines:
            line.set_linestyle('-.')

        for label in ticklabels:
            label.set_color("b")
            label.set_fontsize(13)

        axis.grid(b=True, which="both", alpha=1.0)

        fig.set_figheight(6)
        fig.set_figwidth(10)
        fig.tight_layout()

        plt.show()

    @staticmethod
    def get_activations(sess, image_in_tf, keep_prob_tf, layer, stimuli):
        # units = sess.run(layer, feed_dict={image_in_tf:np.reshape(stimuli, [1, -1], order="F"), keep_prob_tf:1.0})
        units = sess.run(layer, feed_dict={image_in_tf: np.reshape(stimuli, [-1, stimuli.shape[0], stimuli.shape[1], stimuli.shape[2]]), keep_prob_tf: 1.0})
        # units = sess.run(layer, feed_dict={image_in_tf:stimuli, keep_prob_tf:1.0})
        # print(units.shape)
        return units

    @staticmethod
    def plot_nn_filter(units, n_columns):
        filter_count = units.shape[3]
        plt.figure(1, figsize=(20, 20))
        # n_columns = 8
        n_rows = math.ceil(filter_count / n_columns) + 1

        for i in range(filter_count):
            axis = plt.subplot(n_rows, n_columns, i + 1)

            plt.title("Filter " + str(i + 1))
            plt.imshow(units[0, :, :, i], interpolation="nearest", cmap="gray")

            axis.set_axis_off()

    @staticmethod
    def load_preprocess_training_batch(batch_id, batch_size):
        """
        Load the Preprocessed Training data and return them in batches of <batch_size> or less
        """
        filename = 'preprocess_batch_' + str(batch_id) + '.p'
        features, labels = pickle.load(open(filename, mode='rb'))

        # Return the training data in batches of size <batch_size> or less
        return Cnn.batch_features_labels(features, labels, batch_size)

    @staticmethod
    def plot_flattened_image(X):
        X = (X * 255).astype(np.uint8)

        plt.figure(figsize=(1.5, 1.5))
        plt.imshow(X.reshape(32, 32, 3))
        plt.show()
        plt.close()

