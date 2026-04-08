class DenialCodeDB:
    """Curated database of common CARC/RARC denial codes with CMS rules and appeal arguments."""

    def __init__(self) -> None:
        self._codes: dict[str, dict] = {}
        self._load_codes()

    def lookup(self, code: str) -> dict | None:
        """Look up a denial code. Returns the code entry or None."""
        return self._codes.get(code.upper())

    def search_by_keyword(self, keyword: str) -> dict | None:
        """Case-insensitive substring search on description and category. Returns first match or None."""
        keyword_lower = keyword.lower()
        for entry in self._codes.values():
            if (
                keyword_lower in entry["description"].lower()
                or keyword_lower in entry["category"].lower()
            ):
                return entry
        return None

    def all_codes(self) -> list[dict]:
        """Return all code entries."""
        return list(self._codes.values())

    def _load_codes(self) -> None:
        codes = [
            {
                "code": "CO-4",
                "description": "The procedure code is inconsistent with the modifier used or a required modifier is missing",
                "category": "Coding Error",
                "cms_rule": "Correct Coding Initiative (CCI) edits require proper modifier usage per CMS guidelines. Review NCCI Policy Manual Chapter 1.",
                "appeal_grounds": [
                    "Review and correct modifier usage per CPT guidelines",
                    "Provide operative report documenting distinct procedures",
                    "Reference NCCI Policy Manual for correct modifier pairing",
                ],
                "precedents": [
                    "CMS NCCI Policy Manual — modifier guidelines",
                    "42 CFR §414.40 — Coding and payment for surgical services",
                ],
            },
            {
                "code": "CO-11",
                "description": "The diagnosis is inconsistent with the procedure",
                "category": "Coding Error",
                "cms_rule": "ICD-10 diagnosis must support medical necessity for the billed CPT/HCPCS code per LCD/NCD requirements.",
                "appeal_grounds": [
                    "Review diagnosis codes for accuracy and specificity",
                    "Provide clinical documentation supporting the diagnosis-procedure link",
                    "Reference applicable LCD for covered diagnosis codes",
                ],
                "precedents": [
                    "CMS ICD-10-CM Official Guidelines for Coding",
                    "42 CFR §411.15 — Medical necessity requirements",
                ],
            },
            {
                "code": "CO-16",
                "description": "Claim/service lacks information or has submission/billing error(s)",
                "category": "Billing Error",
                "cms_rule": "Claims must include all required data elements per CMS-1500 or UB-04 form instructions. Missing information causes automatic denial.",
                "appeal_grounds": [
                    "Resubmit claim with all required fields completed",
                    "Verify patient demographics and insurance information",
                    "Include all required supporting documentation",
                    "Check for data entry errors in dates, codes, and identifiers",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 1 §80",
                    "42 CFR §424.5 — Basic conditions for payment",
                ],
            },
            {
                "code": "CO-18",
                "description": "Exact duplicate claim/service",
                "category": "Duplicate Claim",
                "cms_rule": "Medicare does not pay for duplicate claims. If resubmitting, include documentation that services were distinct.",
                "appeal_grounds": [
                    "If not a duplicate, provide documentation of distinct services",
                    "Include modifier 76 or 77 for repeat procedures",
                    "Provide operative notes showing separate sessions or sites",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 1 §80.3.2",
                    "Medicare Benefit Policy Manual Chapter 16",
                ],
            },
            {
                "code": "CO-22",
                "description": "This care may be covered by another payer per coordination of benefits",
                "category": "Coordination of Benefits",
                "cms_rule": "Medicare Secondary Payer (MSP) rules require proper coordination when another insurer is primary. See 42 CFR §411.20-411.206.",
                "appeal_grounds": [
                    "Verify coordination of benefits order",
                    "Submit primary payer EOB with claim",
                    "Provide documentation that Medicare is primary",
                ],
                "precedents": [
                    "42 CFR §411.20-411.206 — Medicare Secondary Payer",
                    "CMS Medicare Secondary Payer Manual Chapter 1",
                ],
            },
            {
                "code": "CO-27",
                "description": "Expenses incurred after coverage terminated",
                "category": "Coverage Terminated",
                "cms_rule": "Services must be rendered during active coverage period. Verify enrollment dates in Medicare Beneficiary Database.",
                "appeal_grounds": [
                    "Verify patient enrollment dates with CMS",
                    "Check for retroactive enrollment or reinstatement",
                    "Provide proof of active coverage at time of service",
                ],
                "precedents": [
                    "42 CFR §406 — Medicare eligibility and enrollment",
                    "CMS Medicare General Information Manual Chapter 2",
                ],
            },
            {
                "code": "CO-29",
                "description": "The time limit for filing has expired",
                "category": "Timely Filing",
                "cms_rule": "Medicare claims must be filed within 1 calendar year of date of service (or 27 months for MSP). See 42 CFR §424.44.",
                "appeal_grounds": [
                    "Document reasons for late filing (administrative error, retroactive eligibility)",
                    "Request good cause exception under 42 CFR §424.44(b)",
                    "Provide evidence of timely filing to primary payer if applicable",
                ],
                "precedents": [
                    "42 CFR §424.44 — Time limits for filing claims",
                    "CMS Claims Processing Manual Chapter 1 §70",
                ],
            },
            {
                "code": "CO-45",
                "description": "Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement",
                "category": "Fee Schedule",
                "cms_rule": "Medicare pays based on the Medicare Physician Fee Schedule (MPFS). Charges exceeding the fee schedule are reduced to the allowed amount.",
                "appeal_grounds": [
                    "Verify correct CPT code and place of service",
                    "Check for geographic adjustment factor errors",
                    "Review for correct modifier application affecting payment",
                ],
                "precedents": [
                    "42 CFR §414.20-414.48 — Medicare Physician Fee Schedule",
                    "CMS Claims Processing Manual Chapter 12",
                ],
            },
            {
                "code": "CO-50",
                "description": "These are non-covered services because this is not deemed a medical necessity",
                "category": "Medical Necessity",
                "cms_rule": "Medicare covers services when medically necessary as defined in Section 1862(a)(1)(A) of the Social Security Act. Documentation must demonstrate the service is reasonable and necessary for diagnosis or treatment.",
                "appeal_grounds": [
                    "Provide detailed clinical documentation supporting medical necessity",
                    "Include physician letter explaining why the service is required",
                    "Reference applicable Local Coverage Determination (LCD) or National Coverage Determination (NCD)",
                    "Submit supporting lab results, imaging, or specialist notes",
                ],
                "precedents": [
                    "CMS Manual Chapter 13 §13.5.1 — Redetermination rights",
                    "42 CFR §405.940-405.958 — Medicare appeals process",
                ],
            },
            {
                "code": "CO-96",
                "description": "Non-covered charge(s). At least one Remark Code must be provided",
                "category": "Non-Covered Service",
                "cms_rule": "Service is not covered under the patient's current benefit plan. Review specific remark codes for the reason.",
                "appeal_grounds": [
                    "Review accompanying remark codes for specific denial reason",
                    "Verify benefit coverage for the service",
                    "Check if prior authorization was required and obtained",
                    "Determine if an alternative covered service exists",
                ],
                "precedents": [
                    "Medicare Benefit Policy Manual Chapter 16",
                    "42 CFR §411.15 — Particular services excluded from coverage",
                ],
            },
            {
                "code": "CO-97",
                "description": "The benefit for this service is included in the payment/allowance for another service/procedure that has already been adjudicated",
                "category": "Bundled Service",
                "cms_rule": "CCI edits bundle certain services together. The component service is included in the comprehensive service payment.",
                "appeal_grounds": [
                    "Review CCI edits for the code pair",
                    "Provide documentation that services were distinct and separate",
                    "Use appropriate modifier (59, XE, XS, XP, XU) if services are truly separate",
                    "Include operative report supporting distinct procedures",
                ],
                "precedents": [
                    "CMS NCCI Policy Manual Chapter 1 — bundling edits",
                    "42 CFR §414.40 — Surgical services payment rules",
                ],
            },
            {
                "code": "CO-109",
                "description": "Claim/service not covered by this payer/contractor. You must send the claim/service to the correct payer/contractor",
                "category": "Wrong Payer",
                "cms_rule": "Claim was submitted to the wrong Medicare Administrative Contractor (MAC) or payer. Redirect to the correct entity.",
                "appeal_grounds": [
                    "Identify the correct payer/contractor for the service",
                    "Resubmit to the correct MAC jurisdiction",
                    "Verify patient's plan assignment and coverage",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 1 §10",
                    "42 CFR §421 — Medicare contracting",
                ],
            },
            {
                "code": "CO-119",
                "description": "Benefit maximum for this time period or occurrence has been reached",
                "category": "Benefit Limit",
                "cms_rule": "Medicare has specific visit or service limits for certain benefits (e.g., therapy caps, preventive services). See Medicare Benefit Policy Manual.",
                "appeal_grounds": [
                    "Verify benefit period dates and utilization counts",
                    "Request exceptions process if available (e.g., therapy cap exception)",
                    "Provide documentation of medical necessity for additional services",
                    "Check if benefit reset applies (new benefit period)",
                ],
                "precedents": [
                    "Medicare Benefit Policy Manual Chapter 15 — therapy services",
                    "42 CFR §410.60-410.62 — Therapy services limitations",
                ],
            },
            {
                "code": "CO-167",
                "description": "This (these) diagnosis(es) is (are) not covered. Note: Refer to the 835 Healthcare Policy Identification Segment",
                "category": "Non-Covered Diagnosis",
                "cms_rule": "The diagnosis code submitted does not meet coverage criteria per the applicable LCD or NCD.",
                "appeal_grounds": [
                    "Review LCD/NCD for covered diagnosis codes",
                    "Update diagnosis coding to most specific ICD-10 code",
                    "Provide clinical documentation supporting the diagnosis",
                    "Request LCD reconsideration if diagnosis should be covered",
                ],
                "precedents": [
                    "CMS LCD/NCD database — applicable determination",
                    "42 CFR §405.920 — Reconsideration of LCD/NCD",
                ],
            },
            {
                "code": "CO-197",
                "description": "Precertification/authorization/notification/pre-treatment absent",
                "category": "Prior Authorization",
                "cms_rule": "Service requires prior authorization that was not obtained before the service was rendered.",
                "appeal_grounds": [
                    "Obtain retroactive authorization if payer allows",
                    "Provide documentation that service was emergent and authorization was not feasible",
                    "Show evidence that authorization was actually obtained (reference number)",
                    "Appeal on grounds of medical necessity for urgent services",
                ],
                "precedents": [
                    "42 CFR §422.568 — MA plan prior authorization requirements",
                    "CMS Interoperability and Prior Authorization Final Rule (CMS-0057-F)",
                ],
            },
            {
                "code": "CO-242",
                "description": "Services not provided by network/primary care providers",
                "category": "Out of Network",
                "cms_rule": "MA plans may require use of in-network providers. Out-of-network services covered only for emergencies or if no in-network provider available.",
                "appeal_grounds": [
                    "Document that no in-network provider was available for the service",
                    "Show that the service was emergent or urgently needed",
                    "Request continuity of care exception if provider recently left network",
                    "Provide evidence of prior authorization for out-of-network care",
                ],
                "precedents": [
                    "42 CFR §422.112 — MA access to services",
                    "CMS Medicare Managed Care Manual Chapter 4",
                ],
            },
            {
                "code": "CO-252",
                "description": "An attachment/other documentation is required to adjudicate this claim/service",
                "category": "Documentation Required",
                "cms_rule": "Additional clinical documentation is needed to process the claim. Submit requested records.",
                "appeal_grounds": [
                    "Submit all requested documentation promptly",
                    "Include cover letter referencing the original claim",
                    "Provide complete medical records for the dates of service",
                    "Ensure documentation supports medical necessity",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 1 §80.3",
                    "42 CFR §424.5(a)(6) — Documentation requirements",
                ],
            },
            {
                "code": "PR-1",
                "description": "Deductible amount",
                "category": "Patient Responsibility",
                "cms_rule": "Patient is responsible for the annual deductible amount before Medicare pays. Part B deductible is set annually by CMS.",
                "appeal_grounds": [
                    "Verify deductible has not already been met for the period",
                    "Check for secondary insurance that covers deductible",
                    "Confirm correct benefit period for deductible application",
                ],
                "precedents": [
                    "42 CFR §410.160 — Part B annual deductible",
                    "Medicare Benefit Policy Manual Chapter 1",
                ],
            },
            {
                "code": "PR-2",
                "description": "Coinsurance amount",
                "category": "Patient Responsibility",
                "cms_rule": "Patient is responsible for the coinsurance percentage after deductible is met. Standard Medicare Part B coinsurance is 20%.",
                "appeal_grounds": [
                    "Verify coinsurance percentage is correctly applied",
                    "Check for secondary insurance or Medigap coverage",
                    "Confirm allowed amount used for coinsurance calculation is correct",
                ],
                "precedents": [
                    "42 CFR §410.152 — Part B coinsurance",
                    "Medicare Claims Processing Manual Chapter 12",
                ],
            },
            {
                "code": "PR-3",
                "description": "Co-payment amount",
                "category": "Patient Responsibility",
                "cms_rule": "Patient is responsible for the plan copayment amount for the service type. MA plans set copay amounts in the Evidence of Coverage.",
                "appeal_grounds": [
                    "Verify copay amount matches the plan's Evidence of Coverage",
                    "Check if service category was correctly classified",
                    "Confirm in-network vs out-of-network copay was correctly applied",
                ],
                "precedents": [
                    "42 CFR §422.100 — MA plan cost sharing requirements",
                    "Medicare Managed Care Manual Chapter 4",
                ],
            },
            {
                "code": "PR-96",
                "description": "Non-covered charge(s) - patient responsibility",
                "category": "Patient Responsibility",
                "cms_rule": "Service is not covered and patient is responsible for the full charge. Review ABN (Advance Beneficiary Notice) requirements.",
                "appeal_grounds": [
                    "Verify an ABN was properly issued before the service",
                    "Challenge whether the service should be covered",
                    "Check if alternative covered service codes apply",
                    "Request plan reconsideration with supporting documentation",
                ],
                "precedents": [
                    "CMS ABN requirements — Form CMS-R-131",
                    "42 CFR §411.404 — Advance Beneficiary Notice",
                ],
            },
            {
                "code": "PR-204",
                "description": "This service/equipment/drug is not covered under the patient's current benefit plan",
                "category": "Not Covered by Plan",
                "cms_rule": "The service is excluded from the patient's specific plan benefits. Review the plan's Evidence of Coverage for exclusions.",
                "appeal_grounds": [
                    "Review the plan's Evidence of Coverage for the specific exclusion",
                    "Request coverage determination or exception",
                    "Provide medical necessity documentation for exception request",
                    "Consider plan change during Open Enrollment if service is needed",
                ],
                "precedents": [
                    "42 CFR §422.568 — MA coverage determination process",
                    "Medicare Managed Care Manual Chapter 13",
                ],
            },
            {
                "code": "OA-18",
                "description": "Exact duplicate claim/service (Outpatient Adjudication)",
                "category": "Duplicate Claim",
                "cms_rule": "Duplicate claim identified during outpatient adjudication. If services are distinct, resubmit with appropriate documentation.",
                "appeal_grounds": [
                    "Provide documentation that services were distinct",
                    "Include appropriate modifiers for repeat or bilateral procedures",
                    "Submit operative notes showing separate encounters",
                ],
                "precedents": [
                    "CMS Claims Processing Manual Chapter 4 — Outpatient claims",
                    "42 CFR §419 — Outpatient prospective payment system",
                ],
            },
            {
                "code": "OA-23",
                "description": "The impact of prior payer(s) adjudication including payments and/or adjustments",
                "category": "Coordination of Benefits",
                "cms_rule": "Payment adjusted based on prior payer's adjudication. Verify coordination of benefits and submit primary payer EOB.",
                "appeal_grounds": [
                    "Submit primary payer's Explanation of Benefits (EOB)",
                    "Verify coordination of benefits order is correct",
                    "Ensure all payer information is current and accurate",
                ],
                "precedents": [
                    "42 CFR §411.20-411.206 — Medicare Secondary Payer",
                    "CMS Medicare Secondary Payer Manual",
                ],
            },
            {
                "code": "N-30",
                "description": "Patient ineligible for this service",
                "category": "Eligibility",
                "cms_rule": "Patient does not meet eligibility criteria for the billed service. Verify enrollment and benefit eligibility.",
                "appeal_grounds": [
                    "Verify patient enrollment and eligibility dates",
                    "Check for retroactive eligibility changes",
                    "Confirm patient meets age, condition, or other eligibility criteria",
                    "Request eligibility verification from CMS",
                ],
                "precedents": [
                    "42 CFR §406 — Medicare eligibility requirements",
                    "CMS Medicare General Information Manual Chapter 2",
                ],
            },
        ]

        for code_entry in codes:
            self._codes[code_entry["code"].upper()] = code_entry
