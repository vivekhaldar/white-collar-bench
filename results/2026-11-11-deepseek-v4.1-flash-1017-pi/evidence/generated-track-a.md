# white-collar-bench report

- Run: `/home/user/workspace/repo/runs/pi-deepseek-v41-flash-1017/track-a/measured` (Track A, status completed)
- Adapter: pi-nebius-deepseek-v41-flash-1017 pi-1.5.2-runtime-v1 (model nebius/deepseek-ai/DeepSeek-V4.1-Flash-1017)
- Judge: heuristic
- Scored at 2026-11-12T03:20:59+00:00 with wcb 0.1.0 (scorer 0.1); run made with wcb 0.1.0

## Headline

| Metric | Value |
|---|---|
| WCB score | 84.6 [95% CI 80.4, 87.7] |
| Synthesis score (oracle store) | 90.8 [95% CI 88.4, 92.9] |
| Ingestion cost (Synthesis - WCB) | 6.2 |
| SIS (mean over days) | 99.0 |
| SIS (final day) | 98.6 |
| Worlds / episodes / questions | 11 / 11 / 745 |

Scores are on a 0-100 scale. The interval is a 95% bootstrap over worlds; with one world it is degenerate.

## By world and repeat

| World | Repeat | WCB | Synthesis | Ingestion cost | SIS | SIS final |
|---|---|---|---|---|---|---|
| gen-s8-w4 | r1 | 83.0 | 88.5 | 5.5 | 98.9 | 98.7 |
| gen-s4-w2 | r1 | 87.9 | 91.7 | 3.8 | 99.3 | 98.7 |
| gen-s7-w2 | r1 | 82.4 | 95.0 | 12.6 | 99.3 | 99.0 |
| gen-s10-w2-small | r1 | 84.5 | 92.8 | 8.4 | 99.0 | 98.5 |
| pilot | r1 | 67.1 | 82.0 | 14.9 | 96.0 | 93.5 |
| gen-s9-large | r1 | 88.2 | 93.1 | 4.9 | 99.2 | 99.0 |
| gen-s1-w1 | r1 | 87.7 | 88.9 | 1.2 | 99.6 | 99.4 |
| gen-s2-w1 | r1 | 88.9 | 92.7 | 3.8 | 99.3 | 99.4 |
| gen-s3-w1 | r1 | 91.5 | 96.0 | 4.5 | 99.4 | 99.2 |
| gen-s5-small | r1 | 83.2 | 86.8 | 3.5 | 99.2 | 99.1 |
| gen-s6-w1 | r1 | 86.7 | 91.3 | 4.6 | 99.7 | 99.6 |

## By question type

| Type | n | WCB | Synthesis | Ingestion cost |
|---|---|---|---|---|
| point | 187 | 87.5 | 95.9 | 8.4 |
| list | 165 | 80.8 | 90.0 | 9.1 |
| status | 52 | 86.7 | 82.1 | -4.5 |
| brief | 77 | 82.7 | 90.8 | 8.0 |
| change | 52 | 54.8 | 73.3 | 18.5 |
| temporal | 85 | 97.7 | 98.5 | 0.8 |
| priority | 51 | 85.0 | 94.7 | 9.7 |
| unanswerable | 76 | 97.4 | 98.7 | 1.3 |

Mean question score per type over all checkpoints and repeats. Unanswerable questions form their own bucket.

## By planted challenge

| Challenge | n | WCB | Synthesis | Ingestion cost |
|---|---|---|---|---|
| acceptance_vs_occurrence | 2 | 83.3 | 100.0 | 16.7 |
| alias | 161 | 81.3 | 87.9 | 6.6 |
| batch_catchup | 65 | 82.2 | 89.5 | 7.4 |
| correction | 56 | 82.3 | 84.9 | 2.6 |
| draft_vs_sent | 1 | 63.3 | 100.0 | 36.7 |
| duplicate_signal | 211 | 84.9 | 89.6 | 4.7 |
| endorsement | 127 | 81.9 | 87.7 | 5.8 |
| implied_commitment | 130 | 82.3 | 88.4 | 6.2 |
| name_collision | 56 | 81.8 | 91.4 | 9.6 |
| new_entity | 130 | 81.0 | 88.1 | 7.2 |
| noise | 1 | 66.7 | 100.0 | 33.3 |
| restructuring | 67 | 75.2 | 87.1 | 11.9 |
| reversal | 12 | 79.5 | 81.2 | 1.7 |
| scattered_evidence | 70 | 79.8 | 89.3 | 9.5 |
| silent_closure | 14 | 75.6 | 95.5 | 19.9 |
| supersession | 113 | 83.8 | 88.4 | 4.6 |
| transfer | 69 | 81.5 | 93.5 | 12.0 |
| unobservable | 129 | 90.1 | 95.6 | 5.5 |
| version_mismatch | 7 | 82.3 | 91.3 | 9.1 |
| weak_evidence | 12 | 97.2 | 100.0 | 2.8 |
| worker_directive | 92 | 83.7 | 87.7 | 4.0 |

## By checkpoint

