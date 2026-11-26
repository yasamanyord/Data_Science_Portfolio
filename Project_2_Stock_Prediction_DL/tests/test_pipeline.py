import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from marketpulse.api import app, create_app
from marketpulse.artifact import forecast, read_bundle
from marketpulse.cli import compare
from marketpulse.data import csv_text, demo_series, features, latest_window, load_csv, parse_csv, synthetic, windows
from marketpulse.evaluate import calibrated_radius, folds, metrics, prices, release_gate, split_indices
from marketpulse.models import fit_ridge, fit_scaler, ridge_predict, scale
from marketpulse.pipeline import run
from marketpulse.monitor import shadow

DEMO = Path(__file__).resolve().parents[1]/"artifacts"/"demo"


class DataTests(unittest.TestCase):
    def test_synthetic_reproducible(self):
        a, b = synthetic(), synthetic()
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertEqual(a.dates, b.dates)
        self.assertEqual(a.source, "synthetic:seed=42;rows=900")
        self.assertNotEqual(a.fingerprint, synthetic(43).fingerprint)

    def test_invalid_rows(self):
        for body in ("date,price\n2020-01-01,1\n",
                     "date,close\n2020-01-01,NaN\n2020-01-02,2\n",
                     "date,close\n2020-01-01,-1\n2020-01-02,2\n",
                     "date,close\n2020-01-01,inf\n2020-01-02,2\n",
                     "date,close\n2020-01-01,1\n2020-01-01,2\n",
                     "date,close\n2020-01-02,1\n2020-01-01,2\n",
                     "date,close\n2020-01-01,1,extra\n2020-01-02,2\n",
                     "date,close\n2020/01/01,1\n2020-01-02,2\n",
                     "date,close\n2999-01-01,1\n2999-01-02,2\n"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_csv(body, "AAPL", "test fixture")

    def test_ticker_source_required(self):
        for ticker, source in (("", "test"), ("A/B", "test"), ("ABC", "")):
            with self.subTest(ticker=ticker, source=source), self.assertRaises(ValueError):
                parse_csv("date,close\n2020-01-01,1\n2020-01-02,2\n", ticker, source)

    def test_causal_features(self):
        a = synthetic().close
        b = a.copy()
        b[400:] *= 3
        for mode in ("returns", "technical"):
            np.testing.assert_allclose(features(a, mode)[:400], features(b, mode)[:400], equal_nan=True)

    def test_windows_align_target_and_previous(self):
        series = synthetic()
        X, y, idx = windows(series, 60, "returns")
        self.assertEqual(X.shape, (839, 60, 1))
        self.assertEqual(idx[-1], len(series.close)-1)
        np.testing.assert_allclose(y, np.log(series.close[idx]/series.close[idx-1]))
        np.testing.assert_allclose(X[0, -1, 0], np.log(series.close[60]/series.close[59]))
        np.testing.assert_allclose(latest_window(series, 60, "returns")[0,-1,0], y[-1])

    def test_technical_features_finite(self):
        X, _, _ = windows(synthetic(), 60, "technical")
        self.assertEqual(X.shape[-1], 5)
        self.assertTrue(np.isfinite(X).all())

    def test_short_history_rejected(self):
        s = parse_csv("date,close\n2020-01-01,1\n2020-01-02,2\n", "X", "fixture")
        with self.assertRaises(ValueError):
            latest_window(s, 60, "returns")
        with self.assertRaises(ValueError):
            windows(s, 60, "returns")


class EvaluationTests(unittest.TestCase):
    def test_fold_indices(self):
        n = 840
        a,b = split_indices(n)
        seen=[]
        for tr,va in folds(n):
            self.assertEqual(tr.stop, va.start)
            self.assertEqual(tr.start, 0)
            self.assertLessEqual(va.stop,b)
            seen.extend(range(va.start,va.stop))
        self.assertEqual(seen,list(range(a,b)))

    def test_split_minimum(self):
        with self.assertRaises(ValueError):
            split_indices(40)

    def test_metrics_known(self):
        m = metrics([10,20], [11,18], [9,19])
        self.assertAlmostEqual(m["rmse"], np.sqrt(2.5))
        self.assertAlmostEqual(m["mae"], 1.5)
        self.assertAlmostEqual(m["directional_accuracy_pct"], 50.)

    def test_persistence_no_change(self):
        np.testing.assert_allclose(prices(np.array([1,2]), [0,0]), [1,2])

    def test_invalid_returns(self):
        for value in [np.nan, np.inf, 3]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                prices(100,value)

    def test_gate_negative_control(self):
        ref={"rmse":1., "mae":1., "return_mae_pct":1.}
        self.assertTrue(release_gate(ref,ref)["passed"])
        self.assertFalse(release_gate({**ref,"mae":1.03},ref)["passed"])

    def test_interval_rank(self):
        self.assertEqual(calibrated_radius([0,1,2],[0,0,0]),2.)

    def test_scaler_training_only(self):
        X = np.array([[[1.],[2.]],[[2.],[3.]],[[1000.],[1000.]]])
        c,s=fit_scaler(X[:2])
        self.assertEqual(c[0],2.)
        self.assertGreater(scale(X[2:], c,s).mean(),100.)

    def test_constant_scaler(self):
        c,s=fit_scaler(np.ones((4,5,2)))
        np.testing.assert_allclose(s,[1,1])
        np.testing.assert_allclose(scale(np.ones((4,5,2)),c,s),0.)

    def test_ridge_fit(self):
        X=np.arange(50).reshape(25,2,1)/50
        y=X[:,1,0]*.2
        w=fit_ridge(X,y,alpha=.001)
        self.assertLess(np.mean(np.abs(ridge_predict(X,w)-y)),.001)


class PipelineTests(unittest.TestCase):
    def test_reproduction_and_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"run"
            r=run(demo_series(),folder)
            ref=read_bundle(DEMO)[1]
            self.assertTrue(compare(ref,r)["passed"])
            self.assertEqual(r["selected_model"],ref["selected_model"])
            self.assertAlmostEqual(r["test"]["candidate"]["mae"],ref["test"]["candidate"]["mae"], places=8)
            f=forecast(folder,demo_series())
            self.assertAlmostEqual(f["point"],r["forecast"]["point"])
            self.assertLessEqual(f["lower"],f["point"])
            self.assertGreaterEqual(f["upper"],f["point"])
            with self.assertRaises(ValueError):
                run(demo_series(),folder)

    def test_holdout_cannot_change_selection_or_fit(self):
        s=synthetic()
        X,_,idx=windows(s,60,"returns")
        _,b=split_indices(len(X))
        modified=s.close.copy()
        modified[idx[b]:]*=1.1
        changed=parse_csv(csv_text(s.dates,modified),s.ticker,s.source)
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"a"; z=Path(tmp)/"b"
            r1=run(s,a); r2=run(changed,z)
            self.assertEqual(r1["validation"],r2["validation"])
            self.assertEqual(r1["selected_model"],r2["selected_model"])
            m1,m2 = read_bundle(a)[0],read_bundle(z)[0]
            np.testing.assert_allclose(m1["weights"],m2["weights"])
            self.assertNotEqual(r1["dataset"]["sha256"],r2["dataset"]["sha256"])

    def test_technical_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=run(synthetic(),Path(tmp)/"run",lookback=20,feature_set="technical")
            self.assertEqual(r["config"]["feature_set"],"technical")
            self.assertEqual(len(r["holdout"]),r["counts"]["holdout"])

    def test_compare_blocks_regression(self):
        ref=read_bundle(DEMO)[1]
        bad=json.loads(json.dumps(ref)); bad["test"]["candidate"]["mae"]*=1.5
        self.assertFalse(compare(ref,bad)["passed"])

    def test_compare_blocks_changed_data(self):
        ref=read_bundle(DEMO)[1]
        bad=json.loads(json.dumps(ref)); bad["dataset"]["sha256"]="changed"
        with self.assertRaises(ValueError): compare(ref,bad)

    def test_compare_blocks_changed_labels(self):
        ref=read_bundle(DEMO)[1]
        bad=json.loads(json.dumps(ref)); bad["holdout"][0]["actual"]*=2
        with self.assertRaises(ValueError): compare(ref,bad)

    def test_artifact_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for fn in ("model.json","report.json","manifest.json"):
                (p/fn).write_bytes((DEMO/fn).read_bytes())
            (p/"report.json").write_text("{}")
            with self.assertRaises(ValueError): read_bundle(p)

    def test_revised_history_rejected(self):
        s=demo_series(); p=s.close.copy(); p[0]*=2
        with self.assertRaises(ValueError):
            forecast(DEMO,parse_csv(csv_text(s.dates,p),s.ticker,s.source))

    def test_wrong_ticker_rejected(self):
        s=synthetic()
        with self.assertRaises(ValueError):
            forecast(DEMO,parse_csv(csv_text(s.dates,s.close),"AAPL",s.source))

    def test_rejected_artifact_blocks_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            r=read_bundle(DEMO)[1]; r["gate"]["passed"]=False
            (p/"report.json").write_text(json.dumps(r))
            m=read_bundle(DEMO)[0]; m["approved"]=False
            m["report_sha256"]=hashlib.sha256((p/"report.json").read_bytes()).hexdigest()
            (p/"model.json").write_text(json.dumps(m))
            (p/"manifest.json").write_text(json.dumps({name: hashlib.sha256((p/name).read_bytes()).hexdigest() for name in ("model.json","report.json")}))
            (p/"observations.csv").write_bytes((DEMO/"observations.csv").read_bytes())
            with self.assertRaisesRegex(ValueError,"blocked"):
                forecast(p,demo_series())
            self.assertEqual(TestClient(create_app(p)).get("/api/forecast").status_code,409)

    def test_dashboard_source(self):
        c=TestClient(app)
        r=c.get("/")
        self.assertEqual(r.status_code,200)
        self.assertIn("SYNTHETIC DATA",r.text)
        self.assertIn("default-src",r.headers["content-security-policy"])
        self.assertEqual(c.get("/static/app.js").status_code,200)

    def test_api_forecast_lineage(self):
        c=TestClient(app)
        f=c.get("/api/forecast").json()
        report=c.get("/api/report").json()
        self.assertTrue(f["synthetic"])
        self.assertEqual(f["model"],report["selected_model"])
        self.assertAlmostEqual(f["point"],report["forecast"]["point"])
        self.assertEqual(c.get("/health").json()["mode"],"synthetic/offline")

    def test_shadow_uses_only_new_observations(self):
        from datetime import date, timedelta
        s=demo_series()
        end=date.fromisoformat(s.dates[-1])
        dates=list(s.dates)+[(end+timedelta(days=i)).isoformat() for i in (1,2,3)]
        prices=list(s.close)+[s.close[-1]*v for v in (1.01,1.02,.99)]
        extended=parse_csv(csv_text(dates,prices),s.ticker,s.source)
        out=shadow(DEMO,extended)
        self.assertEqual(out["n"],3)
        self.assertTrue(out["alert"])
        self.assertEqual(out["as_of"],dates[-1])
        with self.assertRaises(ValueError):
            shadow(DEMO,s)

    def test_api_no_post_or_trade(self):
        c=TestClient(app)
        self.assertEqual(c.post("/api/forecast",json={}).status_code,405)
        self.assertEqual(c.post("/api/trade",json={}).status_code,404)


if __name__ == "__main__":
    unittest.main()
