"""The grounding checks are the correctness property of this repo. These run with no network."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from ledeline.evals.checks import check, ungrounded_numbers, ungrounded_names, word_count

SRC = ("Acme Corp shipped Widget 2.0 on Tuesday. The release cuts p99 latency by 40% and costs $12 per "
       "month. Engineers at Acme say the rewrite took nine months in Rust.")


def test_grounded_blurb_passes():
    b = ("Acme Corp released Widget 2.0 on Tuesday, cutting p99 latency by 40% for $12 per month. Engineers at Acme say the Rust "
         "rewrite took nine months. Latency-sensitive teams get a cheaper path to faster responses without changing their "
         "integration, which is the part most rewrites get wrong.")
    r = check("Acme ships Widget 2.0 with 40% lower latency", b, ["Latency fell 40%", "It costs $12 per month"], SRC)
    assert r.passed, r.failed_rules


def test_invented_number_fails():
    b = "Acme Corp released Widget 2.0, cutting p99 latency by 60% for $12 per month. The rewrite took nine months. Teams get faster responses."
    assert ungrounded_numbers(b, SRC) == ["60%"]
    r = check("Acme ships Widget", b, ["a", "b"], SRC)
    assert "rule1.numbers_grounded" in r.failed_rules


def test_invented_company_fails():
    b = "Acme Corp released Widget 2.0 after Microsoft pressure, cutting p99 latency by 40%. The rewrite took nine months. Teams get faster responses now."
    assert ungrounded_names(b, SRC) == ["Microsoft"]


def test_sentence_initial_stopwords_are_not_names():
    b = "The release cuts latency by 40%. Engineers at Acme say the rewrite took nine months. This matters for latency-sensitive teams."
    assert ungrounded_names(b, SRC) == []


def test_hype_and_first_person_fail():
    b = "We think this game-changer from Acme Corp cuts latency by 40%. The rewrite took nine months. You should try it."
    r = check("Acme ships Widget", b, ["a", "b"], SRC)
    assert {"rule2.no_hype", "rule3.third_person"} <= set(r.failed_rules)


def test_number_with_thousands_separator_matches_source():
    src = "It handles 1,200 requests per second."
    assert ungrounded_numbers("It handles 1200 requests per second.", src) == []
    assert ungrounded_numbers("It handles 1,500 requests per second.", src) == ["1,500"]


def test_word_count_window():
    assert word_count("one two three") == 3


def test_title_case_headline_is_not_a_list_of_names():
    src = "Parts of the Netherlands were hit by rail disruption after suspected sabotage, ProRail said."
    # Title Case carries no name signal, so the names check ignores such a headline and
    # headline.sentence_case flags it instead. A sentence-case headline is checked word by word.
    assert ungrounded_names("", src, headline="Suspected Sabotage Disrupts Netherlands Rail Network") == []
    assert ungrounded_names("", src, headline="Suspected sabotage disrupts Belgian rail network") == ["Belgian"]
    r = check("Suspected Sabotage Disrupts Netherlands Rail Network", "x", [], src)
    assert "headline.sentence_case" in r.failed_rules
    r = check("Suspected sabotage disrupts Netherlands rail network", "x", [], src)
    assert "headline.sentence_case" not in r.failed_rules


def test_trailing_punctuation_does_not_break_grounding():
    src = "Chrome and Firefox run WebGL on the M4."
    assert ungrounded_names("The driver runs WebGL.", src) == []


def test_hyphenated_compound_is_grounded_by_its_head():
    src = "The keyboard is MFi certified. AI tools are everywhere."
    assert ungrounded_names("An MFi-compatible keyboard and AI-generated images.", src) == []
    assert ungrounded_names("An Bluetooth-compatible keyboard.", src) == ["Bluetooth-compatible"]
