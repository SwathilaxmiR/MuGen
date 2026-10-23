"""FluidSynth (subprocess, fast-render) + permissive SoundFont. Reverb/chorus off; our own FX follow."""
import os
import subprocess
import tempfile
from functools import lru_cache

import numpy as np
import pretty_midi
import soundfile as sf

from ..composer.base import StemPart
from ..config import get_settings
from .base import RenderSpec, events_seconds, fit_length, total_samples

PAD_CC = 110  # undefined controller; a late CC keeps fluidsynth rendering through the tail


class FluidSynthRenderer:
    name = "fluidsynth"

    def __init__(self, settings=None):
        self.s = settings or get_settings()

    def version(self) -> str:
        return _version(self.s.fluidsynth_bin)

    def render(self, part: StemPart, rs: RenderSpec) -> np.ndarray:
        if self.s.fault_inject == "render_primary_fail":
            raise RuntimeError("fault injected: render_primary_fail")
        n = total_samples(rs)
        pm = pretty_midi.PrettyMIDI(initial_tempo=60.0 / rs.beat_s)
        inst = pretty_midi.Instrument(program=part.program, is_drum=part.is_drum, name=part.name)
        for start, dur, pitch, vel in events_seconds(part, rs):
            inst.notes.append(pretty_midi.Note(velocity=int(vel), pitch=int(pitch), start=start,
                                               end=start + max(dur, 0.02)))
        inst.control_changes.append(pretty_midi.ControlChange(PAD_CC, 0, n / rs.sr + 0.25))
        pm.instruments.append(inst)
        with tempfile.TemporaryDirectory(prefix="fs_") as tmp:
            mid, wav = os.path.join(tmp, "in.mid"), os.path.join(tmp, "out.wav")
            pm.write(mid)
            cmd = [self.s.fluidsynth_bin, "-ni", "-q", "-F", wav, "-T", "wav", "-O", "float",
                   "-r", str(rs.sr), "-g", "0.6", "-R", "0", "-C", "0",
                   "-o", "synth.reverb.active=0", "-o", "synth.chorus.active=0",
                   "-o", "synth.polyphony=512",
                   self.s.soundfont_path, mid]
            timeout = 0.001 if self.s.fault_inject == "render_timeout" else self.s.fluidsynth_timeout_s
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
            if proc.returncode != 0 or not os.path.exists(wav):
                raise RuntimeError(f"fluidsynth exit {proc.returncode}: {proc.stderr.decode()[-300:]}")
            audio, sr = sf.read(wav, dtype="float64", always_2d=True)
        if sr != rs.sr:
            raise RuntimeError(f"fluidsynth wrote {sr} Hz, expected {rs.sr}")
        return fit_length(audio, n)


@lru_cache
def _version(binary: str) -> str:
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, timeout=5).stdout.decode()
        return out.splitlines()[0].replace("FluidSynth runtime version", "").strip()
    except Exception:
        return "unknown"
