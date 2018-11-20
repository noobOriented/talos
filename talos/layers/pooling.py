import abc

import tensorflow as tf


class GlobalPooling1D(tf.keras.layers.Layer, abc.ABC):
    """Abstract class for different global pooling 1D layers.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input_spec = tf.keras.layers.InputSpec(ndim=3)

    def compute_output_shape(self, input_shape):
        input_shape = tf.TensorShape(input_shape).as_list()
        return tf.TensorShape([input_shape[0], input_shape[2]])

    @abc.abstractmethod
    def call(self, inputs, seqlen, mask):
        pass

    @staticmethod
    def _get_mask(inputs, seqlen, mask):
        if mask is not None:
            return tf.cast(mask, inputs.dtype)
        elif seqlen is not None:
            maxlen = inputs.shape[1].value
            return tf.sequence_mask(seqlen, maxlen=maxlen, dtype=inputs.dtype)  # shape (N, T)
        else:
            return None


class GlobalAveragePooling1D(GlobalPooling1D):

    def call(self, inputs, seqlen, mask):
        mask = self._get_mask(inputs, mask, seqlen)
        if mask is not None:
            inputs *= tf.expand_dims(mask, axis=2)
            return tf.reduce_sum(inputs, axis=1) / tf.reduce_sum(mask, axis=1)
        return tf.mean(inputs, axis=1)


class GlobalAttentionPooling1D(GlobalPooling1D):
    """Reference: https://arxiv.org/pdf/1703.03130.pdf
    """
    def __init__(
            self,
            units,
            heads=1,
            activation='tanh',
            use_bias=False,
            kernel_initializer='glorot_uniform',
            bias_initializer='zeros',
            kernel_regularizer=None,
            bias_regularizer=None,
            activity_regularizer=None,
            kernel_constraint=None,
            bias_constraint=None,
            reg_coeff=0.,
            **kwargs,
        ):
        super().__init__(
            activity_regularizer=tf.keras.regularizers.get(activity_regularizer),
            **kwargs,
        )
        self.units = units
        self.heads = heads
        self.activation = tf.keras.activations.get(activation)
        self.use_bias = use_bias
        self.kernel_initializer = tf.keras.initializers.get(kernel_initializer)
        self.bias_initializer = tf.keras.initializers.get(bias_initializer)
        self.kernel_regularizer = tf.keras.regularizers.get(kernel_regularizer)
        self.bias_regularizer = tf.keras.regularizers.get(bias_regularizer)
        self.kernel_constraint = tf.keras.constraints.get(kernel_constraint)
        self.bias_constraint = tf.keras.constraints.get(bias_constraint)

        if reg_coeff < 0:
            raise ValueError("reg_coeff can't be negative!")
        self.reg_coeff = reg_coeff
        self._identity_matrix = None

    def build(self, input_shape):
        self.candidate_kernel = self.add_weight(
            name='candidate_kernel',
            shape=(input_shape[2].value, self.units),
            initializer=self.kernel_initializer,
            regularizer=self.kernel_regularizer,
            constraint=self.kernel_constraint,
            trainable=True,
        )
        self.softmax_kernel = self.add_weight(
            name='softmax_kernel',
            shape=(self.units, self.heads),
            initializer=self.kernel_initializer,
            regularizer=self.kernel_regularizer,
            constraint=self.kernel_constraint,
            trainable=True,
        )
        if self.use_bias:
            self.bias = self.add_weight(
                name='candidate_bias',
                shape=(self.units, ),
                initializer=self.bias_initializer,
                regularizer=self.bias_regularizer,
                constraint=self.bias_constraint,
                trainable=True,
            )
        else:
            self.bias = None
        super().build(input_shape)

    def call(
            self,
            inputs: tf.Tensor,
            seqlen: tf.Tensor = None,
            mask: tf.Tensor = None,
        ) -> tf.Tensor:
        # shape (N, T, units)
        hidden_outputs = tf.tensordot(inputs, self.candidate_kernel, axes=[[2], [0]])
        if self.use_bias:
            hidden_outputs = tf.nn.bias_add(hidden_outputs, self.bias)
        if self.activation is not None:
            hidden_outputs = self.activation(hidden_outputs)
        # shape (N, T, Head)
        logits = tf.tensordot(hidden_outputs, self.softmax_kernel, axes=[[2], [0]])
        weights = tf.nn.softmax(logits, axis=1)

        mask = self._get_mask(inputs, seqlen, mask)
        if mask is not None:
            # Renormalize for lower seqlen
            weights *= tf.expand_dims(mask, axis=2)
            weights /= tf.reduce_sum(weights, axis=1, keepdims=True)

        if self.reg_coeff > 0:
            weights_product = tf.matmul(weights, weights, transpose_a=True)
            identity_matrix = self._get_identity_matrix()
            penalty = self.reg_coeff * tf.reduce_sum(tf.square(
                weights_product - identity_matrix,
            ))
            self.add_loss(penalty)
        # shape (N, Head, input_dim)
        outputs = tf.matmul(weights, inputs, transpose_a=True)
        return outputs

    def _get_identity_matrix(self):
        if self._identity_matrix is None:
            self._identity_matrix = tf.eye(self.heads, batch_shape=[1])
        return self._identity_matrix

    def compute_output_shape(self, input_shape):
        output_shape = input_shape.as_list()
        output_shape[1] = self.heads
        return tf.TensorShape(output_shape)
