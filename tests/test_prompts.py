"""Tests for prompts.py."""

from __future__ import annotations

import pytest

from clawlippytm_bots.prompts import (
    CODE_REVIEW,
    EXTRACT_JSON,
    QA,
    SUMMARISE,
    TRANSLATE,
    PromptTemplate,
)


class TestPromptTemplate:
    def test_variables(self):
        t = PromptTemplate(template="Hello {name}, you are {age} years old.")
        assert t.variables == ["name", "age"]

    def test_render_basic(self):
        t = PromptTemplate(template="Say {word}!")
        assert t.render(word="hi") == "Say hi!"

    def test_render_with_defaults(self):
        t = PromptTemplate(template="Count to {n}", defaults={"n": "10"})
        assert t.render() == "Count to 10"

    def test_render_override_default(self):
        t = PromptTemplate(template="Count to {n}", defaults={"n": "10"})
        assert t.render(n="5") == "Count to 5"

    def test_render_missing_variable_raises(self):
        t = PromptTemplate(template="Hello {name}")
        with pytest.raises(ValueError, match="Missing required template variables"):
            t.render()

    def test_callable(self):
        t = PromptTemplate(template="Ping {target}")
        assert t(target="pong") == "Ping pong"

    def test_required_variables(self):
        t = PromptTemplate(
            template="{a} {b} {c}",
            defaults={"c": "default"},
        )
        assert t.required_variables == ["a", "b"]

    def test_no_variables(self):
        t = PromptTemplate(template="Static prompt")
        assert t.variables == []
        assert t.render() == "Static prompt"

    def test_repr(self):
        t = PromptTemplate(template="{x}", description="test")
        r = repr(t)
        assert "variables=" in r
        assert "description=" in r


class TestBuiltinTemplates:
    def test_summarise_defaults(self):
        result = SUMMARISE.render(text="The quick brown fox.")
        assert "200" in result
        assert "The quick brown fox." in result

    def test_summarise_override_max_words(self):
        result = SUMMARISE.render(text="foo", max_words="50")
        assert "50" in result

    def test_extract_json(self):
        result = EXTRACT_JSON.render(schema='{"name": "string"}', text="John Smith")
        assert "John Smith" in result
        assert "JSON" in result

    def test_qa(self):
        result = QA.render(context="Paris is the capital of France.", question="What is the capital of France?")
        assert "Paris" in result

    def test_code_review_defaults(self):
        result = CODE_REVIEW.render(code="x = 1")
        assert "python" in result
        assert "x = 1" in result

    def test_translate_defaults(self):
        result = TRANSLATE.render(text="Hello")
        assert "English" in result
        assert "Hello" in result

    def test_translate_target(self):
        result = TRANSLATE.render(text="Hello", target_language="French")
        assert "French" in result
