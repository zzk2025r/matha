# Makefile — Matha RISC-V 嵌入式项目 (v2)
# 目标架构: SiFive FE310 (RISC-V 32-bit)
# 生成方式: python scripts/riscv_embedded_demo.py
# 构建日志: 详细输出每个编译步骤，包含时间戳和内存估算

SHELL := /bin/bash

TOOLCHAIN_PREFIX ?= riscv64-unknown-elf-
CC       = $(TOOLCHAIN_PREFIX)gcc
AS       = $(TOOLCHAIN_PREFIX)as
LD       = $(TOOLCHAIN_PREFIX)ld
OBJCOPY  = $(TOOLCHAIN_PREFIX)objcopy
OBJDUMP  = $(TOOLCHAIN_PREFIX)objdump
SIZE     = $(TOOLCHAIN_PREFIX)size
AR       = $(TOOLCHAIN_PREFIX)ar

# 目标芯片
CHIP     = FE310
ARCH     = rv32imac
ABI      = ilp32
OPT      = -Os

# 编译器标志
CFLAGS   = -march=$(ARCH) -mabi=$(ABI) $(OPT) \
           -ffreestanding -nostdlib -nostartfiles \
           -I. -Iinclude \
           -Wall -Wextra -Wno-unused-function \
           -T link.ld
LDFLAGS  = -march=$(ARCH) -mabi=$(ABI) -T link.ld --nmagic

# 源文件
SRC_DIR  = src
INC_DIR  = include
OBJ_DIR  = build
LOG_DIR  = $(OBJ_DIR)/logs

