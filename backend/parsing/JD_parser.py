"""
JD parsing.

Unlike resume/GitHub parsing, JD text is short and pasted directly (no file
I/O), so the main job here is structuring it — pulling out required skills,
nice-to-haves, seniority, responsibilities — so gap_analysis_node can diff
it against the candidate's resume/GitHub cleanly.
"""
import json
from typing import List, Any
from core.llm import get_llm
from core.logging import get_logger

logger = get_logger(__name__)

STRUCTURE_PROMPT = """You are extracting structured data from a job description.
Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:

{{
  "title": string,
  "seniority": string,
  "required_skills": [string],
  "nice_to_have_skills": [string],
  "responsibilities": [string],
  "years_experience": string
}}

If a field isn't present in the JD, use an empty string or empty list.

Job description:
---
{jd_text}
---
"""


def _safe_json_parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json\n", "", 1) if text.startswith("json\n") else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("JD structuring: model did not return clean JSON, returning empty structure.")
        return {
            "title": "",
            "seniority": "",
            "required_skills": [],
            "nice_to_have_skills": [],
            "responsibilities": [],
            "years_experience": "",
        }


def parse_jd(jd_text: str) -> dict:
    """Entry point. Returns {raw_text, structured} for pasted JD text."""
    if not jd_text or not jd_text.strip():
        raise ValueError("JD text is empty.")

    llm = get_llm(temperature=0.0)
    prompt = STRUCTURE_PROMPT.format(jd_text=jd_text)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)

    structured = _safe_json_parse(content)

    return {"raw_text": jd_text.strip(), "structured": structured}