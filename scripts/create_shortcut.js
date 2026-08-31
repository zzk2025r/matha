// JavaScript 创建快捷方式
var shell = new ActiveXObject("WScript.Shell");
var shortcut = shell.CreateShortcut(WScript.Arguments(0));
if (WScript.Arguments.length > 1) {
    shortcut.TargetPath = WScript.Arguments(1);
}
if (WScript.Arguments.length > 2) {
    shortcut.Description = WScript.Arguments(2);
}
shortcut.WorkingDirectory = WScript.Arguments(1).replace(/\\[^\\]+$/, "");
shortcut.Save();