| World | Checkpoint | Date | Episode day | Questions | WCB | Synthesis | Ingestion cost |
|---|---|---|---|---|---|---|---|
| gen-s8-w4 | cp1 | 2027-09-14 | 2 of 24 | 15 | 88.7 | 89.8 | 1.2 |
| gen-s8-w4 | cp2 | 2027-09-16 | 4 of 24 | 15 | 92.5 | 85.8 | -6.7 |
| gen-s8-w4 | cp3 | 2027-09-18 | 6 of 24 | 15 | 92.7 | 90.2 | -2.5 |
| gen-s8-w4 | cp4 | 2027-09-21 | 8 of 24 | 15 | 77.5 | 83.9 | 6.3 |
| gen-s8-w4 | cp5 | 2027-09-23 | 10 of 24 | 15 | 77.4 | 92.0 | 14.6 |
| gen-s8-w4 | cp6 | 2027-09-25 | 12 of 24 | 15 | 93.1 | 92.3 | -0.8 |
| gen-s8-w4 | cp7 | 2027-09-28 | 14 of 24 | 15 | 71.6 | 85.5 | 13.9 |
| gen-s8-w4 | cp8 | 2027-09-30 | 16 of 24 | 15 | 77.6 | 92.8 | 15.2 |
| gen-s8-w4 | cp9 | 2027-10-02 | 18 of 24 | 15 | 77.6 | 80.7 | 3.1 |
| gen-s8-w4 | cp10 | 2027-10-05 | 20 of 24 | 15 | 82.5 | 87.1 | 4.6 |
| gen-s8-w4 | cp11 | 2027-10-07 | 22 of 24 | 15 | 77.9 | 89.7 | 11.8 |
| gen-s8-w4 | cp12 | 2027-10-09 | 24 of 24 | 15 | 87.1 | 92.1 | 4.9 |
| gen-s4-w2 | cp1 | 2027-09-07 | 2 of 12 | 15 | 91.2 | 94.3 | 3.0 |
| gen-s4-w2 | cp2 | 2027-09-09 | 4 of 12 | 15 | 89.6 | 88.9 | -0.8 |
| gen-s4-w2 | cp3 | 2027-09-11 | 6 of 12 | 15 | 83.0 | 84.0 | 1.0 |
| gen-s4-w2 | cp4 | 2027-09-14 | 8 of 12 | 15 | 83.7 | 90.9 | 7.3 |
| gen-s4-w2 | cp5 | 2027-09-16 | 10 of 12 | 15 | 87.6 | 95.3 | 7.7 |
| gen-s4-w2 | cp6 | 2027-09-18 | 12 of 12 | 15 | 92.2 | 96.7 | 4.6 |
| gen-s7-w2 | cp1 | 2027-07-06 | 2 of 12 | 15 | 83.6 | 96.5 | 12.9 |
| gen-s7-w2 | cp2 | 2027-07-08 | 4 of 12 | 15 | 87.2 | 90.0 | 2.7 |
| gen-s7-w2 | cp3 | 2027-07-10 | 6 of 12 | 15 | 78.0 | 95.6 | 17.6 |
| gen-s7-w2 | cp4 | 2027-07-13 | 8 of 12 | 15 | 77.7 | 95.5 | 17.8 |
| gen-s7-w2 | cp5 | 2027-07-15 | 10 of 12 | 15 | 86.4 | 94.5 | 8.1 |
| gen-s7-w2 | cp6 | 2027-07-17 | 12 of 12 | 15 | 81.3 | 97.7 | 16.4 |
| gen-s10-w2-small | cp1 | 2027-08-31 | 2 of 11 | 11 | 92.1 | 89.3 | -2.8 |
| gen-s10-w2-small | cp2 | 2027-09-02 | 4 of 11 | 11 | 86.4 | 95.9 | 9.5 |
| gen-s10-w2-small | cp3 | 2027-09-03 | 5 of 11 | 11 | 87.8 | 95.5 | 7.7 |
| gen-s10-w2-small | cp4 | 2027-09-07 | 7 of 11 | 11 | 76.6 | 95.7 | 19.1 |
| gen-s10-w2-small | cp5 | 2027-09-09 | 9 of 11 | 11 | 81.0 | 93.3 | 12.3 |
| gen-s10-w2-small | cp6 | 2027-09-11 | 11 of 11 | 11 | 82.8 | 87.3 | 4.6 |
| pilot | cp1 | 2027-03-02 | 2 of 6 | 14 | 71.8 | 86.0 | 14.2 |
| pilot | cp2 | 2027-03-04 | 4 of 6 | 17 | 67.7 | 76.5 | 8.8 |
| pilot | cp3 | 2027-03-06 | 6 of 6 | 21 | 61.9 | 83.5 | 21.6 |
| gen-s9-large | cp1 | 2027-11-02 | 2 of 6 | 18 | 91.6 | 97.4 | 5.8 |
| gen-s9-large | cp2 | 2027-11-04 | 4 of 6 | 18 | 84.9 | 89.3 | 4.4 |
| gen-s9-large | cp3 | 2027-11-06 | 6 of 6 | 18 | 88.0 | 92.6 | 4.6 |
| gen-s1-w1 | cp1 | 2027-11-09 | 2 of 6 | 15 | 93.8 | 84.3 | -9.5 |
| gen-s1-w1 | cp2 | 2027-11-11 | 4 of 6 | 15 | 89.1 | 88.9 | -0.2 |
| gen-s1-w1 | cp3 | 2027-11-13 | 6 of 6 | 15 | 80.2 | 93.5 | 13.3 |
| gen-s2-w1 | cp1 | 2027-03-09 | 2 of 5 | 15 | 85.1 | 90.6 | 5.5 |
| gen-s2-w1 | cp2 | 2027-03-11 | 4 of 5 | 15 | 92.1 | 97.4 | 5.3 |
| gen-s2-w1 | cp3 | 2027-03-12 | 5 of 5 | 15 | 89.5 | 90.0 | 0.5 |
| gen-s3-w1 | cp1 | 2027-09-21 | 2 of 6 | 15 | 89.2 | 93.8 | 4.6 |
| gen-s3-w1 | cp2 | 2027-09-23 | 4 of 6 | 15 | 91.0 | 98.5 | 7.5 |
| gen-s3-w1 | cp3 | 2027-09-25 | 6 of 6 | 15 | 94.4 | 95.7 | 1.4 |
| gen-s5-small | cp1 | 2027-03-30 | 2 of 6 | 11 | 82.2 | 87.9 | 5.7 |
| gen-s5-small | cp2 | 2027-04-01 | 4 of 6 | 11 | 88.3 | 90.7 | 2.4 |
| gen-s5-small | cp3 | 2027-04-03 | 6 of 6 | 11 | 79.2 | 81.7 | 2.5 |
| gen-s6-w1 | cp1 | 2027-02-23 | 2 of 6 | 15 | 87.2 | 88.8 | 1.6 |
| gen-s6-w1 | cp2 | 2027-02-25 | 4 of 6 | 15 | 91.0 | 95.9 | 4.9 |
| gen-s6-w1 | cp3 | 2027-02-27 | 6 of 6 | 15 | 81.9 | 89.3 | 7.4 |

## Store integrity per day

