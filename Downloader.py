import sys
import subprocess
import os
from pathlib import Path
import zipfile
import time
import io
import winreg

REQUIRED_PACKAGES = ["requests", "rich", "questionary"]

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
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.prompt import Prompt
import questionary
from questionary import Style

console = Console()

custom_style = Style([
    ('qmark', 'fg:#673ab7 bold'),
    ('question', 'bold'),
    ('answer', 'fg:#f44336 bold'),
    ('pointer', 'fg:#673ab7 bold'),
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#cc5454'),
    ('separator', 'fg:#cc5454'),
    ('instruction', 'fg:#000000'),
    ('text', ''),
    ('disabled', 'fg:#858585 italic')
])

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


def parse_deploy_history(binary_type, max_versions=15):
    response = requests.get(DEPLOY_HISTORY_URL)
    response.raise_for_status()
    
    lines = response.text.strip().split("\n")
    target_type = "WindowsPlayer" if binary_type == "WindowsPlayer" else "Studio64"
    versions = []
    
    for line in reversed(lines[-200:]):
        if f"New {target_type}" in line and "version-" in line:
            try:
                parts = line.split("version-")
                if len(parts) > 1:
                    version_hash = "version-" + parts[1].split()[0]
                    
                    date_str = ""
                    if " at " in line:
                        date_part = line.split(" at ")[1].split(",")[0].strip()
                        date_str = date_part
                    
                    if version_hash not in [v["hash"] for v in versions]:
                        versions.append({
                            "hash": version_hash,
                            "date": date_str,
                            "raw_line": line
                        })
                        
                        if len(versions) >= max_versions:
                            break
            except:
                continue
    
    return versions


def get_version_from_history(version_mode, binary_type):
    console.print("[cyan]Getting version...[/cyan]")
    versions = parse_deploy_history(binary_type, max_versions=15)
    
    if not versions:
        raise ValueError("Could not find version in deploy history")
    
    if version_mode == "1":
        version_hash = versions[0]["hash"]
    elif version_mode == "2":
        version_hash = versions[2]["hash"] if len(versions) > 2 else versions[-1]["hash"]
    else:
        return None
    
    console.print(f"[green]Version: {version_hash}[/green]")
    return version_hash


def show_version_list_and_select(binary_type):
    console.print("\n[cyan]Fetching version history...[/cyan]")
    versions = parse_deploy_history(binary_type, max_versions=15)
    
    if not versions:
        console.print("[red]No versions found[/red]")
        return None
    
    choices = []
    for version in versions:
        date_str = version["date"] if version["date"] else "Unknown date"
        choice_text = f"{version['hash']} - {date_str}"
        choices.append({
            "name": choice_text,
            "value": version["hash"]
        })
    
    choices.append({"name": "Cancel", "value": None})
    
    selected = questionary.select(
        "Select a version",
        choices=choices,
        style=custom_style,
        use_shortcuts=False,
        use_arrow_keys=True,
        qmark=">"
    ).ask()
    
    if selected:
        console.print(f"\n[green]Selected: {selected}[/green]")
    
    return selected


def download_and_package_roblox(binary_type, version_hash, output_path):
    console.print("\n[cyan]Fetching manifest...[/cyan]")
    
    version_path = f"{CDN_BASE}/{version_hash}-"
    manifest_url = f"{version_path}rbxPkgManifest.txt"
    
    response = requests.get(manifest_url)
    
    if response.status_code == 403:
        console.print("[red]Error: Version not available on Roblox CDN[/red]")
        console.print("[yellow]Only recent versions can be downloaded[/yellow]")
        raise ValueError("Version not available")
    
    response.raise_for_status()
    manifest_lines = [line.strip() for line in response.text.split("\n")]
    
    if manifest_lines[0] != "v0":
        raise ValueError(f"Unknown manifest version: {manifest_lines[0]}")
    
    is_player = "RobloxApp.zip" in manifest_lines
    extract_roots = EXTRACT_ROOTS_PLAYER if is_player else EXTRACT_ROOTS_STUDIO
    
    packages = [line for line in manifest_lines if line.endswith(".zip")]
    
    console.print(f"[green]Found {len(packages)} packages[/green]\n")
    
    final_zip = zipfile.ZipFile(output_path, 'w', zipfile.ZIP_STORED)
    
    final_zip.writestr("AppSettings.xml", 
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Settings>\n'
        '    <ContentFolder>content</ContentFolder>\n'
        '    <BaseUrl>http://www.roblox.com</BaseUrl>\n'
        '</Settings>\n')
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Downloading packages...", total=len(packages))
        
        for package_name in packages:
            progress.update(task, description=f"[cyan]{package_name}")
            
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
            
            progress.advance(task)
    
    final_zip.close()
    console.print("[green]Done![/green]")


