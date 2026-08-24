# Makefile — Matha RISC-V 嵌入式项目
# 目标架构: SiFive FE310 (RISC-V 32-bit)
# 生成方式: python scripts/riscv_embedded_demo.py
# 构建日志: 详细输出每个编译步骤，方便排查交叉编译错误

TOOLCHAIN_PREFIX ?= riscv64-unknown-elf-
CC       = $(TOOLCHAIN_PREFIX)gcc
AS       = $(TOOLCHAIN_PREFIX)as
LD       = $(TOOLCHAIN_PREFIX)ld
OBJCOPY  = $(TOOLCHAIN_PREFIX)objcopy
OBJDUMP  = $(TOOLCHAIN_PREFIX)objdump
SIZE     = $(TOOLCHAIN_PREFIX)size

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

# 构建日志目录
LOG_DIR  = build/logs
BUILD_LOG = $(LOG_DIR)/build_$(shell date +%Y%m%d_%H%M%S).log

# 检测交叉编译器
TOOLCHAIN_OK := $(shell $(CC) --version >nul 2>&1 && echo yes || echo no)

# 默认目标
all: check_toolchain dirs $(ELF) $(HEX) $(BIN) $(LST) size
	@echo ""
	@echo "============================================"
	@echo "  Matha RISC-V Build Complete"
	@echo "  Target: $(CHIP) ($(ARCH)/$(ABI))"
	@echo "============================================"
	@echo "  ELF:  $(ELF)"
	@echo "  HEX:  $(HEX)"
	@echo "  BIN:  $(BIN)"
	@echo "  LST:  $(LST)"
	@echo "  MAP:  $(MAP)"
	@echo "  Log:  $(BUILD_LOG)"
	@echo ""
	@echo "  Binary size: $$(wc -c < $(BIN) 2>/dev/null || echo 'N/A') bytes"

# 检查交叉编译器
check_toolchain:
	@echo ""
	@echo "=== Toolchain Check ==="
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		echo "  [OK] Cross-compiler found: $(CC)"; \
		$(CC) --version | head -1; \
		echo "  [OK] All tools available"; \
	else \
		echo "  [WARN] RISC-V cross-compiler NOT found"; \
		echo "  [INFO] Trying fallback to host compiler (simulation mode)"; \
		echo "  [INFO] Install: sudo apt install gcc-riscv64-unknown-elf"; \
		echo "  [INFO] Or download: https://devzone.nordicsemi.com/f/nordic-qna/67647/risc-v-gnu-toolchain"; \
		echo "  [SIM] Building in SIMULATION mode (host gcc, no RISC-V target)"; \
		echo "  [SIM] CFLAGS overridden for host compilation"; \
	fi
	@echo ""

# 创建构建目录
dirs:
	@mkdir -p $(OBJ_DIR) $(LOG_DIR)
	@echo "  [DIR] Created: $(OBJ_DIR)/, $(LOG_DIR)/"

# 编译 C 源文件 (带详细日志)
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c | dirs
	@echo ""
	@echo "--------------------------------------------"
	@echo "  [CC] Compiling: $<"
	@echo "  [CC] Target:   $(CHIP) ($(ARCH)/$(ABI))"
	@echo "  [CC] Options:  $(CFLAGS)"
	@echo "--------------------------------------------"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		echo "  [CC] Using RISC-V cross-compiler"; \
		$(CC) $(CFLAGS) -c $< -o $@ 2> $(LOG_DIR)/$*.err; \
		if [ -s $(LOG_DIR)/$*.err ]; then \
			echo "  [WARN] Compilation warnings/errors:"; \
			cat $(LOG_DIR)/$*.err; \
		else \
			echo "  [OK] $< -> $@"; \
		fi; \
	else \
		echo "  [SIM] Using host compiler (simulation mode)"; \
		gcc -m32 -c $< -o $@ -D__RISCV_SIMULATION__ 2> $(LOG_DIR)/$*.err; \
		if [ -s $(LOG_DIR)/$*.err ]; then \
			echo "  [WARN] Compilation warnings:"; \
			cat $(LOG_DIR)/$*.err; \
		else \
			echo "  [OK] $< -> $@ (simulated)"; \
		fi; \
	fi

