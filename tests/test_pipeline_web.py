"""End-to-end glue tests. TabPFN is swapped for a cheap fake here (the real model is exercised by
eval/backtest.py); everything else (cleaning, weeks, note, report, web upload) is real."""
import json
import threading
import time
import urllib.request
import uuid

import numpy as np
import pandas as pd
import pytest

from tidy_predict import cli, web
from tidy_predict.forecast import Forecast
from tidy_predict.weekly import feature_rows


def fake_forecast(tab, products, target_week, **kw):
    te = feature_rows(tab, products, [target_week])
    m = np.expm1(te["mean4"].to_numpy())
    t = te[["product", "week", "actual"]].assign(mean=m, p10=m * 0.5, p50=m, p90=m * 1.5)
    return Forecast(table=t.reset_index(drop=True), seconds=0.01, n_train=0)


def synthetic_export(path, weeks=40, seed=1):
    """SYNTHETIC test data: 3 products sold most weeks, plus a duplicate, a return and a postage line."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2011-01-03")
    rows, inv = [], 1000
    for w in range(weeks):
        for code, name, base in (("10001", "BLUE MUG", 30), ("10002", "RED  MUG", 12), ("10003", "TEA TOWEL", 6)):
            inv += 1
            rows.append([str(inv), code, name, str(int(base + rng.integers(0, 5))),
                         (start + pd.Timedelta(days=7 * w + 1)).strftime("%d/%m/%Y %H:%M"), "2.50", "C1"])
    rows.append(rows[5][:])                                                     # duplicate
    rows.append(["9001", "POST", "POSTAGE", "1", "05/01/2011 10:00", "18", "C1"])  # service line
    rows.append(["C9002", "10001", "BLUE MUG", "-3", "06/01/2011 10:00", "2.50", "C1"])
    pd.DataFrame(rows, columns=["Order No", "SKU", "Item name", "Qty", "Order date", "Unit price", "Customer"]) \
        .to_csv(path, index=False)


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    monkeypatch.setattr(cli, "tabpfn_forecast", fake_forecast)


def test_run_pipeline_writes_everything(tmp_path):
    src = tmp_path / "export.csv"
    synthetic_export(src)
    log = []
    run = cli.run_pipeline(src, tmp_path / "out", use_llm=False, label="Synthetic test data", log=log.append)
    for f in ("report.html", "forecast.csv", "issues.csv", "clean_sales.csv", "run.json"):
        assert (tmp_path / "out" / f).exists()
    assert run["clean_stats"]["duplicate"] == 1 and run["clean_stats"]["service_line"] == 1
    assert run["note"]["author"] == "template"
    assert len(run["facts"]["items"]) == 3
    assert "Built with PriorLabs-TabPFN" in (tmp_path / "out" / "report.html").read_text()
    assert any("Forecasting the week of" in m for m in log)


def test_as_of_replays_the_past_and_shows_actuals(tmp_path):
    src = tmp_path / "export.csv"
    synthetic_export(src)
    run = cli.run_pipeline(src, tmp_path / "out", as_of="2011-08-28", use_llm=False)
    assert run["target_week"] == "2011-08-29" and run["actuals"] is not None


def test_too_little_history_is_a_clear_error(tmp_path):
    src = tmp_path / "export.csv"
    synthetic_export(src, weeks=6)
    with pytest.raises(cli.PipelineError):
        cli.run_pipeline(src, tmp_path / "out", use_llm=False)


def test_web_upload_runs_job(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "RUNS", tmp_path / "runs")
    src = tmp_path / "export.csv"
    synthetic_export(src)
    srv = web.ThreadingHTTPServer(("127.0.0.1", 0), web.make_handler(use_llm=False))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        home = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
        assert "Built with PriorLabs-TabPFN" in home
        b = uuid.uuid4().hex
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"label\"\r\n\r\nSynthetic\r\n"
                f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"../../evil name.csv\"\r\n"
                f"Content-Type: text/csv\r\n\r\n").encode() + src.read_bytes() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/run", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        resp = urllib.request.urlopen(req)
        jid = resp.url.rsplit("/", 1)[1]
        for _ in range(100):
            s = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/job/{jid}/status"))
            if s["state"] != "running":
                break
            time.sleep(0.1)
        assert s["state"] == "done", s
        rep = urllib.request.urlopen(f"http://127.0.0.1:{port}/job/{jid}/report.html").read().decode()
        assert "Restock note" in rep
        # the upload stays inside runs/<id>/ whatever its name
        saved = list((tmp_path / "runs" / jid).glob("*.csv"))
        assert [p.name for p in saved] == ["evil_name.csv"]
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/job/{jid}/../../etc/passwd")
    finally:
        srv.shutdown()


def test_command_line_entry_point(tmp_path, capsys):
    src = tmp_path / "export.csv"
    synthetic_export(src)
    assert cli.main([str(src), "--no-llm", "--out", str(tmp_path / "o"), "--as-of", "2011-08-28"]) == 0
    assert "keep the most stock" in capsys.readouterr().out
    assert (tmp_path / "o" / "report.html").exists()
