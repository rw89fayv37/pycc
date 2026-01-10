from pycc.ssair.irgrammar import IRGrammar

class IRParser:
    """Helper class to easily parse and unparse IR grammar"""

    def parse(data: str):
        """Parses the IR synytax tree from a string"""
        return IRGrammar.assignment_block.parse_string(data, parse_all=True)

    def unparse(ir):
        stmt_as_str = []
        for stmt in ir:
            match type(stmt).__name__:
                case "Assignment":
                    stmt_as_str.append(IRGrammar.assignment_tuple_as_str(stmt))
                case "Return":
                    stmt_as_str.append(IRGrammar.returns_tuple_as_str(stmt))
                case _:
                    raise NotImplementedError(type(stmt).__name__)
        return "\n".join(stmt_as_str)
