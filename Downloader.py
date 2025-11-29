import sys
import subprocess
import os
from pathlib import Path
import zipfile
import time
import io
import winreg

REQUIRED_PACKAGES = ["requests"]

def check_and_install_dependencies():
    print("Checking dependencies...")
    missing = []
    
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Installing: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        print("Done")
    else:
        print("All dependencies installed")

check_and_install_dependencies()

import requests

CDN_BASE = "https://setup-aws.rbxcdn.com"
DEPLOY_HISTORY_URL = "https://setup.rbxcdn.com/DeployHistory.txt"

EXTRACT_ROOTS_PLAYER = {
    "RobloxApp.zip": "",
    "redist.zip": "",
    "shaders.zip": "shaders/",
    "ssl.zip": "ssl/",
    "WebView2.zip": "",
    "WebView2RuntimeInstaller.zip": "WebView2RuntimeInstaller/",
    "content-avatar.zip": "content/avatar/",
    "content-configs.zip": "content/configs/",
    "content-fonts.zip": "content/fonts/",
    "content-sky.zip": "content/sky/",
    "content-sounds.zip": "content/sounds/",
    "content-textures2.zip": "content/textures/",
    "content-models.zip": "content/models/",
    "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
    "content-platform-dictionaries.zip": "PlatformContent/pc/shared_compression_dictionaries/",
    "content-terrain.zip": "PlatformContent/pc/terrain/",
    "content-textures3.zip": "PlatformContent/pc/textures/",
    "extracontent-luapackages.zip": "ExtraContent/LuaPackages/",
    "extracontent-translations.zip": "ExtraContent/translations/",
    "extracontent-models.zip": "ExtraContent/models/",
    "extracontent-textures.zip": "ExtraContent/textures/",
    "extracontent-places.zip": "ExtraContent/places/"
}

EXTRACT_ROOTS_STUDIO = {
    "RobloxStudio.zip": "",
    "RibbonConfig.zip": "RibbonConfig/",
    "redist.zip": "",
    "Libraries.zip": "",
    "LibrariesQt5.zip": "",
    "WebView2.zip": "",
    "WebView2RuntimeInstaller.zip": "",
    "shaders.zip": "shaders/",
    "ssl.zip": "ssl/",
    "Qml.zip": "Qml/",
    "Plugins.zip": "Plugins/",
    "StudioFonts.zip": "StudioFonts/",
    "BuiltInPlugins.zip": "BuiltInPlugins/",
    "ApplicationConfig.zip": "ApplicationConfig/",
    "BuiltInStandalonePlugins.zip": "BuiltInStandalonePlugins/",
    "content-qt_translations.zip": "content/qt_translations/",
    "content-sky.zip": "content/sky/",
    "content-fonts.zip": "content/fonts/",
    "content-avatar.zip": "content/avatar/",
    "content-models.zip": "content/models/",
    "content-sounds.zip": "content/sounds/",
    "content-configs.zip": "content/configs/",
    "content-api-docs.zip": "content/api_docs/",
    "content-textures2.zip": "content/textures/",
    "content-studio_svg_textures.zip": "content/studio_svg_textures/",
    "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
    "content-platform-dictionaries.zip": "PlatformContent/pc/shared_compression_dictionaries/",
    "content-terrain.zip": "PlatformContent/pc/terrain/",
    "content-textures3.zip": "PlatformContent/pc/textures/",
    "extracontent-translations.zip": "ExtraContent/translations/",
    "extracontent-luapackages.zip": "ExtraContent/LuaPackages/",
    "extracontent-textures.zip": "ExtraContent/textures/",
    "extracontent-scripts.zip": "ExtraContent/scripts/",
    "extracontent-models.zip": "ExtraContent/models/",
    "studiocontent-models.zip": "StudioContent/models/",
    "studiocontent-textures.zip": "StudioContent/textures/"
}


def get_version_from_history(version_mode, binary_type):
    print("Getting version...")
    response = requests.get(DEPLOY_HISTORY_URL)
    response.raise_for_status()
    
    lines = response.text.strip().split("\n")
    
    target_type = "WindowsPlayer" if binary_type == "WindowsPlayer" else "Studio64"
    versions = []
    
    for line in reversed(lines[-100:]):
        if f"New {target_type}" in line and "version-" in line:
            parts = line.split("version-")
            if len(parts) > 1:
                version_hash = "version-" + parts[1].split()[0]
                if version_hash not in versions:
                    versions.append(version_hash)
                if len(versions) >= 2:
                    break
    
    if not versions:
        raise ValueError("Could not find version in deploy history")
    
    if version_mode == "1":
        version_hash = versions[0]
    elif version_mode == "2":
        version_hash = versions[1] if len(versions) > 1 else versions[0]
    else:
        return None
    
    print(f"Version: {version_hash}")
    return version_hash


