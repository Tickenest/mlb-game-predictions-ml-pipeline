import React, { useState } from "react";

function RecentResults({ data }) {
    const [filter, setFilter] = useState("all");

    if (!data || data.length === 0) {
        return (
            <div className="card">
                <h2>Recent Predictions</h2>
                <p style={{ color: "var(--text-secondary)" }}>
                    No recent predictions available yet.
                </p>
            </div>
        );
    }

    // Enrich with correct/incorrect — we don't have actual results
    // stored yet so we show all predictions with pending status
    const filtered = filter === "all"
        ? data
        : data.filter((g) => g.result === filter);

    const correct = data.filter((g) => g.result === "correct").length;
    const total = data.filter((g) => g.result !== undefined && g.result !== "pending").length;
    const accuracy = total > 0 ? ((correct / total) * 100).toFixed(1) : null;

    return (
        <div className="card">
            <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16
            }}>
                <h2 style={{ marginBottom: 0 }}>Recent Predictions</h2>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    {accuracy && (
                        <span style={{
                            fontSize: "0.85rem",
                            color: "var(--text-secondary)",
                            marginRight: 8
                        }}>
                            Recent accuracy: <strong>{accuracy}%</strong>
                        </span>
                    )}
                    {["all", "correct", "incorrect", "pending"].map((f) => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            style={{
                                padding: "3px 10px",
                                borderRadius: 4,
                                border: "1px solid var(--border)",
                                background: filter === f ? "var(--accent)" : "var(--button-bg)",
                                color: filter === f ? "white" : "var(--button-text)",
                                cursor: "pointer",
                                fontSize: "0.82rem",
                                textTransform: "capitalize",
                            }}
                        >
                            {f}
                        </button>
                    ))}
                </div>
            </div>
            <table className="data-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Matchup</th>
                        <th>Predicted Winner</th>
                        <th>Confidence</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {filtered.map((game, idx) => (
                        <tr key={idx}>
                            <td style={{ whiteSpace: "nowrap", color: "var(--text-secondary)" }}>
                                {game.date}
                            </td>
                            <td style={{ whiteSpace: "nowrap" }}>
                                {game.away_team_abbrev} @ {game.home_team_abbrev}
                            </td>
                            <td className="predicted-winner">
                                {game.predicted_winner}
                            </td>
                            <td style={{
                                fontWeight: 600,
                                color: game.confidence >= 0.65
                                    ? "var(--good)"
                                    : game.confidence >= 0.55
                                    ? "var(--neutral)"
                                    : "var(--text-secondary)"
                            }}>
                                {(game.confidence * 100).toFixed(1)}%
                            </td>
                            <td>
                                {game.result === "correct" ? (
                                    <span className="badge badge-win">✓ Correct</span>
                                ) : game.result === "incorrect" ? (
                                    <span className="badge badge-loss">✗ Wrong</span>
                                ) : (
                                    <span className="badge badge-pending">Pending</span>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default RecentResults;