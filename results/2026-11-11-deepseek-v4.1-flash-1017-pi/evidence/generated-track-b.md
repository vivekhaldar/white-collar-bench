# white-collar-bench report

- Run: `/home/user/workspace/repo/runs/pi-deepseek-v41-flash-1017/track-b/measured` (Track B, status completed)
- Adapter: pi-nebius-deepseek-v41-flash-1017 pi-1.5.2-runtime-v1 (model nebius/deepseek-ai/DeepSeek-V4.1-Flash-1017)
- Judge: heuristic
- Scored at 2026-11-12T03:21:08+00:00 with wcb 0.1.0 (scorer 0.1); run made with wcb 0.1.0

## Headline

| Metric | Value |
|---|---|
| WCB score | 67.5 [95% CI 61.8, 71.9] |
| Synthesis score (oracle store) | n/a |
| Ingestion cost (Synthesis - WCB) | n/a |
| Worlds / episodes / questions | 11 / 11 / 745 |

Scores are on a 0-100 scale. The interval is a 95% bootstrap over worlds; with one world it is degenerate.

## By world and repeat

| World | Repeat | WCB | Synthesis | Ingestion cost | SIS | SIS final |
|---|---|---|---|---|---|---|
| gen-s8-w4 | r1 | 64.1 | n/a | n/a | n/a | n/a |
| gen-s4-w2 | r1 | 69.7 | n/a | n/a | n/a | n/a |
| gen-s7-w2 | r1 | 67.4 | n/a | n/a | n/a | n/a |
| gen-s10-w2-small | r1 | 62.9 | n/a | n/a | n/a | n/a |
| pilot | r1 | 46.2 | n/a | n/a | n/a | n/a |
| gen-s9-large | r1 | 71.8 | n/a | n/a | n/a | n/a |
| gen-s1-w1 | r1 | 76.9 | n/a | n/a | n/a | n/a |
| gen-s2-w1 | r1 | 72.8 | n/a | n/a | n/a | n/a |
| gen-s3-w1 | r1 | 72.3 | n/a | n/a | n/a | n/a |
| gen-s5-small | r1 | 62.2 | n/a | n/a | n/a | n/a |
| gen-s6-w1 | r1 | 76.0 | n/a | n/a | n/a | n/a |

## By question type

| Type | n | WCB | Synthesis | Ingestion cost |
|---|---|---|---|---|
| point | 187 | 72.7 | n/a | n/a |
| list | 165 | 58.1 | n/a | n/a |
| status | 52 | 59.9 | n/a | n/a |
| brief | 77 | 59.8 | n/a | n/a |
| change | 52 | 24.3 | n/a | n/a |
| temporal | 85 | 88.4 | n/a | n/a |
| priority | 51 | 69.3 | n/a | n/a |
| unanswerable | 76 | 97.4 | n/a | n/a |

Mean question score per type over all checkpoints and repeats. Unanswerable questions form their own bucket.

## By planted challenge

| Challenge | n | WCB | Synthesis | Ingestion cost |
|---|---|---|---|---|
| acceptance_vs_occurrence | 2 | 50.0 | n/a | n/a |
| alias | 161 | 60.8 | n/a | n/a |
| batch_catchup | 65 | 61.1 | n/a | n/a |
| correction | 56 | 56.0 | n/a | n/a |
| draft_vs_sent | 1 | 0.0 | n/a | n/a |
| duplicate_signal | 211 | 66.6 | n/a | n/a |
| endorsement | 127 | 62.9 | n/a | n/a |
| implied_commitment | 130 | 61.4 | n/a | n/a |
| name_collision | 56 | 59.2 | n/a | n/a |
| new_entity | 130 | 59.5 | n/a | n/a |
| noise | 1 | 0.0 | n/a | n/a |
| restructuring | 67 | 52.9 | n/a | n/a |
| reversal | 12 | 63.6 | n/a | n/a |
| scattered_evidence | 70 | 63.2 | n/a | n/a |
| silent_closure | 14 | 41.4 | n/a | n/a |
| supersession | 113 | 65.7 | n/a | n/a |
| transfer | 69 | 60.1 | n/a | n/a |
| unobservable | 129 | 81.2 | n/a | n/a |
| version_mismatch | 7 | 63.7 | n/a | n/a |
| weak_evidence | 12 | 83.3 | n/a | n/a |
| worker_directive | 92 | 64.1 | n/a | n/a |

## By checkpoint

