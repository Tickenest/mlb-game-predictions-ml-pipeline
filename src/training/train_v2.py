import pandas as pd
import numpy as np
from pathlib import Path
import pickle
import json

from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score, roc_auc_score, log_loss,
    classification_report, confusion_matrix
)
from sklearn.impute import SimpleImputer
import xgboost as xgb

FEATURES_PATH = Path("data/processed/features_v2.csv")
MODEL_PATH = Path("data/models/xgb_model_v2.pkl")
ENCODERS_PATH = Path("data/models/encoders_v2.pkl")
IMPUTER_PATH = Path("data/models/imputer_v2.pkl")
METRICS_PATH = Path("data/models/metrics_v2.json")

FEATURE_COLS = [
    'month', 'is_day',
    'home_team_enc', 'away_team_enc',
    'home_rolling_win_rate',
    'home_rolling_runs_scored',
    'home_rolling_runs_allowed',
    'home_rolling_run_diff',
    'home_rolling_home_win_rate',
    'away_rolling_win_rate',
    'away_rolling_runs_scored',
    'away_rolling_runs_allowed',
    'away_rolling_run_diff',
    'away_rolling_away_win_rate',
    'home_starter_era',
    'home_starter_whip',
    'home_starter_so9',
    'away_starter_era',
    'away_starter_whip',
    'away_starter_so9',
]

TARGET_COL = 'home_win'


def load_features(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    return df


def encode_teams(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    encoders = {}
    for col in ['home_team', 'away_team']:
        le = LabelEncoder()
        df[f'{col}_enc'] = le.fit_transform(df[col])
        encoders[col] = le
    return df, encoders


def time_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df['season'] <= 2024].copy()
    test = df[df['season'] >= 2025].copy()
    return train, test


def train_model(X_train: pd.DataFrame,
                y_train: pd.Series) -> tuple[xgb.XGBClassifier, SimpleImputer]:
    # Impute missing pitcher stats with median
    imputer = SimpleImputer(strategy='median')
    X_train_imp = imputer.fit_transform(X_train)

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        eval_metric='logloss',
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train_imp, y_train, verbose=False)
    return model, imputer


def evaluate_model(model, imputer, X_test, y_test, label="Test") -> dict:
    X_test_imp = imputer.transform(X_test)
    y_pred = model.predict(X_test_imp)
    y_prob = model.predict_proba(X_test_imp)[:, 1]

    metrics = {
        "label": label,
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "auc_roc": round(roc_auc_score(y_test, y_prob), 4),
        "log_loss": round(log_loss(y_test, y_prob), 4),
        "n_samples": len(y_test),
        "home_win_rate": round(y_test.mean(), 4),
    }

    print(f"\n=== {label} Metrics ===")
    print(f"Accuracy:  {metrics['accuracy']:.4f}")
    print(f"AUC-ROC:   {metrics['auc_roc']:.4f}")
    print(f"Log Loss:  {metrics['log_loss']:.4f}")
    print(f"Samples:   {metrics['n_samples']}")
    print(f"Baseline:  {metrics['home_win_rate']:.4f}")
    print(f"\nClassification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=['Away Win', 'Home Win']))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    return metrics


def feature_importance(model, feature_cols):
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    print("\n=== Feature Importance ===")
    for _, row in importance.iterrows():
        bar = '█' * int(row['importance'] * 100)
        print(f"  {row['feature']:<35} {row['importance']:.4f} {bar}")


def main():
    print("Loading features...")
    df = load_features(FEATURES_PATH)
    print(f"  Total games: {len(df)}")

    print("\nEncoding teams...")
    df, encoders = encode_teams(df)

    print("\nSplitting train/test...")
    train, test = time_split(df)
    print(f"  Train: {len(train)} games ({train['season'].min()}-{train['season'].max()})")
    print(f"  Test:  {len(test)} games ({test['season'].min()}-{test['season'].max()})")

    X_train = train[FEATURE_COLS]
    y_train = train[TARGET_COL]
    X_test = test[FEATURE_COLS]
    y_test = test[TARGET_COL]

    print("\nTraining XGBoost model with pitcher features...")
    model, imputer = train_model(X_train, y_train)
    print("  Training complete.")

    train_metrics = evaluate_model(model, imputer, X_train, y_train, "Train")
    test_metrics = evaluate_model(model, imputer, X_test, y_test, "Test")

    feature_importance(model, FEATURE_COLS)

    # Save everything
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    with open(ENCODERS_PATH, 'wb') as f:
        pickle.dump(encoders, f)
    with open(IMPUTER_PATH, 'wb') as f:
        pickle.dump(imputer, f)
    with open(METRICS_PATH, 'w') as f:
        json.dump({'train': train_metrics, 'test': test_metrics}, f, indent=2)

    print(f"\nModel saved to {MODEL_PATH}")
    print(f"Metrics saved to {METRICS_PATH}")


if __name__ == "__main__":
    main()