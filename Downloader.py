import sys
import subprocess
import os
from pathlib import Path

REQUIRED_PACKAGES = [
    "requests",
    "selenium",
    "webdriver-manager"
]

def check_and_install_dependencies():
    print("Checking dependencies...")
    missing = []
    
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        print("Dependencies installed successfully!")
    else:
        print("All dependencies are installed.")

check_and_install_dependencies()

import requests
import zipfile
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

API_BASE = "https://weao.gg/api/versions"
SITE_URL = "https://rdd.weao.gg/"

BINARY_TYPES = {
    "1": "WindowsPlayer",
    "2": "WindowsStudio64",
    "3": "MacPlayer",
    "4": "MacStudio"
}


def get_version_hash(version_mode, binary_type):
    if version_mode == "1":
        api_url = f"{API_BASE}/current"
    elif version_mode == "2":
        api_url = f"{API_BASE}/past"
    else:
        return None

    print(f"Fetching version info from API...")
    response = requests.get(api_url)
    response.raise_for_status()
    data = response.json()

    if binary_type in ["WindowsPlayer", "WindowsStudio64"]:
        version_hash = data.get("Windows")
    elif binary_type in ["MacPlayer", "MacStudio"]:
        version_hash = data.get("Mac")
    else:
        raise ValueError(f"Unknown binary type: {binary_type}")

    print(f"Version hash: {version_hash}")
    return version_hash


def setup_driver(download_dir):
    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": str(download_dir.absolute()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def download_with_selenium(binary_type, version_hash, include_launcher, download_dir):
    print("\nInitializing browser automation...")

    driver = setup_driver(download_dir)

    try:
        print(f"Opening {SITE_URL}")
        driver.get(SITE_URL)

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "downloadForm")))

        binary_select = Select(driver.find_element(By.ID, "binaryType"))
        binary_select.select_by_value(binary_type)
        print(f"Selected binary type: {binary_type}")

        version_input = driver.find_element(By.ID, "version")
        version_input.clear()
        version_input.send_keys(version_hash)
        print(f"Entered version hash: {version_hash}")

        launcher_checkbox = driver.find_element(By.ID, "includeLauncher")
        if include_launcher and not launcher_checkbox.is_selected():
            launcher_checkbox.click()
        elif not include_launcher and launcher_checkbox.is_selected():
            launcher_checkbox.click()
        print(f"Launcher: {'Enabled' if include_launcher else 'Disabled'}")

        download_button = driver.find_element(
            By.XPATH, "//button[contains(text(), 'Download Specified Hash')]"
        )
        print("\nStarting download...")
        
        for old_file in download_dir.glob("WEAO-*.zip"):
            old_file.unlink()
        
        download_button.click()

        print("Waiting for download to start...")
        max_start_wait = 30
        started = False
        for i in range(max_start_wait):
            if list(download_dir.glob("*.crdownload")) or list(download_dir.glob("WEAO-*.zip")):
                started = True
                print("Download started!")
                break
            time.sleep(1)
        
        if not started:
            raise TimeoutError("Download did not start within 30 seconds")

        print("Waiting for download to complete (this may take several minutes)...")
        max_wait = 900
        elapsed = 0
        last_size = 0
        
        while elapsed < max_wait:
            crdownload_files = list(download_dir.glob("*.crdownload"))
            
            if crdownload_files:
                current_size = crdownload_files[0].stat().st_size
                if current_size != last_size:
                    print(f"  Downloading... {current_size / (1024*1024):.1f} MB ({elapsed}s elapsed)")
                    last_size = current_size
            else:
                files = list(download_dir.glob("WEAO-*.zip"))
                if files and files[0].stat().st_size > 1000:
                    print(f"\nDownload complete: {files[0].name}")
                    time.sleep(2)
                    return files[0]

            time.sleep(3)
            elapsed += 3

        raise TimeoutError("Download timed out after 15 minutes")

    finally:
        driver.quit()


def get_roblox_install_path(binary_type):
    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    
    if binary_type == "WindowsPlayer":
        return local_appdata / "Roblox" / "Versions"
    elif binary_type == "WindowsStudio64":
        return local_appdata / "Roblox" / "Versions"
    else:
        return None


def delete_old_roblox(install_path):
    if not install_path or not install_path.exists():
        print(f"No existing installation found at: {install_path}")
        return
    
    print(f"\nDeleting old Roblox installation at: {install_path}")
    import shutil
    
    for version_folder in install_path.glob("version-*"):
        if version_folder.is_dir():
            print(f"  Deleting: {version_folder.name}")
            shutil.rmtree(version_folder, ignore_errors=True)
    
    print("Old installation deleted!")


