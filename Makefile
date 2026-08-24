# Makefile — Matha RISC-V 嵌入式项目
# 目标架构: SiFive FE310 (RISC-V 32-bit)
# 生成方式: python scripts/riscv_embedded_demo.py

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

# 默认目标
all: dirs $(ELF) $(HEX) $(BIN) $(LST) size
	@echo ""
	@echo "=== Build Complete ==="
	@echo "  ELF: $(ELF)"
	@echo "  HEX: $(HEX)"
	@echo "  BIN: $(BIN)"
	@echo "  LST: $(LST)"

# 创建构建目录
dirs:
	@mkdir -p $(OBJ_DIR)

# 编译 C 源文件
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c
	@echo "  CC    $<"
	@$(CC) $(CFLAGS) -c $< -o $@

# 编译汇编源文件
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.S
	@echo "  AS    $<"
	@$(AS) -march=$(ARCH) -mabi=$(ABI) $< -o $@

# 链接
$(ELF): $(OBJS) link.ld
	@echo "  LD    $@"
	@$(LD) $(LDFLAGS) -o $@ $(OBJS) --print-map > $(MAP)

# 生成 HEX
$(HEX): $(ELF)
	@echo "  OBJCOPY HEX"
	@$(OBJCOPY) -O ihex $< $@

# 生成 BIN
$(BIN): $(ELF)
	@echo "  OBJCOPY BIN"
	@$(OBJCOPY) -O binary $< $@

# 生成 LST (反汇编)
$(LST): $(ELF)
	@echo "  OBJDUMP LST"
	@$(OBJDUMP) -d -S $< > $@

# 代码大小统计
size: $(ELF)
	@echo ""
	@echo "=== Binary Size ==="
	@$(SIZE) $<

# 清理
clean:
	@echo "  CLEAN"
	@rm -rf $(OBJ_DIR)
	@echo "  Done."

# 闪灯测试
flash-led: $(BIN)
	@echo "  Flash LED pattern (simulated)"
	@echo "  Target: SiFive FE310 @ 0x20000000"
	@echo "  Binary: $(BIN) ($(shell wc -c < $(BIN) 2>/dev/null || echo 0) bytes)"

# 运行测试
test: all
	@echo ""
	@echo "=== Running RISC-V Tests ==="
	@python3 scripts/riscv_embedded_demo.py

# 生成代码
generate:
	@echo "  Generating C code from Matha templates..."
	@python3 -c "
from scripts.riscv_embedded_demo import (
    generate_i2c_sensor_c, generate_linalg_c,
    generate_embedded_project_template, generate_watchdog_c_code
)
import os
os.makedirs('src', exist_ok=True)
with open('src/i2c_sensor.c', 'w') as f:
    f.write(generate_i2c_sensor_c())
    print('  src/i2c_sensor.c  generated')
with open('src/linalg.c', 'w') as f:
    f.write(generate_linalg_c())
    print('  src/linalg.c      generated')
with open('src/main.c', 'w') as f:
    f.write(generate_embedded_project_template())
    print('  src/main.c        generated')
with open('src/watchdog.c', 'w') as f:
    f.write(generate_watchdog_c_code())
    print('  src/watchdog.c    generated')
"

# 查看反汇编
disassemble: $(ELF)
	@$(OBJDUMP) -d $(ELF) | head -100

# 查看内存映射
memory-map: $(MAP)
	@cat $(MAP)

# 帮助
help:
	@echo "Matha RISC-V Embedded Project Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all         - Build all outputs (ELF, HEX, BIN, LST)"
	@echo "  clean       - Remove build directory"
	@echo "  test        - Run Python tests"
	@echo "  generate    - Generate C code from Matha templates"
	@echo "  flash-led   - Flash LED pattern (simulated)"
	@echo "  disassemble - View disassembly"
	@echo "  memory-map  - View linker map"
	@echo "  help        - Show this help"
	@echo ""
	@echo "Variables:"
	@echo "  TOOLCHAIN_PREFIX  - Cross-compiler prefix (default: riscv64-unknown-elf-)"
	@echo "  CHIP              - Target chip (default: FE310)"
	@echo "  ARCH              - Architecture (default: rv32imac)"
	@echo "  OPT               - Optimization (default: -Os)"

.PHONY: all clean test flash-led generate disassemble memory-map help size dirs
