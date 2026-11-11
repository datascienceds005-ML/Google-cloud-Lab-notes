"""
train_model.py
---------------
Trains and evaluates a Linear Regression model to predict student
final exam scores, using Scikit-Learn. Saves the fitted model +
a StandardScaler to models/ so the Streamlit app can load them.
Run: python3 src/train_model.py
"""

import os
import json
import pickle

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from data_preprocessing import run_pipeline, get_feature_matrix

MODEL_DIR = "models"


def train_and_evaluate(csv_path: str = "data/student_data.csv", test_size: float = 0.2, random_state: int = 42):
    df = run_pipeline(csv_path)
    X, y = get_feature_matrix(df)
    feature_names = list(X.columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    # Scale features (helps interpretability of coefficients & numerical stability)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LinearRegression()
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)

    metrics = {
        "r2_score": round(r2_score(y_test, y_pred), 4),
        "mae": round(mean_absolute_error(y_test, y_pred), 3),
        "rmse": round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 3),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
    }

    # Feature importance via standardized coefficients
    coef_table = (
        pd.DataFrame({"feature": feature_names, "coefficient": model.coef_})
        .sort_values("coefficient", key=abs, ascending=False)
        .reset_index(drop=True)
    )

    return model, scaler, feature_names, metrics, coef_table


def save_artifacts(model, scaler, feature_names, metrics, coef_table):
    os.makedirs(MODEL_DIR, exist_ok=True)

    with open(os.path.join(MODEL_DIR, "linear_regression_model.pkl"), "wb") as f:
        pickle.dump(model, f)

    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)

    with open(os.path.join(MODEL_DIR, "feature_names.json"), "w") as f:
        json.dump(feature_names, f, indent=2)

    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    coef_table.to_csv(os.path.join(MODEL_DIR, "feature_importance.csv"), index=False)


if __name__ == "__main__":
    model, scaler, feature_names, metrics, coef_table = train_and_evaluate()

    print("=== Model Evaluation ===")
    for k, v in metrics.items():
        print(f"{k}: {v}")

    print("\n=== Feature Importance (standardized coefficients) ===")
    print(coef_table.to_string(index=False))

    save_artifacts(model, scaler, feature_names, metrics, coef_table)
    print(f"\nSaved model + scaler + metadata to {MODEL_DIR}/")
