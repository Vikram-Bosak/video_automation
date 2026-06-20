import os
import json
import time
import argparse
import logging
import subprocess
from playwright.sync_api import sync_playwright
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("automation.log", encoding="utf-8")
    ]
)

DEFAULT_CONFIG = {
    "google_vids_url": "https://docs.google.com/videos/d/1cPx11a5TSjrCAB9P1CHFaJQ7T2qihHxeJm1W8Y4vHJU/edit",
    "sheet_id": "",
    "sheet_range": "Sheet1!A2:A4",
    "drive_folder_id": "",
    "cookies_path": "cookies.json",
    "service_account_path": "service_account.json",
    "download_dir": "downloads",
    "output_filename": "final_merged_video.mp4",
    "timeouts": {
        "page_load_ms": 60000,
        "video_generation_sec": 60,
        "download_wait_sec": 30
    }
}

def load_config():
    """Loads configuration from environment variables, config.json, or defaults."""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
            logging.info("Configuration loaded from config.json")
        except Exception as e:
            logging.warning(f"Could not parse config.json, using defaults: {e}")
    
    # Override with environment variables if present
    for key in ["google_vids_url", "sheet_id", "sheet_range", "drive_folder_id", "cookies_path", "service_account_path", "download_dir", "output_filename"]:
        env_val = os.environ.get(key.upper())
        if env_val:
            config[key] = env_val
            
    return config

def get_google_credentials(config):
    """Retrieves Google API credentials from Environment Variable or Service Account file."""
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_info:
        try:
            info = json.loads(service_account_info)
            logging.info("Google credentials loaded from environment variable")
            return service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly", "https://www.googleapis.com/auth/drive.file"]
            )
        except Exception as e:
            logging.error(f"Error parsing GOOGLE_SERVICE_ACCOUNT_JSON env var: {e}")
            
    sa_path = config["service_account_path"]
    if os.path.exists(sa_path):
        try:
            logging.info(f"Google credentials loaded from file: {sa_path}")
            return service_account.Credentials.from_service_account_file(
                sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly", "https://www.googleapis.com/auth/drive.file"]
            )
        except Exception as e:
            logging.error(f"Error loading credentials from file {sa_path}: {e}")
            
    logging.warning("No valid Google service account credentials found. Using local fallback.")
    return None

def fetch_prompts_from_sheet(config, credentials):
    """Fetches prompts from Google Sheets using Sheets API."""
    sheet_id = config["sheet_id"]
    sheet_range = config["sheet_range"]
    
    if not sheet_id or not credentials:
        logging.warning("Sheet ID or credentials missing. Falling back to local prompts.csv or defaults.")
        if os.path.exists("prompts.csv"):
            try:
                import pandas as pd
                df = pd.read_csv("prompts.csv")
                if "Prompt" in df.columns:
                    return df["Prompt"].dropna().tolist()[:3]
            except Exception as e:
                logging.error(f"Error reading local prompts.csv fallback: {e}")
        return ["Sample prompt 1", "Sample prompt 2", "Sample prompt 3"]
        
    try:
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_range).execute()
        rows = result.get("values", [])
        prompts = [row[0] for row in rows if row]
        logging.info(f"Successfully fetched {len(prompts)} prompts from Google Sheets")
        return prompts[:3] # We only need up to 3 prompts
    except Exception as e:
        logging.error(f"Error fetching from Google Sheets API: {e}")
        return []

def upload_to_google_drive(file_path, config, credentials):
    """Uploads the final merged video to Google Drive."""
    folder_id = config["drive_folder_id"]
    if not credentials:
        logging.error("Cannot upload to Google Drive: credentials are not set up.")
        return False
        
    try:
        service = build("drive", "v3", credentials=credentials)
        file_metadata = {
            "name": os.path.basename(file_path),
            "mimeType": "video/mp4"
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]
            
        media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True)
        logging.info(f"Uploading {file_path} to Google Drive folder '{folder_id}'...")
        file = service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()
        logging.info(f"Upload complete! File ID: {file.get('id')} | View Link: {file.get('webViewLink')}")
        return True
    except Exception as e:
        logging.error(f"Error uploading to Google Drive: {e}")
        return False