def download_and_package_roblox(binary_type, version_hash, output_path):
    print("\nFetching manifest...")
    
    version_path = f"{CDN_BASE}/{version_hash}-"
    manifest_url = f"{version_path}rbxPkgManifest.txt"
    
    response = requests.get(manifest_url)
    
    if response.status_code == 403:
        print("\nError: Version not available on Roblox CDN")
        print("Only recent versions can be downloaded")
        raise ValueError("Version not available")
    
    response.raise_for_status()
    manifest_lines = [line.strip() for line in response.text.split("\n")]
    
    if manifest_lines[0] != "v0":
        raise ValueError(f"Unknown manifest version: {manifest_lines[0]}")
    
    is_player = "RobloxApp.zip" in manifest_lines
    extract_roots = EXTRACT_ROOTS_PLAYER if is_player else EXTRACT_ROOTS_STUDIO
    
    packages = [line for line in manifest_lines if line.endswith(".zip")]
    
    print(f"Found {len(packages)} packages")
    print("Downloading and packaging...")
    
    final_zip = zipfile.ZipFile(output_path, 'w', zipfile.ZIP_STORED)
    
    final_zip.writestr("AppSettings.xml", 
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Settings>\n'
        '    <ContentFolder>content</ContentFolder>\n'
        '    <BaseUrl>http://www.roblox.com</BaseUrl>\n'
        '</Settings>\n')
    
    for i, package_name in enumerate(packages, 1):
        print(f"  [{i}/{len(packages)}] {package_name}")
        
        package_url = version_path + package_name
        response = requests.get(package_url)
        response.raise_for_status()
        
        extract_root = extract_roots.get(package_name, "")
        
        package_zip = zipfile.ZipFile(io.BytesIO(response.content))
        for file_info in package_zip.filelist:
            if not file_info.filename.endswith("/"):
                file_data = package_zip.read(file_info.filename)
                fixed_path = file_info.filename.replace("\\", "/")
                final_zip.writestr(extract_root + fixed_path, file_data)
        package_zip.close()
    

    
    final_zip.close()
    print("Done")


def extract_zip(zip_path, extract_to):
    print("\nExtracting...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    print("Done")


def get_roblox_install_path(binary_type):
    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    
    if binary_type in ["WindowsPlayer", "WindowsStudio64"]:
        return local_appdata / "Roblox" / "Versions"
    else:
        return None


def kill_roblox_processes():
    print("Closing Roblox...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "RobloxPlayerBeta.exe"], 
                      capture_output=True, check=False)
        subprocess.run(["taskkill", "/F", "/IM", "RobloxStudioBeta.exe"], 
                      capture_output=True, check=False)
        subprocess.run(["taskkill", "/F", "/IM", "weblauncher.exe"], 
                      capture_output=True, check=False)
        time.sleep(2)
    except:
        pass


def delete_old_roblox(install_path):
    if not install_path or not install_path.exists():
        return
    
    kill_roblox_processes()
    
    print("Deleting old versions...")
    import shutil
    
    max_retries = 3
    for version_folder in install_path.glob("version-*"):
        if version_folder.is_dir():
            print(f"  {version_folder.name}")
            for attempt in range(max_retries):
                try:
                    shutil.rmtree(version_folder)
                    break
                except PermissionError:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        print(f"    Warning: Could not delete (files in use)")
    
    print("Done")


def register_protocol_handlers():
    print("\nRegistering protocol handlers...")
    
    roblox_path = get_roblox_install_path("WindowsPlayer")
    if not roblox_path or not roblox_path.exists():
        print("Error: No Roblox installation found")
        return False
    
    versions = list(roblox_path.glob("version-*"))
    if not versions:
        print("Error: No Roblox version found")
        return False
    
    version_path = max(versions, key=lambda p: p.stat().st_mtime)
    launcher_path = version_path / "RobloxPlayerBeta.exe"
    
    if not launcher_path.exists():
        print("Error: RobloxPlayerBeta.exe not found")
        return False
    
    try:
        for protocol in ["roblox", "roblox-player"]:
            key_path = f"Software\\Classes\\{protocol}"
            
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f"URL:{protocol} Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\shell\\open\\command") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{launcher_path}" %1')
        
        print("Done! You can now launch from Roblox.com")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def unregister_protocol_handlers():
    print("\nRemoving protocol handlers...")
    
    try:
        for protocol in ["roblox", "roblox-player"]:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{protocol}\\shell\\open\\command")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{protocol}\\shell\\open")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{protocol}\\shell")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{protocol}")
            except:
                pass
        
        print("Done!")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def launch_roblox():
    roblox_path = get_roblox_install_path("WindowsPlayer")
    if not roblox_path or not roblox_path.exists():
        print("Error: No Roblox installation found")
        return False
    
    versions = list(roblox_path.glob("version-*"))
    if not versions:
        print("Error: No Roblox version found")
        return False
    
    version_path = max(versions, key=lambda p: p.stat().st_mtime)
    launcher_path = version_path / "RobloxPlayerBeta.exe"
    
    if not launcher_path.exists():
        print("Error: RobloxPlayerBeta.exe not found")
        return False
    
    subprocess.Popen([str(launcher_path)])
    print("Launching Roblox...")
    return True