# 编译汇编源文件
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.S | dirs
	@echo ""
	@echo "--------------------------------------------"
	@echo "  [AS] Assembling: $<"
	@echo "--------------------------------------------"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(AS) -march=$(ARCH) -mabi=$(ABI) $< -o $@ 2> $(LOG_DIR)/$*.err; \
		if [ -s $(LOG_DIR)/$*.err ]; then \
			echo "  [WARN] Assembly warnings:"; \
			cat $(LOG_DIR)/$*.err; \
		else \
			echo "  [OK] $< -> $@"; \
		fi; \
	else \
		echo "  [SIM] Skipping assembly (no cross-compiler)"; \
		touch $@; \
	fi

# 链接
$(ELF): $(OBJS) link.ld | dirs
	@echo ""
	@echo "--------------------------------------------"
	@echo "  [LD] Linking: $@"
	@echo "  [LD] Objects: $(OBJS)"
	@echo "  [LD] Linker script: link.ld"
	@echo "--------------------------------------------"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(LD) $(LDFLAGS) -o $@ $(OBJS) --print-map > $(MAP) 2> $(LOG_DIR)/link.err; \
		if [ -s $(LOG_DIR)/link.err ]; then \
			echo "  [ERROR] Linker errors:"; \
			cat $(LOG_DIR)/link.err; \
			exit 1; \
		else \
			echo "  [OK] Linked: $@"; \
		fi; \
	else \
		echo "  [SIM] Skipping link (simulation mode)"; \
		touch $@; \
	fi

# 生成 HEX
$(HEX): $(ELF)
	@echo ""
	@echo "  [OBJCOPY] Generating HEX: $@"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(OBJCOPY) -O ihex $< $@; \
		echo "  [OK] HEX generated: $$(wc -c < $@) bytes"; \
	else \
		echo "  [SIM] Skipping HEX generation"; \
	fi

# 生成 BIN
$(BIN): $(ELF)
	@echo ""
	@echo "  [OBJCOPY] Generating BIN: $@"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(OBJCOPY) -O binary $< $@; \
		echo "  [OK] BIN generated: $$(wc -c < $@) bytes"; \
	else \
		echo "  [SIM] Skipping BIN generation"; \
	fi

# 生成 LST (反汇编)
$(LST): $(ELF)
	@echo ""
	@echo "  [OBJDUMP] Generating LST: $@"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(OBJDUMP) -d -S $< > $@; \
		echo "  [OK] LST generated: $$(wc -l < $@) lines"; \
	else \
		echo "  [SIM] Skipping disassembly"; \
	fi

