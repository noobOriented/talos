import tensorflow as tf

from ..sequential import Sequential


def test_build_sublayers_when_first_called():
    sequential = Sequential([
        tf.keras.layers.Embedding(20, 10),
        tf.keras.layers.LSTM(10, return_sequences=True),
        tf.keras.layers.Dense(5),
        tf.keras.layers.MaxPooling1D(),
    ])
    assert all(not layer.built for layer in sequential.layers)
    inputs = tf.zeros([1, 3], dtype=tf.float32)
    sequential(inputs)
    assert all(layer.built for layer in sequential.layers)


def test_context_manager_work_when_first_called():
    new_graph = tf.Graph()
    assert new_graph is not tf.get_default_graph()

    sequential = Sequential([
        tf.keras.layers.Embedding(20, 10),
        tf.keras.layers.LSTM(10, return_sequences=True),
        tf.keras.layers.Dense(5),
        tf.keras.layers.MaxPooling1D(),
    ])  # don't create variables in default_graph

    with new_graph.as_default(), tf.variable_scope('scope'):
        inputs = tf.zeros([1, 3], dtype=tf.float32)
        sequential(inputs)

    variables = sequential.variables
    assert all(var.graph is new_graph for var in variables)
    assert all(var.name.startswith('scope') for var in variables)
