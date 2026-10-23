Model `laion/clap-htsat-unfused` (Apache-2.0), transformers 4.46.3, torch 2.5.1, device cpu, 42 outputs, 36 distinct prompts.

| case | prompt | cos(audio, own prompt) | mean cos(audio, other prompts) | rank of own prompt |
|---|---|---|---|---|
| adv_key_tempo_44k | jazz lounge | 0.188 | 0.284 | 27/36 |
| adv_loop_16s | chill lo-fi beats | 0.430 | 0.213 | 5/36 |
| adv_loop_fixed_tempo | electronic groove | 0.252 | 0.164 | 11/36 |
| adv_lufs_minus23 | calm documentary piano | 0.429 | 0.325 | 10/36 |
| adv_regenerate_drums | driving rock | 0.460 | 0.203 | 2/36 |
| d010_cinematic_sections | calm cinematic piano that builds to an uplifting peak | 0.470 | 0.289 | 6/36 |
| d030_cinematic_sections | calm cinematic piano that builds to an uplifting peak | 0.471 | 0.307 | 4/36 |
| d060_cinematic_sections | calm cinematic piano that builds to an uplifting peak | 0.460 | 0.314 | 5/36 |
| d180_cinematic_sections | calm cinematic piano that builds to an uplifting peak | 0.444 | 0.306 | 5/36 |
| hard_concurrent_1 | lofi beats | 0.289 | 0.245 | 11/36 |
| hard_concurrent_2 | epic trailer | 0.323 | 0.254 | 11/36 |
| hard_concurrent_3 | jazz lounge | 0.214 | 0.267 | 23/36 |
| hard_contradictory | calm but aggressive and fast but sleepy | 0.085 | 0.333 | 34/36 |
| hard_ending_on_beat | ambient | 0.010 | 0.289 | 34/36 |
| hard_long_300s | calm ambient meditation that slowly builds | 0.328 | 0.325 | 23/36 |
| hard_named_song | make it sound like Interstellar by Hans Zimmer, epic organ s | 0.463 | 0.255 | 3/36 |
| hard_narration_long_silences | warm acoustic guitar for a documentary | 0.351 | 0.252 | 12/36 |
| hard_narration_longer_than_music | calm ambient | 0.035 | 0.320 | 35/36 |
| hard_narration_no_speech | corporate background | 0.011 | 0.278 | 35/36 |
| hard_narration_ssrf_blocked | calm ambient | 0.001 | 0.301 | 34/36 |
| hard_same_key_twice | upbeat happy vlog | 0.418 | 0.188 | 2/36 |
| hard_section_after_end | corporate inspiring | 0.233 | 0.267 | 22/36 |
| hard_sections_close | energetic electronic track | 0.345 | 0.198 | 9/36 |
| hard_short_5_5s | corporate logo sting | 0.189 | 0.218 | 22/36 |
| hard_short_5s | playful quirky cartoon sting | 0.402 | 0.218 | 4/36 |
| hard_short_6s | tense dark hit | 0.355 | 0.319 | 18/36 |
| hard_slow_fixed_tempo | ambient pad | 0.208 | 0.326 | 29/36 |
| hard_vocals | upbeat pop song with a female singer and catchy lyrics | 0.438 | 0.197 | 3/36 |
| p01_cinematic | Epic cinematic orchestral score that builds to a heroic clim | 0.694 | 0.315 | 1/36 |
| p02_lofi | chill lo-fi beats for studying late at night | 0.496 | 0.243 | 6/36 |
| p03_corporate | upbeat corporate background for a tech product explainer | 0.316 | 0.261 | 13/36 |
| p04_electronic | energetic EDM festival track with a big drop | 0.315 | 0.181 | 9/36 |
| p05_acoustic | warm acoustic guitar folk for a travel vlog | 0.449 | 0.263 | 4/36 |
| p06_tense | tense suspense thriller underscore, dark and ominous | 0.481 | 0.333 | 5/36 |
| p07_playful | playful quirky cartoon music for kids | 0.578 | 0.269 | 1/36 |
| p08_ambient | calm ambient meditation pad, peaceful and serene | 0.353 | 0.347 | 22/36 |
| p09_epic | massive trailer battle music, epic and powerful | 0.600 | 0.277 | 2/36 |
| p10_rock | driving rock with guitar riffs for a sports montage | 0.725 | 0.211 | 1/36 |
| p11_jazz | smooth jazz lounge with saxophone | 0.613 | 0.249 | 1/36 |
| p12_upbeat | happy cheerful summer celebration | 0.425 | 0.206 | 6/36 |
| speed_60s_a_first | upbeat corporate background | 0.109 | 0.257 | 28/36 |
| speed_60s_b_second | upbeat corporate background | 0.112 | 0.262 | 30/36 |

**Matched** mean 0.347 (sd 0.180); **mismatched control** mean 0.265 (sd 0.048); matched > control in 30/42. Retrieval: top-1 4/42, top-3 9/42, chance top-1 = 0.03.

### Ours vs baseline (piano loop) on the listening-test prompts

| prompt | ours | baseline |
|---|---|---|
| Epic cinematic orchestral score that builds to a heroic clim | 0.694 | 0.180 |
| chill lo-fi beats for studying late at night | 0.496 | 0.401 |
| energetic EDM festival track with a big drop | 0.315 | 0.184 |
| tense suspense thriller underscore, dark and ominous | 0.481 | 0.112 |
| playful quirky cartoon music for kids | 0.578 | 0.382 |
| smooth jazz lounge with saxophone | 0.613 | 0.363 |

Ours scores higher than the baseline on 6/6 prompts.
