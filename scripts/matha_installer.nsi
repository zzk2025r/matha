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
# 编译命令:
#   makensis /DOUTPUT_DIR=dist /DVERSION=4.4 matha_installer.nsi

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

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
!define MUI_ICON "matha_icon.ico"
!define MUI_UNICON "matha_icon.ico"

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

    ; 复制主程序
    File "matha-offline\matha.exe"
    File "matha-cc-offline\matha-cc.exe"

    ; 复制脚本和文档
    SetOutPath "$INSTDIR\scripts"
    File /r "scripts\*.py"
    File /r "scripts\*.bat"
    File /r "scripts\*.sh"

    SetOutPath "$INSTDIR\docs"
    File /r "docs\*.md"

    SetOutPath "$INSTDIR\src"
    File /r "src\*.py"
    File /r "src\compiler\*.py"
    File /r "src\domains\*.py"
    File /r "src\offline\*.py"
    File /r "src\stdlib\*.py"
    File /r "src\intent\*.py"

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
    CreateShortCut "$SMPROGRAMS\Matha\Matha 文档.lnk" "$INSTDIR\docs\README.md" "" "$INSTDIR\docs\README.md" 0
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
    ; 检查是否需要管理员权限
    ${If} $ PROCESSOR_ARCHITECTURE == "AMD64"
        ; 64 位系统
    ${EndIf}
FunctionEnd

; ============================
; 函数: 安装完成后的操作
; ============================
Function .onInstSuccess
    MessageBox MB_ICONINFORMATION|MB_OK "Matha v${VERSION} 安装成功！\n\n桌面快捷方式已创建。\n双击 'Matha REPL' 启动交互式使用。"
FunctionEnd