| World | Date | SIS | Entity F1 | Loop F1 | Field acc. | Freshness | Grounded | Validity |
|---|---|---|---|---|---|---|---|---|
| gen-s8-w4 | 2027-09-13 | 99.6 | 1.000 | 0.984 | 0.992 | 1.000 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-14 | 99.4 | 1.000 | 0.978 | 0.985 | 1.000 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-15 | 99.5 | 1.000 | 0.980 | 0.989 | 1.000 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-16 | 99.3 | 1.000 | 0.982 | 0.988 | 0.989 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-17 | 99.3 | 1.000 | 0.983 | 0.986 | 0.990 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-18 | 99.3 | 1.000 | 0.983 | 0.984 | 0.990 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-20 | 99.5 | 1.000 | 0.985 | 0.984 | 1.000 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-21 | 99.2 | 1.000 | 0.981 | 0.981 | 0.992 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-22 | 98.9 | 1.000 | 0.978 | 0.979 | 0.976 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-23 | 98.8 | 1.000 | 0.971 | 0.979 | 0.977 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-24 | 98.8 | 1.000 | 0.973 | 0.979 | 0.979 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-25 | 98.8 | 1.000 | 0.974 | 0.976 | 0.979 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-27 | 98.8 | 1.000 | 0.972 | 0.976 | 0.980 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-28 | 98.8 | 1.000 | 0.973 | 0.975 | 0.981 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-29 | 98.9 | 1.000 | 0.973 | 0.978 | 0.981 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-09-30 | 98.5 | 1.000 | 0.975 | 0.966 | 0.971 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-10-01 | 98.5 | 1.000 | 0.970 | 0.967 | 0.972 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-10-02 | 98.5 | 1.000 | 0.970 | 0.967 | 0.972 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-10-04 | 98.6 | 1.000 | 0.969 | 0.968 | 0.979 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-10-05 | 98.5 | 1.000 | 0.970 | 0.968 | 0.975 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-10-06 | 98.7 | 1.000 | 0.972 | 0.971 | 0.981 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-10-07 | 98.7 | 1.000 | 0.970 | 0.971 | 0.981 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-10-08 | 98.7 | 1.000 | 0.971 | 0.971 | 0.982 | 1.000 | 1.000 |
| gen-s8-w4 | 2027-10-09 | 98.7 | 1.000 | 0.971 | 0.971 | 0.982 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-06 | 99.9 | 1.000 | 1.000 | 0.992 | 1.000 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-07 | 99.9 | 1.000 | 1.000 | 0.992 | 1.000 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-08 | 99.8 | 1.000 | 0.994 | 0.995 | 1.000 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-09 | 99.7 | 1.000 | 0.989 | 0.991 | 1.000 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-10 | 99.6 | 1.000 | 0.984 | 0.991 | 1.000 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-11 | 99.5 | 1.000 | 0.984 | 0.988 | 1.000 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-13 | 99.2 | 1.000 | 0.985 | 0.985 | 0.982 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-14 | 98.8 | 1.000 | 0.982 | 0.982 | 0.967 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-15 | 98.9 | 1.000 | 0.982 | 0.982 | 0.968 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-16 | 98.7 | 1.000 | 0.972 | 0.979 | 0.970 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-17 | 98.7 | 1.000 | 0.973 | 0.976 | 0.971 | 1.000 | 1.000 |
| gen-s4-w2 | 2027-09-18 | 98.7 | 1.000 | 0.974 | 0.977 | 0.972 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-05 | 99.7 | 1.000 | 0.992 | 0.990 | 1.000 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-06 | 99.3 | 1.000 | 0.985 | 0.986 | 0.987 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-07 | 99.4 | 1.000 | 0.987 | 0.987 | 0.988 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-08 | 99.3 | 1.000 | 0.988 | 0.984 | 0.989 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-09 | 99.5 | 1.000 | 0.988 | 0.981 | 1.000 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-10 | 99.5 | 1.000 | 0.988 | 0.981 | 1.000 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-12 | 99.4 | 1.000 | 0.990 | 0.976 | 1.000 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-13 | 99.2 | 1.000 | 0.980 | 0.972 | 1.000 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-14 | 99.1 | 1.000 | 0.982 | 0.965 | 1.000 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-15 | 99.0 | 1.000 | 0.984 | 0.966 | 0.992 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-16 | 99.0 | 1.000 | 0.984 | 0.965 | 0.993 | 1.000 | 1.000 |
| gen-s7-w2 | 2027-07-17 | 99.0 | 1.000 | 0.985 | 0.965 | 0.993 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-08-30 | 99.9 | 1.000 | 1.000 | 0.995 | 1.000 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-08-31 | 99.8 | 1.000 | 1.000 | 0.990 | 1.000 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-01 | 99.5 | 1.000 | 0.982 | 0.987 | 1.000 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-02 | 99.3 | 1.000 | 0.975 | 0.985 | 1.000 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-03 | 99.2 | 1.000 | 0.969 | 0.982 | 1.000 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-06 | 98.8 | 1.000 | 0.958 | 0.981 | 0.987 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-07 | 98.5 | 1.000 | 0.943 | 0.977 | 0.988 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-08 | 98.5 | 1.000 | 0.945 | 0.977 | 0.988 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-09 | 98.5 | 1.000 | 0.937 | 0.973 | 1.000 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-10 | 98.5 | 1.000 | 0.939 | 0.969 | 1.000 | 1.000 | 1.000 |
| gen-s10-w2-small | 2027-09-11 | 98.5 | 1.000 | 0.941 | 0.970 | 1.000 | 1.000 | 1.000 |
| pilot | 2027-03-01 | 98.5 | 1.000 | 0.930 | 0.979 | 1.000 | 1.000 | 1.000 |
| pilot | 2027-03-02 | 97.5 | 0.991 | 0.908 | 0.965 | 0.988 | 1.000 | 1.000 |
| pilot | 2027-03-03 | 97.0 | 0.991 | 0.893 | 0.961 | 0.976 | 1.000 | 1.000 |
| pilot | 2027-03-04 | 96.3 | 0.992 | 0.859 | 0.941 | 0.990 | 1.000 | 1.000 |
| pilot | 2027-03-05 | 93.1 | 0.983 | 0.806 | 0.913 | 0.887 | 1.000 | 1.000 |
| pilot | 2027-03-06 | 93.5 | 0.983 | 0.807 | 0.918 | 0.900 | 1.000 | 1.000 |
| gen-s9-large | 2027-11-01 | 99.7 | 1.000 | 0.988 | 0.992 | 1.000 | 1.000 | 1.000 |
| gen-s9-large | 2027-11-02 | 99.5 | 1.000 | 0.977 | 0.990 | 1.000 | 1.000 | 1.000 |
| gen-s9-large | 2027-11-03 | 99.1 | 1.000 | 0.974 | 0.980 | 0.991 | 1.000 | 1.000 |
| gen-s9-large | 2027-11-04 | 99.1 | 1.000 | 0.971 | 0.973 | 1.000 | 1.000 | 1.000 |
| gen-s9-large | 2027-11-05 | 99.0 | 1.000 | 0.973 | 0.966 | 1.000 | 1.000 | 1.000 |
| gen-s9-large | 2027-11-06 | 99.0 | 1.000 | 0.974 | 0.967 | 1.000 | 1.000 | 1.000 |
| gen-s1-w1 | 2027-11-08 | 99.7 | 1.000 | 0.987 | 0.997 | 1.000 | 1.000 | 1.000 |
| gen-s1-w1 | 2027-11-09 | 99.7 | 1.000 | 0.988 | 0.995 | 1.000 | 1.000 | 1.000 |
| gen-s1-w1 | 2027-11-10 | 99.7 | 1.000 | 0.989 | 0.993 | 1.000 | 1.000 | 1.000 |
| gen-s1-w1 | 2027-11-11 | 99.5 | 1.000 | 0.985 | 0.988 | 1.000 | 1.000 | 1.000 |
| gen-s1-w1 | 2027-11-12 | 99.4 | 1.000 | 0.986 | 0.985 | 0.992 | 1.000 | 1.000 |
| gen-s1-w1 | 2027-11-13 | 99.4 | 1.000 | 0.986 | 0.985 | 0.992 | 1.000 | 1.000 |
| gen-s2-w1 | 2027-03-08 | 99.2 | 1.000 | 0.993 | 0.973 | 0.988 | 1.000 | 1.000 |
| gen-s2-w1 | 2027-03-09 | 99.2 | 1.000 | 0.994 | 0.970 | 0.990 | 1.000 | 1.000 |
| gen-s2-w1 | 2027-03-10 | 99.4 | 1.000 | 0.994 | 0.972 | 1.000 | 1.000 | 1.000 |
| gen-s2-w1 | 2027-03-11 | 99.3 | 1.000 | 0.990 | 0.969 | 1.000 | 1.000 | 1.000 |
| gen-s2-w1 | 2027-03-12 | 99.4 | 1.000 | 0.990 | 0.973 | 1.000 | 1.000 | 1.000 |
| gen-s3-w1 | 2027-09-20 | 99.9 | 1.000 | 1.000 | 0.994 | 1.000 | 1.000 | 1.000 |
| gen-s3-w1 | 2027-09-21 | 99.5 | 1.000 | 1.000 | 0.983 | 0.988 | 1.000 | 1.000 |
| gen-s3-w1 | 2027-09-22 | 99.6 | 1.000 | 1.000 | 0.987 | 0.989 | 1.000 | 1.000 |
| gen-s3-w1 | 2027-09-23 | 99.2 | 0.990 | 0.988 | 0.984 | 0.989 | 1.000 | 1.000 |
| gen-s3-w1 | 2027-09-24 | 99.2 | 0.990 | 0.989 | 0.983 | 0.990 | 1.000 | 1.000 |
| gen-s3-w1 | 2027-09-25 | 99.2 | 0.990 | 0.989 | 0.983 | 0.990 | 1.000 | 1.000 |
| gen-s5-small | 2027-03-29 | 99.5 | 1.000 | 1.000 | 0.987 | 0.983 | 1.000 | 1.000 |
| gen-s5-small | 2027-03-30 | 99.3 | 1.000 | 1.000 | 0.975 | 0.985 | 1.000 | 1.000 |
| gen-s5-small | 2027-03-31 | 99.1 | 1.000 | 0.992 | 0.970 | 0.986 | 1.000 | 1.000 |
| gen-s5-small | 2027-04-01 | 99.1 | 1.000 | 0.966 | 0.979 | 1.000 | 1.000 | 1.000 |
| gen-s5-small | 2027-04-02 | 99.1 | 1.000 | 0.962 | 0.983 | 1.000 | 1.000 | 1.000 |
| gen-s5-small | 2027-04-03 | 99.1 | 1.000 | 0.962 | 0.983 | 1.000 | 1.000 | 1.000 |
| gen-s6-w1 | 2027-02-22 | 99.9 | 1.000 | 1.000 | 0.993 | 1.000 | 1.000 | 1.000 |
| gen-s6-w1 | 2027-02-23 | 99.7 | 1.000 | 1.000 | 0.983 | 1.000 | 1.000 | 1.000 |
| gen-s6-w1 | 2027-02-24 | 99.7 | 1.000 | 0.994 | 0.986 | 1.000 | 1.000 | 1.000 |
| gen-s6-w1 | 2027-02-25 | 99.7 | 1.000 | 0.995 | 0.985 | 1.000 | 1.000 | 1.000 |
| gen-s6-w1 | 2027-02-26 | 99.7 | 1.000 | 0.995 | 0.986 | 1.000 | 1.000 | 1.000 |
| gen-s6-w1 | 2027-02-27 | 99.6 | 1.000 | 0.995 | 0.983 | 1.000 | 1.000 | 1.000 |

SIS is 0-100; sub-metrics are 0-1. Values are means over repeats.

Final-day store errors:

