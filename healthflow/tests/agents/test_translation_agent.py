from unittest.mock import MagicMock, patch
from healthflow.agents.translation_agent import TranslationAgent
from healthflow.models.schemas import DocumentSection


SAMPLE_SECTIONS = [
    DocumentSection(
        title="EMERGENCY CARE",
        content="Emergency room: $90 copay (waived if admitted)\nAmbulance: $250 copay",
    ),
    DocumentSection(
        title="INPATIENT HOSPITAL CARE",
        content="You pay $250 copay per day for days 1-5.\nPrior authorization required.",
    ),
]


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_returns_answer(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The ER copay is $90.")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    answer, section_titles = agent.translate(
        sections=SAMPLE_SECTIONS,
        question="What is the ER copay?",
    )

    assert "ER copay" in answer or "$90" in answer
    mock_client.messages.create.assert_called_once()


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_returns_section_titles(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The answer is...")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    _, section_titles = agent.translate(
        sections=SAMPLE_SECTIONS,
        question="What is the ER copay?",
    )

    assert "EMERGENCY CARE" in section_titles
    assert "INPATIENT HOSPITAL CARE" in section_titles


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_sends_system_prompt_no_medical_advice(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Answer")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    agent.translate(sections=SAMPLE_SECTIONS, question="test?")

    call_kwargs = mock_client.messages.create.call_args
    system = call_kwargs.kwargs["system"]
    assert "medical advice" in system.lower()
    assert "plain" in system.lower() or "clear" in system.lower()


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_includes_sections_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Answer")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    agent.translate(sections=SAMPLE_SECTIONS, question="What is the ER copay?")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "EMERGENCY CARE" in user_msg
    assert "$90 copay" in user_msg


@patch("healthflow.agents.translation_agent.anthropic")
def test_agent_includes_question_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Answer")]
    mock_client.messages.create.return_value = mock_response

    agent = TranslationAgent()
    agent.translate(sections=SAMPLE_SECTIONS, question="What is the ER copay?")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "What is the ER copay?" in user_msg


def test_translate_sends_redacted_prompt_to_claude():
    """The user_prompt reaching client.messages.create must be redacted."""
    agent = TranslationAgent()
    sections = [
        DocumentSection(title="Eligibility", content="Patient: Robert Frost is eligible."),
    ]

    with patch.object(agent.client.messages, "create") as mock_create:
        mock_create.return_value = MagicMock(
            content=[MagicMock(type="text", text="Answer.")]
        )
        agent.translate(sections=sections, question="Dear Robert Frost, what is the copay?")

    sent_prompt = mock_create.call_args.kwargs["messages"][0]["content"]
    assert "Robert Frost" not in sent_prompt
    assert "[PATIENT_NAME]" in sent_prompt
