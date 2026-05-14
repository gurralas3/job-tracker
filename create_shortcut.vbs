Set WshShell = CreateObject("WScript.Shell")
Set shortcut = WshShell.CreateShortcut(WshShell.SpecialFolders("Desktop") & "\Job Tracker.lnk")
shortcut.TargetPath = "C:\Users\saite\AppData\Local\Programs\Python\Python313\pythonw.exe"
shortcut.Arguments = """C:\Users\saite\job-tracker\JobTracker.pyw"""
shortcut.WorkingDirectory = "C:\Users\saite\job-tracker"
shortcut.WindowStyle = 1
shortcut.Description = "Job Application Tracker"
shortcut.Save
WScript.Echo "Shortcut created on Desktop!"