| World | Checkpoint | Date | Episode day | Questions | WCB | Synthesis | Ingestion cost |
|---|---|---|---|---|---|---|---|
| gen-s8-w4 | cp1 | 2027-09-14 | 2 of 24 | 15 | 66.3 | n/a | n/a |
| gen-s8-w4 | cp2 | 2027-09-16 | 4 of 24 | 15 | 65.1 | n/a | n/a |
| gen-s8-w4 | cp3 | 2027-09-18 | 6 of 24 | 15 | 63.6 | n/a | n/a |
| gen-s8-w4 | cp4 | 2027-09-21 | 8 of 24 | 15 | 71.6 | n/a | n/a |
| gen-s8-w4 | cp5 | 2027-09-23 | 10 of 24 | 15 | 52.7 | n/a | n/a |
| gen-s8-w4 | cp6 | 2027-09-25 | 12 of 24 | 15 | 77.4 | n/a | n/a |
| gen-s8-w4 | cp7 | 2027-09-28 | 14 of 24 | 15 | 66.2 | n/a | n/a |
| gen-s8-w4 | cp8 | 2027-09-30 | 16 of 24 | 15 | 67.7 | n/a | n/a |
| gen-s8-w4 | cp9 | 2027-10-02 | 18 of 24 | 15 | 56.2 | n/a | n/a |
| gen-s8-w4 | cp10 | 2027-10-05 | 20 of 24 | 15 | 56.8 | n/a | n/a |
| gen-s8-w4 | cp11 | 2027-10-07 | 22 of 24 | 15 | 62.4 | n/a | n/a |
| gen-s8-w4 | cp12 | 2027-10-09 | 24 of 24 | 15 | 62.6 | n/a | n/a |
| gen-s4-w2 | cp1 | 2027-09-07 | 2 of 12 | 15 | 74.4 | n/a | n/a |
| gen-s4-w2 | cp2 | 2027-09-09 | 4 of 12 | 15 | 75.0 | n/a | n/a |
| gen-s4-w2 | cp3 | 2027-09-11 | 6 of 12 | 15 | 66.4 | n/a | n/a |
| gen-s4-w2 | cp4 | 2027-09-14 | 8 of 12 | 15 | 74.2 | n/a | n/a |
| gen-s4-w2 | cp5 | 2027-09-16 | 10 of 12 | 15 | 65.6 | n/a | n/a |
| gen-s4-w2 | cp6 | 2027-09-18 | 12 of 12 | 15 | 62.7 | n/a | n/a |
| gen-s7-w2 | cp1 | 2027-07-06 | 2 of 12 | 15 | 71.6 | n/a | n/a |
| gen-s7-w2 | cp2 | 2027-07-08 | 4 of 12 | 15 | 76.2 | n/a | n/a |
| gen-s7-w2 | cp3 | 2027-07-10 | 6 of 12 | 15 | 70.4 | n/a | n/a |
| gen-s7-w2 | cp4 | 2027-07-13 | 8 of 12 | 15 | 60.4 | n/a | n/a |
| gen-s7-w2 | cp5 | 2027-07-15 | 10 of 12 | 15 | 73.5 | n/a | n/a |
| gen-s7-w2 | cp6 | 2027-07-17 | 12 of 12 | 15 | 52.3 | n/a | n/a |
| gen-s10-w2-small | cp1 | 2027-08-31 | 2 of 11 | 11 | 67.7 | n/a | n/a |
| gen-s10-w2-small | cp2 | 2027-09-02 | 4 of 11 | 11 | 63.4 | n/a | n/a |
| gen-s10-w2-small | cp3 | 2027-09-03 | 5 of 11 | 11 | 53.7 | n/a | n/a |
| gen-s10-w2-small | cp4 | 2027-09-07 | 7 of 11 | 11 | 75.1 | n/a | n/a |
| gen-s10-w2-small | cp5 | 2027-09-09 | 9 of 11 | 11 | 63.9 | n/a | n/a |
| gen-s10-w2-small | cp6 | 2027-09-11 | 11 of 11 | 11 | 53.6 | n/a | n/a |
| pilot | cp1 | 2027-03-02 | 2 of 6 | 14 | 59.9 | n/a | n/a |
| pilot | cp2 | 2027-03-04 | 4 of 6 | 17 | 28.1 | n/a | n/a |
| pilot | cp3 | 2027-03-06 | 6 of 6 | 21 | 50.6 | n/a | n/a |
| gen-s9-large | cp1 | 2027-11-02 | 2 of 6 | 18 | 77.6 | n/a | n/a |
| gen-s9-large | cp2 | 2027-11-04 | 4 of 6 | 18 | 64.2 | n/a | n/a |
| gen-s9-large | cp3 | 2027-11-06 | 6 of 6 | 18 | 73.7 | n/a | n/a |
| gen-s1-w1 | cp1 | 2027-11-09 | 2 of 6 | 15 | 75.1 | n/a | n/a |
| gen-s1-w1 | cp2 | 2027-11-11 | 4 of 6 | 15 | 75.0 | n/a | n/a |
| gen-s1-w1 | cp3 | 2027-11-13 | 6 of 6 | 15 | 80.7 | n/a | n/a |
| gen-s2-w1 | cp1 | 2027-03-09 | 2 of 5 | 15 | 65.8 | n/a | n/a |
| gen-s2-w1 | cp2 | 2027-03-11 | 4 of 5 | 15 | 73.3 | n/a | n/a |
| gen-s2-w1 | cp3 | 2027-03-12 | 5 of 5 | 15 | 79.3 | n/a | n/a |
| gen-s3-w1 | cp1 | 2027-09-21 | 2 of 6 | 15 | 70.0 | n/a | n/a |
| gen-s3-w1 | cp2 | 2027-09-23 | 4 of 6 | 15 | 80.9 | n/a | n/a |
| gen-s3-w1 | cp3 | 2027-09-25 | 6 of 6 | 15 | 66.0 | n/a | n/a |
| gen-s5-small | cp1 | 2027-03-30 | 2 of 6 | 11 | 65.8 | n/a | n/a |
| gen-s5-small | cp2 | 2027-04-01 | 4 of 6 | 11 | 65.3 | n/a | n/a |
| gen-s5-small | cp3 | 2027-04-03 | 6 of 6 | 11 | 55.6 | n/a | n/a |
| gen-s6-w1 | cp1 | 2027-02-23 | 2 of 6 | 15 | 74.0 | n/a | n/a |
| gen-s6-w1 | cp2 | 2027-02-25 | 4 of 6 | 15 | 78.0 | n/a | n/a |
| gen-s6-w1 | cp3 | 2027-02-27 | 6 of 6 | 15 | 76.0 | n/a | n/a |

## Efficiency

| Sessions | n | Wall s (total) | Wall s (mean) | Input tokens | Output tokens | Cost USD | Timeouts | Failures | Usage reported | Metered |
|---|---|---|---|---|---|---|---|---|---|---|
| Ingestion | 111 | 79133.6 | 712.9 | 966706672 | 6218295 | 54.88 | 0 | 3 | 111 | 111 |
| Query (agent store) | 51 | 11639.3 | 228.2 | 57338574 | 870860 | 9.61 | 0 | 0 | 51 | 51 |

Per episode (agent sessions): 8252.1 s, 93095022 input tokens, 644469 output tokens, $5.86. Token counts are measured for metered sessions (`wcb run --meter`) and self-reported otherwise; cost is always self-reported.

### Per ingestion day

