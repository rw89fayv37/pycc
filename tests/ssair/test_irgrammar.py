from pycc.ssair import irgrammar
from pyparsing.exceptions import ParseException
import pytest


def test_returns_statement():
    assert irgrammar.IRGrammar().returns_statement.parse_string(
        "ret x#0", parse_all=True
    )

    with pytest.raises(ParseException):
        irgrammar.IRGrammar().returns_statement.parse_string("ret x", parse_all=True)


def test_integer():
    assert irgrammar.IRGrammar().integer.parse_string("1", parse_all=True)

    with pytest.raises(ParseException):
        irgrammar.IRGrammar().returns_statement.parse_string("1.12345", parse_all=True)


def test_double():
    assert irgrammar.IRGrammar().double.parse_string("1")
    assert irgrammar.IRGrammar().double.parse_string("1.2345")

    with pytest.raises(ParseException):
        irgrammar.IRGrammar().double.parse_string("sdfaq")
