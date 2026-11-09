# Geographical access to intensivist-staffed intensive care in South Korea

Code and data for: Baik SM, Lee J-M, Hong KS. "Geographical access to intensivist-staffed intensive care in an ageing population: a nationwide travel-time analysis of South Korea". *Critical Care* (submitted; **[CHECK: volume, article number and DOI at publication]**).

The study estimates how many residents live more than 60 min by road from an adult intensive care unit (ICU) with a dedicated intensivist, how this changes under population ageing to 2035, and how far staffing intensivists in existing ICUs would reduce it. Only public, aggregate data are used; there are no individual-level data.

## Repository structure

| Folder | Contents |
|---|---|
| `code/` | Pipeline scripts: `collect_*` (download) → `clean_*` (cleaning) → `analyze_*` (analysis) → `fig_all.py` (figures). `probe_*` and `inspect_*` are exploratory checks kept for transparency. |
| `data/clean/` | Cleaned and derived datasets (CSV, UTF-8 with BOM). |
| `data/raw/` | Only the small raw files that are not available elsewhere in this form (see below). |
| `docs/SOURCES.md` | Every source: URL, access date, version, licence, local path and checks (in Korean). |
| `docs/RESULTS.md`, `docs/snapfix_changes_2026-11-03.md` | Working log of every analysis step and correction (in Korean), including the hospital-connection fix found through the OSRM comparison. |
| `data/raw_manifest_sha256.csv` | Size and SHA-256 of every raw file used, including those not redistributed here. |
| `output/tables/`, `output/figures/` | Tables 1–3, Additional file 1 tables S1–S3, figures 1–4 (300 dpi PNG and TIFF). The article identifies hospitals in Tables S2 and S3 by code (H01–H28); `output/tables/hospital_codes_S2-S3.csv` maps each code to the hospital name (made by `code/make_hospital_codes.py`), and `tableS2_*`/`tableS3_*` here keep the names. |
| `docs/khqa_*` | The bookmarklet and checklist used to record intensivist indicators (see below). |

## Data not redistributed (download with the scripts)

| Data | Source | Script |
|---|---|---|
| OpenStreetMap extract for South Korea, 3 Nov 2026 | Geofabrik (ODbL) | `code/collect_osm.py` |
| Administrative-dong boundaries ver20261001 | Statistics Korea SGIS via vuski/admdongkor (CC BY 4.0) | `code/collect_boundaries.py` |
| HIRA hospital and facility files, Sept 2026 | data.go.kr (KOGL type 1) | manual download; see `docs/SOURCES.md` §1 |
| KOSIS resident population and projections | KOSIS OpenAPI | `code/collect_kosis_population.py` (needs a KOSIS API key) |
| HIRA quality-assessment grades | data.go.kr OpenAPI | `code/collect_hira_eval.py` (needs a data.go.kr API key) |

API keys are read from a local `.env` file (`DATA_GO_KR_KEY`, `KOSIS_KEY`), which is not part of this repository. Check downloaded files against `data/raw_manifest_sha256.csv`; current versions of these sources may differ from the 2026 versions used here.

## How the intensivist data were obtained

Facility-level values of the indicator "adult ICU beds per dedicated intensivist" from HIRA's fourth ICU quality assessment (2023) are published only on each institution's page of the hospital-assessment portal (khqa.kr). One author (SMB) opened each of the 297 institutions' public pages on 3 November 2026 and recorded the displayed values with the bookmarklet in `docs/khqa_bookmarklet.html`. **No automated crawling was done**, in keeping with the portal's robots exclusion policy. The recorded file is `data/raw/khqa_manual_2026-11/` (cleaned and matched version: `data/clean/icu_intensivist_khqa.csv`); matching and validation are in `code/clean_khqa_manual.py` and `output/khqa_manual_qc.md`.

## Reproducing the analysis

Python 3.12 with the packages in `requirements.txt`. Run scripts from the repository root, for example `python -I -X utf8 code/analyze_tables.py` (scripts that use pyosmium or matplotlib installed in the user site need `python -P` instead of `-I`).

1. Cleaning: `clean_icu_hospitals.py`, `clean_icu_eval_grade.py`, `clean_khqa_manual.py`, `clean_kosis_population.py`, `clean_sgg_crosswalk.py`, `clean_emd_centroids.py`, `clean_fiscal.py`, `clean_responsible.py`, `clean_emergency.py`
2. Supply and straight-line distance: `analyze_supply_sido.py`, `analyze_access_euclid.py`; road travel time: `analyze_access_road.py` (builds the road graph from the OSM extract on first run, about 1 min, and caches it)
3. Downstream: `analyze_scenarios.py data/clean/access_road_emd.csv ICU_분 전담ICU_분 분 30,60,90 road`, `analyze_equity.py`, `analyze_sensitivity.py`, `analyze_2sfca.py`, `analyze_policy.py`, `analyze_greedy_responsible.py`
4. Tables and figures: `analyze_tables.py`, `fig_all.py`; hospital code map for Tables S2 and S3: `make_hospital_codes.py`

**OSRM sensitivity analysis** (optional, needs Docker, eg in WSL2): `code/osrm_prepare.sh` builds the network with `ghcr.io/project-osrm/osrm-backend:v6.0.0` (default car profile), `code/osrm_serve.sh` starts the server, and `code/analyze_access_osrm.py` computes travel times and the comparison (`output/osrm_comparison.md`).

Column names and comments in the code are partly in Korean.

## Licences

- Code: MIT (`LICENSE`).
- Data: see `DATA_LICENSE.md`. In short, datasets derived from OpenStreetMap (travel times, 2SFCA scores, policy outputs and the maps in figure 2) are under the Open Database Licence; other derived data are under CC BY 4.0; source data remain under their original terms.

## Citation

See `CITATION.cff`. **[CHECK: add the DOI at publication]**

## Contact

Prof Seung Min Baik, Division of Critical Care Medicine, Department of Surgery, Ewha Womans University Mokdong Hospital, Seoul, Republic of Korea (baiksm@ewha.ac.kr).
