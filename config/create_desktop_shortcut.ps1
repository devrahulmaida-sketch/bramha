$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('C:\Users\ravit\OneDrive\Desktop\Rahul AI - Premium.lnk')
$Shortcut.TargetPath = 'D:\TiTech Prabha Solution\Rahul AI\Rahul AI\Rahul-AI---Lite-main\Rahul-AI---Lite-main\.venv\Scripts\pythonw.exe'
$Shortcut.Arguments = '"D:\TiTech Prabha Solution\Rahul AI\Rahul AI\Rahul-AI---Lite-main\Rahul-AI---Lite-main\main.py"'
$Shortcut.WorkingDirectory = 'D:\TiTech Prabha Solution\Rahul AI\Rahul AI\Rahul-AI---Lite-main\Rahul-AI---Lite-main'
$Shortcut.WindowStyle = 7
$Shortcut.Description = 'Launch Rahul AI - Premium'
if ('D:\TiTech Prabha Solution\Rahul AI\Rahul AI\Rahul-AI---Lite-main\Rahul-AI---Lite-main\assets\Rahul_AI_Logo.ico') { $Shortcut.IconLocation = 'D:\TiTech Prabha Solution\Rahul AI\Rahul AI\Rahul-AI---Lite-main\Rahul-AI---Lite-main\assets\Rahul_AI_Logo.ico,0' }
$Shortcut.Save()