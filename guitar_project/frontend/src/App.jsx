import React, { useEffect, useMemo, useState } from "react";
import "./App.css";

// Steps in the quiz: company (pick one or more), guitar type (fixed
// Acoustic / Classical / Electric choice), then budget last since its
// slider range comes from the backend.
const STEPS = [
  { key: "brands", label: "Company", question: "Which guitar companies are you considering? (pick one or more)" },
  { key: "guitar_type", label: "Type", question: "Acoustic, classical, or electric?" },
  { key: "budget", label: "Budget", question: "What's your budget?" },
];

function FretProgress({ stepIndex }) {
  const fillPct = STEPS.length > 1 ? (stepIndex / (STEPS.length - 1)) * 100 : 0;
  return (
    <div className="fret-progress">
      <div className="fret-progress__fill" style={{ width: `calc(${fillPct}% - 8px)` }} />
      {STEPS.map((step, i) => (
        <div
          key={step.key}
          className={
            "fret-progress__marker " +
            (i < stepIndex
              ? "fret-progress__marker--done"
              : i === stepIndex
              ? "fret-progress__marker--active"
              : "")
          }
        >
          {i < stepIndex ? "\u2713" : i + 1}
          <span className="fret-progress__label">{step.label}</span>
        </div>
      ))}
    </div>
  );
}

