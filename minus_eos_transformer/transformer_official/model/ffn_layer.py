# Copyright 2018 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Implementation of fully connected network."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf

from tcn.nn import CausalConv1D


class FeedFowardNetwork(tf.layers.Layer):
    """Fully connected feedforward network."""

    def __init__(self,
                 hidden_size,
                 filter_size,
                 relu_dropout,
                 train,
                 allow_pad,
                 use_conv=False,
                 bidirection=False):
        super(FeedFowardNetwork, self).__init__()
        self.hidden_size = hidden_size
        self.filter_size = filter_size
        self.relu_dropout = relu_dropout
        self.train = train
        self.allow_pad = allow_pad
        self.use_conv = use_conv
        self.bidirection = bidirection

        self.filter_dense_layer = tf.layers.Dense(
            filter_size,
            use_bias=True,
            activation=tf.nn.relu,
            name="filter_layer")
        self.output_dense_layer = tf.layers.Dense(
            hidden_size, use_bias=True, name="output_layer")
        if self.use_conv:
            self.conv_layers = []
            for i in range(2):
                self.conv_layers.append(
                    CausalConv1D(
                        hidden_size,
                        3,
                        1,
                        use_bias=True,
                        activation=tf.nn.relu,
                        name='conv{}'.format(i + 1)))

        if self.bidirection:
            self.reverse_conv_layers = []
            for i in range(2):
                self.reverse_conv_layers.append(
                    CausalConv1D(
                        hidden_size,
                        3,
                        1,
                        activation=tf.nn.relu,
                        name='reverse_conv{}'.format(i + 1)))

    def call(self, x, padding=None):
        """Return outputs of the feedforward network.

    Args:
      x: tensor with shape [batch_size, length, hidden_size]
      padding: (optional) If set, the padding values are temporarily removed
        from x (provided self.allow_pad is set). The padding values are placed
        back in the output tensor in the same locations.
        shape [batch_size, length]

    Returns:
      Output of the feedforward network.
      tensor with shape [batch_size, length, hidden_size]
    """
        padding = None if not self.allow_pad else padding

        # Retrieve dynamically known shapes
        batch_size = tf.shape(x)[0]
        length = tf.shape(x)[1]

        # if padding is not None:
            # with tf.name_scope("remove_padding"):
                # # Flatten padding to [batch_size*length]
                # pad_mask = tf.reshape(padding, [-1])

                # nonpad_ids = tf.to_int32(tf.where(pad_mask < 1e-9))

                # # Reshape x to [batch_size*length, hidden_size] to remove padding
                # x = tf.reshape(x, [-1, self.hidden_size])
                # x = tf.gather_nd(x, indices=nonpad_ids)

                # # Reshape x from 2 dimensions to 3 dimensions.
                # x = tf.reshape(x, tf.stack([batch_size, -1, self.hidden_size]))
                # # x.set_shape([None, self.hidden_size])
                # # x = tf.expand_dims(x, axis=0)

        output = self.filter_dense_layer(x)
        if self.train:
            output = tf.nn.dropout(output, 1.0 - self.relu_dropout)
        output = self.output_dense_layer(output)

        # conv x
        if self.use_conv:
            conv_output = x
            for layer in self.conv_layers:
                conv_output = layer(conv_output)
                conv_output = tf.contrib.layers.layer_norm(conv_output)
                if self.train:
                    conv_output = tf.nn.dropout(conv_output,
                                                1.0 - self.relu_dropout)
            output += conv_output

        # reverse conv x
        if self.bidirection:
            reverse_conv_output = tf.reverse(x, axis=[1])
            for layer in self.reverse_conv_layers:
                reverse_conv_output = layer(reverse_conv_output)
                reverse_conv_output = tf.contrib.layers.layer_norm(
                    reverse_conv_output)
                if self.train:
                    reverse_conv_output = tf.nn.dropout(
                        reverse_conv_output, 1.0 - self.relu_dropout)
            output += reverse_conv_output

        if padding is not None:
            padding = 1-padding # nopaddings are ones and paddings are zeros.
            padding = tf.expand_dims(padding, axis=-1)  # [batch_size, length, 1] 
            padding = tf.tile(padding, [1,1,self.hidden_size] ) # [batch_size, length, hidden_size] 
            output = tf.multiply(output, padding) 
            # with tf.name_scope("re_add_padding"):
                # output = tf.reshape(output, [-1, self.hidden_size])
                # # output = tf.squeeze(output, axis=0)
                # output = tf.scatter_nd(
                    # indices=nonpad_ids,
                    # updates=output,
                    # shape=[batch_size * length, self.hidden_size])
                # output = tf.reshape(output,
                                    # [batch_size, length, self.hidden_size])
        return output
