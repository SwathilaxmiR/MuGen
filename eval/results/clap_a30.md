Model `laion/clap-htsat-unfused` (Apache-2.0), transformers 4.46.3, torch 2.5.1, device cpu, 5 outputs, 5 distinct prompts.

| case | prompt | cos(audio, own prompt) | mean cos(audio, other prompts) | rank of own prompt |
|---|---|---|---|---|
| p01_cinematic | Epic cinematic orchestral score that builds to a heroic clim | 0.708 | 0.359 | 1/5 |
| p02_lofi | chill lo-fi beats for studying late at night | 0.456 | 0.286 | 2/5 |
| p04_electronic | energetic EDM festival track with a big drop | 0.324 | 0.273 | 2/5 |
| p06_tense | tense suspense thriller underscore, dark and ominous | 0.468 | 0.417 | 2/5 |
| p11_jazz | smooth jazz lounge with saxophone | 0.582 | 0.292 | 1/5 |

**Matched** mean 0.508 (sd 0.130); **mismatched control** mean 0.326 (sd 0.055); matched > control in 5/5. Retrieval: top-1 2/5, top-3 5/5, chance top-1 = 0.20.
