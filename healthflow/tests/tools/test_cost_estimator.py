from healthflow.tools.cost_estimator import CostEstimator


def test_estimate_medication_known():
    estimator = CostEstimator()
    result = estimator.estimate("Metformin", "medication", "HMO")
    assert result is not None
    assert result["estimated_cost"] >= 0
    assert "cost_details" in result
    assert result["cost_details"]["formulary_tier"] is not None


def test_estimate_medication_case_insensitive():
    estimator = CostEstimator()
    result = estimator.estimate("metformin", "medication", "HMO")
    assert result is not None


def test_estimate_medication_fuzzy_match():
    estimator = CostEstimator()
    result = estimator.estimate("Metformin 500mg", "medication", "HMO")
    assert result is not None
    assert "Metformin" in result["item_name"]


def test_estimate_medication_unknown():
    estimator = CostEstimator()
    result = estimator.estimate("MadeUpDrug123", "medication", "HMO")
    assert result is None


def test_estimate_procedure_known():
    estimator = CostEstimator()
    result = estimator.estimate("MRI", "procedure", "PPO")
    assert result is not None
    assert result["estimated_cost"] > 0


def test_estimate_procedure_case_insensitive():
    estimator = CostEstimator()
    result = estimator.estimate("annual physical", "procedure", "HMO")
    assert result is not None


def test_estimate_procedure_unknown():
    estimator = CostEstimator()
    result = estimator.estimate("Brain Transplant", "procedure", "HMO")
    assert result is None


def test_estimate_procedure_hmo_vs_ppo_differs():
    estimator = CostEstimator()
    hmo = estimator.estimate("MRI", "procedure", "HMO")
    ppo = estimator.estimate("MRI", "procedure", "PPO")
    assert hmo is not None
    assert ppo is not None
    assert isinstance(hmo["estimated_cost"], (int, float))
    assert isinstance(ppo["estimated_cost"], (int, float))


def test_estimate_multiple_medications():
    estimator = CostEstimator()
    meds = ["Metformin", "Lisinopril", "Atorvastatin"]
    results = estimator.estimate_multiple(meds, "medication", "HMO")
    assert len(results) == 3
    for med, result in results.items():
        assert result is not None


def test_estimate_multiple_procedures():
    estimator = CostEstimator()
    procs = ["Annual physical", "Blood work"]
    results = estimator.estimate_multiple(procs, "procedure", "PPO")
    assert len(results) == 2