def extract_zip(zip_path, extract_to):
    console.print("\n[cyan]Extracting...[/cyan]")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        members = zip_ref.namelist()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Extracting files...", total=len(members))
            
            for member in members:
                zip_ref.extract(member, extract_to)
                progress.advance(task)
    
    console.print("[green]Done![/green]")


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
    console.print("\n[cyan]Launching Roblox Player...[/cyan]")
    
    roblox_path = get_roblox_install_path("WindowsPlayer")
    if not roblox_path or not roblox_path.exists():
        console.print("[red]Error: No Roblox Player installation found[/red]")
        input("\nPress Enter to continue...")
        return False
    
    versions = list(roblox_path.glob("version-*"))
    if not versions:
        console.print("[red]Error: No Roblox Player version found[/red]")
        input("\nPress Enter to continue...")
        return False
    
    version_path = max(versions, key=lambda p: p.stat().st_mtime)
    launcher_path = version_path / "RobloxPlayerBeta.exe"
    
    if not launcher_path.exists():
        console.print("[red]Error: RobloxPlayerBeta.exe not found[/red]")
        console.print(f"[yellow]Looked in: {version_path}[/yellow]")
        input("\nPress Enter to continue...")
        return False
    
    try:
        subprocess.Popen([str(launcher_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        console.print(f"[green]Launched from: {version_path.name}[/green]")
        time.sleep(1)
        return True
    except Exception as e:
        console.print(f"[red]Error launching: {e}[/red]")
        input("\nPress Enter to continue...")
        return False


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
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]ROBLOX DOWNGRADER[/bold cyan]\n[dim]Created by kirsh/isaac[/dim]",
            border_style="cyan"
        ))

        action = questionary.select(
            "",
            choices=[
                {"name": "Install Roblox", "value": "install"},
                {"name": "Launch Roblox", "value": "launch"},
                {"name": "Register Protocol Handlers", "value": "register"},
                {"name": "Remove Protocol Handlers", "value": "unregister"},
                {"name": "Delete All Versions", "value": "delete"},
                {"name": "Exit", "value": "exit"}
            ],
            style=custom_style,
            use_shortcuts=False,
            use_arrow_keys=True,
            qmark=">"
        ).ask()

        if action == "delete":
            if questionary.confirm("Delete all Roblox versions?", default=False, style=custom_style).ask():
                clean_all_roblox_versions()
            input("\nPress Enter to continue...")
            continue
        elif action == "register":
            register_protocol_handlers()
            input("\nPress Enter to continue...")
            continue
        elif action == "unregister":
            unregister_protocol_handlers()
            input("\nPress Enter to continue...")
            continue
        elif action == "launch":
            launch_roblox()
            input("\nPress Enter to continue...")
            continue
        elif action == "exit":
            console.print("\n[cyan]Goodbye![/cyan]")
            return
        elif action != "install":
            continue
        
        break

    binary_choice = questionary.select(
        "Select installation type",
        choices=[
            {"name": "Player", "value": "player"},
            {"name": "Studio", "value": "studio"},
            {"name": "Both (Player + Studio)", "value": "both"}
        ],
        style=custom_style,
        use_shortcuts=False,
        use_arrow_keys=True,
        qmark=">"
    ).ask()
    
    if binary_choice == "both":
        binary_types = ["WindowsPlayer", "WindowsStudio64"]
    elif binary_choice == "player":
        binary_types = ["WindowsPlayer"]
    else:
        binary_types = ["WindowsStudio64"]

    version_choice = questionary.select(
        "Select version",
        choices=[
            {"name": "Latest", "value": "latest"},
            {"name": "Downgrade (3 versions back)", "value": "downgrade"},
            {"name": "Browse Last 15 Versions", "value": "list"},
            {"name": "Custom Hash", "value": "custom"}
        ],
        style=custom_style,
        use_shortcuts=False,
        use_arrow_keys=True,
        qmark=">"
    ).ask()

    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    for binary_type in binary_types:
        if len(binary_types) > 1:
            type_name = "Player" if binary_type == "WindowsPlayer" else "Studio"
            console.print(f"\n[bold cyan]Installing {type_name}...[/bold cyan]")
        
        if version_choice == "list":
            version_hash = show_version_list_and_select(binary_type)
            if not version_hash:
                console.print("[yellow]Cancelled[/yellow]")
                continue
        elif version_choice == "custom":
            version_hash = questionary.text(
                f"Enter version hash for {binary_type}:",
                style=custom_style
            ).ask()
            if not version_hash:
                console.print("[red]Empty hash[/red]")
                continue
        else:
            try:
                mode = "1" if version_choice == "latest" else "2"
                version_hash = get_version_from_history(mode, binary_type)
                if not version_hash:
                    console.print("[red]Failed[/red]")
                    continue
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                continue

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
                
                console.print(f"\n[green]Installed to: {extract_dir.absolute()}[/green]")
                
                if binary_type == "WindowsPlayer":
                    register_protocol_handlers()
                
                os.remove(zip_path)
                console.print("[green]Zip deleted[/green]\n")

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            time.sleep(2)


if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            break
