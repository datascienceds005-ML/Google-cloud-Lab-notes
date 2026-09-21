# 🎓 AI Student Performance Prediction System

An end-to-end Machine Learning web application that predicts student final
exam scores from study habits and background data, built with Python,
Pandas, NumPy, Scikit-Learn, and Streamlit.

## Features

- **Data ingestion & cleaning** — loads a real-world-style student dataset,
  casts types, and handles missing values.
- **Feature engineering** — ordinal encoding, binary encoding, and a
  composite "engagement index" feature.
- **EDA** — statistical summaries plus correlation heatmaps and distribution
  charts (Matplotlib/Seaborn).
- **Modeling** — a Scikit-Learn `LinearRegression` model, trained on an
  80/20 split and evaluated with R², MAE, and RMSE.
- **Interactive web app** — a Streamlit UI where anyone can enter a
  student's parameters and get a real-time predicted score.

## Project Structure

```
student-performance-app/
├── app.py                     # Streamlit web application
├── requirements.txt
├── data/
│   ├── generate_dataset.py    # Synthetic dataset generator
│   └── student_data.csv       # Generated dataset (1000 students)
├── src/
│   ├── data_preprocessing.py  # Cleaning + feature engineering pipeline
│   ├── eda.py                 # Exploratory data analysis + charts
│   └── train_model.py         # Model training + evaluation
├── models/                    # Saved model, scaler, and metrics (generated)
└── assets/                    # Saved EDA charts (generated)
```

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. (Optional) Regenerate the dataset

A dataset is already included at `data/student_data.csv`. To regenerate it,
or to swap in your own real-world CSV with the same column names:

```bash
python3 data/generate_dataset.py
```

### 3. Run the EDA

```bash
cd src && python3 eda.py
```

This prints summary statistics and saves charts to `assets/`.

### 4. Train the model

```bash
cd src && python3 train_model.py
```

This trains the Linear Regression model and saves it (plus the scaler and
metrics) to `models/`.

### 5. Launch the web app

From the project root:

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## Dataset

The included dataset (`data/student_data.csv`) is **synthetically generated**
(see `data/generate_dataset.py`) but modeled after common real-world student
performance datasets (study hours, attendance, previous scores, sleep,
screen time, parental education, tutoring, etc.), with realistic noise and
a small amount of injected missing data. To use a real dataset instead,
replace the CSV with your own file using the same column names, or update
the column lists in `src/data_preprocessing.py`.

## Model Performance

On the included dataset, the Linear Regression model achieves:

| Metric | Value |
|---|---|
| R² Score | ~0.74 |
| MAE | ~4.7 points |
| RMSE | ~6.0 points |

(Exact numbers are saved to `models/metrics.json` after training and shown
in the app's sidebar.)

## Deployment

To deploy live on **Streamlit Community Cloud**:

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, and select this repo.
3. Set the main file path to `app.py` and deploy.

Make sure `models/` (or the training scripts) are included in the repo so
the app can load or generate the trained model.

## Tech Stack

- **Python** — core language
- **Pandas / NumPy** — data manipulation and numerical computing
- **Matplotlib / Seaborn** — visualization
- **Scikit-Learn** — Linear Regression modeling
- **Streamlit** — web application UI
- **Git / GitHub** — version control and deployment
