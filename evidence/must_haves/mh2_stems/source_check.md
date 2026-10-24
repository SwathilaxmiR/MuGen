# Stem source check

Every stem is rendered from its own note list and GM program (`stem_inventory.csv`: production = 'symbolic MIDI -> fluidsynth render + numpy FX').

- Max |waveform cross-correlation| between any two stems in any run: **0.165**.
- Mean spectral overlap (share of each stem's spectrum shared with another stem): **0.71**. EQ bands of one mix score about 0.25 (`evidence/eval/bleed.md`), so these are played parts, not filters.
- Code: `src/musicengine/composer/registry.py` (one composer per stem), `src/musicengine/renderer/__init__.py` (one render per stem).
