class AsmX64:

    def __init__(self):
        self.double_consts = {}
        self.instrs = []

    def gen_gnu_as(self):
        """Compiles the generated assembly into a gnu assembler file"""

        s_file = "# pycc compiled for x86_64\n\n"
        s_file += ".section .rodata\n"
        for key, value in self.double_consts.items():
            s_file += "\t" + value + ":" + " .double " + str(key) + "\n"
        s_file += "\n"

        s_file += ".section .text\n"
        s_file += ".global _start\n"
        s_file += "_start:\n"
        s_file += "\n"
        for instruction in self.instrs:
            s_file += "\t" + instruction[0] + " " + ",".join(instruction[1:]) + "\n"
        return s_file

    def double_const(self, value):
        if value in self.double_consts:
            return self.double_consts[value] + "(%rip)"
        else:
            asm_const_name = f"__PYCC_INTERNAL_DOUBLE_CONST__N{len(self.double_consts)}"
            self.double_consts[value] = asm_const_name
            return asm_const_name + "(%rip)"

    def movsd(self, src, dst):
        self.instrs.append(("movsd", src, dst))

    def ret(self):
        self.instrs.append(("ret",))
