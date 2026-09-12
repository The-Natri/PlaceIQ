"""
Trains the placement-probability model directly off the live database — NOT
off a static CSV export — so the model always reflects whatever the current
`student` table actually contains (re-run this after re-seeding, or
periodically in a real deployment as more outcomes accumulate).

FEATURES: cgpa, backlogs, dept_id (categorical), skill_count (derived by
counting each student's student_skill rows). LABEL: placement_status ==
'Placed'. These are exactly the columns db/seed.py was written to make
predictive (see the big comment at the top of that file) — CGPA in
particular should dominate the model's coefficients, which is the "real
signal, not random" property the assignment spec asks for.

MODEL: logistic regression over a ColumnTransformer (StandardScaler on the
numeric features, OneHotEncoder on dept_id). Logistic regression was chosen
over a heavier model because (a) the spec explicitly allows it, (b) with
only 4 features, a linear decision boundary is already expressive enough,
and (c) its coefficients are directly inspectable — useful if you're asked
in the viva "what does the model think matters most".
"""
import os

import joblib
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, "..", ".env"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://placement_admin:placement_dev_password@localhost:5432/placement_db",
)
MODEL_PATH = os.path.join(_here, "model", "model.joblib")

FEATURE_COLUMNS = ["cgpa", "backlogs", "dept_id", "skill_count"]
NUMERIC_FEATURES = ["cgpa", "backlogs", "skill_count"]
CATEGORICAL_FEATURES = ["dept_id"]


def fetch_training_data() -> pd.DataFrame:
    """
    Raw psycopg2 (not pandas.read_sql + SQLAlchemy) to stay consistent with
    the rest of this project's "no ORM/heavier DB layer than necessary"
    choice, and to avoid pandas' DBAPI2-connection deprecation warning.
    """
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT s.student_id, s.cgpa, s.backlogs, s.dept_id,
                   COUNT(ss.skill_id) AS skill_count,
                   (s.placement_status = 'Placed') AS placed
            FROM student s
            LEFT JOIN student_skill ss ON ss.student_id = s.student_id
            GROUP BY s.student_id, s.cgpa, s.backlogs, s.dept_id, s.placement_status
            """
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    return pd.DataFrame(rows)


def build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        # handle_unknown="ignore": if a department id shows up at inference
        # time that wasn't in the training set (shouldn't happen once
        # seeded, but guards against a future new department), the encoder
        # zeroes that column instead of raising — degrade gracefully rather
        # than 500 the dashboard widget.
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    return Pipeline([
        ("preprocess", preprocessor),
        ("clf", LogisticRegression(max_iter=1000)),
    ])


def main():
    df = fetch_training_data()
    if len(df) < 20:
        raise RuntimeError(
            f"Only {len(df)} students in the database — run db/seed.py first."
        )

    X = df[FEATURE_COLUMNS]
    y = df["placed"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    train_acc = accuracy_score(y_train, pipeline.predict(X_train))
    test_acc = accuracy_score(y_test, pipeline.predict(X_test))
    test_auc = roc_auc_score(y_test, pipeline.predict_proba(X_test)[:, 1])

    print(f"Training rows: {len(X_train)}, test rows: {len(X_test)}")
    print(f"Train accuracy: {train_acc:.3f}")
    print(f"Test accuracy:  {test_acc:.3f}")
    print(f"Test ROC-AUC:   {test_auc:.3f}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