def generate_videos_playwright(prompts, config):
    """Automates video generation in browser using Playwright."""
    download_paths = []
    download_dir = config["download_dir"]
    os.makedirs(download_dir, exist_ok=True)
    
    cookies_data = None
    cookies_env = os.environ.get("GOOGLE_COOKIES_JSON")
    if cookies_env:
        try:
            cookies_data = json.loads(cookies_env)
            logging.info("Cookies loaded from environment variable")
        except Exception as e:
            logging.error(f"Error parsing GOOGLE_COOKIES_JSON env var: {e}")
            
    if not cookies_data and os.path.exists(config["cookies_path"]):
        try:
            with open(config["cookies_path"], "r", encoding="utf-8") as f:
                cookies_data = json.load(f)
                logging.info(f"Cookies loaded from file: {config['cookies_path']}")
        except Exception as e:
            logging.error(f"Error reading cookie file: {e}")

    with sync_playwright() as p:
        # Launching headless since it will run in automated workflows (like GitHub Actions)
        # headless mode is true by default unless specified
        is_headless = os.environ.get("HEADLESS", "true").lower() == "true"
        browser = p.chromium.launch(headless=is_headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        # Load authentication cookies
        if cookies_data:
            context.add_cookies(cookies_data)
            logging.info("Injected authentication cookies into browser context")
        else:
            logging.warning("No cookies provided. Google Vids will likely request sign-in.")
            
        page = context.new_page()
        website_url = config["google_vids_url"]
        
        try:
            logging.info(f"Opening Vids website: {website_url}")
            page.goto(website_url, timeout=config["timeouts"]["page_load_ms"])
            
            # Wait for manual login if not headless and no cookies
            if not is_headless and not cookies_data:
                logging.info("Headless is off & no cookies. Pausing 60 seconds for manual login...")
                time.sleep(60)
            else:
                # Add a brief pause to let scripts load
                page.wait_for_timeout(5000)
                
            for i, prompt in enumerate(prompts):
                logging.info(f"Processing prompt {i+1}/{len(prompts)}: '{prompt}'")
                
                # Input Box Selector matching the screenshot exactly:
                # "Describe your video. You can add ingredients such as brand images, characters, and more."
                input_selector = "textarea[placeholder*='Describe your video']"
                page.wait_for_selector(input_selector, timeout=20000)
                
                input_box = page.locator(input_selector).first
                input_box.click()
                
                # Clear existing text
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.wait_for_timeout(500)
                
                input_box.fill(prompt)
                page.wait_for_timeout(1000)
                
                # Locate and click Generate button (below the input box inside AI video clip panel)
                generate_btn = page.locator("button:has-text('Generate'), [aria-label*='Generate']").first
                generate_btn.click()
                
                logging.info(f"Generating video... waiting {config['timeouts']['video_generation_sec']} seconds")
                page.wait_for_timeout(config["timeouts"]["video_generation_sec"] * 1000)
                
                # Share & Download automation
                # Clicking the top-right blue "Share" button
                share_btn = page.locator("button:has-text('Share')").first
                share_btn.click()
                page.wait_for_timeout(2000)
                
                # Find download option inside the Share dropdown menu
                download_option = page.locator("text=Download, text=Export video, [aria-label*='Download']").first
                
                file_path = os.path.join(download_dir, f"video_{i+1}.mp4")
                with page.expect_download(timeout=config["timeouts"]["download_wait_sec"] * 1000) as download_info:
                    download_option.click()
                
                download = download_info.value
                download.save_as(file_path)
                logging.info(f"Downloaded video clip saved to: {file_path}")
                download_paths.append(file_path)
                
                # Cooldown period between prompts
                page.wait_for_timeout(3000)
                
        except Exception as e:
            logging.error(f"Error during video generation workflow: {e}")
        finally:
            browser.close()
            
    return download_paths

def merge_videos_ffmpeg(video_list, output_path):
    """Merges a list of video file paths into a single video file using FFmpeg."""
    if not video_list:
        logging.error("No videos provided to merge.")
        return False
        
    if len(video_list) == 1:
        logging.info("Only one video generated, copying to output path.")
        try:
            import shutil
            shutil.copyfile(video_list[0], output_path)
            return True
        except Exception as e:
            logging.error(f"Failed to copy single video file: {e}")
            return False
            
    # Create the concatenation list file
    concat_file = "concat_list.txt"
    try:
        with open(concat_file, "w", encoding="utf-8") as f:
            for video in video_list:
                # FFmpeg concat file expects absolute paths or escaped paths
                abs_path = os.path.abspath(video)
                f.write(f"file '{abs_path}'\n")
                
        # Command: ffmpeg -f concat -safe 0 -i concat_list.txt -c copy output_path -y
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path, "-y"]
        logging.info(f"Running FFmpeg merge command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            logging.info(f"Successfully merged videos into: {output_path}")
            return True
        else:
            logging.error(f"FFmpeg failed with return code {result.returncode}. Stderr: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Exception during FFmpeg merge: {e}")
        return False
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)

def run_pipeline():
    """Runs the complete end-to-end automation pipeline."""
    config = load_config()
    credentials = get_google_credentials(config)
    
    logging.info("Step 1: Fetching prompts from Google Sheets")
    prompts = fetch_prompts_from_sheet(config, credentials)
    if not prompts:
        logging.error("No prompts found to process. Pipeline aborted.")
        return
        
    logging.info(f"Found prompts: {prompts}")
    
    logging.info("Step 2: Automating Google Vids to generate clips")
    clips = generate_videos_playwright(prompts, config)
    if not clips:
        logging.error("Video generation failed or returned no clips. Pipeline aborted.")
        return
        
    logging.info("Step 3: Merging generated clips")
    output_video = config["output_filename"]
    merge_success = merge_videos_ffmpeg(clips, output_video)
    if not merge_success or not os.path.exists(output_video):
        logging.error("Failed to merge videos. Pipeline aborted.")
        return
        
    logging.info("Step 4: Uploading final video to Google Drive")
    upload_success = upload_to_google_drive(output_video, config, credentials)
    if upload_success:
        logging.info("Pipeline executed successfully!")
    else:
        logging.error("Pipeline finished with Drive upload errors.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Vids Auto-Generation Pipeline")
    parser.add_argument("--test-sheets", action="store_true", help="Test fetching prompts from Google Sheets")
    parser.add_argument("--test-merge", nargs="+", help="Test merging specific video files using FFmpeg")
    parser.add_argument("--test-drive", help="Test uploading a specific file to Google Drive")
    parser.add_argument("--validate-only", action="store_true", help="Validate credentials and configurations")
    
    args = parser.parse_args()
    
    if args.test_sheets:
        config = load_config()
        creds = get_google_credentials(config)
        prompts = fetch_prompts_from_sheet(config, creds)
        print(f"Test Sheets output: {prompts}")
    elif args.test_merge:
        merge_videos_ffmpeg(args.test_merge, "test_merged_output.mp4")
    elif args.test_drive:
        config = load_config()
        creds = get_google_credentials(config)
        upload_to_google_drive(args.test_drive, config, creds)
    elif args.validate_only:
        config = load_config()
        creds = get_google_credentials(config)
        print("Config and credential validation check completed.")
    else:
        run_pipeline()
