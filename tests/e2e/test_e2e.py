"""Full stack: api + worker + postgres + S3 + real renderer. Set E2E_API_URL (compose sets it)."""
import glob
import hashlib
import json
import os
import uuid

import pytest

from musicengine import mixdown, qa
from musicengine.cli import _run_case, _submit_case
from musicengine.client import ApiClient

pytestmark = pytest.mark.e2e
INPUTS = os.path.join(os.path.dirname(__file__), "..", "inputs")


@pytest.fixture(scope="module")
def client():
    c = ApiClient(os.environ["E2E_API_URL"], os.environ.get("API_TOKEN", ""))
    c.run_id = f"e2e-{uuid.uuid4().hex[:8]}"
    return c


def _case(name):
    return json.load(open(os.path.join(INPUTS, f"{name}.json")))


@pytest.mark.parametrize("D", [10, 60])
def test_generate_real_renderer(client, tmp_path, D):
    body = {"prompt": "upbeat corporate background for a product video", "duration_s": D, "seed": 5,
            "output": {"formats": ["wav", "mp3"]}}
    r = client.submit(body)
    assert r.status_code == 202
    st = client.wait(r.json()["job_id"])
    assert st["status"] == "succeeded", st["error"]
    files = client.download_result(st, str(tmp_path))
    m = json.load(open(files["music_manifest.json"]))
    assert m["ai_generated"] and all(s["renderer"] == "fluidsynth" for s in m["stems"])
    mix, sr = mixdown.read_wav(files["mix.wav"])
    assert len(mix) == D * 48000 and sr == 48000
    assert abs(qa.integrated_lufs(mix, sr) + 16) <= 0.5 and qa.true_peak_dbtp(mix) <= -1.0
    stems = [mixdown.read_wav(f)[0] for k, f in files.items() if k.startswith("stems/")]
    assert len(stems) == 4 and qa.sum_diff_db(stems, mix) < -90


def test_regenerate_stem_byte_identical(client, tmp_path):
    row = _run_case(client, "adv_regenerate_drums", _case("adv_regenerate_drums"), str(tmp_path))
    assert row["checks_passed"], row


def test_loop_seam(client, tmp_path):
    row = _run_case(client, "adv_loop_16s", _case("adv_loop_16s"), str(tmp_path))
    assert row["checks_passed"], row
    mix, sr = mixdown.read_wav(str(tmp_path / "adv_loop_16s" / "mix.wav"))
    assert not qa.loop_seam_report(mix, sr)["click"]


def test_same_key_twice_one_job_one_set_of_objects(client, tmp_path):
    body = {"prompt": "calm piano", "duration_s": 6, "seed": 77}
    key = f"twice-{uuid.uuid4()}"
    a, b = client.submit(body, key=key).json(), client.submit(body, key=key).json()
    assert a["job_id"] == b["job_id"]
    st = client.wait(a["job_id"])
    c = client.submit(body, key=key).json()
    assert c["job_id"] == a["job_id"] and client.status(c["job_id"])["status"] == "succeeded"


def test_concurrent_jobs(client):
    ids = [client.submit({"prompt": p, "duration_s": 12, "seed": i}).json()["job_id"]
           for i, p in enumerate(["lofi beats", "epic trailer", "jazz lounge", "rock anthem"])]
    sts = [client.wait(j) for j in ids]
    assert all(s["status"] == "succeeded" for s in sts)
    assert len({s["result"]["mix_wav"].split("?")[0] for s in sts}) == 4


HARD = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(INPUTS, "hard_*.json")))


@pytest.mark.parametrize("name", HARD)
def test_hard_cases(client, tmp_path, name):
    data = _case(name)
    sub = _submit_case(client, name, data, str(tmp_path / name))
    row = _run_case(client, name, data, str(tmp_path), sub)
    assert row["checks_passed"], (row.get("failed_checks"), row.get("error"), row.get("qa_failures"))


def test_status_has_presigned_links_that_download(client, tmp_path):
    r = client.submit({"prompt": "ambient", "duration_s": 5, "seed": 1})
    st = client.wait(r.json()["job_id"])
    p = client.download(st["result"]["stems"]["harmony"], str(tmp_path / "h.wav"))
    assert hashlib.sha256(open(p, "rb").read()).hexdigest()
