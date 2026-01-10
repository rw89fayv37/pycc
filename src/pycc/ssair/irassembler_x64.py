from pycc.ssair.irgrammar import IRGrammar
from pycc.ssair.irparser import IRParser
from pycc.assembler.asm_x64 import AsmX64


class IRAssemblerX64:
    """Conver the SSA IR into GNU AS assembly"""

    def __init__(self, ir):
        self.asmx64 = AsmX64()
        self.xmm_registers = {f"%xmm{n}": None for n in range(15)}
        self.ir = ir

    def assignment_has_dependent(
        self, name: str, assignment: IRGrammar.assignment_tuple
    ):
        match type(assignment.Right).__name__:
            case "BinOp":
                binop: IRGrammar.binop_tuple = assignment.Right

                left: IRGrammar.versioned_variable_tuple = binop.Left
                left_str = IRGrammar.versioned_variable_as_str(left)

                right: IRGrammar.versioned_variable_tuple = binop.Right
                right_str = IRGrammar.versioned_variable_as_str(right)

                return left_str == name or right_str == name
            case "VersionedVariable":
                return IRGrammar.versioned_variable_as_str(assignment.Right) == name
            case _:
                raise NotImplementedError(type(assignment).__name__)

    def variable_has_dependent(self, name: str, line_idx: int):
        for stmt in self.ir[line_idx + 1 :]:
            match type(stmt).__name__:
                case "Assignment":
                    if self.assignment_has_dependent(name, stmt):
                        return True
        return False

    def visit_BinOp(self, node: IRGrammar.binop_tuple, idx: int):

        binop_left_vv = IRGrammar.versioned_variable_as_str(node.Left)
        binop_right_vv = IRGrammar.versioned_variable_as_str(node.Right)

        left_register = next(
            (key for key, val in self.xmm_registers.items() if val == binop_left_vv),
            None,
        )
        right_register = next(
            (key for key, val in self.xmm_registers.items() if val == binop_right_vv),
            None,
        )

        if left_register is None:
            raise Exception(f"{binop_left_vv} is not defined")
        if right_register is None:
            raise Exception(f"{binop_right_vv} is not defined")

        if left_register[:4] != right_register[:4]:
            raise Exception(f"Refusing to change variable type")

        match node.Op:
            case "*":
                match left_register[:4]:
                    case "%xmm":
                        # mulsd reg1, reg2
                        if not self.variable_has_dependent(
                            self.xmm_registers[left_register], idx
                        ):
                            self.asmx64.mulsd(right_register, left_register)
                            return left_register
                        elif not self.variable_has_dependent(
                            self.xmm_registers[right_register], idx
                        ):
                            self.asmx64.mulsd(left_register, right_register)
                            return right_register
                        else:
                            raise NotImplementedError(
                                "Compilation of this program requires moving data to stack"
                            )
                    case _:
                        raise Exception("Unsuported binop")

    def visit_Constant(self, node: IRGrammar.const_statement_tuple, idx: int):
        """Obtain the constant RIP assembly code"""
        match type(node.Value).__name__:
            case "float":
                rip_ptr = self.asmx64.double_const(node.Value)
                # Check if this rip_ptr is currently assigned to a register
                register = next(
                    (key for key, val in self.xmm_registers.items() if val == rip_ptr),
                    None,
                )
                if not register is None:
                    return key_found

                # Find a register to place this constant value into
                # for key, value in self.xmm_registers.items():
                first_free_reg = None
                for key, value in self.xmm_registers.items():
                    if value is None or not self.variable_has_dependent(value, idx):
                        first_free_reg = key
                        break

                if first_free_reg is None:
                    raise NotImplementedError("This function requires the stack")

                self.asmx64.movsd(rip_ptr, first_free_reg)
                self.xmm_registers[first_free_reg] = rip_ptr
                return first_free_reg

    def visit_Return(self, node: IRGrammar.returns_tuple, idx: int):
        """Emits a return statement and ensures that the return value is in
        the correct register"""
        return_variable = IRGrammar.versioned_variable_as_str(node.VersionedVariable)
        register = next(
            (key for key, val in self.xmm_registers.items() if val == return_variable),
            None,
        )
        if register != "%xmm0":
            # Must move this to the xmm0 register to follow x86 calling conventions
            self.asmx64.movsd(register, "%xmm0")

        self.asmx64.ret()

    def visit_Assignment(self, node: IRGrammar.assignment_tuple, idx: int):

        vv_str = IRGrammar.versioned_variable_as_str(node.Left)
        match type(node.Right).__name__:
            case "Constant":
                # When assigning a constant we need to know the RIP pointer
                register = self.visit_Constant(node.Right, idx)
                self.xmm_registers[register] = vv_str
            case "XmmRegister":
                xmm_reg: IRGrammar.xmm_registers_tuple = node.Right
                self.xmm_registers[xmm_reg.Name] = vv_str
            case "BinOp":
                # Check the xmm registers to find the left variable
                binop: IRGrammar.binop_tuple = node.Right
                register = self.visit_BinOp(binop, idx)

                assignment_vv = IRGrammar.versioned_variable_as_str(node.Left)
                if register.startswith("%xmm"):
                    self.xmm_registers[register] = assignment_vv
            case _:
                raise NotImplementedError(type(node.Right).__name__)

    def assemble(self):
        for stmt_idx, stmt in enumerate(self.ir):
            match type(stmt).__name__:
                case "Assignment":
                    self.visit_Assignment(stmt, stmt_idx)
                case "Return":
                    self.visit_Return(stmt, stmt_idx)
