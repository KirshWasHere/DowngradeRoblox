import sys
import subprocess
import os
from pathlib import Path
import zipfile
import time
import io
import winreg
from datetime import datetime

REQUIRED_PACKAGES = ["requests", "rich"]

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
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import print as rprint

console = Console()

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


def get_version_history(binary_type, limit=15):
    console.print("[cyan]Getting version history...[/cyan]")
    response = requests.get(DEPLOY_HISTORY_URL)
    response.raise_for_status()
    
    lines = response.text.strip().split("\n")
    
    target_type = "WindowsPlayer" if binary_type == "WindowsPlayer" else "Studio64"
    versions = []
    seen_hashes = set()
    
    for line in reversed(lines):
        if f"New {target_type}" in line and "version-" in line:
            parts = line.split("version-")
            if len(parts) > 1:
                version_hash = "version-" + parts[1].split()[0]
                if version_hash not in seen_hashes:
                    # Extract date and time from the start of the line
                    # Find the date string, which is between " at " and the first comma
                    try:
                        start_index = line.index(" at ") + 4
                        end_index = line.index(",", start_index)
                        date_time_str = line[start_index:end_index].strip()

                        # Parse the original format and reformat to MM/DD/YYYY HH:MM:SS AM/PM
                        dt_object = datetime.strptime(date_time_str, "%m/%d/%Y %I:%M:%S %p")
                        formatted_date_time = dt_object.strftime("%m/%d/%Y %I:%M:%S %p")
                    except ValueError:
                        # Fallback if parsing fails for any reason
                        formatted_date_time = "Date N/A"

                    versions.append((version_hash, formatted_date_time))
                    seen_hashes.add(version_hash)
                if len(versions) >= limit:
                    break
    
    if not versions:
        raise ValueError("Could not find any versions in deploy history")
    
    console.print(f"[green]Found {len(versions)} versions[/green]")
    return versions





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
            "[bold cyan]ROBLOX DOWNGRADER[/bold cyan]",
            border_style="cyan"
        ))

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="cyan", justify="right")
        table.add_column(style="white")
        
        table.add_row("1", "Install Roblox")
        table.add_row("2", "Delete All Versions")
        table.add_row("3", "Register Protocol Handlers")
        table.add_row("4", "Remove Protocol Handlers")
        table.add_row("5", "Launch Roblox")
        table.add_row("6", "Exit")
        
        console.print(table)
        choice = Prompt.ask("\n[cyan]Choice[/cyan]", choices=["1", "2", "3", "4", "5", "6"])

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

    console.print("\n[cyan]Type:[/cyan]")
    console.print("  1. Player")
    console.print("  2. Studio")
    console.print("  3. Both")

    choice = Prompt.ask("\n[cyan]Choice[/cyan]", choices=["1", "2", "3"])
    
    if choice == "3":
        binary_types = ["WindowsPlayer", "WindowsStudio64"]
    else:
        binary_types = ["WindowsPlayer" if choice == "1" else "WindowsStudio64"]

    console.print("\n[cyan]Version:[/cyan]")
    console.print("  1. Latest")
    console.print("  2. Downgrade (3 versions back)")
    console.print("  3. Select from a list of recent versions")
    console.print("  4. Enter a custom hash")

    version_choice = Prompt.ask("\n[cyan]Choice[/cyan]", choices=["1", "2", "3", "4"])

    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    for binary_type in binary_types:
        if len(binary_types) > 1:
            type_name = "Player" if binary_type == "WindowsPlayer" else "Studio"
            console.print(f"\n[bold cyan]Installing {type_name}...[/bold cyan]")
        
        version_hash = None
        try:
            if version_choice == "4":
                version_hash = Prompt.ask(f"\n[cyan]Version hash for {binary_type}[/cyan]")
                if not version_hash:
                    console.print("[red]Empty hash[/red]")
                    continue
            else:
                versions = get_version_history(binary_type)
                if not versions:
                    console.print("[red]Failed to get version history.[/red]")
                    continue

                if version_choice == "1":
                    version_hash = versions[0][0] # Get the hash from the tuple
                    console.print(f"[green]Selected Latest: {version_hash}[/green]")
                elif version_choice == "2":
                    if len(versions) < 3:
                        console.print("[red]Not enough versions available to downgrade 3 versions back.[/red]")
                        console.print(f"[yellow]Found only {len(versions)} version(s). Try selecting from the list.[/yellow]")
                        continue
                    version_hash = versions[2][0] # Get the hash from the tuple
                    console.print(f"[green]Selected Downgrade: {version_hash}[/green]")
                elif version_choice == "3":
                    version_table = Table(title="Recent Roblox Versions", box=None, padding=(0, 2))
                    version_table.add_column("Index", style="cyan", justify="right")
                    version_table.add_column("Version Hash", style="white")
                    version_table.add_column("Release Date", style="magenta")

                    for i, (v_hash, v_date) in enumerate(versions):
                        version_table.add_row(str(i + 1), v_hash, v_date)
                    
                    console.print(version_table)
                    
                    selection = Prompt.ask(
                        f"\n[cyan]Select a version (1-{len(versions)})[/cyan]", 
                        choices=[str(i) for i in range(1, len(versions) + 1)]
                    )
                    version_hash = versions[int(selection) - 1][0] # Get the hash from the tuple
                    console.print(f"[green]Selected: {version_hash}[/green]")

        except Exception as e:
            console.print(f"[red]Error during version selection: {e}[/red]")
            continue
        
        if not version_hash:
            console.print("[red]Could not determine a version to install.[/red]")
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
