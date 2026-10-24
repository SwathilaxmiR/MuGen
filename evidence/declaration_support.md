# Support for 7_Declaration (you answer and sign; nothing here fills the sheet)

| Statement | Supporting evidence |
|---|---|
| Individual work; can explain and change any part | AI_USE.md lists exactly what the coding agent did; you must be able to walk through every module |
| Every claim true and backed by evidence | FORM_REPORT.md (every filled cell -> verdict -> files), evidence/INDEX.md, evidence/consistency.txt |
| All tools/models/APIs/libraries/data listed | SOURCES.md, licenses.yaml, eval/README.md, AI_USE.md, evidence/must_haves/mh4_licences/pip_licenses.csv |
| Default path and outputs licensed for commercial use | evidence/must_haves/mh4_licences/ (agpl_scan.txt, clause_check.csv); MinIO is compose/demo-only |
| No outputs edited by hand | 58 runs in the latest evidence run each have files.json (SHA-256 of every delivered file, as downloaded) next to the manifest and job id produced by the service; the audio pack is zipped from those downloads unchanged |
| No real person's voice/face/content used | the engine has no vocal programs and uses no recordings except the MIT SoundFont; narration in tests is synthetic noise ("speech-like" bursts) |
| No API keys or secrets in repo/logs/screenshots/form | evidence/security/secret_scan.txt: verdict FAIL; presigned URL signatures are stripped from every committed JSON |
| Demo and links stay up until results | not provable in advance; needs your hosting + uptime monitor |

Commit: 28bda2d802da3cfdafcdc172d99b7fc129577dbe
