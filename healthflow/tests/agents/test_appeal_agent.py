from unittest.mock import MagicMock, patch

from healthflow.agents.appeal_agent import AppealAgent


SAMPLE_DENIAL = (
    "Patient: John Smith\n"
    "Member ID: ABC123456\n"
    "DOB: 01/15/1960\n"
    "Date of denial: 03/15/2026\n"
    "\n"
    "Dear John Smith,\n"
    "\n"
    "Your claim for MRI of lumbar spine has been denied.\n"
    "Denial code: CO-50. The service is not deemed medically necessary.\n"
    "Per LCD L35936, this service does not meet coverage criteria.\n"
    "You have 60 days to file an appeal.\n"
)


@patch("healthflow.agents.appeal_agent.anthropic")
def test_full_flow_returns_all_components(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Additional appeal suggestion: request peer-to-peer review.")]
    mock_client.messages.create.return_value = mock_response

    agent = AppealAgent()
    analysis, argument, letter, recommendation = agent.process_appeal(SAMPLE_DENIAL, "")

    assert analysis.denial_reason_code == "CO-50"
    assert argument.cms_rule != ""
    assert len(argument.common_appeal_grounds) > 0
    assert "[PATIENT_NAME]" in letter
    assert recommendation != ""


@patch("healthflow.agents.appeal_agent.anthropic")
def test_claude_receives_redacted_text_only(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Suggestion")]
    mock_client.messages.create.return_value = mock_response

    agent = AppealAgent()
    agent.process_appeal(SAMPLE_DENIAL, "")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "John Smith" not in user_msg
    assert "ABC123456" not in user_msg
    assert "01/15/1960" not in user_msg
    assert "[PATIENT_NAME]" in user_msg or "CO-50" in user_msg


@patch("healthflow.agents.appeal_agent.anthropic")
def test_system_prompt_prohibits_medical_advice(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Suggestion")]
    mock_client.messages.create.return_value = mock_response

    agent = AppealAgent()
    agent.process_appeal(SAMPLE_DENIAL, "")

    call_kwargs = mock_client.messages.create.call_args
    system = call_kwargs.kwargs["system"]
    assert "medical advice" in system.lower()
    assert "guarantee" in system.lower()


@patch("healthflow.agents.appeal_agent.anthropic")
def test_unknown_code_uses_fallback(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Review your appeal rights.")]
    mock_client.messages.create.return_value = mock_response

    denial_text = "Your claim has been denied. Code: CO-9999. The service is not covered."
    agent = AppealAgent()
    analysis, argument, letter, recommendation = agent.process_appeal(denial_text, "")

    assert analysis.denial_reason_code == "CO-9999"
    assert argument.cms_rule != ""
    assert len(argument.common_appeal_grounds) > 0
    assert "[PATIENT_NAME]" in letter


def test_process_appeal_sends_redacted_text_to_claude():
    """The denial text reaching client.messages.create must be redacted."""
    agent = AppealAgent()

    with patch.object(agent.client.messages, "create") as mock_create:
        mock_create.return_value = MagicMock(
            content=[MagicMock(type="text", text="Refined advice.")]
        )
        agent.process_appeal(
            denial_text="Patient: Emily Dickinson denied. DOB: 03/04/1950.",
            additional_context="",
        )

    sent_prompt = mock_create.call_args.kwargs["messages"][0]["content"]
    assert "Emily Dickinson" not in sent_prompt
    assert "[PATIENT_NAME]" in sent_prompt
    assert "03/04/1950" not in sent_prompt
    assert "[DOB]" in sent_prompt