| World | Date | n | Wall s | Input tokens | Output tokens | Cost USD | Status |
|---|---|---|---|---|---|---|---|
| gen-s1-w1 | 2027-11-06 | 1 | 768.3 | 6234221 | 63800 | 0.41 | ok |
| gen-s1-w1 | 2027-11-08 | 1 | 393.3 | 3453876 | 29315 | 0.24 | ok |
| gen-s1-w1 | 2027-11-09 | 1 | 443.9 | 2670734 | 33433 | 0.26 | ok |
| gen-s1-w1 | 2027-11-10 | 1 | 579.0 | 4710172 | 50413 | 0.36 | ok |
| gen-s1-w1 | 2027-11-11 | 1 | 483.5 | 4069754 | 45056 | 0.40 | ok |
| gen-s1-w1 | 2027-11-12 | 1 | 499.0 | 4455746 | 44151 | 0.35 | ok |
| gen-s1-w1 | 2027-11-13 | 1 | 178.1 | 1208171 | 14194 | 0.15 | ok |
| gen-s10-w2-small | 2027-08-27 | 1 | 706.8 | 3069532 | 54428 | 0.32 | ok |
| gen-s10-w2-small | 2027-08-30 | 1 | 221.0 | 1030352 | 22164 | 0.15 | ok |
| gen-s10-w2-small | 2027-08-31 | 1 | 326.6 | 2854644 | 28326 | 0.23 | ok |
| gen-s10-w2-small | 2027-09-01 | 1 | 654.3 | 5996779 | 64514 | 0.45 | ok |
| gen-s10-w2-small | 2027-09-02 | 1 | 802.3 | 8644072 | 69841 | 0.54 | ok |
| gen-s10-w2-small | 2027-09-03 | 1 | 613.9 | 6099650 | 52955 | 0.47 | ok |
| gen-s10-w2-small | 2027-09-06 | 1 | 829.7 | 10243074 | 58468 | 0.54 | ok |
| gen-s10-w2-small | 2027-09-07 | 1 | 558.1 | 6593958 | 45898 | 0.48 | ok |
| gen-s10-w2-small | 2027-09-08 | 1 | 663.8 | 9789995 | 58535 | 0.64 | ok |
| gen-s10-w2-small | 2027-09-09 | 1 | 1115.7 | 19307682 | 83926 | 0.82 | ok |
| gen-s10-w2-small | 2027-09-10 | 1 | 961.4 | 16762649 | 74849 | 0.73 | ok |
| gen-s10-w2-small | 2027-09-11 | 1 | 408.5 | 4963210 | 30797 | 0.47 | ok |
| gen-s2-w1 | 2027-03-06 | 1 | 1013.6 | 9059378 | 104580 | 0.64 | ok |
| gen-s2-w1 | 2027-03-08 | 1 | 329.7 | 2200606 | 35083 | 0.24 | ok |
| gen-s2-w1 | 2027-03-09 | 1 | 432.4 | 3783232 | 38525 | 0.28 | ok |
| gen-s2-w1 | 2027-03-10 | 1 | 488.7 | 3986247 | 39518 | 0.33 | ok |
| gen-s2-w1 | 2027-03-11 | 1 | 738.1 | 6469660 | 56236 | 0.43 | ok |
| gen-s2-w1 | 2027-03-12 | 1 | 662.8 | 6753980 | 50883 | 0.42 | ok |
| gen-s3-w1 | 2027-09-17 | 1 | 730.6 | 4923270 | 76305 | 0.44 | ok |
| gen-s3-w1 | 2027-09-20 | 1 | 397.0 | 3378461 | 40041 | 0.28 | ok |
| gen-s3-w1 | 2027-09-21 | 1 | 601.5 | 6203333 | 50630 | 0.38 | ok |
| gen-s3-w1 | 2027-09-22 | 1 | 765.2 | 9262070 | 56431 | 0.49 | ok |
| gen-s3-w1 | 2027-09-23 | 1 | 1070.8 | 10776475 | 81362 | 0.57 | ok |
| gen-s3-w1 | 2027-09-24 | 1 | 1019.0 | 9035653 | 64301 | 0.49 | ok |
| gen-s3-w1 | 2027-09-25 | 1 | 467.0 | 3458044 | 27953 | 0.35 | ok |
| gen-s4-w2 | 2027-09-04 | 1 | 1241.4 | 11029881 | 100672 | 0.60 | ok |
| gen-s4-w2 | 2027-09-06 | 1 | 322.2 | 3226063 | 26051 | 0.27 | ok |
| gen-s4-w2 | 2027-09-07 | 1 | 539.8 | 5563744 | 49299 | 0.37 | ok |
| gen-s4-w2 | 2027-09-08 | 1 | 673.8 | 7446261 | 62926 | 0.48 | ok |
| gen-s4-w2 | 2027-09-09 | 1 | 721.5 | 9425519 | 58887 | 0.50 | ok |
| gen-s4-w2 | 2027-09-10 | 1 | 814.8 | 8358799 | 61524 | 0.51 | ok |
| gen-s4-w2 | 2027-09-11 | 1 | 173.7 | 1583091 | 13432 | 0.21 | ok |
| gen-s4-w2 | 2027-09-13 | 1 | 781.9 | 12801062 | 66546 | 0.61 | ok |
| gen-s4-w2 | 2027-09-14 | 1 | 728.1 | 9687410 | 57398 | 0.54 | ok |
| gen-s4-w2 | 2027-09-15 | 1 | 792.6 | 11284636 | 65013 | 0.56 | ok |
| gen-s4-w2 | 2027-09-16 | 1 | 839.0 | 12829921 | 65788 | 0.73 | ok |
| gen-s4-w2 | 2027-09-17 | 1 | 894.9 | 18110915 | 69999 | 0.77 | ok |
| gen-s4-w2 | 2027-09-18 | 1 | 393.2 | 4902925 | 29921 | 0.46 | ok |
| gen-s5-small | 2027-03-27 | 1 | 624.8 | 2333909 | 42473 | 0.26 | ok |
| gen-s5-small | 2027-03-29 | 1 | 507.0 | 2105501 | 32374 | 0.21 | ok |
| gen-s5-small | 2027-03-30 | 1 | 336.7 | 1263028 | 23484 | 0.16 | ok |
| gen-s5-small | 2027-03-31 | 1 | 470.4 | 2210359 | 31319 | 0.21 | ok |
| gen-s5-small | 2027-04-01 | 1 | 965.4 | 8725675 | 61209 | 0.46 | ok |
| gen-s5-small | 2027-04-02 | 1 | 666.6 | 5559396 | 45615 | 0.40 | ok |
| gen-s5-small | 2027-04-03 | 1 | 250.5 | 1128576 | 13773 | 0.15 | ok |
| gen-s6-w1 | 2027-02-19 | 1 | 1384.4 | 6493314 | 94471 | 0.47 | ok |
| gen-s6-w1 | 2027-02-22 | 1 | 774.9 | 6841319 | 52642 | 0.40 | ok |
| gen-s6-w1 | 2027-02-23 | 1 | 671.4 | 5255528 | 47353 | 0.38 | ok |
| gen-s6-w1 | 2027-02-24 | 1 | 685.9 | 6129090 | 46271 | 0.38 | ok |
| gen-s6-w1 | 2027-02-25 | 1 | 1285.4 | 10556194 | 75475 | 0.65 | ok |
| gen-s6-w1 | 2027-02-26 | 1 | 1280.2 | 12842583 | 65623 | 0.55 | ok |
| gen-s6-w1 | 2027-02-27 | 1 | 359.7 | 2663205 | 14739 | 0.24 | ok |
| gen-s7-w2 | 2027-07-03 | 1 | 1198.8 | 12071496 | 93037 | 0.56 | ok |
| gen-s7-w2 | 2027-07-05 | 1 | 365.1 | 2652324 | 35411 | 0.23 | ok |
| gen-s7-w2 | 2027-07-06 | 1 | 560.8 | 3698892 | 59194 | 0.36 | ok |
| gen-s7-w2 | 2027-07-07 | 1 | 635.9 | 5093832 | 62444 | 0.42 | ok |
| gen-s7-w2 | 2027-07-08 | 1 | 541.1 | 5560602 | 47868 | 0.39 | ok |
| gen-s7-w2 | 2027-07-09 | 1 | 802.1 | 7240297 | 52670 | 0.44 | ok |
| gen-s7-w2 | 2027-07-10 | 1 | 291.5 | 2771284 | 20953 | 0.27 | ok |
| gen-s7-w2 | 2027-07-12 | 1 | 457.3 | 4365188 | 45229 | 0.36 | ok |
| gen-s7-w2 | 2027-07-13 | 1 | 702.9 | 11067110 | 56881 | 0.62 | ok |
| gen-s7-w2 | 2027-07-14 | 1 | 990.8 | 16975108 | 71291 | 0.73 | ok |
| gen-s7-w2 | 2027-07-15 | 1 | 587.4 | 6442081 | 49968 | 0.48 | ok |
| gen-s7-w2 | 2027-07-16 | 1 | 932.2 | 18097583 | 66569 | 0.69 | failed |
| gen-s7-w2 | 2027-07-17 | 1 | 314.0 | 4234530 | 21727 | 0.36 | ok |
| gen-s8-w4 | 2027-09-10 | 1 | 984.4 | 8075611 | 75489 | 0.48 | ok |
| gen-s8-w4 | 2027-09-13 | 1 | 488.6 | 4646778 | 41381 | 0.36 | ok |
| gen-s8-w4 | 2027-09-14 | 1 | 547.7 | 5207063 | 48696 | 0.33 | ok |
| gen-s8-w4 | 2027-09-15 | 1 | 679.8 | 8002325 | 54136 | 0.42 | ok |
| gen-s8-w4 | 2027-09-16 | 1 | 789.7 | 10441730 | 60887 | 0.48 | ok |
| gen-s8-w4 | 2027-09-17 | 1 | 705.4 | 7315609 | 51378 | 0.49 | ok |
| gen-s8-w4 | 2027-09-18 | 1 | 414.8 | 4947130 | 33611 | 0.33 | ok |
| gen-s8-w4 | 2027-09-20 | 1 | 847.7 | 12380664 | 78282 | 0.58 | ok |
| gen-s8-w4 | 2027-09-21 | 1 | 691.4 | 11293515 | 55316 | 0.61 | ok |
| gen-s8-w4 | 2027-09-22 | 1 | 913.8 | 17168946 | 64937 | 0.75 | ok |
| gen-s8-w4 | 2027-09-23 | 1 | 1026.4 | 18113456 | 83418 | 0.79 | ok |
| gen-s8-w4 | 2027-09-24 | 1 | 1083.3 | 22612086 | 79814 | 0.90 | ok |
| gen-s8-w4 | 2027-09-25 | 1 | 655.4 | 11012315 | 47654 | 0.60 | ok |
| gen-s8-w4 | 2027-09-27 | 1 | 1006.5 | 17680641 | 75559 | 0.78 | ok |
| gen-s8-w4 | 2027-09-28 | 1 | 826.4 | 17414328 | 62859 | 0.74 | ok |
| gen-s8-w4 | 2027-09-29 | 1 | 652.8 | 9910626 | 55601 | 0.61 | ok |
| gen-s8-w4 | 2027-09-30 | 1 | 1007.8 | 24936958 | 82706 | 1.05 | ok |
| gen-s8-w4 | 2027-10-01 | 1 | 874.2 | 21879305 | 70080 | 0.87 | ok |
| gen-s8-w4 | 2027-10-02 | 1 | 374.5 | 5000038 | 26485 | 0.50 | ok |
| gen-s8-w4 | 2027-10-04 | 1 | 921.3 | 18034425 | 61468 | 0.87 | ok |
| gen-s8-w4 | 2027-10-05 | 1 | 991.8 | 22527450 | 65190 | 0.95 | ok |
| gen-s8-w4 | 2027-10-06 | 1 | 869.9 | 11090952 | 53468 | 0.86 | ok |
| gen-s8-w4 | 2027-10-07 | 1 | 1042.8 | 19220877 | 66245 | 0.92 | ok |
| gen-s8-w4 | 2027-10-08 | 1 | 1012.9 | 19014367 | 64078 | 0.80 | ok |
| gen-s8-w4 | 2027-10-09 | 1 | 469.3 | 9111165 | 24231 | 0.59 | ok |
| gen-s9-large | 2027-10-29 | 1 | 655.3 | 3306953 | 63516 | 0.37 | ok |
| gen-s9-large | 2027-11-01 | 1 | 455.0 | 3771855 | 35972 | 0.29 | ok |
| gen-s9-large | 2027-11-02 | 1 | 430.6 | 2791552 | 38159 | 0.25 | ok |
| gen-s9-large | 2027-11-03 | 1 | 619.9 | 6294035 | 52176 | 0.46 | ok |
| gen-s9-large | 2027-11-04 | 1 | 723.3 | 8621200 | 64287 | 0.46 | ok |
| gen-s9-large | 2027-11-05 | 1 | 597.5 | 6169251 | 57939 | 0.46 | ok |
| gen-s9-large | 2027-11-06 | 1 | 185.2 | 1974247 | 13967 | 0.24 | ok |
| pilot | 2027-02-26 | 1 | 1676.9 | 13406288 | 150919 | 0.75 | ok |
| pilot | 2027-03-01 | 1 | 1261.2 | 15237431 | 102693 | 0.72 | ok |
| pilot | 2027-03-02 | 1 | 999.3 | 10770059 | 98754 | 0.63 | ok |
| pilot | 2027-03-03 | 1 | 756.8 | 10508928 | 66367 | 0.53 | ok |
| pilot | 2027-03-04 | 1 | 1191.2 | 21013548 | 113207 | 0.80 | failed |
| pilot | 2027-03-05 | 1 | 1408.7 | 23765686 | 110422 | 0.87 | failed |
| pilot | 2027-03-06 | 1 | 809.9 | 9960368 | 62518 | 0.59 | ok |

