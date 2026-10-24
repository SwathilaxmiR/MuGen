# Listening checks (human)

Open `log.csv` and, for every row, listen to `clip` and fill `rating/pass`, `notes` and `listener`.

| check | what to listen for | value |
|---|---|---|
| ending | ends on purpose (final hit or fade), no hard cut | pass / fail |
| section_change | change is audible, on the beat, no click or gap | pass / fail |
| stem_solo / mix_excerpt | each stem is one clear part; no clicks | pass / fail |
| prompt_match | does the full mix obviously match the prompt in `notes`? | matches / partly / no |
| vocals_free | no voice, singing or spoken words | pass / fail |

Full WAVs are in `out/evidence/<run>/` (and `audio-pack.zip`). Re-run `make evidence-form` afterwards.
