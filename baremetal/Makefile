# baremetal/Makefile — Matha P5「脱离宿主 OS」裸机 HAL 的独立构建
#
# 这是 baremetal/ 自带的构建脚本，与仓库根 Makefile 完全隔离：
#   - `make check`  —— 结构校验 + 宿主 gcc -fsyntax-only（本机无需交叉工具链即可跑）
#   - `make all`    —— 若装有 RISC-V 交叉工具链则真正产出 ELF/BIN；否则如实降级
#
# 目标：SiFive FE310 / RV32IMAC，裸机 freestanding（-ffreestanding -nostdlib）。

TOOLCHAIN_PREFIX ?= riscv64-unknown-elf-
CROSS_CC   = $(TOOLCHAIN_PREFIX)gcc
CROSS_LD   = $(TOOLCHAIN_PREFIX)ld
OBJCOPY    = $(TOOLCHAIN_PREFIX)objcopy

ARCH = rv32imac
ABI  = ilp32

HAL_INC   = include
SRC_DIR   = .
BUILD_DIR = build

C_SRCS = main.c hal/drivers/uart.c hal/mem/allocator.c hal/trap/trap.c
S_SRCS = boot/crt0.S boot/vector.S

CFLAGS = -march=$(ARCH) -mabi=$(ABI) -Os -ffreestanding -nostdlib \
         -Wall -Wextra -I$(HAL_INC) -T link.ld

# 交叉工具链是否存在（决定 all 能否真正产出固件）
CROSS_OK := $(shell command -v $(CROSS_CC) >/dev/null 2>&1 && echo yes || echo no)
# 宿主 gcc（用于无交叉工具链时的 -fsyntax-only 语法门禁）
HOST_CC  ?= gcc

.PHONY: all check dirs clean

# ── 结构校验 + 宿主语法门禁（本机可跑，不需要交叉工具链）────────────────
check:
	@python3 tools/check_skeleton.py

all: check
ifeq ($(CROSS_OK),yes)
	@echo "[baremetal] 交叉工具链就绪：$(CROSS_CC)"
	@$(MAKE) firmware
else
	@echo "[baremetal] 未检测到 RISC-V 交叉工具链，all 仅完成骨架校验。"
	@echo "[baremetal] 安装后可执行 'make firmware' 真正产出 ELF/BIN。"
endif

# ── 真正裸机产物（仅在有交叉工具链时有意义）────────────────────────────
.PHONY: firmware
firmware: dirs
	@mkdir -p $(BUILD_DIR)/obj
	@for f in $(C_SRCS); do \
	  echo "  [CC ] $$f"; \
	  $(CROSS_CC) $(CFLAGS) -c $$f -o $(BUILD_DIR)/obj/$$(basename $$f .c).o || exit 1; \
	done
	@for f in $(S_SRCS); do \
	  echo "  [AS ] $$f"; \
	  $(CROSS_CC) $(CFLAGS) -c $$f -o $(BUILD_DIR)/obj/$$(basename $$f .S).o || exit 1; \
	done
	@echo "  [LD ] -> $(BUILD_DIR)/matha_hal.elf"
	@$(CROSS_LD) -march=$(ARCH) -mabi=$(ABI) -T link.ld --nmagic \
	  -o $(BUILD_DIR)/matha_hal.elf $(BUILD_DIR)/obj/*.o
	@$(OBJCOPY) -O binary $(BUILD_DIR)/matha_hal.elf $(BUILD_DIR)/matha_hal.bin
	@echo "[baremetal] 固件产出：$(BUILD_DIR)/matha_hal.{elf,bin}"

.PHONY: dirs
dirs:
	@mkdir -p $(BUILD_DIR)

clean:
	@rm -rf $(BUILD_DIR)
	@echo "[baremetal] 已清理 build/"