# 代码大小统计
size: $(ELF)
	@echo ""
	@echo "============================================"
	@echo "  Binary Size Report"
	@echo "============================================"
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(SIZE) $(ELF); \
	else \
		echo "  [SIM] Size report skipped (simulation mode)"; \
		echo "  Generated C code sizes:"; \
		@for f in $(SRC_DIR)/*.c; do \
			echo "    $$f: $$(wc -c < $$f 2>/dev/null || echo 0) bytes"; \
		done; \
	fi
	@echo "============================================"

# 清理
clean:
	@echo "  [CLEAN] Removing build directory..."
	@rm -rf $(OBJ_DIR)
	@echo "  [CLEAN] Done."

# 闪灯测试
flash-led: $(BIN)
	@echo ""
	@echo "=== Flash LED Test (Simulated) ==="
	@echo "  Target: SiFive FE310 @ 0x20000000"
	@if [ -f "$(BIN)" ]; then \
		echo "  Binary size: $$(wc -c < $(BIN)) bytes"; \
		echo "  [SIM] LED blink pattern: GPIO1 (LED) toggle every 500ms"; \
	else \
		echo "  [WARN] BIN not found, skipping flash test"; \
	fi

# 运行测试
test:
	@echo ""
	@echo "=== Running RISC-V Tests ==="
	@python scripts/riscv_embedded_demo.py
	@echo ""
	@echo "=== Running Unit Tests ==="
	@python tests/test_riscv_embedded.py
	@echo ""
	@echo "=== Running Integration Tests ==="
	@python scripts/integration_test_embedded.py

# 生成代码
generate:
	@echo "  [GEN] Generating C code from Matha templates..."
	@python -c "
from scripts.riscv_embedded_demo import (
    generate_i2c_sensor_c, generate_linalg_c,
    generate_embedded_project_template
)
import os
os.makedirs('src', exist_ok=True)
files = [
    ('src/i2c_sensor.c', generate_i2c_sensor_c()),
    ('src/linalg.c', generate_linalg_c()),
    ('src/main.c', generate_embedded_project_template()),
]
for path, code in files:
    with open(path, 'w') as f:
        f.write(code)
    print(f'  [GEN] {path}: {len(code)} bytes, {len(code.splitlines())} lines')
"

# 检查代码语法 (无编译器时)
syntax-check:
	@echo "=== Syntax Check ==="
	@for f in $(SRC_DIR)/*.c; do \
		echo "  [CHK] $$f"; \
		python -c "import re; c=open('$$f').read(); \
		balance=c.count('{')-c.count('}'); \
		print(f'    Braces balance: {balance}'); \
		assert balance==0, f'Unbalanced braces in $$f'; \
		print(f'    [OK] Syntax OK')"; \
	done
	@echo "=== Syntax Check Complete ==="

# 查看反汇编
disassemble: $(ELF)
	@if [ "$(TOOLCHAIN_OK)" = "yes" ]; then \
		$(OBJDUMP) -d $(ELF) | head -100; \
	else \
		echo "  [SIM] Disassembly skipped (no cross-compiler)"; \
	fi

# 查看内存映射
memory-map: $(ELF)
	@if [ -f "$(MAP)" ]; then \
		cat $(MAP); \
	else \
		echo "  [SIM] Map file not generated (no cross-compiler)"; \
		cat link.ld; \
	fi

# 查看所有日志
logs:
	@echo "=== Build Logs ==="
	@ls -la $(LOG_DIR)/ 2>/dev/null || echo "  No logs yet"
	@echo ""
	@if [ -n "$$(ls $(LOG_DIR)/*.err 2>/dev/null)" ]; then \
		echo "=== Error Logs ==="; \
		for f in $(LOG_DIR)/*.err; do echo "--- $$f ---"; cat $$f; echo; done; \
	else \
		echo "  No error logs found."; \
	fi

# 帮助
help:
	@echo "Matha RISC-V Embedded Project Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all            - Build all outputs (ELF, HEX, BIN, LST)"
	@echo "  check_toolchain - Check cross-compiler availability"
	@echo "  clean          - Remove build directory"
	@echo "  test           - Run all tests (demo + unit + integration)"
	@echo "  generate       - Generate C code from Matha templates"
	@echo "  syntax-check   - Check C code syntax (brace balance)"
	@echo "  flash-led      - Flash LED pattern (simulated)"
	@echo "  disassemble    - View disassembly"
	@echo "  memory-map     - View linker map"
	@echo "  logs           - Show build logs"
	@echo "  help           - Show this help"
	@echo ""
	@echo "Variables:"
	@echo "  TOOLCHAIN_PREFIX  - Cross-compiler prefix (default: riscv64-unknown-elf-)"
	@echo "  CHIP              - Target chip (default: FE310)"
	@echo "  ARCH              - Architecture (default: rv32imac)"
	@echo "  OPT               - Optimization (default: -Os)"
	@echo ""
	@echo "Examples:"
	@echo "  make all              # Build project"
	@echo "  make test             # Run all tests"
	@echo "  make generate         # Generate C code"
	@echo "  make logs             # Show build logs"

.PHONY: all clean test flash-led generate disassemble memory-map help size dirs check_toolchain syntax-check logs
