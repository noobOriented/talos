import pytest

import numpy as np
import tensorflow as tf

from ..transformer_block import TransformerBlock


@pytest.fixture(scope='module')
def layer():
    return TransformerBlock(units=3, heads=2)


def test_output_shape(inputs, layer):
    outputs = layer(inputs)
    assert outputs.shape.as_list() == inputs.shape.as_list()


def test_masked_inputs_propagate(masked_inputs, layer):
    outputs = layer(masked_inputs)
    assert outputs._keras_mask is masked_inputs._keras_mask


def test_mask_gradients(inputs, mask, layer, sess):
    maxlen, channel = inputs.shape.as_list()[1:]

    outputs = layer(inputs, mask=mask)
    grads = tf.gradients(outputs, inputs)[0]  # same shape as inputs

    mask_batch = np.random.choice(2, size=[5, maxlen]).astype(np.bool)
    sess.run(tf.variables_initializer(var_list=layer.variables))
    grad_batch = sess.run(
        grads,
        feed_dict={
            inputs: [np.random.rand(maxlen, channel) for _ in range(5)],
            mask: mask_batch,
        },
    )
    for mask_sample, grad_sample in zip(mask_batch, grad_batch):
        attended_section = grad_sample[mask_sample]
        dropped_section = grad_sample[np.logical_not(mask_sample)]
        assert (attended_section != 0.).all()
        assert (dropped_section == 0.).all()


def test_forward_mask_gradients(inputs, sess):
    layer = TransformerBlock(units=3, heads=2, use_forward_mask=True)
    maxlen, channel = inputs.shape.as_list()[1:]

    outputs = layer(inputs)
    grads_list = [
        tf.gradients(
            outputs[:, t],
            inputs,
        )[0]
        for t in range(maxlen)
    ]  # every elements have same shape as inputs

    sess.run(tf.variables_initializer(var_list=layer.variables))
    grad_list_val = sess.run(
        grads_list,
        feed_dict={inputs: np.random.rand(1, maxlen, channel)},
    )
    for t, grad_of_output_t in enumerate(grad_list_val):
        attended_section = grad_of_output_t[:, :t + 1]
        dropped_section = grad_of_output_t[:, t + 1:]
        assert (attended_section != 0.).all()
        assert (dropped_section == 0.).all()
