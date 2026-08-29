"""Unit tests for Continuous Learning Engine."""

import pytest
from app.learning_engine import ContinuousLearningEngine


def test_learning_engine_base_lexicon(tmp_path):
    db_file = str(tmp_path / "test_learn.db")
    engine = ContinuousLearningEngine(db_path=db_file)

    # Base knowledge check
    text = "เราใช้ ChatGPT และ OpenAI ในการทำงาน"
    phonetic = engine.apply_learned_phonetics(text)
    assert "แชตจีพีที" in phonetic
    assert "โอเพนเอไอ" in phonetic


def test_learning_engine_user_teach(tmp_path):
    db_file = str(tmp_path / "test_learn.db")
    engine = ContinuousLearningEngine(db_path=db_file)

    # Teach custom word
    success = engine.learn_term("CustomFramework", "คัสตอมเฟรมเวิร์ก")
    assert success is True

    # Check persistence and application
    text = "ลองใช้ CustomFramework ดูสิ"
    phonetic = engine.apply_learned_phonetics(text)
    assert "คัสตอมเฟรมเวิร์ก" in phonetic

    # Check lexicon retrieval
    lex = engine.get_learned_lexicon()
    found = [item for item in lex if item["term"] == "CustomFramework"]
    assert len(found) == 1
    assert found[0]["phonetic_thai"] == "คัสตอมเฟรมเวิร์ก"
