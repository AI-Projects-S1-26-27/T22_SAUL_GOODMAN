"""W1 command-line entry points."""

from courtroom.cli import main


def test_find_lists_generated_cases(capsys):
    assert main(["find", "--count", "6", "--top", "2"]) == 0
    assert "gen-" in capsys.readouterr().out


def test_matters_rates_a_case(capsys):
    assert main(["matters", "--case", "cookie-jar", "--seeds", "2"]) == 0
    assert "Decided by the evidence" in capsys.readouterr().out


def test_verify_with_surprises_is_bit_identical():
    assert main(["verify", "--case", "helix-espionage", "--seed", "6", "-p", "adaptive", "-d", "aggressive", "--surprises"]) == 0
