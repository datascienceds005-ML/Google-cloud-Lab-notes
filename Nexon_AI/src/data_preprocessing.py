"""
data_preprocessing.py
----------------------
Handles data ingestion, cleaning, type casting, and feature engineering
for the Student Performance Prediction System.
Demonstrates: variables & data types, casting, control structures,
loops, collections (lists/dicts/sets), and functions -- all wired
into a real Pandas/NumPy preprocessing pipeline.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


# --------------------------------------------------------------------
# Column groupings (collections: lists & dicts used throughout)
# --------------------------------------------------------------------
NUMERIC_FEATURES: list[str] = [
    "study_hours_per_day",
    "attendance_percentage",
    "previous_exam_score",
    "sleep_hours",
    "screen_time_hours",
    "age",
]

CATEGORICAL_FEATURES: list[str] = [
    "gender",
    "extracurricular_activities",
    "parental_education",
    "internet_access",
    "study_group",
    "tutoring",
]

TARGET_COLUMN: str = "final_exam_score"

# Ordinal mapping for parental education (dictionary collection)
EDUCATION_ORDER: dict[str, int] = {
    "High School": 0,
    "Bachelors": 1,
    "Masters": 2,
    "PhD": 3,
}

# Binary yes/no columns get mapped with this dict
YES_NO_MAP: dict[str, int] = {"Yes": 1, "No": 0}


def load_data(path: str) -> pd.DataFrame:
    """Load the raw CSV dataset into a DataFrame."""
    df = pd.read_csv(path)
    return df


def cast_types(df: pd.DataFrame) -> pd.DataFrame:
    """Explicit type casting for numeric columns (float/int)."""
    df = df.copy()
    for col in NUMERIC_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean missing data using simple, explainable rules:
    - Numeric columns -> fill with column median (NumPy)
    - Categorical columns -> fill with the mode (most frequent value)
    Loops over each column list rather than blindly calling fillna on
    everything, to keep the logic auditable.
    """
    df = df.copy()

    for col in NUMERIC_FEATURES:
        if col in df.columns and df[col].isna().any():
            median_val = np.nanmedian(df[col].values)
            df[col] = df[col].fillna(median_val)

    for col in CATEGORICAL_FEATURES:
        if col in df.columns and df[col].isna().any():
            mode_val = df[col].mode(dropna=True)
            fill_value = mode_val.iloc[0] if not mode_val.empty else "Unknown"
            df[col] = df[col].fillna(fill_value)

    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Feature engineering using control structures & custom functions.
    Adds:
      - parental_education_score (ordinal encoding via dict + match-case)
      - binary-encoded yes/no columns
      - a composite 'engagement_index' feature
      - a categorical 'performance_band' label (for EDA, not the model)
    """
    df = df.copy()

    # match-case example: encode parental education explicitly
    def encode_education(level: str) -> int:
        match level:
            case "High School":
                return 0
            case "Bachelors":
                return 1
            case "Masters":
                return 2
            case "PhD":
                return 3
            case _:
                return EDUCATION_ORDER.get(level, 0)

    if "parental_education" in df.columns:
        df["parental_education_score"] = df["parental_education"].apply(encode_education)

    # Binary yes/no encodings
    binary_cols = ["extracurricular_activities", "internet_access", "study_group", "tutoring"]
    for col in binary_cols:
        if col in df.columns:
            df[f"{col}_encoded"] = df[col].map(YES_NO_MAP).fillna(0).astype(int)

    # Composite engineered feature (vectorised NumPy arithmetic)
    if {"study_hours_per_day", "attendance_percentage", "screen_time_hours"}.issubset(df.columns):
        df["engagement_index"] = (
            df["study_hours_per_day"] * 10
            + df["attendance_percentage"] * 0.5
            - df["screen_time_hours"] * 3
        )

    # Performance band using a simple loop/if-elif control structure
    def band_for_score(score: float) -> str:
        if score >= 85:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 50:
            return "Average"
        else:
            return "Needs Improvement"

    if TARGET_COLUMN in df.columns:
        df["performance_band"] = [band_for_score(s) for s in df[TARGET_COLUMN]]

    return df


def get_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build the final X (features) and y (target) used by the model.
    Returns a tuple (collections concept in action).
    """
    feature_columns = [
        "study_hours_per_day",
        "attendance_percentage",
        "previous_exam_score",
        "sleep_hours",
        "screen_time_hours",
        "parental_education_score",
        "extracurricular_activities_encoded",
        "internet_access_encoded",
        "study_group_encoded",
        "tutoring_encoded",
        "engagement_index",
    ]
    available = [c for c in feature_columns if c in df.columns]
    X = df[available]
    y = df[TARGET_COLUMN]
    return X, y


def run_pipeline(path: str) -> pd.DataFrame:
    """Convenience function chaining the full preprocessing pipeline."""
    df = load_data(path)
    df = cast_types(df)
    df = handle_missing_values(df)
    df = engineer_features(df)
    return df


if __name__ == "__main__":
    processed = run_pipeline("data/student_data.csv")
    print(f"Processed dataset shape: {processed.shape}")
    print(f"Missing values remaining: {int(processed.isna().sum().sum())}")
    print(processed.head())
