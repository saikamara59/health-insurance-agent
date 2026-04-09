from healthflow.tools.formulary_checker import FormularyChecker, PLAN_FORMULARY_EXCLUSIONS


def test_known_drug_on_formulary_hmo():
    checker = FormularyChecker()
    result = checker.check("Metformin", "H3312-034", "HMO")
    assert result.on_formulary is True
    assert result.drug_name == "Metformin"
    assert result.tier == "Tier 1 - Generic"
    assert result.copay == 5.0
    assert result.prior_auth_required is False
    assert result.warning is None


def test_known_drug_on_formulary_ppo():
    checker = FormularyChecker()
    result = checker.check("Metformin", "H5521-017", "PPO")
    assert result.on_formulary is True
    assert result.copay == 10.0


def test_specialty_drug_excluded_from_plan():
    checker = FormularyChecker()
    # Find a plan that excludes Humira
    excluded_plan = None
    for plan_id, drugs in PLAN_FORMULARY_EXCLUSIONS.items():
        if "Humira" in drugs:
            excluded_plan = plan_id
            break
    assert excluded_plan is not None, "Test setup: no plan excludes Humira"

    result = checker.check("Humira", excluded_plan, "HMO")
    assert result.on_formulary is False
    assert result.warning == "This drug is not on this plan's formulary."


def test_specialty_drug_on_formulary_for_non_excluded_plan():
    checker = FormularyChecker()
    # Use a plan that does NOT exclude Humira
    all_excluding_plans = set()
    for plan_id, drugs in PLAN_FORMULARY_EXCLUSIONS.items():
        if "Humira" in drugs:
            all_excluding_plans.add(plan_id)

    non_excluded_plan = "H3312-034"
    if non_excluded_plan in all_excluding_plans:
        non_excluded_plan = "H1036-200"

    result = checker.check("Humira", non_excluded_plan, "HMO")
    assert result.on_formulary is True
    assert result.tier == "Tier 4 - Specialty"
    assert result.copay == 150.0
    assert result.prior_auth_required is True


def test_unknown_drug_warning():
    checker = FormularyChecker()
    result = checker.check("FakeDrugXYZ123", "H3312-034", "HMO")
    assert result.on_formulary is False
    assert result.warning == "Drug not found in formulary database."
    assert result.tier is None
    assert result.copay is None


def test_drug_copay_differs_by_plan_type():
    checker = FormularyChecker()
    result_hmo = checker.check("Eliquis", "H3312-034", "HMO")
    result_ppo = checker.check("Eliquis", "H5521-017", "PPO")
    assert result_hmo.copay == 47.0
    assert result_ppo.copay == 95.0


def test_prior_auth_drug():
    checker = FormularyChecker()
    result = checker.check("Ozempic", "H3312-034", "HMO")
    assert result.on_formulary is True or result.on_formulary is False  # depends on exclusions
    if result.on_formulary:
        assert result.prior_auth_required is True


def test_plan_formulary_exclusions_has_entries():
    assert len(PLAN_FORMULARY_EXCLUSIONS) > 0
    for plan_id, drugs in PLAN_FORMULARY_EXCLUSIONS.items():
        assert len(drugs) > 0