def extract_zip(zip_path, extract_to):
    print(f"\nExtracting to: {extract_to}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    print("Extraction complete!")


def clean_all_roblox_versions():
    print("\n" + "=" * 50)
    print("CLEAN ALL ROBLOX VERSIONS")
    print("=" * 50)

    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    versions_path = local_appdata / "Roblox" / "Versions"

    if not versions_path.exists():
        print("\nNo Roblox installation found!")
        return

    version_folders = list(versions_path.glob("version-*"))

    if not version_folders:
        print("\nNo version folders found!")
        return

    print(f"\nFound {len(version_folders)} version(s):")
    for folder in version_folders:
        print(f"  - {folder.name}")

    confirm = input("\nDelete ALL versions? (y/n): ").strip().lower()

    if confirm == "y":
        import shutil

        for folder in version_folders:
            print(f"Deleting: {folder.name}")
            shutil.rmtree(folder, ignore_errors=True)
        print("\nAll versions deleted!")
    else:
        print("\nCancelled")


def main():
    while True:
        print("\n" + "=" * 50)
        print("ROBLOX AUTO DOWNGRADER - WEAO RDD")
        print("=" * 50)

        print("\nMain Menu:")
        print("  1. Download & Install Roblox")
        print("  2. Clean All Roblox Versions")
        print("  3. Exit")

        menu_choice = input("\nEnter choice (1-3): ").strip()

        if menu_choice == "2":
            clean_all_roblox_versions()
            continue
        elif menu_choice == "3":
            print("Goodbye!")
            return
        elif menu_choice != "1":
            print("Invalid choice!")
            continue
        
        break

    print("\nSelect Binary Type:")
    for key, value in BINARY_TYPES.items():
        print(f"  {key}. {value}")

    binary_choice = input("\nEnter choice (1-4): ").strip()
    if binary_choice not in BINARY_TYPES:
        print("Invalid choice!")
        return

    binary_type = BINARY_TYPES[binary_choice]

    print("\nSelect Version:")
    print("  1. Latest Version")
    print("  2. Previous Version (Downgrade)")
    print("  3. Specific Version Hash")

    version_choice = input("\nEnter choice (1-3): ").strip()

    if version_choice == "3":
        version_hash = input("Enter version hash: ").strip()
        if not version_hash:
            print("Version hash cannot be empty!")
            return
    else:
        try:
            version_hash = get_version_hash(version_choice, binary_type)
            if not version_hash:
                print("Failed to get version hash!")
                return
        except Exception as e:
            print(f"Error fetching version: {e}")
            return

    include_launcher = input("\nInclude WEAO Launcher? (y/n): ").strip().lower() == "y"

    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    try:
        zip_path = download_with_selenium(
            binary_type, version_hash, include_launcher, downloads_dir
        )

        roblox_install_path = get_roblox_install_path(binary_type)
        
        if roblox_install_path and binary_type in ["WindowsPlayer", "WindowsStudio64"]:
            install_to_roblox = input("\nInstall to Roblox directory? (y/n): ").strip().lower() == "y"
            
            if install_to_roblox:
                delete_old_roblox(roblox_install_path)
                
                roblox_install_path.mkdir(parents=True, exist_ok=True)
                extract_dir = roblox_install_path / version_hash
                extract_dir.mkdir(exist_ok=True)
                extract_zip(zip_path, extract_dir)
                
                print(f"\nSuccess! Roblox installed to: {extract_dir.absolute()}")
                
                if include_launcher:
                    launcher_path = extract_dir / "weblauncher.exe"
                    if launcher_path.exists():
                        print("\nLaunching WEAO Launcher (first time setup)...")
                        import subprocess
                        
                        process = subprocess.Popen([str(launcher_path)], cwd=str(extract_dir))
                        print("Waiting for setup to complete...")
                        process.wait()
                        
                        print("Relaunching WEAO Launcher...")
                        subprocess.Popen([str(launcher_path)], cwd=str(extract_dir))
                        print("WEAO Launcher opened!")
                    else:
                        print("\nWEAO Launcher not found in installation")
            else:
                version_label = (
                    "latest"
                    if version_choice == "1"
                    else "previous" if version_choice == "2" else version_hash
                )
                extract_dir = downloads_dir / f"{binary_type}_{version_label}"
                extract_dir.mkdir(exist_ok=True)
                extract_zip(zip_path, extract_dir)
                
                print(f"\nSuccess! Files extracted to: {extract_dir.absolute()}")
        else:
            version_label = (
                "latest"
                if version_choice == "1"
                else "previous" if version_choice == "2" else version_hash
            )
            extract_dir = downloads_dir / f"{binary_type}_{version_label}"
            extract_dir.mkdir(exist_ok=True)
            extract_zip(zip_path, extract_dir)
            
            print(f"\nSuccess! Files extracted to: {extract_dir.absolute()}")

        if input("\nDelete zip file? (y/n): ").strip().lower() == "y":
            os.remove(zip_path)
            print("Zip file deleted.")
        
        if input("\nReturn to main menu? (y/n): ").strip().lower() == "y":
            main()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return


if __name__ == "__main__":
    main()
