# Styles v2: a fast, free look for the 17-minute film

Every sample here was made only with free, open tools on the studio's free Kaggle GPUs (T4, via the kodfilm farm) and this container's CPU. No paid services.
Code: `kodfilm` repo, branch `claude/project-thread-citfs0` (`studio/styles_v2.py`, `studio/parallax25d.py`, jobs in `films/styles_v2/`).

## The core idea
The reference reels are not 3D. They are painted keyframes brought to life by a video model (most likely Midjourney + Kling/Runway, which are paid).
The free equivalent is:
1. **Keyframe**: an open image model (SDXL, run on Kaggle) paints each shot. ~25 s per image on a T4; make 4 and pick one.
2. **Motion**, one of two ways:
   - **Wan 2.2 (TI2V-5B)** image-to-video: real motion (cars drive, whales swim, trees sway). Measured: **~13 min of T4 time per 2-second clip** at 1024x576.
   - **2.5D "living painting"** (our own code, no video model): depth map → camera moves through the painting with parallax, drifting brush-stroke haze, dust, light breathing. **~7 s of CPU per 2-second clip**, deterministic, zero jank, but objects themselves don't move.
3. Edit, sound, grade in the kodfilm core as before.

## The four styles
| # | Style | Like the refs | Files |
|---|---|---|---|
| 1 | Painted concept art, action | jeep, desert chase, train | `1_painted_chase_wan.mp4` |
| 2 | Living painting (painted, slow, epic) | cemetery with whales | `2_living_painting_whales_wan.mp4` vs `2_living_painting_whales_25d.mp4` |
| 3 | Stylized diorama / miniature | overgrown forest town, junkyard robot | `3_diorama_forest_wan.mp4` |
| 4 | Silhouette noir in fog | mech in fog | `4_noir_mech_wan.mp4` vs `4_noir_mech_25d.mp4` |

`0_all_styles_grid.mp4` plays all six clips side by side. `keyframes/` shows the 4 candidate keyframes per style (I picked one of each).

## Honest cost per minute of film
| Path | GPU per finished minute | 17 minutes | Notes |
|---|---|---|---|
| Keyframes only (all shots) | ~0.5 T4-hour (≈15 shots × 4 variants) | ~8 T4-hours | the cheap part |
| 2.5D for every shot | keyframes only, CPU for motion | ~1 Kaggle week on one account | camera moves only, nothing in frame acts |
| Wan i2v for every shot | ~6.5 T4-hours per take, ~16 with retakes | ~270 T4-hours | Kaggle gives 30 h/week per account; your 5 accounts ≈ 150 h/week → about 2 weeks of compute |
| **Recommended mix**: 2.5D for ~60% of shots, Wan for ~40% (action, characters moving) | ~7 T4-hours | ~110 T4-hours | under one week on the 5 accounts |

Human time is the real cost, not GPU: a shot list, picking keyframes, and re-rolling bad takes. Expect roughly 1–2 working days per finished minute once the pipeline is set.

## What is still hard (and how to handle it)
- **Same character in every shot.** SDXL won't keep a face or costume consistent on its own. Fix: train a small LoRA on each main character (≈1 hour on Kaggle each) and keep them small in frame, in silhouette, or painted loosely. Styles 1, 2 and 4 hide this best.
- **Long continuous action.** Wan clips are 2–5 s. Cut fast, as the references do.
- **Resolution.** Wan output is 1024x576; upscale to 1080p/4K with Real-ESRGAN (free) at the end.