### Per query session

| World | Checkpoint | Store | n | Wall s | Input tokens | Output tokens | Cost USD | Status |
|---|---|---|---|---|---|---|---|---|
| gen-s1-w1 | cp1 | agent | 1 | 166.7 | 451246 | 14868 | 0.08 | ok |
| gen-s1-w1 | cp2 | agent | 1 | 154.4 | 636000 | 13902 | 0.13 | ok |
| gen-s1-w1 | cp3 | agent | 1 | 189.0 | 707734 | 16804 | 0.18 | ok |
| gen-s10-w2-small | cp1 | agent | 1 | 136.9 | 426103 | 11506 | 0.09 | ok |
| gen-s10-w2-small | cp2 | agent | 1 | 166.1 | 576233 | 13919 | 0.10 | ok |
| gen-s10-w2-small | cp3 | agent | 1 | 380.7 | 1854676 | 21052 | 0.25 | ok |
| gen-s10-w2-small | cp4 | agent | 1 | 196.1 | 1278853 | 16470 | 0.19 | ok |
| gen-s10-w2-small | cp5 | agent | 1 | 185.2 | 879430 | 14270 | 0.18 | ok |
| gen-s10-w2-small | cp6 | agent | 1 | 142.5 | 844120 | 12562 | 0.14 | ok |
| gen-s2-w1 | cp1 | agent | 1 | 211.6 | 996199 | 17641 | 0.19 | ok |
| gen-s2-w1 | cp2 | agent | 1 | 221.5 | 755499 | 18097 | 0.14 | ok |
| gen-s2-w1 | cp3 | agent | 1 | 231.3 | 742078 | 16123 | 0.14 | ok |
| gen-s3-w1 | cp1 | agent | 1 | 137.5 | 499880 | 10606 | 0.10 | ok |
| gen-s3-w1 | cp2 | agent | 1 | 263.5 | 1453286 | 15908 | 0.20 | ok |
| gen-s3-w1 | cp3 | agent | 1 | 279.3 | 1138755 | 15936 | 0.17 | ok |
| gen-s4-w2 | cp1 | agent | 1 | 197.3 | 1130847 | 17279 | 0.18 | ok |
| gen-s4-w2 | cp2 | agent | 1 | 315.7 | 740225 | 20584 | 0.17 | ok |
| gen-s4-w2 | cp3 | agent | 1 | 193.7 | 659475 | 16528 | 0.16 | ok |
| gen-s4-w2 | cp4 | agent | 1 | 178.4 | 1277994 | 14264 | 0.16 | ok |
| gen-s4-w2 | cp5 | agent | 1 | 274.1 | 2078675 | 19998 | 0.27 | ok |
| gen-s4-w2 | cp6 | agent | 1 | 154.4 | 745610 | 12367 | 0.18 | ok |
| gen-s5-small | cp1 | agent | 1 | 203.2 | 620786 | 13512 | 0.10 | ok |
| gen-s5-small | cp2 | agent | 1 | 218.8 | 754402 | 18458 | 0.14 | ok |
| gen-s5-small | cp3 | agent | 1 | 222.8 | 625302 | 13982 | 0.12 | ok |
| gen-s6-w1 | cp1 | agent | 1 | 255.5 | 999826 | 20679 | 0.11 | ok |
| gen-s6-w1 | cp2 | agent | 1 | 290.2 | 981694 | 15229 | 0.17 | ok |
| gen-s6-w1 | cp3 | agent | 1 | 444.5 | 961941 | 19622 | 0.16 | ok |
| gen-s7-w2 | cp1 | agent | 1 | 204.3 | 1238774 | 17656 | 0.21 | ok |
| gen-s7-w2 | cp2 | agent | 1 | 268.6 | 978691 | 19665 | 0.17 | ok |
| gen-s7-w2 | cp3 | agent | 1 | 208.1 | 979038 | 18272 | 0.19 | ok |
| gen-s7-w2 | cp4 | agent | 1 | 242.1 | 1624075 | 17630 | 0.23 | ok |
| gen-s7-w2 | cp5 | agent | 1 | 186.0 | 1141539 | 15884 | 0.23 | ok |
| gen-s7-w2 | cp6 | agent | 1 | 236.0 | 1954611 | 17642 | 0.25 | ok |
| gen-s8-w4 | cp1 | agent | 1 | 174.4 | 688953 | 15038 | 0.14 | ok |
| gen-s8-w4 | cp10 | agent | 1 | 266.3 | 1760960 | 14414 | 0.28 | ok |
| gen-s8-w4 | cp11 | agent | 1 | 220.0 | 1596720 | 12079 | 0.25 | ok |
| gen-s8-w4 | cp12 | agent | 1 | 262.3 | 1146656 | 16472 | 0.24 | ok |
| gen-s8-w4 | cp2 | agent | 1 | 307.2 | 1461104 | 18670 | 0.24 | ok |
| gen-s8-w4 | cp3 | agent | 1 | 194.3 | 742657 | 17696 | 0.18 | ok |
| gen-s8-w4 | cp4 | agent | 1 | 236.2 | 1027660 | 19558 | 0.22 | ok |
| gen-s8-w4 | cp5 | agent | 1 | 200.6 | 1106704 | 17268 | 0.26 | ok |
| gen-s8-w4 | cp6 | agent | 1 | 156.5 | 589406 | 13760 | 0.17 | ok |
| gen-s8-w4 | cp7 | agent | 1 | 166.3 | 1302540 | 13045 | 0.21 | ok |
| gen-s8-w4 | cp8 | agent | 1 | 217.8 | 2305150 | 17474 | 0.32 | ok |
| gen-s8-w4 | cp9 | agent | 1 | 251.2 | 1915749 | 17813 | 0.32 | ok |
| gen-s9-large | cp1 | agent | 1 | 243.6 | 940829 | 21449 | 0.16 | ok |
| gen-s9-large | cp2 | agent | 1 | 230.7 | 935575 | 20758 | 0.18 | ok |
| gen-s9-large | cp3 | agent | 1 | 225.9 | 1390826 | 19228 | 0.23 | ok |
| pilot | cp1 | agent | 1 | 190.4 | 1119863 | 17673 | 0.22 | ok |
| pilot | cp2 | agent | 1 | 335.7 | 2706721 | 28476 | 0.36 | ok |
| pilot | cp3 | agent | 1 | 404.1 | 1866904 | 31074 | 0.19 | ok |

