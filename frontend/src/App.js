import React, { useState, useEffect } from "react";
import TodaysPredictions from "./components/TodaysPredictions";
import RecentResults from "./components/RecentResults";
import ModelMetrics from "./components/ModelMetrics";
import config from "./config";
import "./App.css";

function fetchQuery(queryType, params = {}) {
    return fetch(`${config.apiUrl}/query`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "x-api-key": config.apiKey,
        },
        body: JSON.stringify({ query_type: queryType, params }),
    }).then((res) => res.json());
}

function App() {
    const [darkMode, setDarkMode] = useState(() => {
        return localStorage.getItem("darkMode") === "true";
    });

    const [data, setData] = useState({
        todaysPredictions: null,
        recentPredictions: null,
        modelMetrics: null,
    });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [today] = useState(new Date().toISOString().split("T")[0]);

    useEffect(() => {
        if (darkMode) {
            document.body.classList.add("dark");
        } else {
            document.body.classList.remove("dark");
        }
        localStorage.setItem("darkMode", darkMode);
    }, [darkMode]);

    useEffect(() => {
        Promise.all([
            fetchQuery("todays_predictions", { date: today }),
            fetchQuery("recent_predictions", { days: 7 }),
            fetchQuery("model_metrics"),
        ])
            .then(([todaysPredictions, recentPredictions, modelMetrics]) => {
                setData({
                    todaysPredictions: todaysPredictions.data || [],
                    recentPredictions: recentPredictions.data || [],
                    modelMetrics: modelMetrics.data || {},
                });
                setLoading(false);
            })
            .catch((err) => {
                setError(err.message);
                setLoading(false);
            });
    }, [today]);

    if (loading) {
        return (
            <div className="app">
                <header className="app-header">
                    <div className="header-top">
                        <h1>⚾ MLB Game Predictions</h1>
                        <button
                            className="dark-mode-toggle"
                            onClick={() => setDarkMode((d) => !d)}
                        >
                            {darkMode ? "☀️ Light" : "🌙 Dark"}
                        </button>
                    </div>
                    <p className="subtitle">
                        ML-powered game outcome predictions
                    </p>
                </header>
                <main className="app-main">
                    <div className="card">Loading predictions...</div>
                </main>
            </div>
        );
    }

    if (error) {
        return (
            <div className="app">
                <header className="app-header">
                    <div className="header-top">
                        <h1>⚾ MLB Game Predictions</h1>
                        <button
                            className="dark-mode-toggle"
                            onClick={() => setDarkMode((d) => !d)}
                        >
                            {darkMode ? "☀️ Light" : "🌙 Dark"}
                        </button>
                    </div>
                    <p className="subtitle">
                        ML-powered game outcome predictions
                    </p>
                </header>
                <main className="app-main">
                    <div className="card">Error loading data: {error}</div>
                </main>
            </div>
        );
    }

    return (
        <div className="app">
            <header className="app-header">
                <div className="header-top">
                    <h1>⚾ MLB Game Predictions</h1>
                    <button
                        className="dark-mode-toggle"
                        onClick={() => setDarkMode((d) => !d)}
                        title="Toggle dark mode"
                    >
                        {darkMode ? "☀️ Light" : "🌙 Dark"}
                    </button>
                </div>
                <p className="subtitle">
                    ML-powered game outcome predictions • {today}
                </p>
            </header>
            <main className="app-main">
                <ModelMetrics data={data.modelMetrics} />
                <TodaysPredictions data={data.todaysPredictions} date={today} />
                <RecentResults data={data.recentPredictions} />
            </main>
        </div>
    );
}

export default App;