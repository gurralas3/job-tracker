Set WshShell = CreateObject("WScript.Shell")

' Start Flask server silently
WshShell.Run "cmd /c cd /d C:\Users\saite\job-tracker && C:\Users\saite\AppData\Local\Programs\Python\Python313\python.exe app.py", 0, False

' Wait 2 seconds for server to start
WScript.Sleep 2000

' Open Chrome as standalone app window (no browser UI)
Dim chromePath
chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
If Not CreateObject("Scripting.FileSystemObject").FileExists(chromePath) Then
    chromePath = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
End If

WshShell.Run """" & chromePath & """ --app=http://localhost:5000 --window-size=1400,900", 1, False
