from pycc.ssair.irgrammar import IRGrammar
from pycc.ssair.irparser import IRParser
from pycc.assembler.asm_x64 import AsmX64


class IRAssemblerX64:
    """Convert the SSA IR into GNU AS assembly."""

    def __init__(self, ir):
        self.asmx64 = AsmX64()
        self.xmm_registers = {f"%xmm{n}": None for n in range(15)}
        self.ir = ir

    def find_versioned_var(self, var: str):
        """Search through all register dicts to find the dict and the key
        that cooresponds to this variable"""
        for key, value in self.xmm_registers.items():
            if value == var:
                return (self.xmm_registers, key)

        raise NotImplementedError("Error")

    def find_free_xmm_register(self, idx: int):
        for key, value in self.xmm_registers.items():
            if not key.startswith("%xmm"):
                continue
            if value is None:
                return key

            # We want to run idx - 1 because we want to include this
            # statement
            if not self.variable_has_dependent(value, idx - 1):
                return key

        raise Exception("No more free registers, must push to stack")

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
            case "Constant":
                # We can't be dependent on a constant that we have not set
                return False
            case _:
                raise NotImplementedError(type(assignment.Right).__name__)

    def variable_has_dependent(self, name: str, line_idx: int):
        for stmt in self.ir[line_idx + 1 :]:
            match type(stmt).__name__:
                case "Assignment":
                    if self.assignment_has_dependent(name, stmt):
                        return True
        return False

    def binop_xmm_reg_reg(self, left: str, right: str, op: str, idx: int):
        # mulsd reg1, reg2
        if op == "*":
            if not self.variable_has_dependent(self.xmm_registers[left], idx):
                self.asmx64.mulsd(right, left)
                return left
            elif not self.variable_has_dependent(self.xmm_registers[right], idx):
                self.asmx64.mulsd(left, right)
                return right
            raise NotImplementedError("Requires stack storage of a register")
        elif op == "+":
            if not self.variable_has_dependent(self.xmm_registers[left], idx):
                self.asmx64.addsd(right, left)
                return left
            elif not self.variable_has_dependent(self.xmm_registers[right], idx):
                self.asmx64.addsd(left, right)
                return right
            raise NotImplementedError("Requires stack storage of a register")
        elif op == "-":
            # left - right
            # dst  - src
            if not self.variable_has_dependent(self.xmm_registers[left], idx):
                self.asmx64.subsd(right, left)
                return left
            raise NotImplementedError("Requires stack storage of a register")
        elif op == "/":
            # left / right
            # dst / src
            if not self.variable_has_dependent(self.xmm_registers[left], idx):
                self.asmx64.divsd(right, left)
                return left
            raise NotImplementedError("Requires stack storage of a register")

    def binop_xmm_mem_reg(self, left: str, right: str, op: str, idx: int):
        # mulsd mem, reg2
        if op == "*":
            # left * right
            if not self.variable_has_dependent(self.xmm_registers[right], idx):
                self.asmx64.mulsd(left, right)
                return right

            # Get temporary register to move the memory location into
            tmp_reg = self.find_free_xmm_register(idx)
            self.asmx64.movsd(left, tmp_reg)
            self.asmx64.mulsd(right, tmp_reg)
            return tmp_reg
        elif op == "+":
            if not self.variable_has_dependent(self.xmm_registers[right], idx):
                self.asmx64.addsd(left, right)
                return right

            # Get temporary register to move the memory location into
            tmp_reg = self.find_free_xmm_register(idx)
            self.asmx64.movsd(left, tmp_reg)
            self.asmx64.addsd(right, tmp_reg)
            return tmp_reg
        elif op == "-":
            # left - right
            # dst - src
            tmp_reg = self.find_free_xmm_register(idx)
            self.asmx64.movsd(left, tmp_reg)
            self.asmx64.subsd(right, tmp_reg)
            return tmp_reg
        elif op == "/":
            tmp_reg = self.find_free_xmm_register(idx)
            self.asmx64.movsd(left, tmp_reg)
            self.asmx64.divsd(right, tmp_reg)
            return tmp_reg

    def binop_xmm_reg_mem(self, left: str, right: str, op: str, idx: int):
        # mulsd reg, mem
        if op == "*":
            # left * right
            # dst * src
            if not self.variable_has_dependent(self.xmm_registers[left], idx):
                self.asmx64.mulsd(right, left)
                return left
            raise NotImplementedError("Requires stack storage of a register")
        elif op == "+":
            if not self.variable_has_dependent(self.xmm_registers[left], idx):
                self.asmx64.addsd(right, left)
                return left
            raise NotImplementedError("Requires stack storage of a register")
        elif op == "-":
            if not self.variable_has_dependent(self.xmm_registers[left], idx):
                self.asmx64.subsd(right, left)
                return left
            raise NotImplementedError("Requires stack storage of a register")
        elif op == "/":
            if not self.variable_has_dependent(self.xmm_registers[left], idx):
                self.asmx64.divsd(right, left)
                return left
            raise NotImplementedError("Requires stack storage of a register")

    def visit_BinOp(self, node: IRGrammar.binop_tuple, idx: int):

        # Get the leaf nodes of the left and right of this operation
        binop_left_vv = IRGrammar.versioned_variable_as_str(node.Left)
        binop_right_vv = IRGrammar.versioned_variable_as_str(node.Right)

        # Get the location of the left and right nodes
        lrd, lrd_key = self.find_versioned_var(binop_left_vv)
        rrd, rrd_key = self.find_versioned_var(binop_right_vv)

        if lrd != rrd:
            raise Exception(f"Must change variable type here")

        if lrd_key[0] == "%" and rrd_key[0] == "%":
            if lrd_key.startswith("%xmm"):
                result_reg = self.binop_xmm_reg_reg(lrd_key, rrd_key, node.Op, idx)
            else:
                raise NotImplementedError("")
        elif lrd_key[0] == "_" and rrd_key[0] == "%":
            if rrd_key.startswith("%xmm"):
                result_reg = self.binop_xmm_mem_reg(lrd_key, rrd_key, node.Op, idx)
            else:
                raise NotImplementedError("")
        elif lrd_key[0] == "%" and rrd_key[0] == "_":
            if lrd_key.startswith("%xmm"):
                result_reg = self.binop_xmm_reg_mem(lrd_key, rrd_key, node.Op, idx)
            else:
                raise NotImplementedError("")
        elif lrd_key[0] == "_" and rrd_key[0] == "_":
            raise NotImplementedError("")

        return result_reg

    def visit_Constant(self, node: IRGrammar.const_statement_tuple, idx: int):
        """Obtain the constant RIP assembly code.

        Constants to not return a register. Instead visit_Constant returns
        a RIP value. It is up to parent nodes that have called this function
        to determine how to use the relative addresses. This is because
        for example returning a constant requires movement of the constant
        into a register. But for math operands, for example mulsd, the src
        register may be a memory location, meaning that in some contexs these
        it is not necessary to allocate a register to this constant value.

        """
        match type(node.Value).__name__:
            case "float":
                rip_ptr = self.asmx64.double_const(node.Value)
                return rip_ptr

    def visit_Return(self, node: IRGrammar.returns_tuple, idx: int):
        """Emits a return statement and ensures that the return value is in
        the correct register."""

        return_variable = IRGrammar.versioned_variable_as_str(node.VersionedVariable)

        retval_dict, retval_dict_loc = self.find_versioned_var(return_variable)
        # Obtain the location that this variable is in

        if retval_dict_loc.startswith("%"):
            # The return variable lives in a register
            if retval_dict_loc.startswith("%xmm"):
                if retval_dict_loc != "%xmm0":
                    # We must move the return variable into xmm0 if it is not already
                    self.asmx64.movsd(retval_dict_loc, "%xmm0")
            else:
                raise NotImplementedError("Unable to return non floating point data")
        else:
            # The return variable lives in a constant location
            if retval_dict_loc.startswith("__PYCC_INTERNAL_DOUBLE_C"):
                self.asmx64.movsd(retval_dict_loc, "%xmm0")
            else:
                raise NotImplementedError("Unable to return non floating point data")

        self.asmx64.ret()

    def visit_Assignment(self, node: IRGrammar.assignment_tuple, idx: int):

        vv_str = IRGrammar.versioned_variable_as_str(node.Left)
        match type(node.Right).__name__:
            case "Constant":
                # When assigning a constant we need to know the RIP pointer
                register = self.visit_Constant(node.Right, idx)
                if register.startswith("%xmm") or register.startswith(
                    "__PYCC_INTERNAL_DOUBLE_C"
                ):
                    self.xmm_registers[register] = vv_str
                else:
                    raise NotImplementedError("Error")
                pass
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
            case "VersionedVariable":
                # Find a free register
                vv_str = IRGrammar.versioned_variable_as_str(node.Right)
                if not self.variable_has_dependent(vv_str, idx):
                    # The variable does not have a dependent so we can just update
                    # the register map of the current variable
                    register = next(
                        (
                            key
                            for key, val in self.xmm_registers.items()
                            if val == vv_str
                        ),
                        None,
                    )
                    vv_str = IRGrammar.versioned_variable_as_str(node.Left)
                    self.xmm_registers[register] = vv_str
                else:
                    raise NotImplementedError("Find a new register to copy the data to")
            case _:
                raise NotImplementedError(type(node.Right).__name__)

    def assemble(self):
        for stmt_idx, stmt in enumerate(self.ir):
            match type(stmt).__name__:
                case "Assignment":
                    self.visit_Assignment(stmt, stmt_idx)
                case "Return":
                    self.visit_Return(stmt, stmt_idx)
