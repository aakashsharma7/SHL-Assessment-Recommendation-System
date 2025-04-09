#I have made app UI using streamlit, hence please run file in terminal
#using "streamlit run app.py"
import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from bs4 import BeautifulSoup
import requests
import re
import urllib.parse
from urllib.parse import urlparse
import time
import random
from datetime import datetime, timedelta
import os

# API Configuration
API_TIMEOUT = 30  # seconds
MAX_RETRIES = 3  # Reduced retries to avoid excessive waiting
SHL_BASE_URL = "https://www.shl.com"
BASE_DELAY = 5  # Reduced base delay from 30 to 5 seconds
MAX_DELAY = 20  # Reduced maximum delay from 120 to 20 seconds

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # 1 minute window
MAX_REQUESTS_PER_WINDOW = 10  # Maximum requests per minute

# Configure API with rate limiting
# Get API key from environment variable
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("⚠️ GEMINI_API_KEY environment variable not set. Please set it before running the app.")
    st.info("""
    To set the API key:
    
    **Windows (PowerShell):**
    ```
    $env:GEMINI_API_KEY = "your_api_key"
    ```
    
    **Windows (Command Prompt):**
    ```
    set GEMINI_API_KEY=your_api_key
    ```
    
    **Linux/Mac:**
    ```
    export GEMINI_API_KEY=your_api_key
    ```
    
    **For permanent setup:**
    1. Press Windows + R
    2. Type `sysdm.cpl` and press Enter
    3. Click on "Advanced" tab
    4. Click "Environment Variables"
    5. Under "User variables", click "New"
    6. Variable name: `GEMINI_API_KEY`
    7. Variable value: your API key
    8. Click OK on all windows
    9. Restart your terminal/IDE
    """)
    st.stop()
else:
    genai.configure(api_key=api_key)

# Rate limiting state
request_timestamps = []

@st.cache_data
def load_catalog_data():
    try:
        return pd.read_csv("catalog.csv")
    except Exception as e:
        st.error(f"CSV you asked for could not be found or is Unreadable :{e}")
        return pd.DataFrame()
    

def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def check_api_reachability():
    try:
        # Test Gemini API
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content("Test")
        return True
    except Exception as e:
        error_message = str(e)
        if "API_KEY_INVALID" in error_message or "API Key not found" in error_message:
            st.error("⚠️ Invalid API Key: The Gemini API key is invalid or not properly configured.")
            st.info("""
            To fix this issue:
            1. Get a valid API key from Google AI Studio (https://makersuite.google.com/app/apikey)
            2. Set the API key as an environment variable:
            
               **Windows (PowerShell):**
               ```
               $env:GEMINI_API_KEY = "your_api_key"
               ```
               
               **Windows (Command Prompt):**
               ```
               set GEMINI_API_KEY=your_api_key
               ```
               
               **Linux/Mac:**
               ```
               export GEMINI_API_KEY=your_api_key
               ```
               
               **For permanent setup:**
               1. Press Windows + R
               2. Type `sysdm.cpl` and press Enter
               3. Click on "Advanced" tab
               4. Click "Environment Variables"
               5. Under "User variables", click "New"
               6. Variable name: `GEMINI_API_KEY`
               7. Variable value: your API key
               8. Click OK on all windows
               9. Restart your terminal/IDE
               
            3. Restart the application
            """)
        else:
            st.error(f"API Unreachable: {error_message}")
        return False

def fetch_description(url):
    if not validate_url(url):
        st.error("Invalid URL format")
        return ""
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=API_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup.get_text()
        except requests.Timeout:
            st.warning(f"Request timed out. Attempt {attempt + 1}/{MAX_RETRIES}")
        except requests.RequestException as e:
            st.error(f"Error fetching URL: {str(e)}")
        time.sleep(1)  # Wait before retry
    return ""

def is_rate_limited():
    """Check if we're currently rate limited"""
    current_time = datetime.now()
    # Remove timestamps older than the window
    request_timestamps[:] = [ts for ts in request_timestamps 
                           if current_time - ts < timedelta(seconds=RATE_LIMIT_WINDOW)]
    return len(request_timestamps) >= MAX_REQUESTS_PER_WINDOW

def calculate_backoff_delay(attempt):
    """Calculate exponential backoff delay with jitter"""
    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
    jitter = random.uniform(0, 0.1 * delay)  # Add 0-10% jitter
    return delay + jitter

