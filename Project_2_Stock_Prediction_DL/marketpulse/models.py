"""Persistence, regularized linear model, and optional thesis neural architectures."""
from __future__ import annotations

import numpy as np

RIDGE = {"ridge": 10., "ridge_regularized": 500.}

NEURAL = ("mlp", "rnn", "gru", "lstm", "stacked_lstm")


def fit_scaler(X):
    # Only fit on training windows. Constant columns are safe.
    center, spread = X.mean(axis=(0, 1)), X.std(axis=(0, 1))
    return center, np.where(spread < 1e-12, 1., spread)


def scale(X, center, spread):
    return (X - center) / spread


def fit_ridge(X, y, alpha=10.):
    A = X.reshape(len(X), -1)
    A = np.column_stack((np.ones(len(A)), A))
    penalty = np.eye(A.shape[1]) * alpha
    penalty[0, 0] = 0.  # never penalize intercept
    return np.linalg.solve(A.T @ A + penalty, A.T @ y)


def ridge_predict(X, weights):
    return X.reshape(len(X), -1) @ weights[1:] + weights[0]


def build_neural(name, shape, seed):
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()
    L = tf.keras.layers
    if name == "mlp":
        layers = [L.Flatten(), L.Dense(64, activation="relu"), L.Dense(32, activation="relu")]
    elif name == "rnn":
        layers = [L.SimpleRNN(32)]
    elif name == "gru":
        layers = [L.GRU(32)]
    elif name == "lstm":
        layers = [L.LSTM(32)]
    elif name == "stacked_lstm":
        layers = [L.LSTM(64, return_sequences=True), L.Dropout(.2), L.LSTM(32), L.Dropout(.2)]
    else:
        raise ValueError("Unknown neural architecture")
    model = tf.keras.Sequential([L.Input(shape=shape), *layers, L.Dense(1)], name=name)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=.001), loss="mse")
    return model


def fit_neural(name, X, y, seed, epochs):
    """Use a chronological inner early-stopping slice, not outer validation/test."""
    import tensorflow as tf

    tf.keras.backend.clear_session()
    inner = int(len(X) * .85)
    if inner < 30:
        raise ValueError("Insufficient neural training observations")
    model = build_neural(name, X.shape[1:], seed)
    # Learn standardized percentage-like log returns to improve numeric conditioning.
    model.fit(X[:inner], y[:inner] * 100, validation_data=(X[inner:], y[inner:] * 100),
              epochs=epochs, batch_size=32, shuffle=False, verbose=0,
              callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5,
                                                         restore_best_weights=True)])
    return model


def neural_predict(model, X):
    return model.predict(X, verbose=0).reshape(-1) / 100
