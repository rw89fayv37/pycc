from pycc.ssair.irgrammar import IRGrammar
from typing import Dict
from pprint import pprint

import ast
import ctypes
import inspect


class CompilableTypes:

    TYPE_MAP = {
        "ctypes.c_double": ctypes.c_double,
        "c_double": ctypes.c_double,
        "float": ctypes.c_double,
    }


class CompilerException(BaseException):

    def __init__(self, msg, loc, node):
        # Create location information from node
        super().__init__(f"\n\t{loc}:{node.lineno} | {msg}")


class Py2IR(ast.NodeVisitor):

    def __init__(self, file_name: str):
        self.file_name = file_name
        self.cdef = None

        # Variable dictionary used to keep track of variables and their versions
        self.variable_db: {str: int} = {}
        self.global_ir = []

    def __create_no_name_variable(self):
        # Create the variable
        n_variables = len(self.variable_db)
        const_preamble = f"__PYCC_INTERNAL__A{n_variables}"
        self.variable_db[const_preamble] = 0

        # Don't return a list because just the versioned variable isn't valid IR code
        return IRGrammar.versioned_variable_tuple(const_preamble, 0)

    def __get_named_variable(self, name):
        if name in self.variable_db:
            return IRGrammar.versioned_variable_tuple(name, self.variable_db[name])
        else:
            self.variable_db[name] = 0
            return IRGrammar.versioned_variable_tuple(name, self.variable_db[name])

    def __create_const_variable(self, value):
        # Create the variable
        n_variables = len(self.variable_db)
        const_preamble = f"__PYCC_INTERNAL__C{n_variables}"
        assert not const_preamble in self.variable_db
        self.variable_db[const_preamble] = 0

        # Create the syntax tree
        constant_value = IRGrammar.const_statement_tuple(value)
        versioned_variable = IRGrammar.versioned_variable_tuple(const_preamble, 0)
        assignment = IRGrammar.assignment_tuple(versioned_variable, constant_value)

        # Return this assignment as the syntax that has been created
        return [assignment]

    def generate_cfunctype(self, node: ast.FunctionDef) -> ctypes.CFUNCTYPE:
        """Use the python function to create a CFUNCTYPE that represents it"""

        cfunctype_returns = None
        cfunctype_args = []
        if not node.returns is None:
            # Obtain the "name" which in this case is the return type
            name: ast.Name = node.returns
            if name.id in CompilableTypes.TYPE_MAP:
                cfunctype_returns = CompilableTypes.TYPE_MAP[name.id]
            else:
                raise CompilerException(
                    f"Unable to generate compile type for return type {name.id}",
                    self.file_name,
                    node,
                )

        arguments: ast.arguments = node.args
        for arg_idx, argument in enumerate(arguments.args):
            if argument.annotation is None:
                raise CompilerException(
                    f"Missing annotation argument arumgnet #{arg_idx}",
                    self.file_name,
                    argument,
                )
            arg_name: ast.Name = argument.annotation
            if not arg_name.id in CompilableTypes.TYPE_MAP:
                raise CompilerException(
                    f"Unable to generate compile type for argument {arg_name.id}",
                    self.file_name,
                    argument,
                )
            cfunctype_args.append(CompilableTypes.TYPE_MAP[arg_name.id])

        # The CFUNCTYPE that is used to call the JITed function
        cdef = ctypes.CFUNCTYPE(cfunctype_returns, *cfunctype_args)
        cdef.argtypes = cfunctype_args
        cdef.restype = cfunctype_returns

        return cdef

    def generic_visit(self, node):
        raise NotImplementedError(
            f"Unable to parse the AST for {type(node).__name__}\n"
            f"Consider making an issue or pull request at github.com/rw89fayv37/pycc\n"
        )

    def visit_Constant(self, node: ast.Constant):
        const_type = type(node.value).__name__
        match const_type:
            case "float":
                # Pass this list up the chain
                return self.__create_const_variable(node.value)
            case _:
                raise NotImplementedError(type(node.value))

    def visit_BinOp(self, node: ast.BinOp):
        left_eval = self.visit(node.left)
        right_eval = self.visit(node.right)

        left_versioned_var = left_eval[-1].Left
        right_versioned_var = right_eval[-1].Left

        # Create the binop
        match type(node.op).__name__:
            case "Mult":
                binop = IRGrammar.binop_tuple(
                    left_versioned_var, "*", right_versioned_var
                )
            case _:
                raise NotImplemented(node.op)

        # Create an unnamed variable
        versioned_variable = self.__create_no_name_variable()
        binop_assignment = IRGrammar.assignment_tuple(versioned_variable, binop)

        # We don't have a variable name here so create an anonymous one
        return left_eval + right_eval + [binop_assignment]

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Generate the function definition for this function
        cdef = self.generate_cfunctype(node)
        self.cdef = cdef

        # Keep track of the initial register values that coorespond to the
        # function arguments
        function_ir = []
        for arg_idx, argument in enumerate(cdef.argtypes):
            match argument.__name__:
                case "c_double":
                    arg_vv = self.__get_named_variable(node.args.args[arg_idx].arg)
                    arg_location = IRGrammar.xmm_registers_tuple(f"%xmm{arg_idx}")
                    arg_assignment = IRGrammar.assignment_tuple(arg_vv, arg_location)
                    function_ir += [arg_assignment]
                case _:
                    raise CompilerException("TODO 2", self.file_location, node)

        # Loop through all the statements in this function body
        for stmt in node.body:
            function_ir += self.visit(stmt)
        return function_ir

    def visit_Name(self, node: ast.Name):
        return self.__get_named_variable(node.id)

    def visit_Module(self, node: ast.Module):
        module_ir = []
        for stmt in node.body:
            module_ir += self.visit(stmt)
        return module_ir

    def visit_Return(self, node: ast.Return):
        ir = self.visit(node.value)

        if type(ir).__name__ == "list":
            last_assignment = ir[-1]
            versioned_var: IRGrammar.versioned_variable_tuple = last_assignment.Left
            returns_tuple = IRGrammar.returns_tuple(versioned_var)
            return ir + [returns_tuple]
        else:
            assert type(ir).__name__ == "VersionedVariable"

        # Get the return'ed version variable
        return [IRGrammar.returns_tuple(ir)]
