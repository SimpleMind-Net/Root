import unittest

import numpy as np

import script_b3


class TestScriptB3(unittest.TestCase):
    def test_compute_ewma_vol_constant_series(self) -> None:
        closes = np.array([100.0, 100.0, 100.0, 100.0], dtype=np.float64)
        vol = script_b3.compute_ewma_vol(closes, span=3)
        self.assertEqual(vol, 0.0)

    def test_kernel_nw_tricube_basic(self) -> None:
        prices = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        result = script_b3.kernel_nw_tricube(prices, bw=2)
        self.assertEqual(result.shape, prices.shape)
        self.assertTrue(np.all(np.isfinite(result)))

    def test_chunk_items_splits(self) -> None:
        items = [("A", (np.array([1.0]), 1.0)) for _ in range(10)]
        chunks = script_b3.chunk_items(items, 4)
        chunk_sizes = [len(chunk) for chunk in chunks]
        self.assertEqual(sum(chunk_sizes), 10)
        self.assertTrue(all(size <= 4 for size in chunk_sizes))


if __name__ == "__main__":
    unittest.main()