- gen-s8-w4 r1 (2027-10-09): missing loops: c-061, c-067, c-104, c-110, c-111, c-131, c-165, c-190; unmatched loop records: loops/change-the-galix-sandbox-password, loops/share-the-fulmar-budget-figure-with-amira, loops/start-the-fulmar-staging-walkthrough, loops/start-the-wagtail-dry-run; stale: loops/send-amira-the-fulmar-architecture-diagram (status), loops/send-amira-the-monthly-wagtail-cost-report (status), loops/send-amira-the-safety-reporting-discovery-interview-guide (status), loops/send-shirin-the-fulmar-cutover-plan (status)
- gen-s4-w2 r1 (2027-09-18): missing loops: c-075; unmatched loop records: loops/agree-the-cairn-budget-ceiling, loops/agree-the-heathridge-course-assistant-discovery-budget, loops/decide-whether-waitlist-management-becomes-its-own-effort, loops/send-ottavio-the-cairn-budget-figure, loops/start-the-syllabus-review-discovery-dry-run, loops/test-the-room-booking-selection-staging-environment; stale: loops/rotate-the-cairn-vault-secrets (status), loops/send-darius-the-fjord-architecture-diagram (status), loops/send-ottavio-the-course-assistant-discovery-stakeholder-map (status), loops/send-ottavio-the-notes-from-the-financial-aid-chat-session (status)
- gen-s7-w2 r1 (2027-07-17): missing loops: c-051, c-099; unmatched loop records: loops/share-the-admissions-triage-selection-budget-figure-with-hiba, loops/share-the-garnet-budget-figure-with-hiba; stale: loops/share-the-holmarsh-partnership-event-invitation-with-hiba (status)
- gen-s10-w2-small r1 (2027-09-11): missing loops: c-053, c-054, c-058, c-063, c-068, c-077; unmatched loop records: loops/change-the-ithtec-sandbox-password, loops/change-the-noris-sandbox-password, loops/reopen-the-nettle-privacy-review-form, loops/send-bisi-a-nettle-update, loops/share-the-holworth-pantry-inventory-discovery-budget-figure-with-aoife
- pilot r1 (2027-03-06): missing entities: pr-cop; spurious or duplicate entity records: orgs/tarrow-university-kestrow; missing loops: c-069, c-072, c-076, c-078, c-079, c-088, c-089, c-090, c-091, c-092, c-093, c-094, c-096, c-097, c-098, d-005, d-007, d-008; unmatched loop records: loops/adopt-an-event-based-lms-context-api-for-tinderbox, loops/attend-the-library-research-assistant-evaluation-partnership-call, loops/attend-the-scrivelo-implementation-walkthrough, loops/carry-deferred-v3-comments-3-and-9-into-reference-architecture-v5, loops/co-lead-a-teaching-with-ai-community-of-practice, loops/correct-the-vendor-scorecard-summary-totals-to-scorecard-v2, loops/decide-the-kettleyard-chargeback-model, loops/decide-the-scope-of-the-saltmarren-discovery-on-advising, loops/decide-whether-to-hire-mateus-okonedo, loops/decide-who-owns-tinderbox-operations-after-go-live, loops/draft-an-internal-build-estimate-for-a-kettleyard-based-alternative, loops/draft-the-workshop-deck-v3, loops/extend-the-offer-to-mateus-okonedo, loops/keep-bartosz-zielke-as-incident-commander, loops/no-tinderbox-expansion-beyond-kestrow-until-chargeback-agreed, loops/re-run-the-kettleyard-chargeback-model-on-the-rebased-fy27-fte-inputs, loops/review-the-kettleyard-reference-architecture-v4, loops/send-clement-the-writing-tool-requirements-by-9-march, loops/send-ilya-the-invite-for-the-deferred-comments-sync, loops/send-mara-the-ta-name-for-the-tinderbox-sandbox-login, loops/send-penmarq-sandbox-access-for-the-writing-center-trial, loops/set-up-a-tinderbox-sandbox-login-for-emekas-ta, loops/tell-dmitri-the-12th-is-fine, loops/tell-joaquin-to-stop-pricing-option-1-dedicated-kestrow-deployment, loops/use-matched-assignment-learning-gains-as-the-tinderbox-success-metric; stale: loops/add-an-internal-build-option-to-the-vendor-scorecard (status), loops/circulate-penmarq-demo-notes-to-the-evaluation-team (status), loops/limit-the-tinderbox-pilot-to-three-courses-chem-110-hist (status), loops/run-a-two-week-penmarq-sandbox-trial-with-saltmarren (status), loops/run-the-tinderbox-load-test-500-concurrent-sessions (status), loops/send-penmarq-s-three-campus-pricing (status), loops/send-sade-the-weekly-ai-data-update-week-of-1-mar (status), loops/set-up-a-meeting-with-sade-and-bart-ngata-on-tinderbox-ownership (owner), projects/citation-helper-placeholder (status), projects/tinderbox (target_date)
- gen-s9-large r1 (2027-11-06): missing loops: c-073, c-099; unmatched loop records: loops/assign-an-owner-for-the-okapi-prototype, loops/change-the-kasane-sandbox-password, loops/decide-whether-anh-picks-up-the-clelera-redline-summary, loops/reopen-the-informatics-nurse-specialist-role-profile
- gen-s1-w1 r1 (2027-11-13): missing loops: c-074; unmatched loop records: loops/change-the-zeneth-sandbox-temporary-password, loops/walk-through-the-marten-test-tenant; stale: loops/send-jalen-the-notice-translation-discovery-stakeholder-map (status)
- gen-s2-w1 r1 (2027-03-12): missing loops: c-066; unmatched loop records: loops/send-dina-the-funding-model-budget-figure
- gen-s3-w1 r1 (2027-09-25): missing entities: p-hiba-nyberg; missing loops: c-079; unmatched loop records: loops/send-alasdair-the-lanmoor-bed-management-budget-figure; stale: loops/collect-two-customer-references-from-kasis (status)
- gen-s5-small r1 (2027-04-03): unmatched loop records: loops/attend-the-clinical-documentation-discovery-follow-up, loops/attend-the-nurse-scheduling-selection-review, loops/change-the-grion-sandbox-password, loops/move-the-wagtail-go-live-to-2027-05-03, loops/split-falbury-referral-backlog-discovery-out-of-falbury-clinical-documentation-discovery, loops/walk-through-the-okapi-test-tenant
- gen-s6-w1 r1 (2027-02-27): missing loops: c-083

## Efficiency

| Sessions | n | Wall s (total) | Wall s (mean) | Input tokens | Output tokens | Cost USD | Timeouts | Failures | Usage reported | Metered |
|---|---|---|---|---|---|---|---|---|---|---|
| Ingestion | 100 | 57035.6 | 570.4 | 400141226 | 4977480 | 35.21 | 0 | 1 | 100 | 100 |
| Query (agent store) | 51 | 14377.8 | 281.9 | 70595354 | 1147632 | 10.60 | 0 | 0 | 51 | 51 |
| Query (oracle store) | 51 | 14120.5 | 276.9 | 52636869 | 1048464 | 8.51 | 0 | 0 | 51 | 51 |

Per episode (agent sessions): 6492.1 s, 42794235 input tokens, 556828 output tokens, $4.16. Token counts are measured for metered sessions (`wcb run --meter`) and self-reported otherwise; cost is always self-reported.

### Per ingestion day