SRCS_C   = $(wildcard $(SRC_DIR)/*.c)
SRCS_S   = $(wildcard $(SRC_DIR)/*.S)
OBJS     = $(patsubst $(SRC_DIR)/%.c,$(OBJ_DIR)/%.o,$(SRCS_C)) \
           $(patsubst $(SRC_DIR)/%.S,$(OBJ_DIR)/%.o,$(SRCS_S))

# 输出文件
ELF      = $(OBJ_DIR)/matha_riscv.elf
HEX      = $(OBJ_DIR)/matha_riscv.hex
BIN      = $(OBJ_DIR)/matha_riscv.bin
LST      = $(OBJ_DIR)/matha_riscv.lst
MAP      = $(OBJ_DIR)/matha_riscv.map
SYM      = $(OBJ_DIR)/matha_riscv.sym

# 构建信息
BUILD_TIME = $(shell date '+%Y-%m-%d %H:%M:%S')
BUILD_LOG  = $(LOG_DIR)/build_$(shell date +%Y%m%d_%H%M%S).log

# 检测交叉编译器
TOOLCHAIN_OK := $(shell command -v $(CC) > /dev/null 2>&1 && echo yes || echo no)
HOST_CC      = $(shell command -v gcc > /dev/null 2>&1 && echo gcc || echo clang)

# ═══════════════════════════════════════════════════════════════════════════════
#  默认目标
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: all
all: check_toolchain dirs generate $(ELF) $(HEX) $(BIN) $(LST) $(SYM) size summary
	@echo ""
	@echo "############################################"
	@echo "  Matha RISC-V Build Complete"
	@echo "  Target:   $(CHIP) ($(ARCH)/$(ABI))"
	@echo "  Time:     $(BUILD_TIME)"
	@echo "  Mode:     $$(if [ '$(TOOLCHAIN_OK)' = 'yes' ]; then echo 'CROSS-COMPILER'; else echo 'SIMULATION'; fi)"
	@echo "############################################"
	@echo "  ELF:  $(ELF)"
	@echo "  HEX:  $(HEX)"
	@echo "  BIN:  $(BIN)"
	@echo "  LST:  $(LST)"
	@echo "  MAP:  $(MAP)"
	@echo "  LOG:  $(BUILD_LOG)"
	@echo ""

# ═══════════════════════════════════════════════════════════════════════════════
#  工具链检查 (详细日志)
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: check_toolchain
check_toolchain:
	@echo ""
	@echo "##################################################"
	@echo "  [1/7] Toolchain Check — $(BUILD_TIME)"
	@echo "##################################################"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		echo "  [OK] Cross-compiler: $(CC)"; \
		$(CC) --version 2>/dev/null | head -1 | sed 's/^/  [OK]   /'; \
		echo "  [OK] Tools:"; \
		for tool in gcc as ld objcopy objdump size; do \
			if command -v $(TOOLCHAIN_PREFIX)$${tool} > /dev/null 2>&1; then \
				echo "    [OK] $(TOOLCHAIN_PREFIX)$${tool}"; \
			else \
				echo "    [MISS] $(TOOLCHAIN_PREFIX)$${tool}"; \
			fi; \
		done; \
	else \
		echo "  [WARN] RISC-V cross-compiler NOT found"; \
		echo "  [INFO] Host compiler: $(HOST_CC)"; \
		echo "  [INFO] Falling back to SIMULATION mode"; \
		echo "  [INFO] Install: sudo apt install gcc-riscv64-unknown-elf"; \
		echo "  [INFO] Or: brew install riscv-none-elf-gcc"; \
		echo "  [INFO] Or download: https://github.com/riscv/riscv-gnu-toolchain"; \
	fi
	@echo ""

# ═══════════════════════════════════════════════════════════════════════════════
#  创建目录
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: dirs
dirs:
	@mkdir -p $(OBJ_DIR) $(LOG_DIR) $(SRC_DIR)
	@echo "  [DIR] build/, build/logs/"

# ═══════════════════════════════════════════════════════════════════════════════
#  生成 C 代码
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: generate
generate:
	@echo ""
	@echo "##################################################"
	@echo "  [2/7] Code Generation"
	@echo "##################################################"
	@python3 -c " \
import os; \
from scripts.riscv_embedded_demo import ( \
    generate_i2c_sensor_c, generate_linalg_c, \
    generate_embedded_project_template \
); \
os.makedirs('src', exist_ok=True); \
files = [ \
    ('src/i2c_sensor.c', generate_i2c_sensor_c()), \
    ('src/linalg.c', generate_linalg_c()), \
    ('src/main.c', generate_embedded_project_template()), \
]; \
for path, code in files: \
    open(path, 'w').write(code); \
    lines = len(code.splitlines()); \
    print(f'  [GEN] {path}: {len(code)} bytes, {lines} lines'); \
print('  [OK] All C files generated'); \
"
	@echo ""

# ═══════════════════════════════════════════════════════════════════════════════
#  编译 C 源文件 (详细日志)
# ═══════════════════════════════════════════════════════════════════════════════
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c | dirs
	@echo ""
	@echo "##################################################"
	@echo "  [3/7] Compile: $<"
	@echo "##################################################"
	@echo "  Target:    $(CHIP) ($(ARCH)/$(ABI))"
	@echo "  Optim:     $(OPT)"
	@echo "  Flags:     $(CFLAGS)"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		echo "  Mode:      RISC-V Cross-Compile"; \
		echo "  Command:   $(CC) $(CFLAGS) -c $< -o $@"; \
		$(CC) $(CFLAGS) -c $< -o $@ 2> $(LOG_DIR)/$*.err; \
		if [ -s $(LOG_DIR)/$*.err ]; then \
			echo "  [WARN] Warnings/Errors:"; \
			cat $(LOG_DIR)/$*.err | sed 's/^/    /'; \
		else \
			echo "  [OK] Compiled successfully"; \
		fi; \
	else \
		echo "  Mode:      SIMULATION (host compiler)"; \
		echo "  Command:   $(HOST_CC) -c $< -o $@ -D__RISCV_SIMULATION__"; \
		$(HOST_CC) -c $< -o $@ -D__RISCV_SIMULATION__ 2> $(LOG_DIR)/$*.err; \
		if [ -s $(LOG_DIR)/$*.err ]; then \
			echo "  [WARN] Compilation warnings:"; \
			cat $(LOG_DIR)/$*.err | sed 's/^/    /'; \
		else \
			echo "  [OK] Compiled (simulated)"; \
		fi; \
	fi
	@SIZE=$$(wc -c < $@ 2>/dev/null || echo 0); \
	echo "  [INFO] Object size: $$SIZE bytes"

# ═══════════════════════════════════════════════════════════════════════════════
#  汇编源文件
# ═══════════════════════════════════════════════════════════════════════════════
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.S | dirs
	@echo ""
	@echo "##################################################"
	@echo "  [AS] Assemble: $<"
	@echo "##################################################"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(AS) -march=$(ARCH) -mabi=$(ABI) $< -o $@ 2> $(LOG_DIR)/$*.err; \
		if [ -s $(LOG_DIR)/$*.err ]; then \
			echo "  [WARN] Assembly warnings:"; \
			cat $(LOG_DIR)/$*.err | sed 's/^/    /'; \
		else \
			echo "  [OK] Assembled: $< -> $@"; \
		fi; \
	else \
		echo "  [SIM] Skipping assembly (no cross-compiler)"; \
		touch $@; \
	fi

# ═══════════════════════════════════════════════════════════════════════════════
#  链接
# ═══════════════════════════════════════════════════════════════════════════════
$(ELF): $(OBJS) link.ld | dirs
	@echo ""
	@echo "##################################################"
	@echo "  [4/7] Link: $@"
	@echo "##################################################"
	@echo "  Objects: $(OBJS)"
	@echo "  Script:  link.ld"
	@echo "  Flags:   $(LDFLAGS)"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		echo "  Mode:      RISC-V Cross-Link"; \
		$(LD) $(LDFLAGS) -o $@ $(OBJS) --print-map > $(MAP) 2> $(LOG_DIR)/link.err; \
		if [ -s $(LOG_DIR)/link.err ]; then \
			echo "  [ERROR] Linker errors:"; \
			cat $(LOG_DIR)/link.err | sed 's/^/    /'; \
			exit 1; \
		else \
			echo "  [OK] Linked successfully"; \
		fi; \
		# 生成符号表
		$(OBJDUMP) -t $@ > $(SYM) 2>/dev/null || true; \
		echo "  [INFO] Symbol table: $(SYM)"; \
	else \
		echo "  [SIM] Skipping link (simulation mode)"; \
		touch $@; \
	fi

# ═══════════════════════════════════════════════════════════════════════════════
#  生成 HEX/BIN/LST
# ═══════════════════════════════════════════════════════════════════════════════
$(HEX): $(ELF)
	@echo ""
	@echo "  [5/7] Generate HEX: $@"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(OBJCOPY) -O ihex $< $@; \
		echo "  [OK] HEX: $$(wc -c < $@) bytes"; \
	else \
		echo "  [SIM] Skipping HEX generation"; \
	fi

$(BIN): $(ELF)
	@echo ""
	@echo "  [6/7] Generate BIN: $@"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(OBJCOPY) -O binary $< $@; \
		echo "  [OK] BIN: $$(wc -c < $@) bytes"; \
	else \
		echo "  [SIM] Skipping BIN generation"; \
	fi

$(LST): $(ELF)
	@echo ""
	@echo "  [OBJDUMP] Generate LST: $@"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(OBJDUMP) -d -S --disassemble-all $< > $@; \
		echo "  [OK] LST: $$(wc -l < $@) lines"; \
	else \
		echo "  [SIM] Skipping disassembly"; \
	fi

# ═══════════════════════════════════════════════════════════════════════════════
#  代码大小统计
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: size
size: $(ELF)
	@echo ""
	@echo "##################################################"
	@echo "  [7/7] Binary Size Report"
	@echo "##################################################"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		echo ""; \
		$(SIZE) $(ELF); \
		echo ""; \
		echo "  Memory Layout (from link.ld):"; \
		echo "    FLASH: 256KB @ 0x20000000"; \
		echo "    RAM:   128KB @ 0x80000000"; \
	else \
		echo "  [SIM] Size report (source code sizes):"; \
		echo ""; \
		for f in $(SRC_DIR)/*.c $(SRC_DIR)/*.S; do \
			if [ -f "$$f" ]; then \
				SIZE=$$(wc -c < "$$f" 2>/dev/null || echo 0); \
				LINES=$$(wc -l < "$$f" 2>/dev/null || echo 0); \
				echo "    $$f: $$SIZE bytes, $$LINES lines"; \
			fi; \
		done; \
		echo ""; \
		echo "  Estimated binary size (RISC-V 32-bit, -Os):"; \
		TOTAL_C=$$(cat $(SRC_DIR)/*.c 2>/dev/null | wc -c); \
		ESTIMATED=$$((TOTAL_C / 3)); \
		echo "    Source code: $$TOTAL_C bytes"; \
		echo "    Estimated ELF: ~$$ESTIMATED bytes (1/3 ratio)"; \
	fi
	@echo "##################################################"

# ═══════════════════════════════════════════════════════════════════════════════
#  构建摘要
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: summary
summary:
	@echo ""
	@echo "============================================"
	@echo "  Build Summary"
	@echo "============================================"
	@echo "  Target:     $(CHIP)"
	@echo "  Arch:       $(ARCH)"
	@echo "  ABI:        $(ABI)"
	@echo "  Optim:      $(OPT)"
	@echo "  Source:     $$(ls $(SRC_DIR)/*.c 2>/dev/null | wc -l) C files"
	@echo "  Assembly:   $$(ls $(SRC_DIR)/*.S 2>/dev/null | wc -l) S files"
	@echo "  Toolchain:  $$(if [ '$(TOOLCHAIN_OK)' = 'yes' ]; then echo 'RISC-V Cross'; else echo 'SIMULATION'; fi)"
	@echo "  Output:     $(ELF)"
	@echo "============================================"
	@echo ""

# ═══════════════════════════════════════════════════════════════════════════════
#  清理
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: clean
clean:
	@echo "  [CLEAN] Removing build directory..."
	@rm -rf $(OBJ_DIR)
	@echo "  [CLEAN] Done."

# ═══════════════════════════════════════════════════════════════════════════════
#  测试
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: test
test:
	@echo ""
	@echo "=== Running RISC-V Embedded Tests ==="
	@python3 scripts/riscv_embedded_demo.py
	@echo ""
	@echo "=== Running Unit Tests ==="
	@python3 tests/test_riscv_embedded.py
	@echo ""
	@echo "=== Running Hardware Simulation Tests ==="
	@python3 scripts/riscv_hardware_sim_test.py
	@echo ""
	@echo "=== Running Integration Tests ==="
	@python3 scripts/integration_test_embedded.py
	@echo ""
	@echo "=== All Tests Complete ==="

# ═══════════════════════════════════════════════════════════════════════════════
#  语法检查
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: syntax-check
syntax-check:
	@echo "=== C Code Syntax Check ==="
	@for f in $(SRC_DIR)/*.c $(SRC_DIR)/*.S; do \
		if [ -f "$$f" ]; then \
			echo "  [CHK] $$f"; \
			python3 -c " \
c = open('$$f').read(); \
b = c.count('{') - c.count('}'); \
p = c.count('(') - c.count(')'); \
s = c.count('[') - c.count(']'); \
status = 'OK' if b == 0 and p == 0 and s == 0 else 'BALANCE ERROR'; \
print(f'    Braces: {b:±d}  Parens: {p:±d}  Brackets: {s:±d}  [{status}]'); \
assert b == 0 and p == 0 and s == 0, f'Balance error in $$f'; \
"; \
		fi; \
	done
	@echo "=== Syntax Check Complete ==="

# ═══════════════════════════════════════════════════════════════════════════════
#  查看日志
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: logs
logs:
	@echo "=== Build Logs ==="
	@ls -la $(LOG_DIR)/ 2>/dev/null || echo "  No logs yet"
	@echo ""
	@if [ -n "$$(ls $(LOG_DIR)/*.err 2>/dev/null)" ]; then \
		echo "=== Error Logs ==="; \
		for f in $(LOG_DIR)/*.err; do \
			echo "--- $$f ---"; \
			cat $$f; \
			echo; \
		done; \
	else \
		echo "  No error logs found."; \
	fi

# ═══════════════════════════════════════════════════════════════════════════════
#  帮助
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: help
help:
	@echo "Matha RISC-V Embedded Project Build System (v2)"
	@echo ""
	@echo "Targets:"
	@echo "  all            - Build all outputs (ELF, HEX, BIN, LST, MAP)"
	@echo "  check_toolchain - Check cross-compiler availability"
	@echo "  clean          - Remove build directory"
	@echo "  test           - Run all tests (demo + unit + sim + integration)"
	@echo "  generate       - Generate C code from Matha templates"
	@echo "  syntax-check   - Check C/S code syntax (brace balance)"
	@echo "  logs           - Show build logs"
	@echo "  help           - Show this help"
	@echo ""
	@echo "Variables:"
	@echo "  TOOLCHAIN_PREFIX - Cross-compiler prefix (default: riscv64-unknown-elf-)"
	@echo "  CHIP             - Target chip (default: FE310)"
	@echo "  ARCH             - Architecture (default: rv32imac)"
	@echo "  OPT              - Optimization (default: -Os)"
	@echo ""
	@echo "Examples:"
	@echo "  make all              # Full build with detailed logs"
	@echo "  make test             # Run all tests"
	@echo "  make generate         # Generate C code only"
	@echo "  make syntax-check     # Check code syntax"
	@echo "  make logs             # Show build logs"
	@echo "  make clean            # Clean build artifacts"

.PHONY: all clean test generate syntax-check logs summary dirs check_toolchain
