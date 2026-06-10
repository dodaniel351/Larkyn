from hermes.prompt.profiles import BUILTIN_PROFILES, build_messages, get_profile
from hermes.prompt.system_prompt import SPEC_SYSTEM_PROMPT


def test_general_uses_base_prompt_without_profile_line():
    msgs = build_messages("hello world", get_profile("general"), [])
    assert msgs[0].role == "system"
    assert "You are Larkyn." in msgs[0].content
    # verbatim spec text is present
    assert SPEC_SYSTEM_PROMPT.strip().endswith("Return only the final rewritten text.")
    assert "Writing profile" not in msgs[0].content
    assert msgs[1].role == "user"
    assert msgs[1].content == "hello world"


def test_email_profile_adds_guidance():
    content = build_messages("x", get_profile("email"), [])[0].content
    assert "Writing profile — Email" in content
    assert "professional email" in content.lower()


def test_vocabulary_injected_into_system_prompt():
    content = build_messages("x", get_profile("it_ops"), ["LibreNMS", "Graylog"])[0].content
    assert "LibreNMS" in content and "Graylog" in content
    assert "exactly as written" in content


def test_all_seven_builtin_profiles_present():
    expected = {"general", "email", "technical", "meeting_notes",
                "exec_summary", "clinical", "it_ops"}
    assert expected <= set(BUILTIN_PROFILES)


def test_unknown_profile_falls_back_to_general():
    assert get_profile("does_not_exist").key == "general"