## Failure samples

The 10 lowest-scoring questions, with gold and predicted answers (dev worlds only; never publish these for test worlds).

### 1. gen-s1-w1 r1 cp2 q-028 (point, loop_owner): score 0.00 [transfer]

Question: Who is responsible for "Generate a synthetic resident data set for Marten"?

Base 0.00, citation precision 0.33

Gold:

```json
{
  "kind": "entity",
  "value": "Nadia Jovanovic",
  "entity": "p-nadia-jovanovic",
  "accept": [
    "Nadia Jovanovic",
    "Nadia",
    "N. Jovanovic",
    "nadia.jovanovic@holcrest.example",
    "@nadia",
    "the CISO"
  ]
}
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.74,
  "value": "Yasmin Mokoena",
  "note": "The 27 Oct platform-sync note says only the 'platform lead' was asked to generate it; the roster identifies Yasmin Mokoena as platform lead. On 11 Nov Yasmin said she was handing a synthetic resident data set for Marten to Nadia Jovanovic, who will take it forward.",
  "cites": [
    "mn-0003",
    "nt-0001",
    "em-0111"
  ]
}
```

### 2. gen-s10-w2-small r1 cp1 q-003 (change, project_changes): score 0.00 [duplicate_signal, endorsement, implied_commitment]

