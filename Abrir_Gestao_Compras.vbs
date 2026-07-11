Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "cmd /c """ & scriptDir & "\start_gestao_compras.bat"""
WshShell.Run cmd, 0, False
