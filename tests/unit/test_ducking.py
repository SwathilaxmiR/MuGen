import numpy as np
import pytest

from musicengine.config import Settings
from musicengine.ducking import FetchError, apply_curve, check_public_url, duck, gain_curve_db

SR = 48000
S = Settings()


def speechlike(phrases, total_s, sr=16000, seed=0):
    """Noise 'syllables' (180 ms on / 70 ms off) inside each phrase, silence elsewhere."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(int(total_s * sr)) * 0.0005  # room noise ~ -66 dBFS
    for a, b in phrases:
        t = a
        while t < b:
            i, j = int(t * sr), int(min(b, t + 0.18) * sr)
            x[i:j] += rng.standard_normal(j - i) * 0.1 * np.hanning(j - i)
            t += 0.25
    return x


def music(total_s):
    t = np.arange(int(total_s * SR)) / SR
    m = 0.2 * np.sin(2 * np.pi * 220 * t)
    return np.stack([m, m], axis=1)


def level_db(curve, t):
    return curve[int(round(t * 100))]


PHRASES = [(0.5, 3.0), (3.4, 5.0), (7.0, 9.0)]  # 0.4 s gap (bridged), 2 s gap (recovers)


def test_depth_recovery_bridging_and_monotonic():
    mix = music(10)
    ducked, info, warnings = duck(mix, SR, speechlike(PHRASES, 10), S)
    assert info["applied"] and not warnings
    curve = gain_curve_db([(s["start_s"], s["end_s"]) for s in info["segments"]], 10, S.duck_db,
                          S.duck_attack_ms, S.duck_release_ms)
    # depth inside speech: 12 +- 1 dB measured on the audio
    for a, b in [(1.0, 2.5), (7.5, 8.5)]:
        i, j = int(a * SR), int(b * SR)
        depth = 20 * np.log10(np.sqrt(np.mean(mix[i:j] ** 2)) / np.sqrt(np.mean(ducked[i:j] ** 2)))
        assert 11 <= depth <= 13
    assert level_db(curve, 3.2) == pytest.approx(-12)  # 0.4 s gap is bridged
    assert level_db(curve, 6.0) == 0.0                  # 2 s gap returns to full level
    # attack starts before speech: already ducking 60 ms before the onset of phrase 3
    onset3 = info["segments"][-1]["start_s"]
    assert -12 < level_db(curve, onset3 - 0.06) < 0
    # no oscillation: between flat regions every transition is monotonic
    d = np.diff(curve)
    moving = d[np.abs(d) > 1e-9]
    assert np.count_nonzero(np.diff(np.sign(moving))) == 2 * len(info["segments"]) - 1
    assert len(info["segments"]) == 2
    assert info["curve"][0] == {"t": 0.0, "db": 0.0}


def test_true_peak_never_increases():
    mix = music(10)
    ducked, _, _ = duck(mix, SR, speechlike(PHRASES, 10), S)
    assert np.abs(ducked).max() <= np.abs(mix).max() + 1e-12


def test_all_silence():
    mix = music(6)
    ducked, info, warnings = duck(mix, SR, np.zeros(6 * 16000), S)
    assert not info["applied"] and np.array_equal(ducked, mix)
    assert [w["code"] for w in warnings] == ["NARRATION_NO_SPEECH"]


def test_room_noise_only_is_no_speech():
    _, info, warnings = duck(music(6), SR, speechlike([], 6), S)
    assert not info["applied"] and warnings[0]["code"] == "NARRATION_NO_SPEECH"


def test_long_silences_return_to_full_level():
    mix = music(20)
    _, info, _ = duck(mix, SR, speechlike([(1, 2.5), (15, 16)], 20), S)
    curve = gain_curve_db([(s["start_s"], s["end_s"]) for s in info["segments"]], 20, 12, 120, 500)
    assert np.all(curve[int(3.5 * 100):int(14.5 * 100)] == 0)


def test_narration_longer_than_music_truncated():
    _, info, warnings = duck(music(5), SR, speechlike([(1, 8)], 9), S)
    assert "NARRATION_TRUNCATED" in [w["code"] for w in warnings]
    assert info["segments"][-1]["end_s"] <= 5.0


def test_apply_curve_length_preserved():
    mix = music(3)
    out = apply_curve(mix, SR, np.full(301, -6.0))
    assert out.shape == mix.shape
    assert 20 * np.log10(np.abs(out).max() / np.abs(mix).max()) == pytest.approx(-6, abs=1e-6)


@pytest.mark.parametrize("url", ["http://127.0.0.1/a.wav", "http://localhost:8000/x", "http://10.1.2.3/x",
                                 "http://169.254.169.254/latest/meta-data/", "http://[::1]/x",
                                 "file:///etc/passwd", "ftp://example.com/x", "http://192.168.0.5/x"])
def test_ssrf_guard_blocks(url):
    with pytest.raises(FetchError):
        check_public_url(url)