| World | Date | n | Wall s | Input tokens | Output tokens | Cost USD | Status |
|---|---|---|---|---|---|---|---|
| gen-s1-w1 | 2027-11-08 | 1 | 547.2 | 3053640 | 47647 | 0.33 | ok |
| gen-s1-w1 | 2027-11-09 | 1 | 389.8 | 1455119 | 36584 | 0.26 | ok |
| gen-s1-w1 | 2027-11-10 | 1 | 609.9 | 3611111 | 52124 | 0.34 | ok |
| gen-s1-w1 | 2027-11-11 | 1 | 743.4 | 4472180 | 68589 | 0.45 | ok |
| gen-s1-w1 | 2027-11-12 | 1 | 578.5 | 4328757 | 56652 | 0.44 | ok |
| gen-s1-w1 | 2027-11-13 | 1 | 135.0 | 575064 | 11837 | 0.10 | ok |
| gen-s10-w2-small | 2027-08-30 | 1 | 466.1 | 1334766 | 34676 | 0.20 | ok |
| gen-s10-w2-small | 2027-08-31 | 1 | 423.3 | 1729907 | 35284 | 0.22 | ok |
| gen-s10-w2-small | 2027-09-01 | 1 | 478.8 | 3082212 | 49355 | 0.31 | ok |
| gen-s10-w2-small | 2027-09-02 | 1 | 649.2 | 3816349 | 67549 | 0.39 | ok |
| gen-s10-w2-small | 2027-09-03 | 1 | 533.0 | 2828886 | 46921 | 0.34 | ok |
| gen-s10-w2-small | 2027-09-06 | 1 | 428.8 | 1907108 | 43253 | 0.25 | ok |
| gen-s10-w2-small | 2027-09-07 | 1 | 624.0 | 3272048 | 48667 | 0.30 | ok |
| gen-s10-w2-small | 2027-09-08 | 1 | 498.0 | 2749621 | 37988 | 0.32 | ok |
| gen-s10-w2-small | 2027-09-09 | 1 | 492.0 | 3362935 | 49360 | 0.35 | ok |
| gen-s10-w2-small | 2027-09-10 | 1 | 525.9 | 4701315 | 46990 | 0.35 | ok |
| gen-s10-w2-small | 2027-09-11 | 1 | 216.4 | 1125700 | 18335 | 0.15 | ok |
| gen-s2-w1 | 2027-03-08 | 1 | 695.7 | 5269451 | 62764 | 0.42 | ok |
| gen-s2-w1 | 2027-03-09 | 1 | 518.9 | 3750511 | 62190 | 0.42 | ok |
| gen-s2-w1 | 2027-03-10 | 1 | 573.0 | 3963694 | 52203 | 0.35 | ok |
| gen-s2-w1 | 2027-03-11 | 1 | 547.8 | 2176987 | 46306 | 0.31 | ok |
| gen-s2-w1 | 2027-03-12 | 1 | 616.9 | 3318176 | 50280 | 0.32 | ok |
| gen-s3-w1 | 2027-09-20 | 1 | 508.7 | 2728400 | 51482 | 0.31 | ok |
| gen-s3-w1 | 2027-09-21 | 1 | 526.1 | 3393118 | 58249 | 0.34 | ok |
| gen-s3-w1 | 2027-09-22 | 1 | 643.7 | 4394922 | 56763 | 0.37 | ok |
| gen-s3-w1 | 2027-09-23 | 1 | 627.5 | 2660056 | 52685 | 0.34 | ok |
| gen-s3-w1 | 2027-09-24 | 1 | 736.0 | 4121026 | 57235 | 0.37 | ok |
| gen-s3-w1 | 2027-09-25 | 1 | 217.8 | 892837 | 14655 | 0.15 | ok |
| gen-s4-w2 | 2027-09-06 | 1 | 631.4 | 3308571 | 50057 | 0.33 | ok |
| gen-s4-w2 | 2027-09-07 | 1 | 427.4 | 2717951 | 39735 | 0.30 | ok |
| gen-s4-w2 | 2027-09-08 | 1 | 511.3 | 2822161 | 51866 | 0.32 | ok |
| gen-s4-w2 | 2027-09-09 | 1 | 562.2 | 3833120 | 53026 | 0.36 | ok |
| gen-s4-w2 | 2027-09-10 | 1 | 514.2 | 3430654 | 51280 | 0.36 | ok |
| gen-s4-w2 | 2027-09-11 | 1 | 253.4 | 1471547 | 18346 | 0.18 | ok |
| gen-s4-w2 | 2027-09-13 | 1 | 851.9 | 4190797 | 57693 | 0.37 | ok |
| gen-s4-w2 | 2027-09-14 | 1 | 610.5 | 3765290 | 63247 | 0.41 | ok |
| gen-s4-w2 | 2027-09-15 | 1 | 518.1 | 3035691 | 51513 | 0.33 | ok |
| gen-s4-w2 | 2027-09-16 | 1 | 666.5 | 5642801 | 56429 | 0.45 | ok |
| gen-s4-w2 | 2027-09-17 | 1 | 561.3 | 3421958 | 46884 | 0.37 | ok |
| gen-s4-w2 | 2027-09-18 | 1 | 293.0 | 1637011 | 23941 | 0.21 | ok |
| gen-s5-small | 2027-03-29 | 1 | 519.7 | 2898884 | 57210 | 0.34 | ok |
| gen-s5-small | 2027-03-30 | 1 | 445.0 | 2803246 | 50694 | 0.27 | ok |
| gen-s5-small | 2027-03-31 | 1 | 478.4 | 2396158 | 44390 | 0.29 | ok |
| gen-s5-small | 2027-04-01 | 1 | 1148.9 | 7548230 | 95954 | 0.52 | ok |
| gen-s5-small | 2027-04-02 | 1 | 611.2 | 3425781 | 48924 | 0.34 | ok |
| gen-s5-small | 2027-04-03 | 1 | 78.0 | 385851 | 3498 | 0.07 | ok |
| gen-s6-w1 | 2027-02-22 | 1 | 695.9 | 2825794 | 47379 | 0.31 | ok |
| gen-s6-w1 | 2027-02-23 | 1 | 829.3 | 4457132 | 56574 | 0.45 | ok |
| gen-s6-w1 | 2027-02-24 | 1 | 739.9 | 4215816 | 52361 | 0.36 | ok |
| gen-s6-w1 | 2027-02-25 | 1 | 747.5 | 4971726 | 58036 | 0.40 | ok |
| gen-s6-w1 | 2027-02-26 | 1 | 927.7 | 3822895 | 60810 | 0.40 | ok |
| gen-s6-w1 | 2027-02-27 | 1 | 209.6 | 735886 | 11648 | 0.11 | ok |
| gen-s7-w2 | 2027-07-05 | 1 | 685.4 | 2534976 | 53151 | 0.29 | ok |
| gen-s7-w2 | 2027-07-06 | 1 | 510.0 | 4063047 | 47823 | 0.37 | ok |
| gen-s7-w2 | 2027-07-07 | 1 | 532.5 | 4009482 | 55169 | 0.38 | ok |
| gen-s7-w2 | 2027-07-08 | 1 | 519.6 | 3101539 | 50813 | 0.30 | ok |
| gen-s7-w2 | 2027-07-09 | 1 | 515.0 | 2806067 | 48667 | 0.29 | ok |
| gen-s7-w2 | 2027-07-10 | 1 | 283.1 | 1539185 | 23633 | 0.18 | ok |
| gen-s7-w2 | 2027-07-12 | 1 | 602.3 | 2920284 | 49109 | 0.36 | ok |
| gen-s7-w2 | 2027-07-13 | 1 | 546.4 | 4047697 | 50574 | 0.35 | ok |
| gen-s7-w2 | 2027-07-14 | 1 | 577.5 | 3497752 | 60168 | 0.36 | ok |
| gen-s7-w2 | 2027-07-15 | 1 | 675.6 | 5968597 | 57958 | 0.41 | ok |
| gen-s7-w2 | 2027-07-16 | 1 | 720.9 | 6237905 | 59784 | 0.44 | ok |
| gen-s7-w2 | 2027-07-17 | 1 | 162.2 | 754856 | 11194 | 0.11 | ok |
| gen-s8-w4 | 2027-09-13 | 1 | 590.0 | 2594581 | 43987 | 0.29 | ok |
| gen-s8-w4 | 2027-09-14 | 1 | 557.8 | 4005082 | 54198 | 0.37 | ok |
| gen-s8-w4 | 2027-09-15 | 1 | 673.0 | 5691181 | 65835 | 0.43 | ok |
| gen-s8-w4 | 2027-09-16 | 1 | 727.1 | 3895137 | 74421 | 0.45 | ok |
| gen-s8-w4 | 2027-09-17 | 1 | 606.4 | 4160919 | 52999 | 0.38 | ok |
| gen-s8-w4 | 2027-09-18 | 1 | 347.2 | 1023658 | 23561 | 0.18 | ok |
| gen-s8-w4 | 2027-09-20 | 1 | 650.6 | 4944951 | 55890 | 0.42 | ok |
| gen-s8-w4 | 2027-09-21 | 1 | 578.2 | 4679476 | 54682 | 0.39 | ok |
| gen-s8-w4 | 2027-09-22 | 1 | 796.2 | 11979978 | 54836 | 0.55 | ok |
| gen-s8-w4 | 2027-09-23 | 1 | 844.1 | 6192318 | 75398 | 0.46 | ok |
| gen-s8-w4 | 2027-09-24 | 1 | 698.0 | 7178968 | 54225 | 0.44 | ok |
| gen-s8-w4 | 2027-09-25 | 1 | 307.5 | 2529467 | 24926 | 0.28 | ok |
| gen-s8-w4 | 2027-09-27 | 1 | 692.4 | 8793738 | 57358 | 0.57 | ok |
| gen-s8-w4 | 2027-09-28 | 1 | 687.7 | 5928068 | 51073 | 0.46 | ok |
| gen-s8-w4 | 2027-09-29 | 1 | 646.3 | 5805485 | 47168 | 0.45 | ok |
| gen-s8-w4 | 2027-09-30 | 1 | 816.2 | 7558423 | 76731 | 0.53 | ok |
| gen-s8-w4 | 2027-10-01 | 1 | 464.9 | 2604678 | 48921 | 0.31 | ok |
| gen-s8-w4 | 2027-10-02 | 1 | 193.6 | 1673705 | 13630 | 0.20 | ok |
| gen-s8-w4 | 2027-10-04 | 1 | 482.7 | 3941524 | 47871 | 0.38 | ok |
| gen-s8-w4 | 2027-10-05 | 1 | 553.9 | 4970795 | 52492 | 0.41 | ok |
| gen-s8-w4 | 2027-10-06 | 1 | 646.0 | 7318630 | 68641 | 0.59 | ok |
| gen-s8-w4 | 2027-10-07 | 1 | 777.5 | 9051121 | 61354 | 0.52 | ok |
| gen-s8-w4 | 2027-10-08 | 1 | 667.4 | 4985231 | 53175 | 0.39 | ok |
| gen-s8-w4 | 2027-10-09 | 1 | 200.6 | 1134152 | 14120 | 0.19 | ok |
| gen-s9-large | 2027-11-01 | 1 | 416.3 | 2513095 | 40544 | 0.34 | ok |
| gen-s9-large | 2027-11-02 | 1 | 563.6 | 2711372 | 50118 | 0.29 | ok |
| gen-s9-large | 2027-11-03 | 1 | 550.1 | 4172644 | 50496 | 0.38 | ok |
| gen-s9-large | 2027-11-04 | 1 | 707.2 | 4610026 | 62052 | 0.42 | ok |
| gen-s9-large | 2027-11-05 | 1 | 766.3 | 6818287 | 68835 | 0.48 | ok |
| gen-s9-large | 2027-11-06 | 1 | 205.3 | 1246447 | 18684 | 0.18 | ok |
| pilot | 2027-03-01 | 1 | 899.6 | 7178039 | 81016 | 0.50 | ok |
| pilot | 2027-03-02 | 1 | 640.8 | 4372876 | 58796 | 0.42 | ok |
| pilot | 2027-03-03 | 1 | 658.3 | 4854295 | 58227 | 0.39 | ok |
| pilot | 2027-03-04 | 1 | 1117.9 | 12359177 | 92928 | 0.68 | ok |
| pilot | 2027-03-05 | 1 | 976.2 | 16793782 | 76749 | 0.62 | failed |
| pilot | 2027-03-06 | 1 | 615.3 | 4547686 | 55382 | 0.39 | ok |

