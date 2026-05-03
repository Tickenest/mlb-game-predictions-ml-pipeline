import React from "react";

function confidenceClass(confidence) {
    if (confidence >= 0.65) return "confidence-high";
    if (confidence >= 0.55) return "confidence-mid";
    return "confidence-low";
}

function ProbBar({ homeProb, awayProb, homeTeam, awayTeam }) {
    return (
        <div style={{ fontSize: "0.85rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ color: "var(--text-secondary)" }}>{awayTeam}</span>
                <span style={{ color: "var(--text-secondary)" }}>{homeTeam}</span>
            </div>
            <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", background: "var(--border)" }}>
                <div style={{
                    width: `${awayProb * 100}%`,
                    background: "var(--text-secondary)",
                    transition: "width 0.3s ease"
                }} />
                <div style={{
                    width: `${homeProb * 100}%`,
                    background: "var(--accent)",
                    transition: "width 0.3s ease"
                }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                <span style={{ fontWeight: 600 }}>{(awayProb * 100).toFixed(1)}%</span>
                <span style={{ fontWeight: 600 }}>{(homeProb * 100).toFixed(1)}%</span>
            </div>
        </div>
    );
}

function TodaysPredictions({ data, date }) {
    if (!data || data.length === 0) {
        return (
            <div className="card">
                <h2>Today's Predictions — {date}</h2>
                <p style={{ color: "var(--text-secondary)" }}>
                    No predictions available for today yet.
                </p>
            </div>
        );
    }

    const sorted = [...data].sort(
        (a, b) => b.confidence - a.confidence
    );

    return (
        <div className="card">
            <h2>Today's Predictions — {date}</h2>
            <table className="data-table">
                <thead>
                    <tr>
                        <th>Matchup</th>
                        <th>Starters</th>
                        <th>Win Probability</th>
                        <th>Predicted Winner</th>
                        <th>Confidence</th>
                    </tr>
                </thead>
                <tbody>
                    {sorted.map((game, idx) => (
                        <tr key={idx}>
                            <td style={{ whiteSpace: "nowrap" }}>
                                <span style={{ color: "var(--text-secondary)" }}>
                                    {game.away_team_abbrev}
                                </span>
                                <span style={{ margin: "0 6px", color: "var(--text-secondary)" }}>
                                    @
                                </span>
                                <span>{game.home_team_abbrev}</span>
                            </td>
                            <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                                <div>{game.away_pitcher}</div>
                                <div>{game.home_pitcher}</div>
                            </td>
                            <td style={{ minWidth: 220 }}>
                                <ProbBar
                                    homeProb={game.home_win_probability}
                                    awayProb={game.away_win_probability}
                                    homeTeam={game.home_team_abbrev}
                                    awayTeam={game.away_team_abbrev}
                                />
                            </td>
                            <td className="predicted-winner">
                                {game.predicted_winner.replace(
                                    /^.+ /,
                                    (m) => m
                                )}
                            </td>
                            <td className={confidenceClass(game.confidence)}>
                                {(game.confidence * 100).toFixed(1)}%
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default TodaysPredictions;