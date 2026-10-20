# Vendored PokéSurvivor sources

Read-only snapshot of https://github.com/JPTER78/pokesurvivor at commit `11fe868` (the game's `main` on 2026-10-20).
It includes `66610d9`, the update with the 38 new attacks. The previous pin, `5a23d49`, is kept in
`../pokesurvivor-5a23d49/` because the published CSVs were generated from it.

Only the files the harnesses execute are here (`simulator/validate/` and `simulator/v3/game_update.test.js`).
Do not edit them. Do not open a pull request, issue, or fork on that repo.

`simulator/v3/extract_v3.js` reads the full tree (`js/`) of a checkout at the same commit
to rebuild `simulator/v3/v3_data.json`.
