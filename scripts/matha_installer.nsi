# NSIS 安装脚本 — Matha 独立可执行文件安装程序
#
# 功能:
# - 安装 matha.exe 和 matha-cc.exe 到指定目录
# - 创建桌面快捷方式
# - 创建开始菜单快捷方式
# - 创建右键菜单（打开命令行）
# - 添加到系统 PATH
# - 卸载程序
#
# 编译命令（从仓库根或任意处运行，路径基准由 !cdpath 定为仓库根）:
#   makensis /DVERSION=4.6.0 scripts\matha_installer.nsi

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

; 本脚本住在 scripts\ 下：编译期 File 路径基准改到仓库根（旧写法没有
; !cdpath，所有 File 按 makensis 的当前目录解析，且指向已退役的
; matha-offline\ 嵌套产物布局——makensis 直接报 "can't open file"）。
!cdpath "${__FILEDIR__}\.."

; 版本号/输出目录：命令行未传时回落默认（VERSION 默认值须与
; src\__version__.py 同步，不再写死旧版号）
!ifndef VERSION
  !define VERSION "4.6.0"
!endif
!ifndef OUTPUT_DIR
  !define OUTPUT_DIR "dist"
!endif

; ============================
; 安装包基本信息
; ============================
Name "Matha v${VERSION}"
OutFile "${OUTPUT_DIR}\Matha-Setup-${VERSION}-Windows-x64.exe"
InstallDir "$PROGRAMFILES64\Matha"
RequestExecutionLevel admin

; ============================
; 页面配置
; ============================
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
; 注：仓库内无 matha_icon.ico（旧写法引用不存在的图标，makensis 编译即失败），
; 用 NSIS 默认图标。

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES

; 卸载页面
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; 语言
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ============================
; 组件定义
; ============================
Section "Matha 主程序 (必需)" SEC01
    SetOutPath "$INSTDIR"

    ; 复制主程序（平铺产物口径：dist\matha.exe / dist\matha-cc.exe，与
    ; scripts\build.bat、.github\workflows\build.yml、scripts\build_exe.py 同判）
    File "dist\matha.exe"
    File "dist\matha-cc.exe"

    ; 复制脚本和文档
    SetOutPath "$INSTDIR\scripts"
    File /r "scripts\*.py"
    File /r "scripts\*.bat"
    File /r "scripts\*.sh"

    SetOutPath "$INSTDIR\docs"
    File /r "docs\*.md"

    SetOutPath "$INSTDIR\src"
    ; File /r 已递归全部子包（src\kernel、src\mbc 等解释器/VM 必需件在内——
    ; 旧写法在此另列 compiler/domains/offline/stdlib/intent 五片，是冗余重复）
    File /r "src\*.py"

    SetOutPath "$INSTDIR\tests"
    File /r "tests\*.py"

    ; 复制配置文件
    File "pyproject.toml"
    File "matha.spec"
    File "matha-cc.spec"
    File "README.md"
    File "requirements.txt"
SectionEnd

Section "桌面快捷方式" SEC02
    CreateShortCut "$DESKTOP\Matha REPL.lnk" "$INSTDIR\matha.exe" "" "$INSTDIR\matha.exe" 0
    CreateShortCut "$DESKTOP\Matha 编译器.lnk" "$INSTDIR\matha-cc.exe" "" "$INSTDIR\matha-cc.exe" 0
    CreateShortCut "$DESKTOP\Matha 安装目录.lnk" "$INSTDIR" "" "$INSTDIR" 0
SectionEnd

Section "开始菜单快捷方式" SEC03
    CreateDirectory "$SMPROGRAMS\Matha"
    CreateShortCut "$SMPROGRAMS\Matha\Matha REPL.lnk" "$INSTDIR\matha.exe" "" "$INSTDIR\matha.exe" 0
    CreateShortCut "$SMPROGRAMS\Matha\Matha 编译器.lnk" "$INSTDIR\matha-cc.exe" "" "$INSTDIR\matha-cc.exe" 0
    CreateShortCut "$SMPROGRAMS\Matha\Matha 文档.lnk" "$INSTDIR\docs\OFFLINE_GUIDE.md" "" "$INSTDIR\docs\OFFLINE_GUIDE.md" 0
    CreateShortCut "$SMPROGRAMS\Matha\Matha 卸载.lnk" "$INSTDIR\uninst.exe" "" "$INSTDIR\uninst.exe" 0
    CreateShortCut "$SMPROGRAMS\Matha\打开命令提示符.lnk" "%SystemRoot%\System32\cmd.exe" "/k cd /d $INSTDIR" "" "$INSTDIR\matha.exe" 0
SectionEnd

Section "添加到系统 PATH" SEC04
    ; 添加安装目录到系统 PATH
    ReadRegStr $0 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "PATH"
    StrCmp $0 "" 0 +2
    StrCpy $0 ""
    StrCpy $1 $0
    Strchr $2 $1 ";"
    StrCmp $2 "" 0 +2
    StrCpy $1 "$1;"
    StrCpy $1 "$INSTDIR;$1"

    ; 检查是否已存在
    StrStr $2 $1 "$INSTDIR"
    StrCmp $2 "" 0 +4
    StrCpy $1 $0
    DetailPrint "已添加到系统 PATH: $INSTDIR"

    WriteRegStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "PATH" "$1"
SectionEnd

Section "卸载"
    Delete "$DESKTOP\Matha REPL.lnk"
    Delete "$DESKTOP\Matha 编译器.lnk"
    Delete "$DESKTOP\Matha 安装目录.lnk"

    RMDir /r "$SMPROGRAMS\Matha"

    ; 从 PATH 中移除
    ReadRegStr $0 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "PATH"
    StrCpy $1 $0
    StrCpy $2 0
    StrCpy $3 ""
    loop:
      StrCpy $4 $1 1
      StrCmp $4 "" done
      StrCmp $4 ";" 0 +4
        StrCpy $2 1
        Goto done
      StrCpy $3 "$3$4"
      StrCpy $1 $1 1 1
      Goto loop
    done:
    StrCmp $2 0 0 +2
      StrCpy $3 "$3;"
    StrCpy $3 "$3$1"
    WriteRegStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "PATH" "$3"

    ; 删除所有文件
    RMDir /r "$INSTDIR"
SectionEnd

; ============================
; 函数: 获取版本
; ============================
Function .onInit
    ; x64.nsh 的宏判据（旧写法 ${If} $ PROCESSOR_ARCHITECTURE == "AMD64" 里
    ; "$ PROCESSOR_ARCHITECTURE" 不是合法的 NSIS 变量写法，makensis 编译即失败）
    ${If} ${RunningX64}
        ; 64 位系统：安装到 $PROGRAMFILES64\Matha（InstallDir 已定）
    ${Else}
        MessageBox MB_ICONSTOP|MB_OK "Matha 独立可执行文件为 x64 构建，需要 64 位 Windows。"
        Quit
    ${EndIf}
FunctionEnd

; ============================
; 函数: 安装完成后的操作
; ============================
Function .onInstSuccess
    MessageBox MB_ICONINFORMATION|MB_OK "Matha v${VERSION} 安装成功！\n\n桌面快捷方式已创建。\n双击 'Matha REPL' 启动交互式使用。"
FunctionEnd
