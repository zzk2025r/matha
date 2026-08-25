
; Matha IR → LLVM IR
define double @main() {
entry:
  %result = fadd double 3.0, 5.0
  ret double %result
}
