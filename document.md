# SHL Assessment Recommender - Solution Approach

## Problem Statement

Develop an AI-powered tool to recommend SHL assessments based on job descriptions, providing structured, relevant assessment matches.

## Solution Architecture

Built a Streamlit-based web application that:

- Accepts job descriptions via text or URL
- Processes input through Google's Gemini AI
- Returns structured assessment recommendations
- Validates and displays results in a user-friendly format

## Key Components

- Frontend: Streamlit for intuitive UI
- AI Engine: Google Gemini Pro for intelligent analysis
- Data Processing: Pandas for data handling
- Web Scraping: BeautifulSoup4 for URL content extraction
- Data Validation: JSON parsing and regex for response formatting

## Implementation Highlights

--- Input Handling:

- Text input via text area
- URL input with web scraping
- Input validation and sanitization

--- AI Processing:

- Gemini Pro model integration
- Structured prompt engineering
- JSON response formatting

-- Output Processing:

- JSON extraction and validation
- Required field verification
- Tabular display of recommendations

## Technical Stack

- Python 3.x
- Streamlit (UI framework)
- Google Generative AI (Gemini Pro)
- Pandas (data processing)
- BeautifulSoup4 (web scraping)
- Requests (HTTP handling)
- JSON (data formatting)

## Key Features

- Dual input methods (text/URL)
- Structured JSON output
- Real-time validation
- Debug mode for transparency
- Error handling at all levels

## Future Enhancements

- User authentication
- Assessment history
- Custom templates
- Batch processing
- API rate limiting