# Setup

Everything on the profile is generated from `data/profile.json` and one photo,
then committed by a GitHub Action. No hosted card services, no third party
reading your stats.

```
README.md
data/profile.json          single source of truth for the info card
scripts/gen_ascii.py       assets/source-photo.jpg -> assets/ascii-portrait.svg
scripts/gen_info_card.py   data/profile.json       -> assets/info-card.svg
scripts/gen_heatmap.py     GitHub GraphQL          -> assets/contrib-heatmap.svg
.github/workflows/refresh.yml
assets/                    committed output (and the source photo)
build/                     local-only proofs, gitignored
```

## 1. Install

Python 3.9+. Pillow is the only dependency, and only `gen_ascii.py` needs it —
the other two scripts are standard library.

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install pillow
```

## 2. Add your photo

Put it at **`assets/source-photo.jpg`**. It must be committed — the workflow
reads it from the repo, not from your machine.

- A head-and-shoulders crop works best. The card is 400×578, so anything from
  square to 3:4 portrait fills it well.
- **Shoot or pick a photo with a dark background.** The card is dark and the
  glyphs are bright, so `INVERT = True` in `scripts/gen_ascii.py` maps *bright*
  pixels to the densest characters: your lit face inks up, the background thins
  out to whitespace. If your only photo has a bright background (a window, a
  white wall), set `ascii.invert` to `false` in `data/profile.json` — otherwise
  the background is what inks up and you disappear into it.
- Contrast matters more than resolution. If the result looks like mush, adjust
  the crop and contrast in any photo editor and re-run; `build/ascii-preprocessed.png`
  shows exactly what the sampler saw after grayscale and autocontrast.

## 3. Run locally

```bash
python3 scripts/gen_info_card.py
```

```bash
python3 scripts/gen_ascii.py
```

```bash
GH_TOKEN=ghp_xxx GH_USERNAME=Riicko-19 python3 scripts/gen_heatmap.py
```

To check the heatmap renderer without a token — layout, grid alignment,
intensity buckets — use synthetic data. **Do not commit that output**; the
workflow will overwrite it with real data on the next run anyway.

```bash
python3 scripts/gen_heatmap.py --synthetic
```

`gen_heatmap.py` exits 0 with a message if `GH_TOKEN` or `GH_USERNAME` is
unset, so it never blocks the rest of a run.

To eyeball the result the way GitHub will show it, open `scripts/preview.html`
in a browser — it composes the three SVGs at their README widths on GitHub's
dark background.

## 4. Editing content

Change `data/profile.json` and re-run `gen_info_card.py`. Name, tagline,
education, location, every highlight, every stack group, and all six theme
colours live there. You should never have to touch the SVG or the layout code.

Two things the layout code enforces for you:

- Long text is word-wrapped to the card width automatically.
- If the content grows past the bottom of the card, `gen_info_card.py` **exits
  1 with the overflow in pixels** instead of drawing outside the box. Either
  shorten a highlight detail or raise `card.height` (currently `578`). If you
  raise it, the ASCII card follows automatically — both read the same value, so
  they stay the same height side by side.

## 5. Publish

```bash
git remote add origin https://github.com/Riicko-19/Riicko-19.git
git branch -M main && git push -u origin main
```

The repo must be named exactly `Riicko-19` and be **public** for GitHub to
render it as your profile README.

The first push triggers `.github/workflows/refresh.yml`, which generates the
portrait and heatmap and commits them. Until that run finishes, the two
`<img>` tags for `ascii-portrait.svg` and `contrib-heatmap.svg` will show as
broken — that is expected, they are deliberately not committed with fake data.
After that it runs daily at 04:17 UTC, on any push touching `data/`, `scripts/`
or the photo, and on demand from the Actions tab.

## 6. If the heatmap comes back empty

The workflow's built-in `GITHUB_TOKEN` can normally read
`contributionsCollection`, but this is not contractual and has broken before.
If a run fails with a GraphQL error or reports 0 contributions:

1. Create a **classic** personal access token (not fine-grained — fine-grained
   tokens do not currently cover the contributions API) at
   **Settings → Developer settings → Personal access tokens → Tokens (classic)**,
   with only the **`read:user`** scope.
2. Add it to this repo under **Settings → Secrets and variables → Actions →
   New repository secret**, named **`GH_PAT`**.

The workflow already prefers `GH_PAT` when it exists and falls back to
`GITHUB_TOKEN` otherwise — no edit needed:

```yaml
GH_TOKEN: ${{ secrets.GH_PAT || secrets.GITHUB_TOKEN }}
```

Set a calendar reminder for the token's expiry; the workflow will start failing
loudly (non-zero exit, red run) rather than quietly publishing a blank chart.

## Placeholders to fill in

| Where | What | Why |
|---|---|---|
| `assets/source-photo.jpg` | **Missing — you must add it.** | Nothing generates the portrait until this exists. The workflow skips the step cleanly and the README image stays broken. |
| `data/profile.json` → `identity.education` | Currently `B.Tech CSE (AI/ML) · Presidency University` | Add a graduation year if you want one; there is room on the line. |
| `data/profile.json` → `highlights.items[].detail` | Full project descriptions as you gave them | Verify the wrapping still pleases you after any edit — the card reports its remaining headroom on every run. |
| `data/profile.json` → `theme.bg_via` (`#203a43`) | **My addition.** | You specified `#0f2027 → #2c5364`. A two-stop gradient across a tall card banded slightly, so I added the conventional midpoint of that palette. Delete the `55%` stop in all three scripts if you want the strict two-stop version. |
| `README.md` badge row | LinkedIn, Email, GitHub | Add a portfolio badge here if you stand one up. |
| Repo secret `GH_PAT` | Only if section 6 applies | Not needed unless the default token fails. |