function OptionGrid({ options, value, onSelect, loading, emptyMessage, multiSelect = false }) {
  if (loading) {
    return <p className="state-message">Loading options…</p>;
  }
  if (!options || options.length === 0) {
    return (
      <p className="state-message">
        {emptyMessage || "No values found for this field in your catalog — skip ahead."}
      </p>
    );
  }
  const isSelected = (opt) => (multiSelect ? Array.isArray(value) && value.includes(opt) : value === opt);
  return (
    <div className="option-grid">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          className={"option-card" + (isSelected(opt) ? " option-card--selected" : "")}
          onClick={() => onSelect(opt)}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

function GuitarCard({ guitar }) {
  return (
    <div className="guitar-card">
      <p className="guitar-card__brand">{guitar.brand}</p>
      <h3 className="guitar-card__model">{guitar.model}</h3>
      <div className="guitar-card__meta">
        {guitar.price != null && (
          <p className="guitar-card__price">
            ₹{Number(guitar.price).toLocaleString("en-IN")}
          </p>
        )}
        {guitar.rating != null && (
          <p className="guitar-card__rating">
            ★ {Number(guitar.rating).toLocaleString()}
            {guitar.review_count != null && (
              <span className="guitar-card__review-count">
                {" "}
                ({Number(guitar.review_count).toLocaleString()})
              </span>
            )}
          </p>
        )}
      </div>
      {guitar.match_reasons && guitar.match_reasons.length > 0 && (
        <ul className="guitar-card__reasons">
          {guitar.match_reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function App() {
  const [options, setOptions] = useState(null); // { brands, guitar_types, price_range }
  const [optionsError, setOptionsError] = useState(null);

  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState({
    brands: [],
    guitar_type: null,
    budget_max: null,
  });
  const [results, setResults] = useState(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const [resultsError, setResultsError] = useState(null);

  // Load the brand list, guitar types, and price range once, up front.
  useEffect(() => {
    fetch("/api/quiz-options")
      .then((r) => {
        if (!r.ok) throw new Error(`Backend returned ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setOptions(data);
        setAnswers((a) => ({
          ...a,
          budget_max: data.price_range?.max ?? 300000,
        }));
      })
      .catch((err) => setOptionsError(err.message));
  }, []);

  const currentStep = STEPS[stepIndex];
  const isLastStep = stepIndex === STEPS.length - 1;

  const canAdvance = useMemo(() => {
    if (!currentStep) return false;
    if (currentStep.key === "budget") return answers.budget_max != null;
    if (currentStep.key === "brands") return answers.brands.length > 0;
    return Boolean(answers[currentStep.key]);
  }, [currentStep, answers]);

  // brands is multi-select (toggle membership in the array);
  // guitar_type is single-select (toggle on/off).
  function toggleBrand(value) {
    setAnswers((a) => {
      const has = a.brands.includes(value);
      return { ...a, brands: has ? a.brands.filter((b) => b !== value) : [...a.brands, value] };
    });
  }

  function selectGuitarType(value) {
    setAnswers((a) => ({ ...a, guitar_type: a.guitar_type === value ? null : value }));
  }

  function goNext() {
    if (!isLastStep) {
      setStepIndex((i) => i + 1);
    } else {
      submitQuiz();
    }
  }

  function goBack() {
    setStepIndex((i) => Math.max(0, i - 1));
  }

  function submitQuiz() {
    setLoadingResults(true);
    setResultsError(null);
    fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        brands: answers.brands,
        guitar_type: answers.guitar_type,
        budget_min: options?.price_range?.min ?? 0,
        budget_max: answers.budget_max,
        limit: 6,
      }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`Backend returned ${r.status}`);
        return r.json();
      })
      .then((data) => setResults(data.results))
      .catch((err) => setResultsError(err.message))
      .finally(() => setLoadingResults(false));
  }

  function restart() {
    setStepIndex(0);
    setResults(null);
    setResultsError(null);
    setAnswers((a) => ({ ...a, brands: [], guitar_type: null }));
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="hero__eyebrow">Tune your search</p>
        <h1 className="hero__title">Find the guitar that fits your hands.</h1>
        <p className="hero__subtitle">
          Company, model, and budget — matched against the current catalog and the clusters your
          KMeans model found, to get you to a shortlist worth playing in person.
        </p>
      </header>

      {optionsError && (
        <p className="state-message state-message--error">
          Couldn't reach the backend ({optionsError}). Make sure `uvicorn main:app --reload` is
          running on port 8000 and your Databricks connection env vars are set.
        </p>
      )}

      {!optionsError && !options && <p className="state-message">Loading the catalog…</p>}

      {options && results === null && (
        <>
          <FretProgress stepIndex={stepIndex} />
          <div className="quiz-card">
            <h2 className="quiz-card__question">{currentStep.question}</h2>

            {currentStep.key === "brands" && (
              <OptionGrid
                options={options.brands}
                value={answers.brands}
                onSelect={toggleBrand}
                multiSelect
              />
            )}
            {currentStep.key === "guitar_type" && (
              <OptionGrid
                options={options.guitar_types}
                value={answers.guitar_type}
                onSelect={selectGuitarType}
              />
            )}
            {currentStep.key === "budget" && (
              <div>
                <p className="budget-value">
                  Up to ₹{Number(answers.budget_max ?? 0).toLocaleString("en-IN")}
                  <span>INR</span>
                </p>
                <input
                  type="range"
                  min={options.price_range.min}
                  max={options.price_range.max}
                  step={Math.max(1, Math.round((options.price_range.max - options.price_range.min) / 100))}
                  value={answers.budget_max ?? options.price_range.max}
                  onChange={(e) =>
                    setAnswers((a) => ({ ...a, budget_max: Number(e.target.value) }))
                  }
                />
                <div className="budget-range-labels">
                  <span>₹{Math.round(options.price_range.min).toLocaleString("en-IN")}</span>
                  <span>₹{Math.round(options.price_range.max).toLocaleString("en-IN")}</span>
                </div>
              </div>
            )}

            <div className="step-nav">
              <button className="btn" onClick={goBack} disabled={stepIndex === 0}>
                Back
              </button>
              <button className="btn btn--primary" onClick={goNext} disabled={!canAdvance}>
                {isLastStep ? "See my matches" : "Next"}
              </button>
            </div>
          </div>
        </>
      )}

      {loadingResults && <p className="state-message">Matching you to the catalog…</p>}

      {resultsError && (
        <p className="state-message state-message--error">
          Couldn't fetch recommendations ({resultsError}).
        </p>
      )}

      {results !== null && !loadingResults && (
        <div>
          <div className="results-header">
            <h2 className="hero__title" style={{ fontSize: "26px", margin: 0 }}>
              Your matches
            </h2>
            <button className="restart-link" onClick={restart}>
              Start over
            </button>
          </div>
          {results.length === 0 ? (
            <p className="state-message">
              Nothing matched closely enough — try widening your budget, or a different company/model.
            </p>
          ) : (
            <div className="results-grid">
              {results.map((g) => (
                <GuitarCard key={g.id} guitar={g} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}