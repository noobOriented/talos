from unittest.mock import call

import tensorflow as tf

from ..dynamic_decode import dynamic_decode


def test_dynamic_decode_logic(mocker):

    def mock_cell_call(inputs, state):
        return chr(inputs + len(state)), state + 's'

    mock_cell = mocker.Mock(side_effect=mock_cell_call)
    first_input = ord('A')
    mocker.patch('tensorflow.stack', lambda lst, axis: ",".join(lst))
    output = dynamic_decode(
        cell=mock_cell,
        first_input=first_input,
        maxlen=5,
        next_input_producer=lambda c: ord(c),
        init_state='s',
    )
    expected_cell_calls = [
        call(first_input, 's'),
        call(first_input + 1, 'ss'),
        call(first_input + 3, 'sss'),
        call(first_input + 6, 'ssss'),
        call(first_input + 10, 'sssss'),
    ]
    expected_output = ",".join([
        chr(first_input + 1),
        chr(first_input + 3),
        chr(first_input + 6),
        chr(first_input + 10),
        chr(first_input + 15),
    ])
    mock_cell.assert_has_calls(expected_cell_calls)
    assert output == expected_output


def test_dynamic_decode_tf():
    batch_size = 6
    with tf.Graph().as_default():
        cell = tf.nn.rnn_cell.LSTMCell(num_units=5)
        first_input = tf.placeholder(shape=[batch_size, 3], dtype=tf.float32)
        init_state = (
            tf.placeholder(shape=[batch_size, 5], dtype=tf.float32),
            tf.placeholder(shape=[batch_size, 5], dtype=tf.float32),
        )
        next_input_producer = tf.keras.layers.Dense(units=3)
        outputs = dynamic_decode(
            cell=cell,
            first_input=first_input,
            maxlen=10,
            next_input_producer=next_input_producer,
            init_state=init_state,
        )
    assert outputs.shape.as_list() == [batch_size, 10, 5]
