from pycc.ssair.irgrammar import IRGrammar
from pycc.assembler.asm_x64 import AsmX64


class IRAssemblerX64:
    """Conver the SSA IR into GNU AS assembly"""

    def __init__(self):
        self.asmx64 = AsmX64()
        self.xmm_registers = {f"%xmm{n}": None for n in range(15)}

    def visit_Constant(self, node: IRGrammar.const_statement_tuple):
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
                first_free_reg = None
                for key, value in self.xmm_registers.items():
                    if value is None:
                        first_free_reg = key
                        break
                if first_free_reg is None:
                    raise NotImplementedError("This function requires the stack")

                self.asmx64.movsd(rip_ptr, first_free_reg)
                self.xmm_registers[first_free_reg] = rip_ptr
                return first_free_reg

    def visit_Return(self, node: IRGrammar.returns_tuple):
        return_variable = IRGrammar.versioned_variable_as_str(node.VersionedVariable)
        register = next(
            (key for key, val in self.xmm_registers.items() if val == return_variable),
            None,
        )
        if register != "%xmm0":
            # Must move this to the xmm0 register to follow x86 calling conventions
            self.asmx64.movsd(register, "%xmm0")

        self.asmx64.ret()

    def visit_Assignment(self, node: IRGrammar.assignment_tuple):

        vv_str = IRGrammar.versioned_variable_as_str(node.Left)
        match type(node.Right).__name__:
            case "Constant":
                # When assigning a constant we need to know the RIP pointer
                register = self.visit_Constant(node.Right)
                self.xmm_registers[register] = vv_str
            case "XmmRegister":
                xmm_reg: IRGrammar.xmm_registers_tuple = node.Right
                self.xmm_registers[xmm_reg.Name] = vv_str
            case _:
                raise NotImplementedError(type(node.Right).__name__)

        # Now that we have the rip_ptr

    def assemble(self, ir):
        for stmt in ir:
            match type(stmt).__name__:
                case "Assignment":
                    self.visit_Assignment(stmt)
                case "Return":
                    self.visit_Return(stmt)
