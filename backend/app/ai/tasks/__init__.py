from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AITaskSpec:
    task_type: str
    execution_mode: str
    default_model: str


TASK_SPECS = {
    "document_parse": AITaskSpec("document_parse", "fixed_function", "document-parse"),
    "information_extract": AITaskSpec(
        "information_extract", "fixed_function", "information-extract"
    ),
    "contract_generate": AITaskSpec("contract_generate", "fixed_function", "solar-pro3"),
    "contract_review": AITaskSpec("contract_review", "bounded_agent", "solar-pro3"),
    "public_summary": AITaskSpec("public_summary", "fixed_function", "solar-pro3"),
    "localize_explain": AITaskSpec("localize_explain", "fixed_function", "solar-pro3"),
    "revision_draft": AITaskSpec("revision_draft", "fixed_function", "solar-pro3"),
}

__all__ = ["AITaskSpec", "TASK_SPECS"]
