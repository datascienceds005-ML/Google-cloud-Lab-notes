"""
eda.py
------
Exploratory Data Analysis for the Student Performance Prediction System.
Generates distribution plots and a correlation heatmap using
Matplotlib and Seaborn, and prints basic statistical summaries
(mean, median, std, skew) using NumPy/Pandas.
Run: python3 src/eda.py
Outputs PNG charts into assets/
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from data_preprocessing import run_pipeline, NUMERIC_FEATURES, TARGET_COLUMN

sns.set_theme(style="whitegrid")
ASSETS_DIR = "assets"


def summarize_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """Basic probability & statistics summary for numeric features."""
    cols = NUMERIC_FEATURES + [TARGET_COLUMN]
    cols = [c for c in cols if c in df.columns]
    summary = pd.DataFrame({
        "mean": df[cols].mean(),
        "median": df[cols].median(),
        "std_dev": df[cols].std(),
        "skew": df[cols].skew(),
        "min": df[cols].min(),
        "max": df[cols].max(),
    })
    return summary.round(2)


def plot_target_distribution(df: pd.DataFrame) -> None:
    plt.figure(figsize=(8, 5))
    sns.histplot(df[TARGET_COLUMN], kde=True, color="#4C72B0", bins=25)
    plt.title("Distribution of Final Exam Scores")
    plt.xlabel("Final Exam Score")
    plt.ylabel("Number of Students")
    plt.tight_layout()
    plt.savefig(os.path.join(ASSETS_DIR, "score_distribution.png"), dpi=150)
    plt.close()


def plot_correlation_heatmap(df: pd.DataFrame) -> None:
    cols = NUMERIC_FEATURES + [TARGET_COLUMN]
    cols = [c for c in cols if c in df.columns]
    corr = df[cols].corr()

    plt.figure(figsize=(9, 7))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", square=True, cbar_kws={"shrink": 0.8})
    plt.title("Feature Correlation Heatmap")
    plt.tight_layout()
    plt.savefig(os.path.join(ASSETS_DIR, "correlation_heatmap.png"), dpi=150)
    plt.close()


def plot_study_hours_vs_score(df: pd.DataFrame) -> None:
    plt.figure(figsize=(8, 5))
    sns.scatterplot(data=df, x="study_hours_per_day", y=TARGET_COLUMN,
                     hue="performance_band", palette="viridis", alpha=0.7)
    plt.title("Study Hours vs Final Exam Score")
    plt.xlabel("Study Hours per Day")
    plt.ylabel("Final Exam Score")
    plt.tight_layout()
    plt.savefig(os.path.join(ASSETS_DIR, "study_hours_vs_score.png"), dpi=150)
    plt.close()


def plot_performance_band_counts(df: pd.DataFrame) -> None:
    plt.figure(figsize=(7, 5))
    order = ["Needs Improvement", "Average", "Good", "Excellent"]
    sns.countplot(data=df, x="performance_band", order=order, hue="performance_band",
                  palette="Blues_d", legend=False)
    plt.title("Student Count by Performance Band")
    plt.xlabel("Performance Band")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(ASSETS_DIR, "performance_band_counts.png"), dpi=150)
    plt.close()


if __name__ == "__main__":
    os.makedirs(ASSETS_DIR, exist_ok=True)
    df = run_pipeline("data/student_data.csv")

    print("=== Statistical Summary ===")
    print(summarize_statistics(df))

    print("\n=== Correlation with target (final_exam_score) ===")
    cols = NUMERIC_FEATURES + [TARGET_COLUMN]
    print(df[cols].corr()[TARGET_COLUMN].sort_values(ascending=False).round(3))

    plot_target_distribution(df)
    plot_correlation_heatmap(df)
    plot_study_hours_vs_score(df)
    plot_performance_band_counts(df)
    print(f"\nSaved 4 charts to {ASSETS_DIR}/")