Question: What changed on Translation Help Tool Selection since the end of Friday 27 August?

Base 0.00, citation precision 0.29

Gold:

```json
{
  "items": [
    {
      "event": "e-0116",
      "summary": "Catrin asked me to review the translation help selection vendor comparison",
      "date": "2027-08-30",
      "type": "commitment.create",
      "keywords": [
        "vendor comparison",
        "translation help selection"
      ],
      "support": [
        "mn-0015"
      ]
    },
    {
      "event": "e-0130",
      "summary": "I asked Amani for the Noris accessibility conformance report",
      "date": "2027-08-31",
      "type": "commitment.create",
      "keywords": [
        "accessibility conformance report",
        "noris"
      ],
      "support": [
        "ch-0041"
      ]
    }
  ]
}
```

Predicted:

```json
{
  "type": "change",
  "abstain": false,
  "confidence": 0.72,
  "items": [
    {
      "text": "A 30 August Holworth site-visit auto-recap mentions \"Catrin's translation help selection vendor comparison\" with no owner agreed, and a suggested action for Aoife to review it. This is the only mention of such a THTS vendor comparison and is uncorroborated, so it may be a recap error or a confusion with Bisi's dropped Nettle vendor comparison.",
      "date": "2027-08-30",
      "cites": [
        "mn-0015",
        "ch-0029"
      ]
    },
    {
      "text": "On 31 August an \"Amani\" DM account said she would send the Noris accessibility conformance report; no report arrived. This may relate to the THTS accessibility-review item, but the sender's surname and the project link are not stated, so it is an inference.",
      "date": "2027-08-31",
      "cites": [
        "ch-0041",
        "dc-0001"
      ]
    },
    {
      "text": "No confirmed stage, requirements-list or vendor-selection change: THTS was still in questionnaires (since 20 August) with the 20 September target unchanged; no later artifact confirms either.",
      "date": null,
      "cites": [
        "mt-0004",
        "nt-0001",
        "dc-0001"
      ]
    }
  ]
}
```

### 3. gen-s10-w2-small r1 cp1 q-009 (point, person_attr): score 0.00 [alias, name_collision]

Question: What is my working relationship with our programs manager?

Base 0.00, citation precision 0.20

Gold:

```json
{
  "kind": "text",
  "value": "peer",
  "entity": null,
  "accept": [
    "peer"
  ]
}
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.8,
  "value": "Akosua Bergstrom (colleague; Programs Manager, FDO)",
  "note": "Our programs manager is Akosua Bergstrom in the Federation Data Office. No reporting line is stated in the inputs; the artifacts show a peer/colleague working relationship across Nettle, Pipit, THTS, HPID and Morgate, with her requesting deliverables from Aoife and Aoife sending her items.",
  "cites": [
    "nt-0001",
    "em-0038",
    "em-0056",
    "em-0053",
    "mt-0008"
  ]
}
```

### 4. gen-s10-w2-small r1 cp2 q-015 (list, i_owe): score 0.00 [alias]

Question: What do I currently owe Paula?

Base 0.00, citation precision 0.50

Gold:

```json
{
  "items": [
    {
      "loop": "c-033",
      "what": "Send Paula the Friday status note for w/e 3 September",
      "counterparty": "p-paula-dubois",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-09-03",
      "keywords": [
        "friday status note",
        "w/e 3 september"
      ],
      "support": [
        "em-0054"
      ]
    }
  ]
}
```

Predicted:

```json
{
  "type": "list",
  "abstain": false,
  "confidence": 0.92,
  "items": [
    {
      "text": "Weekly Friday status note for w/e 3 September: half a page covering what moved, what slipped and what is needed from leadership.",
      "counterparty": "Paula Dubois",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-09-03",
      "cites": [
        "em-0054",
        "em-0052"
      ]
    }
  ]
}
```

### 5. gen-s10-w2-small r1 cp2 q-017 (point, project_attr): score 0.00 [new_entity, restructuring]

Question: What phase is Holworth Duplicate Client Records Discovery in?

Base 0.00, citation precision 1.00

Gold:

