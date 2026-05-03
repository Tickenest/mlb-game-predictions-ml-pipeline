import React from "react";

function ModelMetrics({ data }) {
    if (!data || Object.keys(data).length === 0) {
        return (
            <div className="card">
                <h2>Model Performance</h2>
                <p style={{ color: "var(--text-secondary)" }}>
                    No metrics available.
                </p>
            </div>
        );
    }

    const test = data.test || {};
    const baseline = test.home_win_rate
        ? (test.home_win_rate * 100).toFixed(1)
        : "54.3";

    return (
        <div className="card">
            <h2>Model Performance</h2>
            <div className="metrics-grid">
                <div className="metric-box">
                    <div className="metric-value">
                        {test.accuracy
                            ? `${(test.accuracy * 100).toFixed(1)}%`
                            : "—"}
                    </div>
                    <div className="metric-label">Test Accuracy</div>
                    <div className="metric-sublabel">
                        Baseline: {baseline}%
                    </div>
                </div>
                <div className="metric-box">
                    <div className="metric-value">
                        {test.auc_roc
                            ? test.auc_roc.toFixed(3)
                            : "—"}
                    </div>
                    <div className="metric-label">AUC-ROC</div>
                    <div className="metric-sublabel">
                        Random = 0.500
                    </div>
                </div>
                <div className="metric-box">
                    <div className="metric-value">
                        {test.log_loss
                            ? test.log_loss.toFixed(3)
                            : "—"}
                    </div>
                    <div className="metric-label">Log Loss</div>
                    <div className="metric-sublabel">
                        Lower is better
                    </div>
                </div>
                <div className="metric-box">
                    <div className="metric-value">
                        {test.n_samples
                            ? test.n_samples.toLocaleString()
                            : "—"}
                    </div>
                    <div className="metric-label">Test Games</div>
                    <div className="metric-sublabel">
                        2025–2026 seasons
                    </div>
                </div>
            </div>
        </div>
    );
}

export default ModelMetrics;