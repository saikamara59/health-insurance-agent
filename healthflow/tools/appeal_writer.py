from datetime import date

from healthflow.models.schemas import CoverageArgument, DenialAnalysis


class AppealWriter:
    """Generates a formal appeal letter template from denial analysis and coverage arguments."""

    def generate(self, analysis: DenialAnalysis, argument: CoverageArgument) -> str:
        today = date.today().strftime("%B %d, %Y")

        denial_code_line = (
            f" (Denial Code: {analysis.denial_reason_code})"
            if analysis.denial_reason_code
            else ""
        )
        policy_section_line = (
            f"\nPolicy Section Cited: {analysis.policy_section_cited}"
            if analysis.policy_section_cited
            else ""
        )
        denial_date_line = (
            f"\nDenial Date: {analysis.denial_date}"
            if analysis.denial_date
            else ""
        )
        appeal_deadline_line = (
            f"\nAppeal Deadline: {analysis.appeal_deadline}"
            if analysis.appeal_deadline
            else ""
        )

        appeal_grounds_lines = "\n".join(
            f"  - {ground}" for ground in argument.common_appeal_grounds
        )

        precedents_lines = "\n".join(
            f"  - {precedent}" for precedent in argument.success_precedents
        )

        letter = f"""{today}

[PATIENT_NAME]
[DOB]
[MEMBER_ID]

RE: Formal Appeal of Denied Claim — {analysis.treatment_denied}{denial_code_line}
Claim Number: [CLAIM_NUMBER]
Treating Provider: [PROVIDER_NAME]

To Whom It May Concern,

I am writing to formally appeal the denial of coverage for {analysis.treatment_denied}. The denial cited the reason: {analysis.denial_reason}{denial_code_line}.{denial_date_line}{appeal_deadline_line}{policy_section_line}

I respectfully disagree with this determination and request a full reconsideration based on the following grounds:

COVERAGE ARGUMENT

{argument.cms_rule}

Based on applicable CMS rules and regulations, this treatment is medically necessary and should be covered. The following appeal grounds support this claim:

{appeal_grounds_lines}

SUPPORTING EVIDENCE AND PRECEDENTS

The following regulatory references and precedents support the coverage of this service:

{precedents_lines}

I request that you review the attached clinical documentation, including physician notes, diagnostic results, and any other supporting materials, which demonstrate the medical necessity of {analysis.treatment_denied}.

SPECIFIC REQUEST

I respectfully request that you overturn the denial and approve coverage for {analysis.treatment_denied}. If additional information is required to process this appeal, please contact me at your earliest convenience.

Thank you for your prompt attention to this matter.

Sincerely,

[PATIENT_NAME]
[DOB]
[MEMBER_ID]
[PROVIDER_NAME]
[CLAIM_NUMBER]
"""
        return letter