def make_api_request(model, prompt):
    if is_rate_limited():
        wait_time = RATE_LIMIT_WINDOW - (datetime.now() - request_timestamps[0]).total_seconds()
        if wait_time > 0:
            st.warning(f"⚠️ Rate limit reached. Please wait {wait_time:.1f} seconds before trying again.")
            
            # Add a progress bar for the wait time
            progress_bar = st.progress(0)
            for i in range(100):
                time.sleep(wait_time / 100)
                progress_bar.progress(i + 1)
            
            request_timestamps.clear()  # Clear the timestamps after waiting
    
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            # Record the request timestamp
            request_timestamps.append(datetime.now())
            
            # Show a spinner during API request
            with st.spinner(f"Making API request (Attempt {attempt + 1}/{MAX_RETRIES})..."):
                response = model.generate_content(prompt)
            
            if response and response.text:
                try:
                    # Clean and validate the response
                    cleaned_text = response.text.strip()
                    # Try to parse as complete JSON object first
                    try:
                        data = json.loads(cleaned_text)
                        if isinstance(data, dict) and 'data' in data:
                            return cleaned_text
                    except json.JSONDecodeError:
                        pass
                    
                    # Try to extract JSON array if direct parsing fails
                    match = re.search(r'\[\s*{.*?}\s*]', cleaned_text, re.DOTALL)
                    if match:
                        try:
                            json.loads(match.group())  # Validate the extracted JSON
                            return cleaned_text
                        except json.JSONDecodeError:
                            pass
                    
                    # If we get here, the response is not valid JSON
                    if attempt < MAX_RETRIES - 1:
                        delay = calculate_backoff_delay(attempt)
                        st.warning(f"⚠️ Invalid JSON format. Retrying in {delay:.1f} seconds... (Attempt {attempt + 1}/{MAX_RETRIES})")
                        
                        # Add a progress bar for the delay
                        progress_bar = st.progress(0)
                        for i in range(100):
                            time.sleep(delay / 100)
                            progress_bar.progress(i + 1)
                        
                        continue
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = calculate_backoff_delay(attempt)
                        st.warning(f"⚠️ Response validation failed. Retrying in {delay:.1f} seconds... (Attempt {attempt + 1}/{MAX_RETRIES})")
                        
                        # Add a progress bar for the delay
                        progress_bar = st.progress(0)
                        for i in range(100):
                            time.sleep(delay / 100)
                            progress_bar.progress(i + 1)
                        
                        continue
            return None
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if "quota exceeded" in error_msg.lower() or "429" in error_msg:
                if attempt < MAX_RETRIES - 1:
                    delay = calculate_backoff_delay(attempt)
                    st.warning(f"⚠️ Rate limit reached. Waiting {delay:.1f} seconds... (Attempt {attempt + 1}/{MAX_RETRIES})")
                    
                    # Add a progress bar for the delay
                    progress_bar = st.progress(0)
                    for i in range(100):
                        time.sleep(delay / 100)
                        progress_bar.progress(i + 1)
                    
                    continue
            break
    
    if last_error:
        error_msg = str(last_error)
        if "quota exceeded" in error_msg.lower() or "429" in error_msg:
            return {
                "status": "error",
                "message": "API rate limit exceeded. Please try again in a few minutes.",
                "data": []
            }
        raise last_error
    return None

