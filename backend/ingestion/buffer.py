"""Ring buffer for accumulating sensor snapshots for ML inference."""
import numpy as np
from collections import deque


class SensorBuffer:
    """Fixed-size ring buffer that accumulates feature vectors for the TFT model.

    Features per snapshot (n_features=8):
    [ch0_watts, ch1_watts, ch2_watts, ch3_watts, total, renewable_pct, carbon_intensity, tou_price]
    """

    def __init__(self, window_size: int = 96, n_features: int = 8):
        self._window_size = window_size
        self._n_features = n_features
        self._buffer: deque = deque(maxlen=window_size)

    def add(self, feature_vector: list[float]) -> None:
        """Add a feature vector to the buffer."""
        if len(feature_vector) != self._n_features:
            raise ValueError(
                f"Expected {self._n_features} features, got {len(feature_vector)}"
            )
        self._buffer.append(feature_vector)

    @property
    def is_full(self) -> bool:
        return len(self._buffer) == self._window_size

    @property
    def size(self) -> int:
        return len(self._buffer)

    def get_window(self) -> np.ndarray:
        """Return buffer contents as numpy array (window_size, n_features).

        Zero-pads from the front if not yet full.
        """
        if len(self._buffer) == 0:
            return np.zeros((self._window_size, self._n_features))

        arr = np.array(list(self._buffer))
        if len(arr) < self._window_size:
            pad = np.zeros((self._window_size - len(arr), self._n_features))
            arr = np.vstack([pad, arr])
        return arr

    def clear(self) -> None:
        self._buffer.clear()
