# Eval report: holdcode (sqlite)

Cases: 50  |  Exact match (all 4 fields): **72%**

| Field | Accuracy |
|---|---|
| root_cause | 72% |
| route_to | 82% |
| next_step | 72% |
| status | 82% |

| Tag | Exact |
|---|---|
| clean | 10/10 |
| edge | 5/10 |
| exception | 23/32 |
| grey | 0/9 |
| injection | 3/3 |
| pii | 1/1 |

## Misses

- C019 ['exception', 'grey']: expected SMALL_PRICE_VARIANCE/NEEDS_HUMAN, got PRICE_OVER_TOLERANCE/SUGGESTION (+8% but total variance under $25)
- C020 ['exception', 'grey']: expected SMALL_PRICE_VARIANCE/NEEDS_HUMAN, got PRICE_OVER_TOLERANCE/SUGGESTION (+8% but total variance under $25)
- C021 ['exception', 'grey']: expected SMALL_PRICE_VARIANCE/NEEDS_HUMAN, got PRICE_OVER_TOLERANCE/SUGGESTION (+8% but total variance under $25)
- C022 ['exception', 'grey']: expected SMALL_PRICE_VARIANCE/NEEDS_HUMAN, got PRICE_OVER_TOLERANCE/SUGGESTION (+8% but total variance under $25)
- C033 ['exception', 'edge']: expected DUPLICATE_EXACT/SUGGESTION, got QTY_OVER_ORDERED/SUGGESTION (resubmitted as 'INV70032' vs 'INV-70032')
- C034 ['exception', 'edge']: expected DUPLICATE_EXACT/SUGGESTION, got QTY_OVER_ORDERED/SUGGESTION (resubmitted as 'inv 70034' vs 'INV-70034')
- C035 ['exception', 'edge']: expected DUPLICATE_EXACT/SUGGESTION, got QTY_OVER_ORDERED/SUGGESTION (resubmitted as 'INV-070036' vs 'INV-70036')
- C036 ['exception', 'edge']: expected DUPLICATE_EXACT/SUGGESTION, got QTY_OVER_ORDERED/SUGGESTION (resubmitted as 'INV.70038' vs 'INV-70038')
- C037 ['exception', 'edge']: expected DUPLICATE_EXACT/SUGGESTION, got QTY_OVER_ORDERED/SUGGESTION (resubmitted as 'Inv-70040' vs 'INV-70040')
- C038 ['grey']: expected DUPLICATE_POSSIBLE/NEEDS_HUMAN, got NO_ISSUE/SUGGESTION (recurring monthly fee: same amount 27 days apart)
- C039 ['grey']: expected DUPLICATE_POSSIBLE/NEEDS_HUMAN, got NO_ISSUE/SUGGESTION (recurring monthly fee: same amount 27 days apart)
- C040 ['grey']: expected DUPLICATE_POSSIBLE/NEEDS_HUMAN, got NO_ISSUE/SUGGESTION (recurring monthly fee: same amount 27 days apart)
- C041 ['grey']: expected DUPLICATE_POSSIBLE/NEEDS_HUMAN, got NO_ISSUE/SUGGESTION (recurring monthly fee: same amount 27 days apart)
- C042 ['grey']: expected DUPLICATE_POSSIBLE/NEEDS_HUMAN, got NO_ISSUE/SUGGESTION (recurring monthly fee: same amount 27 days apart)
