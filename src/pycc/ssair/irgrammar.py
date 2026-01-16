from collections import namedtuple
from typing import Any, List
import pyparsing as pp


class IRGrammar:
    """Grammar defines the grammar of the IR language that the python source
    code gets compiled to. This grammar represents the Single Static Assignment
    form of the python code. A simple example is as follows

    ```
        x#0 := %xmm0
        y#0 := %xmm1
        label name
        x#1 := x#0 * y#0
        goto name
        ret x#1
    ```

    The IR representation is then consumed by the IR compiler to produce
    assembly code. The IR is a good place to perform optimizations such as
    finding the minimal number of phi functions, removing unused code,
    or constant propogation to say the least.

    """

    # __init__common
    integer = pp.common().integer
    double = pp.common().fnumber

    # __init__literals
    binop_mult = pp.Literal("*")
    binop_div = pp.Literal("/")
    binop_sub = pp.Literal("-")
    cequals = pp.Literal(":=")
    pound = pp.Literal("#")
    returns = pp.Literal("ret")
    label = pp.Literal("label")
    goto = pp.Literal("goto")

    # __init__words
    varname = pp.Word(pp.alphas)

    # __init__registers
    xmm_registers = pp.Word("%xmm") + integer
    registers = xmm_registers

    versioned_variable = varname + pound + integer

    binop = (
        versioned_variable + (binop_mult | binop_div | binop_sub) + versioned_variable
    )
    returns_statement = returns + versioned_variable
    const_statement = double | integer
    assignment = (
        versioned_variable
        + cequals
        + (binop | registers | versioned_variable | const_statement)
    )
    goto_statement = goto + varname
    label_statement = label + label_statement
    assignment_block = pp.OneOrMore(
        assignment | goto_statement | label_statement | returns_statement
    )

    # __init__namedtuples
    assignment_tuple = namedtuple("Assignment", ["Left", "Right"])
    binop_tuple = namedtuple("BinOp", ["Left", "Op", "Right"])
    const_statement_tuple = namedtuple("Constant", "Value")
    label_statement_tuple = namedtuple("Label", "Name")
    goto_statement_tuple = namedtuple("Goto", "Name")
    returns_tuple = namedtuple("Return", ["VersionedVariable"])
    versioned_variable_tuple = namedtuple("VersionedVariable", ["Name", "Version"])
    xmm_registers_tuple = namedtuple("XmmRegister", ["Name"])

    def label_statement_parse_action(original: str, location: int, tokens: List[Any]):
        return IRGrammar.label_statement_tuple(tokens[1])

    def goto_statement_tuple(original: str, location: int, tokens: List[Any]):
        return IRGrammar.goto_statement_tuple(tokens[1])

    def assignment_parse_action(original: str, location: int, tokens: List[Any]):
        return IRGrammar.assignment_tuple(tokens[0], tokens[2])

    def binop_parse_action(original: str, location: int, tokens: List[Any]):
        return IRGrammar.binop_tuple(tokens[0], tokens[1], tokens[2])

    def const_statement_action(original: str, location: int, tokens: List[Any]):
        return IRGrammar.const_statement_tuple(tokens[0])

    def returns_parse_action(original: str, location: int, tokens: List[Any]):
        return IRGrammar.returns_tuple(tokens[1])

    def xmm_registers_parse_action(original: str, location: int, tokens: List[Any]):
        assert tokens[1] >= 0 and tokens[1] < 16
        return IRGrammar.xmm_registers_tuple(f"{tokens[0]}{tokens[1]}")

    def versioned_variable_parse_action(
        original: str, location: int, tokens: List[Any]
    ):
        assert tokens[2] >= 0
        return IRGrammar.versioned_variable_tuple(tokens[0], tokens[2])

    # __init__parse_actions
    assignment.set_parse_action(assignment_parse_action)
    binop.set_parse_action(binop_parse_action)
    const_statement.set_parse_action(const_statement_action)
    returns_statement.set_parse_action(returns_parse_action)
    versioned_variable.set_parse_action(versioned_variable_parse_action)
    xmm_registers.set_parse_action(xmm_registers_parse_action)

    @classmethod
    def assignment_tuple_as_str(cls: "IRGrammar", node: "IRGrammar.assignment_tuple"):
        lhs = IRGrammar.versioned_variable_as_str(node.Left)

        rhs = ""
        match type(node.Right).__name__:
            case "Constant":
                rhs = str(node.Right.Value)
            case "XmmRegister":
                rhs = str(node.Right.Name)
            case "BinOp":
                binop: IRGrammar.binop_tuple = node.Right
                rhs = (
                    cls.versioned_variable_as_str(binop.Left)
                    + " "
                    + binop.Op
                    + " "
                    + cls.versioned_variable_as_str(binop.Right)
                )
            case "VersionedVariable":
                rhs = cls.versioned_variable_as_str(node.Right)
            case _:
                raise NotImplementedError(type(node.Right).__name__)
        return lhs + "\t:=\t" + rhs

    @classmethod
    def returns_tuple_as_str(cls: "IRGrammar", node: "IRGrammar.returns_tuple"):
        return "ret " + IRGrammar.versioned_variable_as_str(node.VersionedVariable)

    @classmethod
    def versioned_variable_as_str(
        cls: "IRGrammar", node: "IRGrammar.versioned_variable_tuple"
    ):
        return f"{node.Name}#{node.Version}"

    @classmethod
    def goto_statement_as_str(cls: "IRGrammar", node: "IRGrammar.goto_statement_tuple"):
        return f"goto {node.Name}"

    @classmethod
    def label_statement_as_str(
        cls: "IRGrammar", node: "IRGrammar.goto_statement_tuple"
    ):
        return f"label {node.Name}"
