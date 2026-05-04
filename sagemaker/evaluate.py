import subprocess
import sys

# Install xgboost at runtime since scikit-learn container doesn't include it
subprocess.check_call([sys.executable, "-m", "pip", "install", "xgboost", "-q"])

import pandas as pd
import numpy as np
import json
import os
import glob
import tarfile
from pathlib import Path

# SageMaker paths
MODEL_PATH = Path("/opt/ml/processing/input/model")
TEST_DATA_PATH = Path("/opt/ml/processing/input/test")
OUTPUT_PATH = Path("/opt/ml/processing/output")

def load_model(model_path):
    """Load XGBoost model — find the correct model tarball."""
    import xgboost as xgb

    tarballs = list(model_path.glob("**/*.tar.gz"))
    if not tarballs:
        raise FileNotFoundError(f"No model tarball found in {model_path}")

    # Sort by full path string — execution IDs are roughly chronological
    tarballs.sort(key=lambda p: str(p), reverse=True)
    tarball = tarballs[0]
    print(f"Loading model from {tarball}")
    print(f"All available models: {[str(t) for t in tarballs]}")

    extract_path = model_path / "extracted"
    extract_path.mkdir(exist_ok=True)
    with tarfile.open(tarball, 'r:gz') as tar:
        tar.extractall(extract_path)

    model_files = list(extract_path.glob("**/*.model")) + \
                  list(extract_path.glob("**/xgboost-model"))
    if not model_files:
        raise FileNotFoundError(f"No model file found after extraction")

    model_files.sort(key=lambda p: str(p), reverse=True)
    model = xgb.Booster()
    model.load_model(str(model_files[0]))
    print(f"  Model expects {model.num_features()} features")
    return model


def load_test_data(test_path):
    """Load test CSV — target is first column, no header."""
    csv_files = list(test_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV found in {test_path}")

    df = pd.read_csv(csv_files[0], header=None)
    print(f"  Test CSV shape: {df.shape}")
    print(f"  First few values of first column: {df.iloc[:3, 0].tolist()}")
    print(f"  First few values of second column: {df.iloc[:3, 1].tolist()}")
    y = df.iloc[:, 0].values
    X = df.iloc[:, 1:].values
    print(f"  X shape: {X.shape}, y shape: {y.shape}")
    return X, y


def evaluate(model, X_test, y_test):
    """Evaluate model and return metrics."""
    import xgboost as xgb
    from sklearn.metrics import accuracy_score, roc_auc_score, log_loss

    dtest = xgb.DMatrix(X_test)
    y_prob = model.predict(dtest)
    y_pred = (y_prob > 0.5).astype(int)

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "auc_roc": round(float(roc_auc_score(y_test, y_prob)), 4),
        "log_loss": round(float(log_loss(y_test, y_prob)), 4),
        "n_samples": int(len(y_test)),
        "home_win_rate": round(float(y_test.mean()), 4),
    }

    print(f"\n=== Evaluation Metrics ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    return metrics


def load_current_metrics(output_path):
    """
    Load metrics from the currently deployed model if they exist.
    Returns None if no current model exists.
    """
    current_metrics_path = output_path / "current_metrics.json"
    if current_metrics_path.exists():
        with open(current_metrics_path) as f:
            return json.load(f)
    return None


def main():
    print("Loading model...")
    model = load_model(MODEL_PATH)

    print("Loading test data...")
    X_test, y_test = load_test_data(TEST_DATA_PATH)
    print(f"  Test samples: {len(y_test)}")

    print("Evaluating model...")
    metrics = evaluate(model, X_test, y_test)

    # Check against current model
    current = load_current_metrics(OUTPUT_PATH)
    if current:
        current_acc = current.get("accuracy", 0)
        new_acc = metrics["accuracy"]
        improvement = new_acc - current_acc
        print(f"\nCurrent model accuracy: {current_acc:.4f}")
        print(f"New model accuracy: {new_acc:.4f}")
        print(f"Improvement: {improvement:+.4f}")
        metrics["improvement"] = round(improvement, 4)
        metrics["should_register"] = improvement > 0.001
    else:
        print("\nNo current model found — registering new model.")
        metrics["improvement"] = None
        metrics["should_register"] = True

    # Save evaluation report
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_PATH / "evaluation.json"
    with open(report_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\nEvaluation report saved to {report_path}")

    # Save as new current metrics if registering
    if metrics["should_register"]:
        current_path = OUTPUT_PATH / "current_metrics.json"
        with open(current_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        print("Model approved for registration.")
    else:
        print("Model did not improve — skipping registration.")


if __name__ == "__main__":
    main()