### Per query session

| World | Checkpoint | Store | n | Wall s | Input tokens | Output tokens | Cost USD | Status |
|---|---|---|---|---|---|---|---|---|
| gen-s1-w1 | cp1 | agent | 1 | 224.3 | 956637 | 19256 | 0.20 | ok |
| gen-s1-w1 | cp1 | oracle | 1 | 278.2 | 999277 | 23608 | 0.17 | ok |
| gen-s1-w1 | cp2 | agent | 1 | 202.4 | 814083 | 14478 | 0.13 | ok |
| gen-s1-w1 | cp2 | oracle | 1 | 156.2 | 503035 | 14981 | 0.10 | ok |
| gen-s1-w1 | cp3 | agent | 1 | 234.4 | 1166721 | 20892 | 0.21 | ok |
| gen-s1-w1 | cp3 | oracle | 1 | 244.3 | 1235589 | 19638 | 0.16 | ok |
| gen-s10-w2-small | cp1 | agent | 1 | 195.0 | 767661 | 18127 | 0.13 | ok |
| gen-s10-w2-small | cp1 | oracle | 1 | 91.9 | 245774 | 8650 | 0.05 | ok |
| gen-s10-w2-small | cp2 | agent | 1 | 121.0 | 478772 | 11537 | 0.10 | ok |
| gen-s10-w2-small | cp2 | oracle | 1 | 160.3 | 474528 | 12875 | 0.11 | ok |
| gen-s10-w2-small | cp3 | agent | 1 | 94.6 | 469737 | 8427 | 0.11 | ok |
| gen-s10-w2-small | cp3 | oracle | 1 | 203.9 | 447528 | 15492 | 0.09 | ok |
| gen-s10-w2-small | cp4 | agent | 1 | 236.0 | 757767 | 14191 | 0.15 | ok |
| gen-s10-w2-small | cp4 | oracle | 1 | 233.0 | 629951 | 18735 | 0.12 | ok |
| gen-s10-w2-small | cp5 | agent | 1 | 290.2 | 1710371 | 24900 | 0.24 | ok |
| gen-s10-w2-small | cp5 | oracle | 1 | 250.0 | 1076422 | 19646 | 0.16 | ok |
| gen-s10-w2-small | cp6 | agent | 1 | 367.0 | 1409183 | 33789 | 0.22 | ok |
| gen-s10-w2-small | cp6 | oracle | 1 | 201.9 | 658830 | 15121 | 0.15 | ok |
| gen-s2-w1 | cp1 | agent | 1 | 164.7 | 793264 | 14729 | 0.14 | ok |
| gen-s2-w1 | cp1 | oracle | 1 | 253.1 | 850881 | 19814 | 0.15 | ok |
| gen-s2-w1 | cp2 | agent | 1 | 243.0 | 997747 | 16446 | 0.15 | ok |
| gen-s2-w1 | cp2 | oracle | 1 | 244.5 | 940550 | 18099 | 0.17 | ok |
| gen-s2-w1 | cp3 | agent | 1 | 306.5 | 1494526 | 22768 | 0.22 | ok |
| gen-s2-w1 | cp3 | oracle | 1 | 349.6 | 812964 | 23105 | 0.17 | ok |
| gen-s3-w1 | cp1 | agent | 1 | 176.6 | 1223389 | 17747 | 0.18 | ok |
| gen-s3-w1 | cp1 | oracle | 1 | 219.9 | 592121 | 14483 | 0.14 | ok |
| gen-s3-w1 | cp2 | agent | 1 | 282.1 | 1457991 | 20445 | 0.26 | ok |
| gen-s3-w1 | cp2 | oracle | 1 | 331.3 | 964353 | 22345 | 0.17 | ok |
| gen-s3-w1 | cp3 | agent | 1 | 310.2 | 1268163 | 22828 | 0.23 | ok |
| gen-s3-w1 | cp3 | oracle | 1 | 526.3 | 1730812 | 31153 | 0.24 | ok |
| gen-s4-w2 | cp1 | agent | 1 | 212.7 | 818683 | 22864 | 0.15 | ok |
| gen-s4-w2 | cp1 | oracle | 1 | 178.0 | 798383 | 14861 | 0.13 | ok |
| gen-s4-w2 | cp2 | agent | 1 | 246.4 | 1398967 | 21275 | 0.21 | ok |
| gen-s4-w2 | cp2 | oracle | 1 | 198.9 | 1066957 | 17891 | 0.18 | ok |
| gen-s4-w2 | cp3 | agent | 1 | 359.6 | 2493736 | 27418 | 0.28 | ok |
| gen-s4-w2 | cp3 | oracle | 1 | 262.1 | 1307381 | 21358 | 0.19 | ok |
| gen-s4-w2 | cp4 | agent | 1 | 215.2 | 893183 | 20741 | 0.21 | ok |
| gen-s4-w2 | cp4 | oracle | 1 | 267.0 | 1319737 | 21799 | 0.20 | ok |
| gen-s4-w2 | cp5 | agent | 1 | 268.6 | 1061003 | 23217 | 0.18 | ok |
| gen-s4-w2 | cp5 | oracle | 1 | 250.7 | 919288 | 23050 | 0.17 | ok |
| gen-s4-w2 | cp6 | agent | 1 | 233.5 | 773145 | 19220 | 0.16 | ok |
| gen-s4-w2 | cp6 | oracle | 1 | 177.4 | 975137 | 14547 | 0.14 | ok |
| gen-s5-small | cp1 | agent | 1 | 156.6 | 456765 | 16351 | 0.08 | ok |
| gen-s5-small | cp1 | oracle | 1 | 381.9 | 1049454 | 24291 | 0.18 | ok |
| gen-s5-small | cp2 | agent | 1 | 253.1 | 986704 | 21140 | 0.19 | ok |
| gen-s5-small | cp2 | oracle | 1 | 301.0 | 642193 | 19235 | 0.13 | ok |
| gen-s5-small | cp3 | agent | 1 | 333.3 | 789474 | 22197 | 0.13 | ok |
| gen-s5-small | cp3 | oracle | 1 | 398.4 | 1194864 | 25576 | 0.18 | ok |
| gen-s6-w1 | cp1 | agent | 1 | 343.2 | 1608429 | 23197 | 0.21 | ok |
| gen-s6-w1 | cp1 | oracle | 1 | 449.6 | 997867 | 23140 | 0.15 | ok |
| gen-s6-w1 | cp2 | agent | 1 | 331.9 | 1238048 | 22381 | 0.22 | ok |
| gen-s6-w1 | cp2 | oracle | 1 | 400.7 | 1576565 | 21036 | 0.22 | ok |
| gen-s6-w1 | cp3 | agent | 1 | 469.4 | 1767525 | 25158 | 0.23 | ok |
| gen-s6-w1 | cp3 | oracle | 1 | 381.8 | 542024 | 20329 | 0.14 | ok |
| gen-s7-w2 | cp1 | agent | 1 | 239.8 | 1136010 | 21435 | 0.19 | ok |
| gen-s7-w2 | cp1 | oracle | 1 | 165.5 | 719124 | 14157 | 0.17 | ok |
| gen-s7-w2 | cp2 | agent | 1 | 265.5 | 1183473 | 22202 | 0.18 | ok |
| gen-s7-w2 | cp2 | oracle | 1 | 292.4 | 975331 | 24398 | 0.13 | ok |
| gen-s7-w2 | cp3 | agent | 1 | 406.9 | 2112948 | 25929 | 0.22 | ok |
| gen-s7-w2 | cp3 | oracle | 1 | 273.3 | 1335550 | 22333 | 0.20 | ok |
| gen-s7-w2 | cp4 | agent | 1 | 313.0 | 1958023 | 28281 | 0.25 | ok |
| gen-s7-w2 | cp4 | oracle | 1 | 267.3 | 1305732 | 23242 | 0.17 | ok |
| gen-s7-w2 | cp5 | agent | 1 | 297.8 | 1922200 | 23199 | 0.25 | ok |
| gen-s7-w2 | cp5 | oracle | 1 | 234.5 | 1298714 | 19474 | 0.19 | ok |
| gen-s7-w2 | cp6 | agent | 1 | 312.2 | 1765555 | 25261 | 0.26 | ok |
| gen-s7-w2 | cp6 | oracle | 1 | 208.7 | 1101828 | 18689 | 0.18 | ok |
| gen-s8-w4 | cp1 | agent | 1 | 249.7 | 1367554 | 23178 | 0.23 | ok |
| gen-s8-w4 | cp1 | oracle | 1 | 262.4 | 866035 | 21129 | 0.14 | ok |
| gen-s8-w4 | cp10 | agent | 1 | 214.1 | 1061529 | 20872 | 0.20 | ok |
| gen-s8-w4 | cp10 | oracle | 1 | 258.2 | 1120285 | 17689 | 0.17 | ok |
| gen-s8-w4 | cp11 | agent | 1 | 424.1 | 2280939 | 29755 | 0.24 | ok |
| gen-s8-w4 | cp11 | oracle | 1 | 280.4 | 1298313 | 21090 | 0.20 | ok |
| gen-s8-w4 | cp12 | agent | 1 | 320.9 | 1516827 | 22804 | 0.23 | ok |
| gen-s8-w4 | cp12 | oracle | 1 | 300.7 | 1219986 | 23269 | 0.19 | ok |
| gen-s8-w4 | cp2 | agent | 1 | 285.3 | 1462888 | 24394 | 0.22 | ok |
| gen-s8-w4 | cp2 | oracle | 1 | 254.0 | 618998 | 17313 | 0.11 | ok |
| gen-s8-w4 | cp3 | agent | 1 | 304.4 | 824213 | 20296 | 0.18 | ok |
| gen-s8-w4 | cp3 | oracle | 1 | 377.4 | 1257010 | 23364 | 0.19 | ok |
| gen-s8-w4 | cp4 | agent | 1 | 329.6 | 1900193 | 30419 | 0.26 | ok |
| gen-s8-w4 | cp4 | oracle | 1 | 319.9 | 1140337 | 20348 | 0.16 | ok |
| gen-s8-w4 | cp5 | agent | 1 | 344.6 | 2548305 | 24750 | 0.30 | ok |
| gen-s8-w4 | cp5 | oracle | 1 | 564.7 | 2088603 | 38130 | 0.25 | ok |
| gen-s8-w4 | cp6 | agent | 1 | 365.5 | 2371755 | 31321 | 0.30 | ok |
| gen-s8-w4 | cp6 | oracle | 1 | 298.2 | 996854 | 20353 | 0.19 | ok |
| gen-s8-w4 | cp7 | agent | 1 | 311.2 | 1749591 | 23864 | 0.23 | ok |
| gen-s8-w4 | cp7 | oracle | 1 | 269.9 | 918778 | 17064 | 0.14 | ok |
| gen-s8-w4 | cp8 | agent | 1 | 227.4 | 1159623 | 20140 | 0.21 | ok |
| gen-s8-w4 | cp8 | oracle | 1 | 276.8 | 992882 | 17696 | 0.17 | ok |
| gen-s8-w4 | cp9 | agent | 1 | 313.2 | 2174324 | 25242 | 0.24 | ok |
| gen-s8-w4 | cp9 | oracle | 1 | 303.4 | 1388903 | 21394 | 0.19 | ok |
| gen-s9-large | cp1 | agent | 1 | 310.7 | 1613570 | 21828 | 0.24 | ok |
| gen-s9-large | cp1 | oracle | 1 | 269.5 | 1240290 | 24691 | 0.18 | ok |
| gen-s9-large | cp2 | agent | 1 | 333.8 | 1930650 | 27035 | 0.30 | ok |
| gen-s9-large | cp2 | oracle | 1 | 223.8 | 1454109 | 21725 | 0.21 | ok |
| gen-s9-large | cp3 | agent | 1 | 346.9 | 1883941 | 30177 | 0.24 | ok |
| gen-s9-large | cp3 | oracle | 1 | 295.5 | 1237724 | 28954 | 0.18 | ok |
| pilot | cp1 | agent | 1 | 290.1 | 1511143 | 26538 | 0.20 | ok |
| pilot | cp1 | oracle | 1 | 214.4 | 1122089 | 18773 | 0.16 | ok |
| pilot | cp2 | agent | 1 | 417.1 | 1581124 | 31013 | 0.28 | ok |
| pilot | cp2 | oracle | 1 | 267.3 | 1149686 | 26500 | 0.21 | ok |
| pilot | cp3 | agent | 1 | 282.4 | 1527302 | 21980 | 0.24 | ok |
| pilot | cp3 | oracle | 1 | 250.4 | 1237243 | 21831 | 0.24 | ok |