```json
{
  "kind": "text",
  "value": "planning",
  "entity": null,
  "accept": [
    "planning"
  ]
}
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.88,
  "value": "New project",
  "note": "It was split out of Holworth Pantry Inventory Discovery on 2 Sep 2027; no formal phase, scope, owner or target date beyond that is recorded, so a 'discovery' phase should not be assumed from the project name.",
  "cites": [
    "em-0073"
  ]
}
```

### 6. gen-s10-w2-small r1 cp2 q-019 (list, project_loops): score 0.00 [alias]

Question: What loops are open on THTS selection?

Base 0.00, citation precision 0.15

Gold:

```json
{
  "items": [
    {
      "loop": "c-047",
      "what": "Send the Noris accessibility conformance report",
      "counterparty": "p-amani-xu",
      "direction": "owed_to_me",
      "status": "waiting",
      "due": null,
      "keywords": [
        "accessibility conformance report",
        "noris"
      ],
      "support": [
        "ch-0041"
      ]
    },
    {
      "loop": "c-051",
      "what": "Confirm the translation help selection pricing comparison with Akosua",
      "counterparty": "p-akosua-bergstrom",
      "direction": "i_owe",
      "status": "open",
      "due": null,
      "keywords": [
        "pricing comparison",
        "translation help selection"
      ],
      "support": [
        "ch-0047"
      ]
    }
  ]
}
```

Predicted:

```json
{
  "type": "list",
  "abstain": false,
  "confidence": 0.82,
  "items": [
    {
      "text": "Vendor selection is still undecided: no shortlist or award between Noris Cloud and Ithtec Analytics is recorded, and the 20 September target has not been reconfirmed.",
      "counterparty": null,
      "direction": "other",
      "status": "open",
      "due": null,
      "cites": [
        "nt-0001",
        "mt-0004"
      ]
    },
    {
      "text": "THTS is in the questionnaires stage; which questionnaires, to whom and by when are not recorded, and there is no progress evidence after 20 August.",
      "counterparty": null,
      "direction": "other",
      "status": "open",
      "due": null,
      "cites": [
        "mt-0004"
      ]
    },
    {
      "text": "The six-item requirements draft still has open/in-review items: accessibility review open, data feed open, documentation in review and comms in review.",
      "counterparty": null,
      "direction": "other",
      "status": "open",
      "due": null,
      "cites": [
        "dc-0001"
      ]
    },
    {
      "text": "The Noris deep-dive materials have not been received; Akosua Carmichael said on 16 August she could send them, but there is no receipt evidence.",
      "counterparty": "Akosua Carmichael",
      "direction": "owed_to_me",
      "status": "waiting",
      "due": null,
      "cites": [
        "em-0006",
        "ch-0008",
        "nt-0001"
      ]
    },
    {
      "text": "The Noris accessibility 
... (truncated)
```

### 7. gen-s10-w2-small r1 cp3 q-023 (priority, focus_tomorrow): score 0.00 [batch_catchup, duplicate_signal, endorsement, implied_commitment, unobservable, worker_directive]

Question: What should I focus on tomorrow?

Base 0.00, citation precision 0.47

Gold:

```json
{
  "tomorrow": "2027-09-06",
  "must_include": [
    {
      "loop": "c-040",
      "what": "Confirm the Nettle architecture diagram with Bisi",
      "counterparty": "p-bisi-volkov",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-09-01",
      "keywords": [
        "architecture diagram",
        "nettle"
      ],
      "support": [
        "ch-0037"
      ]
    }
  ],
  "worker_active": [
    {
      "loop": "c-040",
      "what": "Confirm the Nettle architecture diagram with Bisi",
      "counterparty": "p-bisi-volkov",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-09-01",
      "keywords": [
        "architecture diagram",
        "nettle"
      ],
      "support": [
        "ch-0037"
      ]
    },
    {
      "loop": "c-039",
      "what": "Review Catrin's translation help selection vendor comparison",
      "counterparty": "p-catrin-dang",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-09-09",
      "keywords": [
        "vendor comparison",
        "translation help selection"
      ],
      "support": [
        "mn-0015",
        "nt-0010"
      ]
    },
    {
      "loop": "c-005",
      "what": "Send Sigrid the Nettle data-flow diagram",
      "counterparty": "p-sigrid-asante",
      "direction": "i_owe",
      "status": "open",
      "due": null,
      "keywords": [
        "data-flow diagram",
        "nettle"
      ],
      "support": [
        "em-0007"
      ]
    },
    {
      "loop": 
... (truncated)
```

Predicted:

```json
{
  "type": "priority",
  "abstain": false,
  "confidence": 0.82,
  "items": [
    {
      "text": "Confirm the Nettle architecture diagram with Bisi Volkov; the confirmation was due Wed 1 Sep and there is still no evidence it happened.",
      "due": "2027-09-01",
      "why": "Overdue, directly accepted on 31 Aug, and still on the Nettle critical path.",
      "cites": [
        "ch-0037",
        "commitments.md#C11",
        "decisions.md"
      ]
    },
    {
      "text": "Finish and send the Nettle member survey to Bisi Volkov; the 3 Sep draft has no attachment and the email/attachment version and totals-tab mismatch still needs resolving.",
      "due": null,
      "why": "Bisi is waiting for it; Aoife already prepared a draft but it is flagged as unsent and incomplete.",
      "cites": [
        "ch-0035",
        "em-0074",
        "dc-0003",
        "em-0079",
        "commitments.md#C08"
      ]
    },
    {
      "text": "Confirm or reschedule the Pipit one-page-summary walkthrough with Douglas Grigoryan; it was booked for 2 Sep but no artifact confirms it took place.",
      "due": "2027-09-02",
      "why": "Scheduled date has passed with no completion evidence.",
      "cites": [
        "em-0057",
        "ca-0002",
        "mn-0019",
        "commitments.md#C07"
      ]
    },
    {
      "text": "Start reviewing Catrin Dang's THTS vendor comparison, committed for completion by Thu 9 Sep.",
      "due": "2027-09-09",
      "why": "The next explicit deadline 
... (truncated)
```

### 8. gen-s10-w2-small r1 cp3 q-029 (list, project_loops): score 0.00 [alias, duplicate_signal, endorsement, implied_commitment]

Question: What loops are open on the pantry inventory work?

Base 0.00, citation precision 0.33

Gold:

