# ML results: placement-probability model

## What the model is

- **Task:** given a student's profile, estimate the probability they get placed.
  The student dashboard shows this (`GET /api/students/:id/placement-probability`,
  which calls the ML service's `POST /predict`).
- **Model:** scikit-learn `LogisticRegression` in a pipeline with `StandardScaler`
  (numeric features) and `OneHotEncoder` (department). Code: `ml-service/train.py`.
- **Features:** `cgpa`, `backlogs`, `skill_count` (counted from `student_skill`),
  `dept_id` (one-hot).
- **Label:** `student.placement_status = 'Placed'`. This is set by the database
  trigger `trg_offer_after_insert`, not typed in by hand.
- **Split:** 80/20, stratified on the label, `random_state=42`.

## Results

Unedited output of `python ml-service/train.py`, run on the freshly seeded
database (Phase 2; the seed is deterministic, so the reseed done before this
evidence was collected produced the same data):

```text
Dataset: 180 students (95 placed, 85 not placed)
Training rows: 144, test rows: 36 (19 placed, 17 not placed)
Train accuracy: 0.875
Test accuracy:  0.750
Test ROC-AUC:   0.774
Confusion matrix on the test set (rows = actual, columns = predicted):
                    pred Not Placed   pred Placed
  actual Not Placed              12             5
  actual Placed                   4            15
Logistic-regression coefficients (log-odds per standard deviation):
  cgpa           +1.496
  backlogs       -1.136
  skill_count    +0.819
  dept_id_3      +0.782
  dept_id_1      -0.637
  dept_id_4      +0.531
  dept_id_5      -0.314
  dept_id_6      -0.180
  dept_id_2      -0.178
  (intercept)    +0.175
Model saved to C:\Users\Naveen M N\college-placement-system\ml-service\model\model.joblib
```

Derived from that confusion matrix (TP = 15, FP = 5, FN = 4, TN = 12):

| Metric | Formula | Value |
|---|---|---|
| Accuracy | (TP + TN) / 36 | 27 / 36 = 0.750 |
| Precision (placed) | TP / (TP + FP) | 15 / 20 = 0.750 |
| Recall (placed) | TP / (TP + FN) | 15 / 19 = 0.789 |
| Specificity | TN / (TN + FP) | 12 / 17 = 0.706 |

## How to read these numbers honestly

- **The test set is tiny: 36 students.** One more right or wrong answer moves
  accuracy by 1/36 ≈ 2.8 percentage points. So 0.750 means "roughly three in four",
  not a precise figure. A different random split could easily give 0.70 or 0.80.
- **The data is synthetic.** `db/seed.py` decides who gets placed using
  rules that favour high CGPA, few backlogs and more skills. The model mostly
  recovers those rules. That shows the pipeline works end to end (database →
  features → model → API → UI). It does **not** show it would predict real
  placements.
- **Train accuracy 0.875 vs test 0.750** is a modest gap. Some overfitting on
  144 rows is expected. Logistic regression was chosen partly because it has few
  parameters and its coefficients can be read directly.
- **The coefficients make sense.** CGPA has the largest positive weight (+1.496
  per standard deviation) and backlogs the largest negative (−1.136). Department
  effects are smaller, and their signs depend on which companies the seed
  assigned to which departments.
- **CGPA is self-reported** at signup in this system. A real deployment would
  need it verified against the institution's records.

## Sample `/predict` requests and responses

Captured from the running ML service (`ml-service/app.py`, port 6000) during
Phase 2 (`raw/ml-predict-samples.txt`, unedited):

```text
$ curl -s http://127.0.0.1:6000/health
{"model_loaded":true,"status":"ok"}


$ curl -s -X POST http://127.0.0.1:6000/predict -H "Content-Type: application/json" -d '{"cgpa": 8.9, "backlogs": 0, "dept_id": 1, "skill_count": 7}'
{"placement_probability":0.992}


$ curl -s -X POST http://127.0.0.1:6000/predict -H "Content-Type: application/json" -d '{"cgpa": 6.1, "backlogs": 3, "dept_id": 1, "skill_count": 2}'
{"placement_probability":0.0027}


$ curl -s -X POST http://127.0.0.1:6000/predict -H "Content-Type: application/json" -d '{"cgpa": 8.9}'   # missing fields
{"error":"Missing required fields: ['backlogs', 'dept_id', 'skill_count']"}

(HTTP 400)

# Backend endpoint (student logs in, asks for own probability):
GET /api/students/15/placement-probability  (student cgpa=9.15, backlogs=0, skills=3, dept=CSE, actual status=Not Placed)
-> HTTP 200 {'placement_probability': 0.9583}
```

Re-run against the same running service while building this evidence pack,
with the same answers, so the deployed model is the one evaluated above:

```text
$ curl -s -X POST http://127.0.0.1:6000/predict -H "Content-Type: application/json" -d '{"cgpa": 8.9, "backlogs": 0, "dept_id": 1, "skill_count": 7}'
{"placement_probability":0.992}

$ curl -s -X POST http://127.0.0.1:6000/predict -H "Content-Type: application/json" -d '{"cgpa": 6.1, "backlogs": 3, "dept_id": 1, "skill_count": 2}'
{"placement_probability":0.0027}

```

The backend example above is a useful reminder of what a probability means.
Student 15 gets 0.9583 but is actually Not Placed. A high probability is
not a guarantee, and with 180 students some confident predictions will be
wrong.