def clean_all_roblox_versions():
    print("\n" + "=" * 40)
    print("DELETE VERSIONS")
    print("=" * 40)

    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    versions_path = local_appdata / "Roblox" / "Versions"

    if not versions_path.exists():
        print("\nNo Roblox found")
        return

    version_folders = list(versions_path.glob("version-*"))

    if not version_folders:
        print("\nNo versions found")
        return

    print(f"\nFound {len(version_folders)} version(s)")
    for folder in version_folders:
        print(f"  {folder.name}")

    confirm = input("\nDelete all? (y/n): ").strip().lower()

    if confirm == "y":
        import shutil

        for folder in version_folders:
            print(f"Deleting {folder.name}")
            shutil.rmtree(folder, ignore_errors=True)
        print("\nDone")
    else:
        print("\nCancelled")


def main():
    while True:
        print("\n" + "=" * 40)
        print("ROBLOX DOWNGRADER")
        print("=" * 40)

        print("\n1. Install Roblox")
        print("2. Delete All Versions")
        print("3. Register Protocol Handlers")
        print("4. Remove Protocol Handlers")
        print("5. Launch Roblox")
        print("6. Exit")

        choice = input("\n> ").strip()

        if choice == "2":
            clean_all_roblox_versions()
            continue
        elif choice == "3":
            register_protocol_handlers()
            continue
        elif choice == "4":
            unregister_protocol_handlers()
            continue
        elif choice == "5":
            launch_roblox()
            continue
        elif choice == "6":
            return
        elif choice != "1":
            print("Invalid")
            continue
        
        break

    print("\nType:")
    print("1. Player")
    print("2. Studio")

    choice = input("\n> ").strip()
    if choice == "1":
        binary_type = "WindowsPlayer"
    elif choice == "2":
        binary_type = "WindowsStudio64"
    else:
        print("Invalid")
        return

    print("\nVersion:")
    print("1. Latest")
    print("2. Previous")
    print("3. Custom Hash")

    version_choice = input("\n> ").strip()

    if version_choice == "3":
        version_hash = input("\nVersion hash: ").strip()
        if not version_hash:
            print("Empty hash")
            return
    else:
        try:
            version_hash = get_version_from_history(version_choice, binary_type)
            if not version_hash:
                print("Failed")
                return
        except Exception as e:
            print(f"Error: {e}")
            return

    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    try:
        zip_filename = f"WEAO-{binary_type}-{version_hash}.zip"
        zip_path = downloads_dir / zip_filename
        
        download_and_package_roblox(binary_type, version_hash, zip_path)

        roblox_install_path = get_roblox_install_path(binary_type)
        
        if roblox_install_path:
            delete_old_roblox(roblox_install_path)
            
            roblox_install_path.mkdir(parents=True, exist_ok=True)
            extract_dir = roblox_install_path / version_hash
            extract_dir.mkdir(exist_ok=True)
            
            kill_roblox_processes()
            extract_zip(zip_path, extract_dir)
            
            print(f"\nInstalled to: {extract_dir.absolute()}")
            
            if input("\nRegister protocol handlers? (y/n): ").strip().lower() == "y":
                register_protocol_handlers()

        if input("\nDelete zip? (y/n): ").strip().lower() == "y":
            os.remove(zip_path)
            print("Deleted")
        
        if input("\nMain menu? (y/n): ").strip().lower() == "y":
            main()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()