## Failure samples

The 10 lowest-scoring questions, with gold and predicted answers (dev worlds only; never publish these for test worlds).

### 1. gen-s1-w1 r1 cp3 q-045 (point, person_attr): score 0.00 [name_collision, unobservable]

Question: Which office or building does Jalen Sandberg work from?

Base 0.00, citation precision n/a; the question is unanswerable (gold: abstain)

Gold:

```json
"abstain"
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.75,
  "value": "Office of Civic Technology",
  "note": "Jalen Sandberg's record lists the Office of Civic Technology as his organization; the store contains no separate physical office or building location for him.",
  "cites": [
    "people/jalen-sandberg",
    "orgs/office-of-civic-technology",
    "logs/2027-10-25"
  ]
}
```

### 2. gen-s10-w2-small r1 cp2 q-017 (point, project_attr): score 0.00 [new_entity, restructuring]

Question: What phase is Holworth Duplicate Client Records Discovery in?

Base 0.00, citation precision n/a

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
  "abstain": true
}
```

### 3. gen-s10-w2-small r1 cp4 q-036 (change, project_changes): score 0.00 [endorsement]

Question: What changed on Pipit since the end of Friday 3 September?

Base 0.00, citation precision 1.00

Gold:

```json
{
  "items": [
    {
      "event": "e-0192",
      "summary": "Akosua owes Aoife the Pipit action log",
      "date": "2027-09-07",
      "type": "commitment.create",
      "keywords": [
        "action log",
        "pipit"
      ],
      "support": [
        "ch-0064"
      ]
    },
    {
      "event": "e-0203",
      "summary": "Sipho asked me to review the Pipit board paper (not yet agreed)",
      "date": "2027-09-07",
      "type": "commitment.create",
      "keywords": [
        "board paper",
        "pipit"
      ],
      "support": [
        "em-0094"
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
  "confidence": 0.9,
  "items": [
    {
      "text": "Akosua Bergstrom said she would send me the Pipit action log, so that loop is now waiting on her.",
      "date": "2027-09-07",
      "cites": [
        "ch-0064",
        "logs/2027-09-07",
        "loops/send-aoife-the-pipit-action-log",
        "projects/pipit"
      ]
    },
    {
      "text": "Sipho Papadopoulos asked me to review his Pipit board paper, creating a new open (suggested) ask.",
      "date": "2027-09-07",
      "cites": [
        "em-0094",
        "logs/2027-09-07",
        "loops/review-sipho-s-pipit-board-paper",
        "projects/pipit"
      ]
    }
  ]
}
```

### 4. gen-s10-w2-small r1 cp6 q-065 (point, project_attr): score 0.00

Question: What is currently blocking Holworth Pantry Inventory Discovery?

Base 0.00, citation precision 0.60

Gold:

```json
{
  "kind": "text",
  "value": "unsigned data-sharing agreement with Holworth",
  "entity": null,
  "accept": [
    "unsigned data-sharing agreement with Holworth"
  ]
}
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.86,
  "value": "Unsigned Holworth data-sharing agreement and process-map access approval",
  "note": "The project's current-state paragraph identifies the unsigned Holworth data-sharing agreement as the current blocker, while the process map is separately blocked pending access approval; its blocker line lists both.",
  "cites": [
    "projects/holworth-pantry-inventory-discovery",
    "loops/countersign-the-holworth-data-sharing-agreement",
    "loops/send-akosua-the-pantry-inventory-discovery-process-map",
    "em-0108",
    "mn-0027"
  ]
}
```

### 5. gen-s4-w2 r1 cp3 q-033 (change, project_changes): score 0.00

Question: What changed on Cairn since the end of Thursday 9 September?

Base 0.00, citation precision 0.80

Gold:

```json
{
  "items": [
    {
      "event": "e-0238",
      "summary": "Bruna fixed the Cairn broken deep links",
      "date": "2027-09-10",
      "type": "commitment.resolve",
      "keywords": [
        "broken deep links",
        "cairn"
      ],
      "support": [
        "ch-0101"
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
  "confidence": 0.94,
  "items": [
    {
      "text": "Bruna Vaughan's fix to the Cairn broken deep links was reported by Meera Bondarenko, and Ottavio confirmed the link worked. This followed the 8 September rollback of the earlier fix.",
      "date": "2027-09-10",
      "cites": [
        "ch-0101",
        "loops/fix-the-cairn-broken-deep-links",
        "projects/cairn",
        "logs/2027-09-10",
        "mt-0012"
      ]
    }
  ]
}
```

### 6. gen-s5-small r1 cp1 q-008 (point, project_attr): score 0.00

Question: What is currently blocking Wagtail?

Base 0.00, citation precision 1.00

Gold:

```json
{
  "kind": "text",
  "value": "real patient data paused pending the security review",
  "entity": null,
  "accept": [
    "real patient data paused pending the security review"
  ]
}
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.9,
  "value": "Security review",
  "note": "Real patient data at Wagtail is paused pending the security review, so the security review is the blocking obstacle.",
  "cites": [
    "projects/wagtail",
    "logs/2027-03-18",
    "mn-0003"
  ]
}
```

### 7. gen-s7-w2 r1 cp2 q-021 (point, project_attr): score 0.00

Question: What is currently blocking Elmwick Alumni Outreach Discovery?

Base 0.00, citation precision 0.33

Gold:

```json
{
  "kind": "text",
  "value": "unsigned data-sharing agreement with Elmwick",
  "entity": null,
  "accept": [
    "unsigned data-sharing agreement with Elmwick"
  ]
}
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.76,
  "value": "None",
  "note": "No current blocker is recorded for Elmwick Alumni Outreach Discovery. The earlier baseline-data blocker tied to the unsigned data-sharing agreement was superseded on 2027-07-05 when the approach A decision ended work on that agreement.",
  "cites": [
    "projects/elmwick-alumni-outreach-discovery",
    "loops/countersign-the-elmwick-data-sharing-agreement",
    "nt-0006"
  ]
}
```

### 8. gen-s7-w2 r1 cp3 q-033 (change, project_changes): score 0.00 [silent_closure]

Question: What changed on Elmwick Alumni Outreach Discovery since the end of Thursday 8 July?

Base 0.00, citation precision 1.00

Gold:

```json
{
  "items": [
    {
      "event": "e-0227",
      "summary": "Desmond set up alumni outreach discovery sandbox access for Hiba",
      "date": "2027-07-09",
      "type": "commitment.resolve",
      "keywords": [
        "sandbox access",
        "alumni outreach discovery"
      ],
      "support": [
        "ch-0094"
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
  "confidence": 0.85,
  "items": [
    {
      "text": "Alumni outreach discovery sandbox access is sorted, and I am starting the walkthrough on 2027-07-10; the related sandbox-access loop is now done.",
      "date": "2027-07-09",
      "cites": [
        "projects/elmwick-alumni-outreach-discovery",
        "loops/set-up-alumni-outreach-discovery-sandbox-access-for-hiba",
        "ch-0094"
      ]
    }
  ]
}
```

### 9. gen-s7-w2 r1 cp4 q-046 (priority, focus_tomorrow): score 0.00 [duplicate_signal, endorsement, implied_commitment, new_entity, restructuring, scattered_evidence, supersession, unobservable, worker_directive]

Question: What should I focus on tomorrow?

Base 0.00, citation precision 0.82

Gold:

```json
{
  "tomorrow": "2027-07-14",
  "must_include": [
    {
      "loop": "c-058",
      "what": "Complete the Garnet privacy impact assessment",
      "counterparty": "p-tyrone-duarte",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-07-07",
      "keywords": [
        "privacy impact assessment",
        "garnet"
      ],
      "support": [
        "em-0087"
      ]
    }
  ],
  "worker_active": [
    {
      "loop": "c-058",
      "what": "Complete the Garnet privacy impact assessment",
      "counterparty": "p-tyrone-duarte",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-07-07",
      "keywords": [
        "privacy impact assessment",
        "garnet"
      ],
      "support": [
        "em-0087"
      ]
    },
    {
      "loop": "c-055",
      "what": "Send Funmilayo the assessment design workshop slides v2",
      "counterparty": "p-bolat-oyelami",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-07-15",
      "keywords": [
        "slides v2",
        "assessment design workshop"
      ],
      "support": [
        "mn-0013",
        "nt-0010"
      ]
    },
    {
      "loop": "c-089",
      "what": "Send Ewan the admissions triage selection reference-check notes",
      "counterparty": "p-ewan-laine",
      "direction": "i_owe",
      "status": "open",
      "due": "2027-07-15",
      "keywords": [
        "reference-check notes",
        "admissions triage selection"
      ],
      "support": [
     
... (truncated)
```

Predicted:

```json
{
  "type": "priority",
  "abstain": false,
  "confidence": 0.86,
  "items": [
    {
      "text": "Prepare for and attend the Garnet review with Ewan and Bolat",
      "due": "2027-07-14",
      "why": "The review is scheduled for tomorrow on the active Garnet pilot, whose security-review blocker is the project's main constraint.",
      "cites": [
        "ca-0020",
        "projects/garnet",
        "logs/2027-07-13"
      ]
    },
    {
      "text": "Walk Ewan through the Garnet stakeholder map",
      "due": "2027-07-14",
      "why": "I committed to this walkthrough and it is scheduled for tomorrow; the loop is still open and due 2027-07-14.",
      "cites": [
        "ch-0101",
        "ca-0019",
        "loops/walk-ewan-through-the-garnet-stakeholder-map"
      ]
    },
    {
      "text": "Look into the Garnet timeout errors",
      "due": null,
      "why": "Adaeze flagged at the 13 July security review that the timeout errors are still not right, and I took them on; this directly affects the security-review blocker.",
      "cites": [
        "mt-0019",
        "loops/look-into-the-garnet-timeout-errors",
        "projects/garnet"
      ]
    },
    {
      "text": "Send Ewan the admissions triage selection reference-check notes",
      "due": "2027-07-15",
      "why": "The deadline is 15 July, corrected from 16 July, and the loop is still open.",
      "cites": [
        "ch-0107",
        "loops/send-ewan-the-admissions-triage-selection-reference-check-notes",

... (truncated)
```

### 10. gen-s7-w2 r1 cp6 q-085 (point, project_attr): score 0.00

Question: What phase is Iselbury Thesis Formatting Idea in?

Base 0.00, citation precision 0.67

Gold:

```json
{
  "kind": "text",
  "value": "placeholder",
  "entity": null,
  "accept": [
    "placeholder"
  ]
}
```

Predicted:

```json
{
  "type": "point",
  "abstain": false,
  "confidence": 0.82,
  "value": "merged",
  "note": "Merged into Corrie on 2027-07-16; no separate phase is recorded for the project.",
  "cites": [
    "projects/iselbury-thesis-formatting-idea",
    "nt-0014",
    "projects/corrie"
  ]
}
```
