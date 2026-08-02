# Script Jython executado DENTRO do Ghidra (via analyzeHeadless -postScript).
# Decompila funções e imprime o resultado entre marcadores, para a Aila capturar.
#
# NÃO é executado pelo Python da Aila — roda no interpretador do Ghidra.
# Uso (montado pelo BinaryAgent):
#   analyzeHeadless <proj> aila_tmp -import <bin> \
#       -scriptPath <esta_pasta> -postScript decompile_headless.py [nome_funcao] \
#       -deleteProject
#
# @category Aila
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor


def run():
    args = getScriptArgs()  # noqa: F821 (injetado pelo Ghidra)
    target = args[0] if len(args) > 0 else None
    max_funcs = 3

    program = getCurrentProgram()  # noqa: F821
    dec = DecompInterface()
    dec.openProgram(program)
    fm = program.getFunctionManager()
    funcs = list(fm.getFunctions(True))

    print("AILA_GHIDRA_BEGIN")
    print("PROGRAM=%s" % program.getName())
    print("FUNCTIONS_TOTAL=%d" % len(funcs))

    if target:
        chosen = [f for f in funcs if f.getName() == target]
        if not chosen:
            print("FUNC_NOT_FOUND=%s" % target)
    else:
        chosen = [f for f in funcs if not f.isThunk()][:max_funcs]

    for f in chosen:
        print("=== FUNC %s @ %s ===" % (f.getName(), f.getEntryPoint()))
        try:
            res = dec.decompileFunction(f, 60, ConsoleTaskMonitor())
            if res and res.decompileCompleted():
                print(res.getDecompiledFunction().getC())
            else:
                print("// (falha ao decompilar esta função)")
        except Exception as exc:  # noqa: BLE001
            print("// erro: %s" % exc)

    print("AILA_GHIDRA_END")


run()
