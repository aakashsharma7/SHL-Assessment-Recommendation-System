#I have made app UI using streamlit, hence please run file in terminal
#using "streamlit run app.py"

import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from bs4 import BeautifulSoup
import requests
import re

genai.configure(api_key="AIzaSyBfV5nU5q9X7E_LeG9z6ObgGmJeWwzR47Q")# my api

@st.cache_data
def load_catalog_data():
    try:
        return pd.read_csv("catalog.csv")
    except Exception as e:
        st.error(f"CSV you asked for could not be found or is Unreadable :{e}")
        return pd.DataFrame()
    

def json_extraction(response_text):
    try:
        match= re.search(r'\[\s*{.*?}\s*]', response_text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return []
    

def get_assesment_recommendation(query):
    model= genai.GenerativeModel("gemini-1.5-pro")
    prompt=("You are a helpful assistant. Based on the following job description, recommend up to 10 relevant SHL assessments.\n\n"
    f"{query.strip()}\n\n"
    "Your response MUST be a valid JSON list. Each object in the list should have the following six keys:\n"
    "- Assessment Name\n"
    "- URL (must link to SHL’s catalog)\n"
    "- Remote Testing Support (Yes/No)\n"
    "- Adaptive/IRT Support (Yes/No)\n"
    "- Duration\n"
    "- Test Type\n\n"
    "Respond ONLY in valid JSON format like this:\n"
    '[{"Assessment Name": "...", "URL": "...", "Remote Testing Support": "Yes", '
    '"Adaptive/IRT Support": "No", "Duration": "30 mins", "Test Type": "Cognitive"}]')
    try:
        response= model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"Gemini API for SHL has Failed {e}")
        return []
        
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

def fetch_descrption(url):
    try:
        response= request.get(url)
        soup= BeautifulSoup(response.content, 'html.parser')
        return soup.get_text()
    except Exception as e:
        st.error(f"Sorry we were unable to fetch job description from url: {url}: {e}")
        return ""
    
st.title("SHL Assessment Recommender")

input_type = st.radio("Select input type:", ["Job Description Text", "Job Description URL"])

job_desc = ""
if input_type == "Job Description Text":
    job_desc = st.text_area("Paste the job description here:")
elif input_type == "Job Description URL":
    job_url = st.text_input("Enter the job description URL:")
    if job_url:
        job_desc = fetch_descrption(job_url)
        
if st.button("Recommend Assessments") and job_desc.strip():
    with st.spinner("Generating recommendations using Gemini..."):
        raw_json = get_assesment_recommendation(job_desc)

        
        st.subheader("📦 Raw Gemini Output (for debugging)")
        st.code(raw_json, language="json")

      
        recommendations = json_extraction(raw_json)

       
        required_keys = {
            "Assessment Name", "URL", "Remote Testing Support",
            "Adaptive/IRT Support", "Duration", "Test Type"
        }

        if recommendations:
            valid_recs = [rec for rec in recommendations if required_keys.issubset(rec.keys())]
            if valid_recs:
                st.subheader("📋 Recommended SHL Assessments according to your need")
                st.table(pd.DataFrame(valid_recs))
            else:
                st.warning("Recommendations received, but they are missing required fields. Please refine your input.")
        else:
            st.error("❌ Sorry we Could not parse valid JSON from Gemini. Try refining your job description.")

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