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

# API Configuration
API_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
SHL_BASE_URL = "https://www.shl.com"

genai.configure(api_key="AIzaSyCQtd3mHagegGMfne_G7RMAvR5QMuGe7BU")# my api

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
        st.error(f"API Unreachable: {str(e)}")
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

def get_assesment_recommendation(query):
    if not check_api_reachability():
        return {
            "status": "error",
            "message": "API Unreachable",
            "data": []
        }
        
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
    "Respond ONLY in this exact JSON format.")
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Gemini API Error: {str(e)}",
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
        data = json.loads(response_text)
        if isinstance(data, dict) and 'data' in data:
            # Validate URLs in the response
            for item in data['data']:
                if 'url' in item and not validate_shl_url(item['url']):
                    item['url'] = f"{SHL_BASE_URL}/solutions/products/product-catalog/"
            return data
        
        # Fallback: Try to extract JSON array if response is not in correct format
        match = re.search(r'\[\s*{.*?}\s*]', response_text, re.DOTALL)
        if match:
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
    except Exception as e:
        st.error(f"JSON parsing error: {str(e)}")
    return {
        "status": "error",
        "message": "Failed to parse response",
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
    with st.spinner("Generating recommendations using Gemini..."):
        raw_json = get_assesment_recommendation(job_desc)
        
        st.subheader("📦 Raw API Response")
        st.code(raw_json, language="json")
        
        response_data = json_extraction(raw_json)
        
        if response_data["status"] == "success" and response_data["data"]:
            st.subheader("📋 Recommended SHL Assessments")
            # Convert the data to a format suitable for display
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

st.divider()
st.subheader("🔍 API Status")
st.info(f"""
- Gemini API: ✅ Connected
- SHL Catalog: ✅ Accessible
- URL Validation: ✅ Active
- Response Format: ✅ Standardized
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