```json
{
  "items": [
    {
      "loop": "c-036",
      "what": "Send Akosua the pantry inventory discovery pain-point list",
      "counterparty": "p-akosua-bergstrom",
      "direction": "i_owe",
      "status": "open",
      "due": null,
      "keywords": [
        "pain-point list",
        "pantry inventory discovery"
      ],
      "support": [
        "em-0056",
        "mn-0015",
        "mn-0017"
      ]
    },
    {
      "loop": "c-058",
      "what": "Send Akosua the pantry inventory discovery pain-point list again",
      "counterparty": "p-akosua-bergstrom",
      "direction": "i_owe",
      "status": "open",
      "due": null,
      "keywords": [
        "pain-point list",
        "pantry inventory discovery"
      ],
      "support": [
        "ch-0058"
      ]
    }
  ]
}
```

Predicted:

```json
{
  "type": "list",
  "abstain": false,
  "confidence": 0.78,
  "items": [
    {
      "text": "Send Akosua Bergstrom the HPID pain-point list; the 3 Sep message is ambiguous about who sends it to whom and no send is recorded.",
      "counterparty": "Akosua Bergstrom",
      "direction": "i_owe",
      "status": "open",
      "due": null,
      "cites": [
        "em-0056",
        "mn-0015",
        "mn-0017",
        "ch-0058",
        "commitments.md#C09"
      ]
    },
    {
      "text": "Review Akosua Bergstrom's pantry inventory discovery opportunity list; still only a suggested action and ownership was never confirmed.",
      "counterparty": "Akosua Bergstrom",
      "direction": "other",
      "status": "open",
      "due": null,
      "cites": [
        "mn-0004",
        "commitments.md#P03"
      ]
    },
    {
      "text": "HPID interview guide: Akosua was to send it to Catrin Dang, but on 2 Sep it moved with the new Holworth duplicate client records project; whether it was sent is unrecorded.",
      "counterparty": "Akosua Bergstrom",
      "direction": "other",
      "status": "open",
      "due": null,
      "cites": [
        "em-0064",
        "em-0073",
        "projects/holworth-duplicate-client-records-discovery.md"
      ]
    },
    {
      "text": "Clarify what remains in HPID after the 2 Sep duplicate-records split, and what the two-branch rollout covers; no revised workplan or target has been recorded.",
      "counterparty": null,
      "directi
... (truncated)
```

### 9. gen-s10-w2-small r1 cp5 q-047 (change, project_changes): score 0.00 [batch_catchup, unobservable]

Question: What changed on Holworth Pantry Inventory Discovery since the end of Tuesday 7 September?

Base 0.00, citation precision 0.50

Gold:

```json
{
  "items": [
    {
      "event": "e-0209",
      "summary": "I said I'd confirm the pantry inventory discovery problem framing note with Akosua",
      "date": "2027-09-08",
      "type": "commitment.create",
      "keywords": [
        "problem framing note",
        "pantry inventory discovery"
      ],
      "support": [
        "em-0099"
      ]
    },
    {
      "event": "e-0210",
      "summary": "I sent Akosua the pantry inventory discovery pain-point list again",
      "date": "2027-09-08",
      "type": "commitment.resolve",
      "keywords": [
        "pain-point list",
        "pantry inventory discovery"
      ],
      "support": [
        "em-0099"
      ]
    },
    {
      "event": "e-0220",
      "summary": "I promised Akosua the pantry inventory discovery process map",
      "date": "2027-09-09",
      "type": "commitment.create",
      "keywords": [
        "process map",
        "pantry inventory discovery"
      ],
      "support": [
        "nt-0012"
      ]
    },
    {
      "event": "e-0222",
      "summary": "Bao asked me for the pantry inventory discovery process map",
      "date": "2027-09-09",
      "type": "commitment.create",
      "keywords": [
        "process map",
        "pantry inventory discovery"
      ],
      "support": [
        "em-0102"
      ]
    }
  ]
}
```

Predicted:

```json
{
  "type": "change",
  "abstain": false,
  "confidence": 0.86,
  "note": "No stage change or target change is recorded: HPID remains in discovery/site-visit work with the 20 September target last stated on 16 August.",
  "items": [
    {
      "text": "Aoife told Akosua Bergstrom to drop the pantry inventory discovery interview guide as 'overtaken by events'; Akosua acknowledged. The guide had moved to the new Holworth duplicate client records project.",
      "date": "2027-09-08",
      "cites": [
        "ch-0071",
        "em-0073"
      ]
    },
    {
      "text": "Amani Xu wrote that the HPID pain-point list had been sent to Akosua again. This is a secondhand 'looks like' report; no email or attachment is in the inputs.",
      "date": "2027-09-08",
      "cites": [
        "em-0099",
        "ch-0058"
      ]
    },
    {
      "text": "Amani Xu said Akosua was still expecting Aoife to confirm the HPID problem framing note. No artifact confirms that the scheduled 8 September walkthrough happened; it shared a slot with a Pipit platform sync.",
      "date": "2027-09-08",
      "cites": [
        "em-0099",
        "ca-0005",
        "mt-0015"
      ]
    },
    {
      "text": "Bao Tembo reported that the HPID budget ceiling has now been agreed; he will share the figure once it is formally signed off.",
      "date": "2027-09-09",
      "cites": [
        "em-0102"
      ]
    },
    {
      "text": "Aoife said she would send Akosua the HPID process map. Bao Tembo sepa
... (truncated)
```

### 10. gen-s10-w2-small r1 cp5 q-052 (point, loop_owner): score 0.00 [transfer]

Question: Who is responsible for "Send Aoife the Noris deep-dive materials"?

Base 0.00, citation precision 0.33

Gold:

```json
{
  "kind": "entity",
  "value": "Jia Delacroix",
  "entity": "p-jia-delacroix",
  "accept": [
    "Jia Delacroix",
    "Jia",
    "J. Delacroix",
    "jia.delacroix@kelholm.reddale.example",
    "@jia"
  ]
}
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.76,
  "value": "Akosua Carmichael",
  "note": "The Noris deep-dive materials were an outstanding request to Akosua Carmichael (Noris Cloud). On 9 September she instead passed them to Jia Delacroix, 'who's closer to it', copying Aoife; the materials were not sent to Aoife, and Jia's role/project is not stated.",
  "cites": [
    "em-0006",
    "ch-0008",
    "em-0101"
  ]
}
```

## Notes

- Track B: store integrity (SIS) is Track A only and is skipped
