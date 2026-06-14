from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os

def read_prompts_from_csv(file_path="prompts.csv"):
    """CSV फाइल से प्रॉम्प्ट्स पढ़ता है।"""
    try:
        df = pd.read_csv(file_path)
        return df['Prompt'].tolist()
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return []

def run_automation():
    prompts = read_prompts_from_csv()
    if not prompts:
        print("कोई प्रॉम्प्ट नहीं मिला! कृपया prompts.csv चेक करें।")
        return

    with sync_playwright() as p:
        # Google अकाउंट में लॉगिन की समस्या से बचने के लिए, 
        # लोकल कंप्यूटर पर पहले से लॉगिन हुए क्रोम का डेटा इस्तेमाल करना बेहतर होता है।
        # अभी के लिए हम साधारण ब्राउज़र लॉन्च कर रहे हैं।
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()

        # TODO: यहाँ आपको अपने Google Vids का सही URL डालना है (जैसे docs.google.com/videos/d/...)
        website_url = "https://docs.google.com/videos/d/1cPx11a5TSjrCAB9P1CHFaJQ7T2qihHxeJm1W8Y4vHJU/edit" 

        try:
            print(f"वेबसाइट खोल रहे हैं: {website_url}")
            page.goto(website_url, timeout=60000)
            
            # --- चेतावनी (WARNING) ---
            # चूंकि यह Google की सर्विस है, आपको पहली बार मैन्युअली ईमेल/पासवर्ड डालकर 
            # लॉगिन करना पड़ सकता है। इसलिए हमने यहाँ 60 सेकंड का पॉज़ (pause) दिया है।
            print("\n*** ध्यान दें: कृपया ब्राउज़र में अपने Google अकाउंट से लॉगिन करें (अगर पहले से नहीं हैं)। ***")
            print("लॉगिन करने और पेज पूरी तरह लोड होने के लिए आपके पास 60 सेकंड हैं...")
            time.sleep(60) 

            for i, prompt in enumerate(prompts):
                print(f"\n--- प्रॉम्प्ट {i+1}/{len(prompts)} प्रोसेस हो रहा है ---")
                print(f"प्रॉम्प्ट: {prompt}")

                # 1. टेक्स्ट बॉक्स खोजें और प्रॉम्प्ट पेस्ट करें
                # Playwright का get_by_placeholder सबसे अच्छा काम करता है
                print("टेक्स्ट बॉक्स ढूँढ रहे हैं...")
                input_box = page.get_by_placeholder("Describe your 8-second video")
                
                # बॉक्स को पहले सेलेक्ट करके खाली करना (clear)
                input_box.click()
                input_box.fill("") 
                input_box.fill(prompt)

                # 2. Generate बटन पर क्लिक करें
                print("Generate बटन पर क्लिक कर रहे हैं...")
                # Generate बटन (जो साइड पैनल में है)
                generate_btn = page.get_by_role("button", name="Generate", exact=True)
                generate_btn.click()

                print("वीडियो जनरेट हो रहा है, कृपया इंतज़ार करें (इसमें समय लग सकता है)...")

                # 3. जनरेट होने का इंतज़ार करें
                # Google Vids में वीडियो बनने के बाद बीच के कैनवास में बदलाव होता है।
                # इसके लिए हम Playwright को थोड़ा एक्स्ट्रा समय देंगे। 
                # (आपको अपनी नेट स्पीड के हिसाब से इसे एडजस्ट करना पड़ सकता है)
                time.sleep(45) # वीडियो जनरेट होने के लिए 45 सेकंड का इंतज़ार (इसे कम/ज़्यादा कर सकते हैं)

                # 4. Share बटन पर क्लिक करें
                print("Share बटन पर क्लिक कर रहे हैं...")
                share_btn = page.get_by_role("button", name="Share")
                share_btn.click()
                
                # मेन्यू खुलने का इंतज़ार करें
                time.sleep(2)

                # 5. Download बटन पर क्लिक करें
                print("Download ऑप्शन ढूँढ रहे हैं...")
                # चूँकि मेन्यू में 'Download' या 'Export' हो सकता है, हम दोनों ट्राई करेंगे
                download_option = page.get_by_text("Download", exact=False)
                
                # डाउनलोड इवेंट को कैप्चर करना
                with page.expect_download() as download_info:
                    download_option.click()
                
                download = download_info.value
                
                # डाउनलोड फोल्डर बनाएं
                os.makedirs("downloads", exist_ok=True)
                file_path = f"downloads/video_{i+1}.mp4"
                
                download.save_as(file_path)
                print(f"वीडियो सेव हो गया: {file_path}")

                # अगले प्रॉम्प्ट से पहले थोड़ा रुकें
                time.sleep(5) 

        except Exception as e:
            print(f"\n[ERROR] ऑटोमेशन के दौरान कोई त्रुटि आई: {e}")
        
        finally:
            print("\nब्राउज़र बंद कर रहे हैं...")
            # browser.close() # टेस्टिंग के दौरान ब्राउज़र खुला रहने दें ताकि आप एरर देख सकें

if __name__ == "__main__":
    if not os.path.exists("prompts.csv"):
        df = pd.DataFrame({"Prompt": ["test video prompt 1", "test video prompt 2"]})
        df.to_csv("prompts.csv", index=False)
        print("टेस्टिंग के लिए prompts.csv फाइल बनाई गई है।")
        
    run_automation()
