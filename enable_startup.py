import os
import subprocess
import sys

def add_to_startup():
    # 1. Target your newly renamed executable directly!
    exe_name = "Start_BlackBox_Pc.exe"
    project_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(project_dir, exe_name)
    
    if not os.path.exists(exe_path):
        print(f"❌ Error: Could not find '{exe_name}' in this folder.")
        print("Please make sure this script is running in the same folder as your renamed executable.")
        return

    # 2. Locate the system's hidden Windows Startup folder
    appdata_dir = os.environ.get("APPDATA")
    startup_folder = os.path.join(appdata_dir, r"Microsoft\Windows\Start Menu\Programs\Startup")
    shortcut_path = os.path.join(startup_folder, "BlackBox_AutoLaunch.lnk")

    # 3. Use PowerShell to build a flawless Windows Shortcut pointing straight to the EXE
    ps_command = (
        f'$WshShell = New-Object -ComObject WScript.Shell; '
        f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); '
        f'$Shortcut.TargetPath = "{exe_path}"; '
        f'$Shortcut.WorkingDirectory = "{project_dir}"; '
        f'$Shortcut.Save()'
    )

    try:
        print("🔄 Connecting to Windows Startup systems...")
        result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("\n🎉 SUCCESS! BlackBox PC is now set to auto-boot.")
            print(f"▶️  '{exe_name}' will run completely invisibly whenever you turn on your PC.")
            print(f"📍 Shortcut dropped in: {shortcut_path}")
        else:
            print(f"❌ PowerShell Error: {result.stderr}")
    except Exception as e:
        print(f"❌ Failed to create startup shortcut: {e}")

if __name__ == "__main__":
    add_to_startup()