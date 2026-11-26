"""Optional provider and neural contracts; skipped unless dependencies are installed."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from marketpulse.data import synthetic
from marketpulse.fetch import normalize
from marketpulse.models import NEURAL, fit_neural, neural_predict
from marketpulse.pipeline import run


@unittest.skipUnless(importlib.util.find_spec("pandas"), "Install requirements-data.txt")
class ProviderTests(unittest.TestCase):
    def test_single_level(self):
        import pandas as pd
        frame=pd.DataFrame({"Close":[100.,101.]},index=pd.to_datetime(["2020-01-02","2020-01-03"]))
        s=normalize(frame,"AAPL")
        self.assertEqual(s.ticker,"AAPL")
        np.testing.assert_allclose(s.close,[100.,101.])

    def test_multi_index(self):
        import pandas as pd
        frame=pd.DataFrame([[100.,42.],[101.,45.]],index=pd.to_datetime(["2020-01-02","2020-01-03"]),
                           columns=pd.MultiIndex.from_tuples([("Close","AAPL"),("Open","AAPL")]))
        np.testing.assert_allclose(normalize(frame,"AAPL").close,[100.,101.])

    def test_empty(self):
        import pandas as pd
        with self.assertRaises(ValueError): normalize(pd.DataFrame(),"AAPL")

    def test_multi_ticker_rejected(self):
        import pandas as pd
        frame=pd.DataFrame([[100.,42.],[101.,45.]],index=pd.to_datetime(["2020-01-02","2020-01-03"]),
                           columns=pd.MultiIndex.from_tuples([("Close","AAPL"),("Close","MSFT")]))
        with self.assertRaises(ValueError): normalize(frame,"AAPL")


@unittest.skipUnless(importlib.util.find_spec("tensorflow"), "Install requirements-deep.txt")
class NeuralTests(unittest.TestCase):
    def test_thesis_models_train(self):
        rng=np.random.default_rng(1)
        X=rng.normal(size=(48,10,1))
        y=rng.normal(scale=.01,size=48)
        for name in NEURAL:
            with self.subTest(name=name):
                m=fit_neural(name,X,y,42,1)
                output=neural_predict(m,X[-4:])
                self.assertEqual(output.shape,(4,))
                self.assertTrue(np.isfinite(output).all())

    def test_deep_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=run(synthetic(rows=300),Path(tmp)/"deep",lookback=10,deep=True,epochs=1)
            self.assertTrue(set(NEURAL).issubset(report["validation"]))
            self.assertIn("tensorflow",report["environment"])


if __name__ == "__main__":
    unittest.main()
