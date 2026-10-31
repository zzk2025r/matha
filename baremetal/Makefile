# baremetal/Makefile — Matha P5「脱离宿主 OS」裸机 HAL 的独立构建
#
# 这是 baremetal/ 自带的构建脚本，与仓库根 Makefile 完全隔离：
#   - `make check`  —— 结构校验 + 宿主 gcc -fsyntax-only（本机无需交叉工具链即可跑）
#   - `make all`    —— 若装有 RISC-V 交叉工具链则真正产出 ELF/BIN；否则如实降级
#
# 目标：SiFive FE310 / RV32IMAC，裸机 freestanding（-ffreestanding -nostdlib）。

TOOLCHAIN_PREFIX ?= riscv-none-elf-
CROSS_CC   = $(TOOLCHAIN_PREFIX)gcc
CROSS_LD   = $(TOOLCHAIN_PREFIX)ld
OBJCOPY    = $(TOOLCHAIN_PREFIX)objcopy

ARCH = rv32imac_zicsr
ABI  = ilp32
# 说明：现代 binutils（xPack 15.2）把 CSR 访问拆成独立扩展 zicsr，
# 不显式列入就会报 `unrecognized opcode csrr ... extension zicsr required`。
# rv32imac 本身含 CSR（特权基线），此处只是满足工具链的新命名要求。
# 链接统一走交叉 gcc 驱动（它会把 march/mabi 翻译为正确的 ld 仿真 elf32lriscv），
# 裸 ld 不接受 -march/-mabi（其 -m 含义是「仿真模式」）。

HAL_INC   = include
SRC_DIR   = .
BUILD_DIR = build

C_SRCS = main.c hal/drivers/uart.c hal/mem/allocator.c hal/trap/trap.c hal/vm/stack_vm.c
S_SRCS = boot/crt0.S boot/vector.S

CFLAGS = -march=$(ARCH) -mabi=$(ABI) -Os -ffreestanding -nostdlib \
         -Wall -Wextra -I$(HAL_INC) -T link.ld

# 交叉工具链是否存在（决定 all 能否真正产出固件）
CROSS_OK := $(shell command -v $(CROSS_CC) >/dev/null 2>&1 && echo yes || echo no)
# 宿主 gcc（用于无交叉工具链时的 -fsyntax-only 语法门禁）
HOST_CC  ?= gcc

.PHONY: all check sim dirs clean


# ── 结构校验 + 宿主语法门禁 + 寄存器级/行为模拟（本机可跑，不需交叉工具链）──
check:
	@python3 tools/check_skeleton.py

# ── 跑全部宿主模拟（真实 uart/allocator/trap/stack_vm.c，用宿主 gcc）────────
sim:
	@python3 tools/run_uart_sim.py
	@python3 tools/run_mem_sim.py
	@python3 tools/run_trap_sim.py
	@python3 tools/run_vm_sim.py

# ── 在 stock QEMU (riscv32 -machine virt) 上实跑「中断接管 + UART 打印」演示 ──
# board-matched 变体（ns16550 UART + virt RAM@0x80000000），非 FE310 产物、与
# firmware 目标无关。需交叉工具链 + QEMU；缺任一由 runner 如实 SKIP（退出码 2）。
.PHONY: qemu-demo
qemu-demo:
	@python3 tools/qemu_virt_demo/run_qemu_virt_demo.py

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
	@$(CROSS_CC) -march=$(ARCH) -mabi=$(ABI) -nostdlib -T link.ld -Wl,--nmagic \
	  -o $(BUILD_DIR)/matha_hal.elf $(BUILD_DIR)/obj/*.o
	@$(OBJCOPY) -O binary $(BUILD_DIR)/matha_hal.elf $(BUILD_DIR)/matha_hal.bin
	@echo "[baremetal] 固件产出：$(BUILD_DIR)/matha_hal.{elf,bin}"

.PHONY: dirs
dirs:
	@mkdir -p $(BUILD_DIR)

clean:
	@rm -rf $(BUILD_DIR)
	@echo "[baremetal] 已清理 build/"
