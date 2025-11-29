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
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

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

    print("Getting version...")
    response = requests.get(api_url)
    response.raise_for_status()
    data = response.json()

    if binary_type in ["WindowsPlayer", "WindowsStudio64"]:
        version_hash = data.get("Windows")
    elif binary_type in ["MacPlayer", "MacStudio"]:
        version_hash = data.get("Mac")
    else:
        raise ValueError(f"Unknown binary type: {binary_type}")

    print(f"Version: {version_hash}")
    return version_hash


def detect_browser():
    browsers = []
    
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        driver.quit()
        browsers.append("chrome")
    except:
        pass
    
    try:
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service)
        driver.quit()
        browsers.append("edge")
    except:
        pass
    
    try:
        service = FirefoxService(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service)
        driver.quit()
        browsers.append("firefox")
    except:
        pass
    
    return browsers


def setup_driver(download_dir, browser="chrome"):
    if browser == "chrome":
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
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    
    elif browser == "edge":
        options = webdriver.EdgeOptions()
        prefs = {
            "download.default_directory": str(download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_experimental_option("prefs", prefs)
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        service = EdgeService(EdgeChromiumDriverManager().install())
        return webdriver.Edge(service=service, options=options)
    
    elif browser == "firefox":
        options = webdriver.FirefoxOptions()
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", str(download_dir.absolute()))
        options.set_preference("browser.download.useDownloadDir", True)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip")
        service = FirefoxService(GeckoDriverManager().install())
        return webdriver.Firefox(service=service, options=options)
    
    else:
        raise ValueError(f"Unsupported browser: {browser}")


def download_with_selenium(binary_type, version_hash, include_launcher, download_dir, browser="chrome"):
    print("\nStarting browser...")

    driver = setup_driver(download_dir, browser)

    try:
        print("Opening site...")
        driver.get(SITE_URL)

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "downloadForm")))

        binary_select = Select(driver.find_element(By.ID, "binaryType"))
        binary_select.select_by_value(binary_type)

        version_input = driver.find_element(By.ID, "version")
        version_input.clear()
        version_input.send_keys(version_hash)

        launcher_checkbox = driver.find_element(By.ID, "includeLauncher")
        if include_launcher and not launcher_checkbox.is_selected():
            launcher_checkbox.click()
        elif not include_launcher and launcher_checkbox.is_selected():
            launcher_checkbox.click()

        download_button = driver.find_element(
            By.XPATH, "//button[contains(text(), 'Download Specified Hash')]"
        )
        print("Downloading...")
        
        for old_file in download_dir.glob("WEAO-*.zip"):
            old_file.unlink()
        
        download_button.click()

        max_start_wait = 30
        started = False
        for i in range(max_start_wait):
            if list(download_dir.glob("*.crdownload")) or list(download_dir.glob("WEAO-*.zip")):
                started = True
                break
            time.sleep(1)
        
        if not started:
            raise TimeoutError("Download failed to start")

        max_wait = 900
        elapsed = 0
        last_size = 0
        
        while elapsed < max_wait:
            crdownload_files = list(download_dir.glob("*.crdownload"))
            
            if crdownload_files:
                current_size = crdownload_files[0].stat().st_size
                if current_size != last_size:
                    print(f"  {current_size / (1024*1024):.0f} MB")
                    last_size = current_size
            else:
                files = list(download_dir.glob("WEAO-*.zip"))
                if files and files[0].stat().st_size > 1000:
                    print(f"\nDone: {files[0].name}")
                    time.sleep(2)
                    return files[0]

            time.sleep(3)
            elapsed += 3

        raise TimeoutError("Download timeout")

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
        return
    
    print("\nDeleting old versions...")
    import shutil
    
    for version_folder in install_path.glob("version-*"):
        if version_folder.is_dir():
            print(f"  {version_folder.name}")
            shutil.rmtree(version_folder, ignore_errors=True)
    
    print("Done")


def extract_zip(zip_path, extract_to):
    print("\nExtracting...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    print("Done")


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
        print("3. Exit")

        choice = input("\n> ").strip()

        if choice == "2":
            clean_all_roblox_versions()
            continue
        elif choice == "3":
            return
        elif choice != "1":
            print("Invalid")
            continue
        
        break
    
    print("\nFinding browsers...")
    browsers = detect_browser()
    
    if not browsers:
        print("No browser found. Install Chrome, Edge, or Firefox.")
        return
    
    if len(browsers) == 1:
        browser = browsers[0]
        print(f"Using {browser}")
    else:
        print("\nBrowser:")
        for i, b in enumerate(browsers, 1):
            print(f"{i}. {b.capitalize()}")
        
        choice = input("\n> ").strip()
        try:
            browser = browsers[int(choice) - 1]
        except:
            print("Invalid")
            return

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
    print("3. Custom")

    version_choice = input("\n> ").strip()

    if version_choice == "3":
        version_hash = input("\nVersion hash: ").strip()
        if not version_hash:
            print("Empty hash")
            return
    else:
        try:
            version_hash = get_version_hash(version_choice, binary_type)
            if not version_hash:
                print("Failed")
                return
        except Exception as e:
            print(f"Error: {e}")
            return

    include_launcher = True

    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    try:
        zip_path = download_with_selenium(
            binary_type, version_hash, include_launcher, downloads_dir, browser
        )

        roblox_install_path = get_roblox_install_path(binary_type)
        
        if roblox_install_path and binary_type in ["WindowsPlayer", "WindowsStudio64"]:
            delete_old_roblox(roblox_install_path)
            
            roblox_install_path.mkdir(parents=True, exist_ok=True)
            extract_dir = roblox_install_path / version_hash
            extract_dir.mkdir(exist_ok=True)
            extract_zip(zip_path, extract_dir)
            
            print(f"\nInstalled to: {extract_dir.absolute()}")
            
            launcher_path = extract_dir / "weblauncher.exe"
            if launcher_path.exists():
                print("\nLaunching...")
                import subprocess
                
                process = subprocess.Popen([str(launcher_path)], cwd=str(extract_dir))
                print("Setup...")
                process.wait()
                
                print("Opening launcher...")
                subprocess.Popen([str(launcher_path)], cwd=str(extract_dir))
                print("Done")
            else:
                print("\nLauncher not found")
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

        if input("\nDelete zip? (y/n): ").strip().lower() == "y":
            os.remove(zip_path)
            print("Deleted")
        
        if input("\nMain menu? (y/n): ").strip().lower() == "y":
            main()

    except Exception as e:
        print(f"\nError: {e}")
        return


if __name__ == "__main__":
    main()