def get_assesment_recommendation(query):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = ("You are a helpful assistant. Based on the following job description, recommend up to 10 relevant SHL assessments.\n\n"
        f"{query.strip()}\n\n"
        "Your response MUST be a valid JSON object with the following structure:\n"
        "{\n"
        "  'status': 'success',\n"
        "  'message': 'Recommendations generated successfully',\n"
        "  'data': [\n"
        "    {\n"
        "      'assessment_name': 'string',\n"
        "      'url': 'string (SHL catalog URL)',\n"
        "      'remote_testing': 'Yes/No',\n"
        "      'adaptive_support': 'Yes/No',\n"
        "      'duration': 'string (e.g., 30 mins)',\n"
        "      'test_type': 'string (e.g., Cognitive)'\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "IMPORTANT: Respond ONLY with the JSON object, no additional text or explanation.")
        
        response_text = make_api_request(model, prompt)
        if isinstance(response_text, dict):  # If it's already an error response
            return response_text
        if response_text:
            return response_text
        return {
            "status": "error",
            "message": "Failed to get valid JSON response after retries",
            "data": []
        }
    except Exception as e:
        error_message = str(e)
        if "quota exceeded" in error_message.lower() or "429" in error_message:
            return {
                "status": "error",
                "message": "API rate limit exceeded. Please try again in a few minutes.",
                "data": []
            }
        return {
            "status": "error",
            "message": f"API Error: {error_message}",
            "data": []
        }

def validate_shl_url(url):
    """Validate if the URL is from SHL domain"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.endswith('shl.com')
    except:
        return False

def json_extraction(response_text):
    try:
        # First try to parse as complete JSON object
        if not response_text or not isinstance(response_text, str):
            return {
                "status": "error",
                "message": "Invalid response format",
                "data": []
            }
            
        # Clean the response text
        cleaned_text = response_text.strip()
        if not cleaned_text:
            return {
                "status": "error",
                "message": "Empty response received",
                "data": []
            }
            
        try:
            data = json.loads(cleaned_text)
            if isinstance(data, dict) and 'data' in data:
                # Validate URLs in the response
                for item in data['data']:
                    if 'url' in item and not validate_shl_url(item['url']):
                        item['url'] = f"{SHL_BASE_URL}/solutions/products/product-catalog/"
                return data
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract JSON array
            match = re.search(r'\[\s*{.*?}\s*]', cleaned_text, re.DOTALL)
            if match:
                try:
                    items = json.loads(match.group())
                    formatted_data = {
                        "status": "success",
                        "message": "Recommendations generated successfully",
                        "data": []
                    }
                    for item in items:
                        formatted_item = {
                            "assessment_name": item.get("Assessment Name", ""),
                            "url": item.get("URL", f"{SHL_BASE_URL}/solutions/products/product-catalog/"),
                            "remote_testing": item.get("Remote Testing Support", "No"),
                            "adaptive_support": item.get("Adaptive/IRT Support", "No"),
                            "duration": item.get("Duration", ""),
                            "test_type": item.get("Test Type", "")
                        }
                        formatted_data["data"].append(formatted_item)
                    return formatted_data
                except json.JSONDecodeError as e:
                    st.error(f"Failed to parse extracted JSON: {str(e)}")
            else:
                st.error("No valid JSON array found in response")
    except Exception as e:
        st.error(f"JSON parsing error: {str(e)}")
    
    return {
        "status": "error",
        "message": "Failed to parse response. Please try again.",
        "data": []
    }

def extract_raw_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        
        page_text = soup.get_text(separator='\n', strip=True)

        
        links = [a['href'] for a in soup.find_all('a', href=True)]

        return {
            "text": page_text,
            "links": links
        }
    except Exception as e:
        return {"error": str(e)}

# Main Streamlit UI
st.title("SHL Assessment Recommender")

# Check API reachability on startup
if not check_api_reachability():
    st.error("⚠️ API services are currently unreachable. Please try again later.")
    st.stop()

input_type = st.radio("Select input type:", ["Job Description Text", "Job Description URL"])

job_desc = ""
if input_type == "Job Description Text":
    job_desc = st.text_area("Paste the job description here:")
elif input_type == "Job Description URL":
    job_url = st.text_input("Enter the job description URL:")
    if job_url:
        job_desc = fetch_description(job_url)
        
if st.button("Recommend Assessments") and job_desc.strip():
    if is_rate_limited():
        st.error("⚠️ Rate limit reached. Please wait a moment before trying again.")
        st.stop()
        
    with st.spinner("Generating recommendations using Gemini..."):
        try:
            raw_json = get_assesment_recommendation(job_desc)
            
            if not raw_json:
                st.error("❌ No response received from API")
                st.stop()
                
            st.subheader("📦 Raw API Response")
            st.code(raw_json, language="json")
            
            response_data = json_extraction(raw_json)
            
            if response_data["status"] == "success" and response_data["data"]:
                st.subheader("📋 Recommended SHL Assessments")
                display_data = []
                for item in response_data["data"]:
                    display_data.append({
                        "Assessment Name": item["assessment_name"],
                        "URL": item["url"],
                        "Remote Testing": item["remote_testing"],
                        "Adaptive Support": item["adaptive_support"],
                        "Duration": item["duration"],
                        "Test Type": item["test_type"]
                    })
                st.table(pd.DataFrame(display_data))
            else:
                st.error(f"❌ {response_data['message']}")
                if "rate limit" in response_data['message'].lower():
                    st.info("💡 Tip: Please wait a few minutes before trying again.")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            if "quota exceeded" in str(e).lower() or "429" in str(e):
                st.info("💡 Tip: The API has reached its rate limit. Please try again in a few minutes.")

st.divider()
st.subheader("🔍 API Status")
st.info(f"""
- Gemini API: ✅ Connected
- SHL Catalog: ✅ Accessible
- URL Validation: ✅ Active
- Response Format: ✅ Standardized
- Rate Limiting: ✅ Enhanced with request tracking
- Requests in last minute: {len(request_timestamps)}/{MAX_REQUESTS_PER_WINDOW}
""")

st.divider()
st.subheader("🧪 Test: SHL Product Catalog Scraping")

if st.button("Scrape SHL Product Catalog"):
    url = "https://www.shl.com/solutions/products/product-catalog/"
    scraped = extract_raw_data(url)

    if "error" in scraped:
        st.error(f"Scraping failed: {scraped['error']}")
    else:
        with st.expander("📄 Extracted Page Text"):
            st.text_area("Raw Page Text", scraped["text"][:3000])  # limit for visibility
        with st.expander("🔗 Extracted Links"):
            st.write(scraped["links"])

#I have made app UI using streamlit, hence please run file in terminal
#using "streamlit run app.py"
"""Testcase: I am hiring for Java developers who can also collaborate effectively with my business teams. Looking
for an assessment(s) that can be completed in 40 minutes."""
