import uuid

from lumini.whatsapp.flow import _STEPS
from lumini.whatsapp.history import minimal_summary


def test_summary_excludes_identifiers_free_text_and_untrusted_ids() -> None:
    service_id = str(uuid.uuid4())
    assert minimal_summary(
        {
            "step": "service",
            "service_id": service_id,
            "professional_id": "arbitrary text",
            "name": "Nome sintético",
            "phone": "+5521999990000",
            "text": "conteúdo clínico",
            "options": ["raw"],
        }
    ) == {"step": "service", "service_id": service_id}
    assert minimal_summary({"step": "texto livre"}) == {}


def test_summary_keeps_every_real_flow_step_without_accepting_arbitrary_values() -> None:
    for step in _STEPS:
        assert minimal_summary({"step": step}) == {"step": step}
    assert minimal_summary({"step": ["untrusted"]}) == {}
