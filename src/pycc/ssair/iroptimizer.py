from pycc.ssair.irgrammar import IRGrammar
from typing import List


class IROptimizer:

    def __init__(self, ir: List[IRGrammar.assignment_tuple | IRGrammar.returns_tuple]):
        self.ir = ir

        self.propogate_version_version_assignments()
        self.precompute_constant_binops()
        self.remove_unused_variables()

    def get_ir_constant(self, node: IRGrammar.versioned_variable_tuple):
        for stmt in self.ir:
            if type(stmt).__name__ != "Assignment":
                continue
            if stmt.Left == node:
                return stmt.Right.Value

    def delete_and_replace(
        self,
        to_delete: IRGrammar.versioned_variable_tuple,
        replace_with: IRGrammar.versioned_variable_tuple,
    ):
        # Delete any assignment that assigns to_delete in its left hand side

        new_ir = []
        for stmt in self.ir:
            stmt_type = type(stmt).__name__
            if stmt_type != "Assignment":
                new_ir.append(stmt)
                continue

            left_type = type(stmt.Left).__name__
            right_type = type(stmt.Right).__name__

            if left_type == "VersionedVariable" and stmt.Left == to_delete:
                # Delete this assignment
                continue

            if right_type == "BinOp":
                new_stmt = stmt.Right
                if stmt.Right.Left == to_delete:
                    new_stmt = IRGrammar.binop_tuple(
                        replace_with, new_stmt.Op, new_stmt.Right
                    )
                if stmt.Right.Right == to_delete:
                    new_stmt = IRGrammar.binop_tuple(
                        new_stmt.Left, new_stmt.Op, replace_with
                    )
                new_ir.append(IRGrammar.assignment_tuple(stmt.Left, new_stmt))
                continue

            new_ir.append(stmt)
        self.ir = new_ir

    def precompute_constant_binops(self):
        new_ir = []
        for stmt in self.ir:
            stmt_type = type(stmt).__name__
            if stmt_type != "Assignment":
                new_ir.append(stmt)
                continue

            stmt_right_type = type(stmt.Right).__name__
            if (
                stmt_right_type == "BinOp"
                and stmt.Right.Left.Name.startswith("__PYCC_INTERNAL__C")
                and stmt.Right.Right.Name.startswith("__PYCC_INTERNAL__C")
            ):
                # We can perform this binop during compilation
                left = self.get_ir_constant(stmt.Right.Left)
                right = self.get_ir_constant(stmt.Right.Right)
                evaluated_const = eval(f"{left} {stmt.Right.Op} {right}")
                new_ir.append(
                    IRGrammar.assignment_tuple(
                        stmt.Left, IRGrammar.const_statement_tuple(evaluated_const)
                    )
                )
                continue
            new_ir.append(stmt)

        self.ir = new_ir

    def propogate_version_version_assignments(self):
        to_propogate = []
        for stmt in self.ir:
            stmt_type = type(stmt).__name__
            if stmt_type != "Assignment":
                continue

            left_type = type(stmt.Left).__name__
            right_type = type(stmt.Right).__name__

            if left_type == "VersionedVariable" and right_type == "VersionedVariable":
                to_propogate.append((stmt.Left, stmt.Right))

        for to_delete, replace_with in to_propogate:
            self.delete_and_replace(to_delete, replace_with)

    def remove_unused_variables(self):
        new_ir = []
        for stmt_idx, stmt in enumerate(self.ir):

            stmt_type = type(stmt).__name__
            if stmt_type != "Assignment":
                new_ir.append(stmt)
                continue

            lhs = stmt.Left

            is_used = False
            for next_stmt in self.ir[stmt_idx + 1 :]:

                if type(next_stmt).__name__ == "Return":
                    next_stmt: IRGrammar.returns_tuple = next_stmt
                    if next_stmt.VersionedVariable == lhs:
                        is_used = True
                        break

                if type(next_stmt).__name__ != "Assignment":
                    continue

                if type(next_stmt.Right).__name__ == "BinOp":
                    binop = next_stmt.Right
                    if binop.Left == lhs or binop.Right == lhs:
                        is_used = True
                        break
            if is_used:
                new_ir.append(stmt)
                continue
        self.ir = new_ir
