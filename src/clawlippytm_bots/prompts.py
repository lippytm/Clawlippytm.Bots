"""
Prompts — reusable, parameterised prompt templates.

Supports simple ``{variable}`` substitution with optional validation.

Example
-------
    from clawlippytm_bots.prompts import PromptTemplate

    summarise = PromptTemplate(
        template="Summarise the following text in {max_words} words or fewer:\\n\\n{text}",
        description="Summarise arbitrary text",
    )

    print(summarise.render(max_words=100, text="Long article..."))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """A reusable prompt template with ``{placeholder}`` substitution.

    Parameters
    ----------
    template:
        The template string, with ``{variable_name}`` placeholders.
    description:
        Human-readable description of what this template is for.
    defaults:
        Optional default values for placeholders.
    """

    template: str
    description: str = ""
    defaults: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def variables(self) -> list[str]:
        """Return all placeholder names found in the template."""
        return list(dict.fromkeys(re.findall(r"\{(\w+)\}", self.template)))

    @property
    def required_variables(self) -> list[str]:
        """Variables that have no default value."""
        return [v for v in self.variables if v not in self.defaults]

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, **kwargs: str) -> str:
        """Substitute all variables and return the final prompt string.

        Raises
        ------
        ValueError
            If a required variable is not supplied.
        """
        values = {**self.defaults, **kwargs}
        missing = [v for v in self.required_variables if v not in values]
        if missing:
            raise ValueError(f"Missing required template variables: {missing}")
        return self.template.format(**values)

    def __call__(self, **kwargs: str) -> str:
        return self.render(**kwargs)

    def __repr__(self) -> str:
        return f"PromptTemplate(variables={self.variables!r}, description={self.description!r})"


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

SUMMARISE = PromptTemplate(
    template=(
        "Summarise the following text in {max_words} words or fewer. "
        "Focus on the key points and be concise.\n\n"
        "TEXT:\n{text}"
    ),
    description="Summarise arbitrary text",
    defaults={"max_words": "200"},
)

EXTRACT_JSON = PromptTemplate(
    template=(
        "Extract structured data from the text below and return it as valid JSON "
        "matching this schema:\n\n{schema}\n\nTEXT:\n{text}\n\n"
        "Return ONLY the JSON object, with no additional commentary."
    ),
    description="Extract structured JSON data from unstructured text",
)

QA = PromptTemplate(
    template=(
        "You are a knowledgeable assistant. Answer the question below using ONLY "
        "the provided context. If the answer is not in the context, say so.\n\n"
        "CONTEXT:\n{context}\n\nQUESTION:\n{question}"
    ),
    description="Answer a question grounded in provided context (RAG-style)",
)

CODE_REVIEW = PromptTemplate(
    template=(
        "Review the following {language} code and provide concise, actionable feedback "
        "covering: correctness, security, performance, and readability.\n\n"
        "```{language}\n{code}\n```"
    ),
    description="AI-powered code review",
    defaults={"language": "python"},
)

TRANSLATE = PromptTemplate(
    template="Translate the following text to {target_language}:\n\n{text}",
    description="Translate text to another language",
    defaults={"target_language": "English"},
)
