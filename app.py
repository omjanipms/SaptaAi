import pandas as pd
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics.pairwise import cosine_similarity
from fpdf import FPDF
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
import requests
import os
import re
from PIL import Image
from datetime import datetime
import logging
import concurrent.futures
from functools import lru_cache
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseUpload
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("matrimonial_handler.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)
# Load environment variables
load_dotenv()

# Constants
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SERVICE_ACCOUNT_FILE = "service_account2.json"
SPREADSHEET_ID = "1b58_GtRw0ZQppXawKUjFgSj-4E6dyXzSdijL1Ne1Zv0"
RANGE_NAME = "'Form Responses 1'!A1:BH1000"
STATIC_HEADER_IMAGE = "logo.png"  # Using the existing logo.png file

# Target Google Sheet constants for tracking sent emails
TARGET_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TARGET_SERVICE_ACCOUNT_FILE = "service_account_target.json"
TARGET_SPREADSHEET_ID = "16UglHoVyKT97BFCkbXZSAiPcoKGjRLdjhQCb3X6jg8w"
TARGET_RANGE_NAME = "Sheet1!A:M"  # Updated to include column M for email text: Sr no, name, whatsappnumber, email, birth date, location, pdf_url, top1_url, top2_url, top3_url, top4_url, top5_url, email_text

# Google Drive constants for PDF upload
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_SERVICE_ACCOUNT_FILE = "service_account_target.json"  # Using same service account for Drive

# Cache for Google Sheets data
_sheets_data_cache = None
_last_fetch_time = None
CACHE_DURATION = 300  # 5 minutes

@lru_cache(maxsize=128)
def convert_height_to_cm(height_value):
    """Convert height to centimeters with caching"""
    if not height_value or pd.isna(height_value):
        return None
    try:
        height_str = str(height_value).lower()
        if "'" in height_str or '"' in height_str:
            feet = 0
            inches = 0
            if "'" in height_str:
                feet = int(height_str.split("'")[0])
            if '"' in height_str:
                inches = int(height_str.split('"')[0].split("'")[-1])
            return (feet * 30.48) + (inches * 2.54)
        return float(height_str)
    except:
        return None

def fetch_data_from_google_sheets():
    """Fetch data from Google Sheets with caching"""
    global _sheets_data_cache, _last_fetch_time
    
    current_time = datetime.now().timestamp()
    
    # Return cached data if it's still valid
    if _sheets_data_cache is not None and _last_fetch_time is not None:
        if current_time - _last_fetch_time < CACHE_DURATION:
            logger.info("Using cached Google Sheets data")
            return _sheets_data_cache
    
    try:
        logger.info(f"Attempting to fetch data from Google Sheets using service account: {SERVICE_ACCOUNT_FILE}")
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        logger.info("Successfully created credentials")
        
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        logger.info(f"Fetching data from spreadsheet ID: {SPREADSHEET_ID}")
        
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        values = result.get("values", [])
        
        if not values:
            logger.error("No data found in Google Sheets")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(values[1:], columns=values[0])
        logger.info(f"Successfully retrieved {len(df)} rows from Google Sheets")
        
        # Update cache
        _sheets_data_cache = df
        _last_fetch_time = current_time
        
        return df
    except Exception as e:
        logger.error(f"Error fetching data from Google Sheets: {str(e)}", exc_info=True)
        return None

def test_target_sheet_connection():
    """Test the connection to the target Google Sheet and verify its structure"""
    try:
        logger.info("Testing target Google Sheet connection...")
        
        # Check if target service account file exists
        if not os.path.exists(TARGET_SERVICE_ACCOUNT_FILE):
            logger.error(f"Target service account file not found: {TARGET_SERVICE_ACCOUNT_FILE}")
            return False
        
        # Create credentials for target sheet
        credentials = service_account.Credentials.from_service_account_file(
            TARGET_SERVICE_ACCOUNT_FILE, scopes=TARGET_SCOPES
        )
        
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        
        # Try to read the target sheet
        result = sheet.values().get(
            spreadsheetId=TARGET_SPREADSHEET_ID, 
            range=TARGET_RANGE_NAME
        ).execute()
        
        values = result.get("values", [])
        
        if not values:
            logger.warning("Target sheet appears to be empty")
            return True  # Still consider it a success if we can connect
        
        logger.info(f"Target sheet has {len(values)} rows")
        if values:
            logger.info(f"First row (headers): {values[0]}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing target sheet connection: {str(e)}", exc_info=True)
        return False

def extract_compatibility_text_from_email(email_message):
    """Extract the compatibility calculation portion from the email message"""
    try:
        if not email_message:
            return ""
        
        # Look for the pattern that starts with numbered matches and compatibility percentages
        import re
        
        # Find the start of the compatibility section (usually starts with "1.")
        lines = email_message.split('\n')
        start_index = -1
        end_index = -1
        
        # Find the start of the numbered compatibility section
        for i, line in enumerate(lines):
            if re.match(r'^\d+\.\s+', line.strip()):
                start_index = i
                break
        
        if start_index == -1:
            logger.warning("No numbered compatibility section found in email message")
            return ""
        
        # Find the end of the compatibility section
        # Look for the 6th numbered item (since we want top 5 matches) or end of message
        match_count = 0
        for i in range(start_index, len(lines)):
            line = lines[i].strip()
            # Count numbered items to find the 6th one
            if re.match(r'^\d+\.\s+', line):
                match_count += 1
                # If we find the 6th numbered item, that's our end point
                if match_count == 6:
                    end_index = i
                    break
            # Also check for common email ending phrases
            elif line.startswith("Best regards") or \
                 line.startswith("Thank you") or \
                 line.startswith("Regards") or \
                 line.startswith("Sincerely") or \
                 line.startswith("Yours sincerely") or \
                 line.startswith("Best wishes"):
                end_index = i
                break
        
        # If no clear end found, take everything from start to end of message
        if end_index == -1:
            end_index = len(lines)
        
        # Extract the compatibility section
        compatibility_lines = lines[start_index:end_index]
        compatibility_text = '\n'.join(compatibility_lines).strip()
        
        if compatibility_text:
            logger.info(f"Successfully extracted compatibility text from email message with {match_count} matches")
            return compatibility_text
        else:
            logger.warning("No compatibility text found in email message")
            return ""
                
    except Exception as e:
        logger.error(f"Error extracting compatibility text from email: {str(e)}")
        return ""

def write_name_to_target_sheet(user_name, whatsapp_number=None, email_address=None, birth_date=None, location=None, pdf_url=None, top_match_urls=None, email_text=None):
    """Write the user name, WhatsApp number, email, birth date, location, PDF URL, top 5 match PDF URLs, and email text to the target Google Sheet with auto-incrementing Sr No"""
    try:
        if not user_name or not user_name.strip():
            logger.warning("Empty or invalid user name provided, skipping target sheet update")
            return False
            
        user_name = user_name.strip()
        whatsapp_number = whatsapp_number.strip() if whatsapp_number and whatsapp_number.strip() else ""
        email_address = email_address.strip() if email_address and email_address.strip() else ""
        birth_date = birth_date.strip() if birth_date and birth_date.strip() else ""
        location = location.strip() if location and location.strip() else ""
        pdf_url = pdf_url.strip() if pdf_url and pdf_url.strip() else ""
        email_text = email_text.strip() if email_text and email_text.strip() else ""
        
        # Initialize top match URLs
        if top_match_urls is None:
            top_match_urls = ["", "", "", "", ""]  # 5 empty strings for top 1-5
        elif len(top_match_urls) < 5:
            # Pad with empty strings if less than 5 URLs provided
            top_match_urls.extend([""] * (5 - len(top_match_urls)))
        elif len(top_match_urls) > 5:
            # Truncate to 5 if more than 5 URLs provided
            top_match_urls = top_match_urls[:5]
        
        # Clean up URLs
        top_match_urls = [url.strip() if url and url.strip() else "" for url in top_match_urls]
        
        logger.info(f"Writing name '{user_name}', WhatsApp '{whatsapp_number}', email '{email_address}', birth date '{birth_date}', location '{location}', PDF URL '{pdf_url}', top match URLs, and email text to target Google Sheet")
        
        # Check if target service account file exists
        if not os.path.exists(TARGET_SERVICE_ACCOUNT_FILE):
            logger.error(f"Target service account file not found: {TARGET_SERVICE_ACCOUNT_FILE}")
            return False
        
        # Create credentials for target sheet
        credentials = service_account.Credentials.from_service_account_file(
            TARGET_SERVICE_ACCOUNT_FILE, scopes=TARGET_SCOPES
        )
        
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        
        # First, get the current data to determine the next Sr No
        try:
            result = sheet.values().get(
                spreadsheetId=TARGET_SPREADSHEET_ID, 
                range=TARGET_RANGE_NAME
            ).execute()
            
            values = result.get("values", [])
        except Exception as e:
            logger.error(f"Error reading target sheet: {e}")
            return False
        
        # Calculate next Sr No (assuming first column is Sr No)
        next_sr_no = 1
        if values and len(values) > 1:  # If there are existing rows (excluding header)
            try:
                # Find the highest Sr No in the first column
                sr_nos = []
                for row in values[1:]:  # Skip header row
                    if row and len(row) > 0:
                        try:
                            sr_nos.append(int(row[0]))
                        except (ValueError, IndexError):
                            continue
                
                if sr_nos:
                    next_sr_no = max(sr_nos) + 1
            except Exception as e:
                logger.warning(f"Error calculating next Sr No, using 1: {e}")
                next_sr_no = 1
        
        # Prepare the new row data: Sr No, Name, WhatsApp Number, Email, Birth Date, Location, PDF URL, Top1 URL, Top2 URL, Top3 URL, Top4 URL, Top5 URL, Email Text
        new_row = [next_sr_no, user_name, whatsapp_number, email_address, birth_date, location, pdf_url] + top_match_urls + [email_text]
        
        # Append the new row to the sheet
        body = {
            'values': [new_row]
        }
        
        result = sheet.values().append(
            spreadsheetId=TARGET_SPREADSHEET_ID,
            range=TARGET_RANGE_NAME,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        logger.info(f"Successfully added name '{user_name}' with Sr No {next_sr_no}, WhatsApp '{whatsapp_number}', email '{email_address}', birth date '{birth_date}', location '{location}', PDF URL '{pdf_url}', top match URLs, and email text to target sheet")
        return True
        
    except Exception as e:
        logger.error(f"Error writing to target Google Sheet: {str(e)}", exc_info=True)
        return False

def process_category_matches(new_user, potential_match, category_info=None):
    """
    Process matches for three main categories with accurate percentage calculations:
    1. Personal, Professional & Family (40%)
    2. Favorites, Likes & Hobbies (35%)
    3. Others (25%)
    """
    # Define exact columns for each category from the Google Sheet
    personal_fields = [
        'Requirements & Preferences [Own business]',
        'Requirements & Preferences [Own house]',
        'Requirements & Preferences [Non-resident national]',
        'Requirements & Preferences [Staying alone]',
        'Requirements & Preferences [Financially independent]'
    ]
    
    professional_fields = [
        'Requirements & Preferences [Higher studies]',
        'Requirements & Preferences [Government service]',
        'Requirements & Preferences [Qualified professional]',
        'Requirements & Preferences [Highly educated]'
    ]
    
    family_fields = [
        'Requirements & Preferences [Small family]',
        'Requirements & Preferences [Joint family]',
        'Requirements & Preferences [With children]',
        'Requirements & Preferences [W/o children]'
    ]
    
    # Combine all fields for Personal, Professional & Family category
    ppf_fields = personal_fields + professional_fields + family_fields
    
    # Favorites, Likes & Hobbies category
    fav_likes_fields = [
        'Requirements & Preferences [Hobbies match]',
        'Requirements & Preferences [Likes]',
        'Requirements & Preferences [Dislikes]'
    ]
    
    # Others category
    others_fields = [
        'Requirements & Preferences [Re-marriage]',
        'Requirements & Preferences [Metro city]',
        'Requirements & Preferences [Kundli match]'
    ]
    
    def normalize_value(value):
        """Normalize string values for better comparison"""
        if pd.isna(value) or value is None:
            return ""
        value = str(value).strip().lower()
        # Handle common variations
        value = value.replace("yes", "true").replace("no", "false")
        value = value.replace("n/a", "").replace("none", "")
        return value
    
    def calculate_field_score(user_val, match_val):
        """Calculate score for a single field with enhanced matching logic"""
        user_val = normalize_value(user_val)
        match_val = normalize_value(match_val)
        
        if not user_val or not match_val:
            return 0.0
            
        # Exact match
        if user_val == match_val:
            return 1.0
            
        # Partial match for hobbies and likes
        if any(field in user_val for field in ['hobbies', 'likes']):
            user_items = set(item.strip() for item in user_val.split(','))
            match_items = set(item.strip() for item in match_val.split(','))
            common_items = user_items.intersection(match_items)
            if common_items:
                return min(1.0, len(common_items) / max(len(user_items), len(match_items)))
                
        # Handle boolean values with partial credit
        if user_val in ['true', 'false'] and match_val in ['true', 'false']:
            return 1.0 if user_val == match_val else 0.0
            
        # Text similarity for other fields
        if user_val and match_val:
            # Calculate similarity based on common words
            user_words = set(user_val.split())
            match_words = set(match_val.split())
            common_words = user_words.intersection(match_words)
            if common_words:
                return min(1.0, len(common_words) / max(len(user_words), len(match_words)))
                
        return 0.0
    
    def calculate_category_score(fields):
        matches = 0
        total_fields = 0
        field_scores = []
        
        for field in fields:
            # Find matching column in both users' data
            user_col = next((col for col in new_user.columns if field.lower() in col.lower()), None)
            match_col = next((col for col in potential_match.index if field.lower() in col.lower()), None)
            
            if user_col and match_col:
                user_val = new_user[user_col].values[0]
                match_val = potential_match[match_col]
                
                # Only count if user has specified a preference
                if user_val and normalize_value(user_val) not in ['', 'false']:
                    total_fields += 1
                    field_score = calculate_field_score(user_val, match_val)
                    field_scores.append(field_score)
                    matches += field_score
        
        # Calculate weighted average if we have fields to compare
        if total_fields > 0:
            # Apply importance weights to fields
            weights = {
                'Requirements & Preferences [Own house]': 1.2,
                'Requirements & Preferences [Own business]': 1.2,
                'Requirements & Preferences [Financially independent]': 1.2,
                'Requirements & Preferences [Qualified professional]': 1.1,
                'Requirements & Preferences [Highly educated]': 1.1,
                'Requirements & Preferences [Hobbies match]': 1.3,
                'Requirements & Preferences [Likes]': 1.3,
                'Requirements & Preferences [Kundli match]': 1.2
            }
            
            # Calculate weighted sum with minimum score of 0.1 for any match
            weighted_sum = sum(max(0.1, score) * weights.get(field, 1.0) for score, field in zip(field_scores, fields))
            total_weight = sum(weights.get(field, 1.0) for field in fields)
            
            # Calculate percentage based on weighted average
            percentage = (weighted_sum / total_weight * 100) if total_weight > 0 else 0
            return min(100, max(10, percentage))  # Ensure percentage is between 10 and 100
            
        return 10.0  # Minimum score for any category
    
    # Calculate scores for each category with enhanced weighting
    ppf_score = calculate_category_score(ppf_fields)
    fav_likes_score = calculate_category_score(fav_likes_fields)
    others_score = calculate_category_score(others_fields)
    
    # Calculate weighted total with category importance
    weighted_total = (ppf_score * 0.40) + (fav_likes_score * 0.35) + (others_score * 0.25)
    
    # Ensure minimum total score of 10%
    final_score = max(10.0, weighted_total)
    
    # Add detailed breakdown for debugging and transparency
    return {
        'matches': [],
        'total_score': final_score,
        'total_weight': 1.0,
        'final_percentage': final_score,
        'category_scores': {
            'personal_professional_family': {
                'score': ppf_score,
                'weight': 0.40,
                'fields': ppf_fields
            },
            'favorites_likes_hobbies': {
                'score': fav_likes_score,
                'weight': 0.35,
                'fields': fav_likes_fields
            },
            'others': {
                'score': others_score,
                'weight': 0.25,
                'fields': others_fields
            }
        }
    }

def process_matrimonial_data(df):
    """Process matrimonial data with optimized matching"""
    # Clean up column names and trim string whitespace
    df.columns = df.columns.str.strip()
    df = df.apply(lambda x: x.map(lambda v: str(v).strip()) if x.dtype == "object" else x)
    
    # Find email column
    possible_email_cols = [col for col in df.columns if "email" in col.lower()]
    if not possible_email_cols:
        raise ValueError("No column containing 'email' found.")
    email_col = possible_email_cols[0]
    df[email_col] = df[email_col].astype(str).str.strip()
    
    if len(df) < 2:
        logger.error("Not enough data for matching.")
        return None
    
    # Separate new user and existing users
    new_user = df.iloc[-1:]
    existing_users = df.iloc[:-1]
    new_user_email = new_user[email_col].values[0]
    new_user_name = new_user["Full Name"].values[0] if "Full Name" in new_user.columns else "New User"
    
    # Extract WhatsApp number
    whatsapp_col = None
    for col in new_user.columns:
        if "whatsapp" in col.lower() and "number" in col.lower():
            whatsapp_col = col
            break
    
    new_user_whatsapp = ""
    if whatsapp_col:
        new_user_whatsapp = new_user[whatsapp_col].values[0] if pd.notna(new_user[whatsapp_col].values[0]) else ""
    else:
        logger.warning("WhatsApp number column not found in source data")
    
    # Extract Birth Date
    birth_date_col = None
    for col in new_user.columns:
        if "birth" in col.lower() and "date" in col.lower():
            birth_date_col = col
            break
    
    new_user_birth_date = ""
    if birth_date_col:
        new_user_birth_date = new_user[birth_date_col].values[0] if pd.notna(new_user[birth_date_col].values[0]) else ""
    else:
        logger.warning("Birth date column not found in source data")
    
    # Extract Location (City, State, Country)
    city_col = None
    state_col = None
    country_col = None
    
    # Find City column
    for col in new_user.columns:
        if (col.strip().lower() == "city" or "city" in col.lower()) and "preference" not in col.lower() and "metro" not in col.lower():
            city_col = col
            break
    
    # Find State column
    for col in new_user.columns:
        if col.strip().lower() == "state" or "state" in col.lower():
            state_col = col
            break
    
    # Find Country column
    for col in new_user.columns:
        if col.strip().lower() == "country" or "country" in col.lower():
            country_col = col
            break
    
    # Build location string
    location_parts = []
    
    if city_col:
        city_value = new_user[city_col].values[0] if pd.notna(new_user[city_col].values[0]) else ""
        if city_value and city_value.strip():
            # Clean up city value (remove prefixes like "City:", "Prefer", etc.)
            city_value = re.sub(r'^(City:|Prefer)\s*', '', city_value.strip(), flags=re.IGNORECASE)
            if city_value:
                location_parts.append(city_value)
    
    if state_col:
        state_value = new_user[state_col].values[0] if pd.notna(new_user[state_col].values[0]) else ""
        if state_value and state_value.strip():
            location_parts.append(state_value.strip())
    
    if country_col:
        country_value = new_user[country_col].values[0] if pd.notna(new_user[country_col].values[0]) else ""
        if country_value and country_value.strip():
            location_parts.append(country_value.strip())
    
    new_user_location = ", ".join(location_parts) if location_parts else ""
    
    if not new_user_location:
        logger.warning("No location information found in source data")
    
    # Filter by gender
    GENDER_COL = "Gender"
    filtered_users = existing_users
    if GENDER_COL in new_user.columns and GENDER_COL in existing_users.columns:
        new_user_gender = str(new_user[GENDER_COL].values[0]).strip().lower()
        existing_users_gender = existing_users[GENDER_COL].fillna("").astype(str).str.lower()
        
        if "male" in new_user_gender and "female" not in new_user_gender:
            filtered_users = existing_users[existing_users_gender.str.contains("female", na=False)]
        elif "female" in new_user_gender:
            filtered_users = existing_users[
                existing_users_gender.str.contains("male", na=False) & 
                ~existing_users_gender.str.contains("female", na=False)
            ]
    
    if filtered_users.empty:
        filtered_users = existing_users
    
    # Process matches
    matches = []
    match_percentages = []
    match_details_list = []
    ppf_scores = []
    fav_likes_scores = []
    others_scores = []
    
    for _, potential_match in filtered_users.iterrows():
        # Process matches using the enhanced category matching
        match_result = process_category_matches(new_user, potential_match, None)
        
        if match_result['total_weight'] > 0:
            matches.append(potential_match)
            match_percentages.append(match_result['final_percentage'])
            match_details_list.append(match_result)
            # Store category breakdowns for easy access in DataFrame
            ppf_scores.append(match_result['category_scores']['personal_professional_family']['score'])
            fav_likes_scores.append(match_result['category_scores']['favorites_likes_hobbies']['score'])
            others_scores.append(match_result['category_scores']['others']['score'])
    
    # Sort matches by percentage
    sorted_indices = sorted(range(len(match_percentages)), key=lambda i: match_percentages[i], reverse=True)
    top_matches = [matches[i] for i in sorted_indices[:5]]
    top_percentages = [match_percentages[i] for i in sorted_indices[:5]]
    top_match_details = [match_details_list[i] for i in sorted_indices[:5]]
    top_ppf_scores = [ppf_scores[i] for i in sorted_indices[:5]]
    top_fav_likes_scores = [fav_likes_scores[i] for i in sorted_indices[:5]]
    top_others_scores = [others_scores[i] for i in sorted_indices[:5]]
    
    # Create DataFrame for top matches
    top_matches_df = pd.DataFrame(top_matches)
    top_matches_df['Match Percentage'] = top_percentages
    top_matches_df['Match Details'] = top_match_details
    top_matches_df['PPF %'] = top_ppf_scores
    top_matches_df['FavLikes %'] = top_fav_likes_scores
    top_matches_df['Others %'] = top_others_scores

    return (
        new_user,
        new_user_name,
        new_user_email,
        new_user_whatsapp,
        new_user_birth_date,
        new_user_location,
        top_matches_df,
        top_percentages,
        top_matches_df
    )

def create_last_response_pdf(new_user, email_col):
    """Create a PDF for the last response using the same format as match PDFs"""
    try:
        pdf = EnhancedSinglePageMatchesPDF()
        pdf.add_page()

        # Add vertical space after BIODATA
        current_y = 50  # Start below enhanced header
        current_y += 3  # Reduced extra vertical space after BIODATA

        # Add photo to the right side with enhanced styling
        photo_added = add_enhanced_photo_to_pdf(pdf, new_user, email_col)

        if photo_added:
            pdf.left_column_width = 110  # Adjust for larger photo
        else:
            pdf.left_column_width = 140

        # First Page Sections
        # Personal Details Section
        current_y = add_compact_section(pdf, "Personal Details", current_y)

        personal_fields = [
            ("Name", "Full Name"),
            ("Birth Date", "Birth Date"),
            ("Birth Time", "Birth Time"),
            ("Birth Place", "Birth Place"),
            ("Height", "Height"),
            ("Weight", "Weight"),
            ("Religion", "Religion"),
            ("Caste / Community", "Caste / Community / Tribe"),
            ("Mother Tongue", "Mother Tongue"),
            ("Nationality", "Nationality"),
        ]

        for display_name, field_name in personal_fields:
            matching_field = next(
                (
                    col
                    for col in new_user.columns
                    if field_name.lower() in col.lower()
                ),
                None,
            )
            if matching_field:
                current_y = add_compact_field(
                    pdf,
                    display_name,
                    new_user[matching_field].values[0],
                    current_y,
                )

        # Professional Details Section
        current_y += 5
        current_y = add_compact_section(pdf, "Professional Details", current_y)

        career_fields = [
            ("Education", "Education"),
            ("Qualification", "Qualification"),
            ("Occupation", "Occupation"),
        ]

        for display_name, field_name in career_fields:
            matching_field = next(
                (
                    col
                    for col in new_user.columns
                    if field_name.lower() in col.lower()
                ),
                None,
            )
            if matching_field:
                current_y = add_compact_field(
                    pdf,
                    display_name,
                    new_user[matching_field].values[0],
                    current_y,
                )

        # Family Information Section
        family_fields = [col for col in new_user.columns if "Family Information" in col]
        if family_fields:
            current_y += 5
            current_y = add_compact_section(pdf, "Family Info", current_y)
            current_y += 3

            family_count = 0
            for field in family_fields:
                if family_count >= 20 or current_y > 245:
                    break
                value = new_user[field].values[0]
                if pd.notna(value) and str(value).strip().lower() not in ["", "no", "n/a"]:
                    match = re.search(r"\[(.*?)\]", field)
                    if match:
                        label = match.group(1)[:35]
                        pdf.set_y(current_y)
                        pdf.set_x(15)
                        pdf.set_font("Arial", "B", 10)
                        pdf.set_text_color(50, 50, 50)
                        pdf.cell(50, 4, f"{label}", border=0)
                        pdf.set_x(70)
                        pdf.set_font("Arial", "", 10)
                        pdf.set_text_color(0, 0, 0)
                        value_text = str(value)
                        if len(value_text) > 40:
                            value_text = value_text[:37] + "..."
                        pdf.cell(pdf.left_column_width - 70, 4, value_text, border=0)
                        current_y += 5
                        family_count += 1

        # Hobbies Section
        hobbies_col = next(
            (
                col
                for col in new_user.columns
                if "favorite" in col.lower() or "hobby" in col.lower()
            ),
            None,
        )

        if hobbies_col:
            current_y += 5
            current_y = add_compact_section(pdf, "Hobbies & Interests", current_y)
            current_y += 3

            hobbies = new_user[hobbies_col].values[0]
            if pd.notna(hobbies) and str(hobbies).strip():
                pdf.set_y(current_y)
                pdf.set_x(15)
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(0)
                hobbies_text = str(hobbies)
                if len(hobbies_text) > 120:
                    hobbies_text = hobbies_text[:117] + "..."
                pdf.cell(pdf.left_column_width - 15, 4, hobbies_text, border=0)

        # Second Page Sections
        pdf.add_page()
        current_y = 50
        current_y += 8  # Add the same spacing as first page after BIODATA

        # Requirements & Preferences Section
        preference_fields = [col for col in new_user.columns if "Requirements & Preferences" in col]
        if preference_fields:
            current_y = add_compact_section(pdf, "Requirements & Preferences", current_y)
            current_y += 3

            # Prepare Requirement and Preferences lists
            requirements = []
            preferences = {}  # Changed to dict to maintain order
            for field in preference_fields:
                value = new_user[field].values[0]
                # Only include if value is not empty, not 'no', not 'n/a', not 'no other preferences'
                if pd.notna(value) and str(value).strip().lower() not in ["", "no", "n/a", "no other preferences"]:
                    match = re.search(r"\[(.*?)\]", field)
                    if match:
                        label = match.group(1)[:35]
                        # Remove "Prefer" from the beginning of the label if it exists
                        label = re.sub(r'^Prefer\s+', '', label, flags=re.IGNORECASE)
                        requirements.append(label)
                        # Clean up the preference value
                        pref_value = str(value).strip()
                        # Remove "Prefer" from the beginning of the value if it exists
                        pref_value = re.sub(r'^Prefer\s+', '', pref_value, flags=re.IGNORECASE)
                        # Only add if not already in preferences (maintains order of first occurrence)
                        if pref_value not in preferences:
                            preferences[pref_value] = None

            # Display as two subfields
            if requirements:
                pdf.set_y(current_y)
                pdf.set_x(15)
                pdf.set_font("Arial", "B", 10)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 5, "Requirement:", ln=1, border=0)  # ln=1 moves to next line
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(0, 0, 0)
                req_text = ", ".join(requirements)
                pdf.set_x(20)
                # Add right padding by reducing the width of the multi_cell so text doesn't touch the right edge
                right_padding = 15  # in mm, adjust as needed
                cell_width = pdf.w - 20 - right_padding
                pdf.multi_cell(cell_width, 5, req_text, border=0)
                current_y = pdf.get_y() + 2

            if preferences:
                pdf.set_y(current_y)
                pdf.set_x(15)
                pdf.set_font("Arial", "B", 10)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 5, "Preferences:", ln=1, border=0)  # ln=1 moves to next line
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(0, 0, 0)
                pref_text = ", ".join(preferences.keys())  # Use keys() to get values in original order
                pdf.set_x(20)
                # Add right padding by reducing the width of the multi_cell so text doesn't touch the right edge
                right_padding = 15  # in mm, adjust as needed
                cell_width = pdf.w - 20 - right_padding
                pdf.multi_cell(cell_width, 5, pref_text, border=0)
                current_y = pdf.get_y() + 2

        # Location Section
        current_y += 5
        current_y = add_compact_section(pdf, "Location", current_y)

        # Get the city value directly from the City column - improved search
        city_col = None
        # First try exact match for "City"
        if "City" in new_user.columns:
            city_col = "City"
        # Then try case-insensitive search with stripped spaces (but avoid preference fields)
        elif any(col.strip().lower() == "city" and "preference" not in col.lower() for col in new_user.columns):
            city_col = next(col for col in new_user.columns if col.strip().lower() == "city" and "preference" not in col.lower())
        # Finally try partial match (but avoid preference fields)
        elif any("city" in col.lower() and "preference" not in col.lower() and "metro" not in col.lower() for col in new_user.columns):
            city_col = next(col for col in new_user.columns if "city" in col.lower() and "preference" not in col.lower() and "metro" not in col.lower())
        
        if city_col:
            city_value = new_user[city_col].values[0] if pd.notna(new_user[city_col].values[0]) else ""
            logger.info(f"DEBUG: Raw city value from column '{city_col}': '{city_value}'")
            if pd.notna(city_value) and str(city_value).strip():
                # Clean up the city value
                city_value = str(city_value).strip()
                logger.info(f"DEBUG: After strip city value: '{city_value}'")
                # Remove any prefixes like "City:" or "Prefer"
                city_value = re.sub(r'^(City:|Prefer)\s*', '', city_value, flags=re.IGNORECASE)
                logger.info(f"DEBUG: After regex cleanup city value: '{city_value}'")
                # Don't truncate city names - use the full cleaned value
                if city_value:
                    current_y = add_compact_field(pdf, "City", city_value, current_y)
                    logger.info(f"DEBUG: Added city field to PDF: '{city_value}'")
        else:
            logger.warning(f"DEBUG: No city column found in data. Available columns: {list(new_user.columns)}")

        # Handle other location fields
        location_fields = [("State", "State"), ("Country", "Country")]
        for display_name, field_name in location_fields:
            matching_field = next(
                (
                    col
                    for col in new_user.columns
                    if field_name.lower() in col.lower()
                ),
                None,
            )
            if matching_field:
                value = new_user[matching_field].values[0]
                if pd.notna(value) and str(value).strip():
                    value = str(value).strip()
                    current_y = add_compact_field(
                        pdf,
                        display_name,
                        value,
                        current_y,
                    )

        # Contact Information (Email only)
        current_y += 10
        current_y = add_compact_section(pdf, "Contact Info", current_y)
        pdf.set_y(current_y)
        pdf.set_x(15)
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(30, 4, "Email", border=0)
        pdf.set_x(50)
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(0, 0, 0)
        email_value = new_user[email_col].values[0]
        pdf.cell(pdf.left_column_width - 50, 4, email_value, border=0)

        # Save the PDF
        output_filename = "Last_Response_Profile.pdf"
        pdf.output(output_filename)
        logger.info(f"Created last response PDF: {output_filename}")
        return output_filename

    except Exception as e:
        logger.error(f"Failed to create last response PDF: {e}")
        return None

def send_admin_last_response_and_matches(new_user, new_user_name, new_user_email, pdf_files):
    """Send last response and matches to admin"""
    try:
        # Create email message
        subject = f"New Matrimonial Registration: {new_user_name}"
        body = f"""
        New matrimonial registration received from {new_user_name} ({new_user_email}).

        Attached files:
        1. Last Response Profile (includes Requirements & Preferences)
        2. Top 5 Match Profiles

        Please review the registration and matches.
        """

        # Get admin email from environment
        admin_email = os.getenv("ADMIN_EMAIL")
        if not admin_email:
            logger.error("Admin email not found in environment variables")
            return False

        # Create message
        msg = MIMEMultipart()
        msg["From"] = os.getenv("SENDER_EMAIL")
        msg["To"] = admin_email
        msg["Subject"] = subject

        # Add body
        msg.attach(MIMEText(body, "plain"))

        # Attach PDFs
        for pdf_file in pdf_files:
            if os.path.exists(pdf_file):
                with open(pdf_file, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{os.path.basename(pdf_file)}"',
                    )
                    msg.attach(part)
            else:
                logger.warning(f"PDF file not found: {pdf_file}")

        # Send email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(
                os.getenv("SENDER_EMAIL"), os.getenv("SENDER_PASSWORD")
            )
            server.send_message(msg)

        logger.info(f"Successfully sent last response and matches to admin: {admin_email}")
        return True

    except Exception as e:
        logger.error(f"Error sending admin notification: {str(e)}", exc_info=True)
        return False

def process_new_matrimonial_registration():
    """Main function to process a new matrimonial registration"""
    try:
        # Step 1: Fetch data from Google Sheets
        logger.info("Starting matrimonial matching process...")
        df = fetch_data_from_google_sheets()

        if df is None or df.empty:
            logger.error("No data retrieved from Google Sheets")
            return False

        logger.info(f"Retrieved {len(df)} records from Google Sheets")
        logger.info(f"Columns in dataset: {df.columns.tolist()}")

        # Step 2: Process the data and find matches
        logger.info("Processing matrimonial data...")
        result = process_matrimonial_data(df)

        if not result or len(result) < 6:
            logger.error("Failed to process matrimonial data or insufficient results")
            return False

        (
            new_user,
            new_user_name,
            new_user_email,
            new_user_whatsapp,
            new_user_birth_date,
            new_user_location,
            top_matches_df,
            top_percentages,
            top_matches_df
        ) = result

        logger.info(f"Found matches for user: {new_user_name} ({new_user_email})")
        logger.info(f"Number of matches found: {len(top_matches_df)}")

        if top_matches_df is None or len(top_matches_df) == 0:
            logger.warning(f"No matches found for {new_user_name}")
            return True

        # Step 3: Log the match results
        log_match_results(new_user_name, new_user_email, top_matches_df)

        # Step 4: Find email column
        possible_email_cols = [col for col in df.columns if "email" in col.lower()]
        email_col = possible_email_cols[0] if possible_email_cols else "Email"
        logger.info(f"Using email column: {email_col}")

        # Step 5: Create last response PDF first
        logger.info("Creating last response PDF...")
        last_response_pdf = create_last_response_pdf(new_user, email_col)
        if not last_response_pdf:
            logger.error("Failed to create last response PDF")
            return False
        logger.info("Successfully created last response PDF")

        # Step 6: Create individual PDFs for each match
        logger.info("Creating individual PDF profiles...")
        pdf_files = create_individual_match_pdfs(
            top_matches_df, top_percentages, new_user_name, email_col
        )

        if not pdf_files:
            logger.error("Failed to create any PDF files")
            return False

        # Add last response PDF to the list of files to send
        pdf_files.append(last_response_pdf)
        logger.info(f"Successfully created {len(pdf_files)} PDF files (including last response)")

        # Step 7: Create personalized email message
        logger.info("Creating email message...")
        email_message = create_email_message(new_user_name, top_matches_df)
        logger.info("Email message created successfully")

        # Step 8: Send email with PDF attachments to user
        logger.info(f"Sending email to {new_user_email}...")
        email_sent = send_email_with_multiple_pdfs(
            new_user_email, email_message, pdf_files, new_user_name, new_user_whatsapp, new_user_email, new_user_birth_date, new_user_location
        )

        if email_sent:
            logger.info(
                f"Successfully sent email with {len(pdf_files)} PDF attachments to {new_user_email}"
            )

            # Step 9: Send copy to admin
            logger.info("Sending copy of user email to admin...")
            admin_copy_sent = send_admin_copy_of_user_email(
                new_user_name, new_user_email, email_message, pdf_files
            )

            if admin_copy_sent:
                logger.info("Successfully sent admin copy of user email")
            else:
                logger.warning(
                    "Failed to send admin copy, but user email was successful"
                )

            # Step 10: Send last response and matches to admin
            if pdf_files:
                admin_notification_sent = send_admin_last_response_and_matches(
                    new_user,
                    new_user_name,
                    new_user_email,
                    pdf_files
                )
                
                if admin_notification_sent:
                    logger.info("Successfully sent last response and matches to admin")
                else:
                    logger.warning("Failed to send last response and matches to admin")

        else:
            logger.error(f"Failed to send email to {new_user_email}")

        # Step 11: Clean up temporary files
        logger.info("Cleaning up temporary PDF files...")
        cleanup_pdf_files(pdf_files)

        return email_sent

    except Exception as e:
        logger.error(
            f"Critical error in matrimonial processing: {str(e)}", exc_info=True
        )
        return False


def extract_drive_id(link):
    if not link or not isinstance(link, str) or "drive.google.com" not in link:
        return None

    try:
        patterns = [
            r"/file/d/([a-zA-Z0-9_-]+)",  # Standard sharing link
            r"[?&]id=([a-zA-Z0-9_-]+)",  # Query parameter format
            r"/document/d/([a-zA-Z0-9_-]+)",  # Google Docs format
            r"drive\.google\.com/([a-zA-Z0-9_-]{25,})",  # Direct ID in URL
            r"([a-zA-Z0-9_-]{25,})",  # Last resort - any long alphanumeric string
        ]

        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                file_id = match.group(1)
                # Validate that it looks like a proper Google Drive file ID
                if len(file_id) >= 25:  # Google Drive IDs are typically 28+ characters
                    return file_id

    except Exception as e:
        logger.error(f"Error extracting Drive ID: {e}")

    return None


def download_drive_image(drive_link, save_filename="temp_image.jpg"):
    if not drive_link or "drive.google.com" not in drive_link:
        logger.warning(f"Invalid or missing Google Drive link: {drive_link}")
        return None

    try:
        file_id = extract_drive_id(drive_link)
        if not file_id:
            logger.error(f"Could not extract file ID from link: {drive_link}")
            return None

        download_urls = [
            f"https://drive.google.com/uc?id={file_id}&export=download",
            f"https://drive.google.com/uc?export=view&id={file_id}",
            f"https://lh3.googleusercontent.com/d/{file_id}",
            f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000",
        ]
        session = requests.Session()
        for download_url in download_urls:
            try:
                response = session.get(download_url, timeout=30)

                # Handle Google Drive virus scan warning
                if "NID" in session.cookies:
                    token = None
                    for cookie in session.cookies:
                        if cookie.name.startswith("download_warning"):
                            token = cookie.value
                            break

                    if token:
                        params = {"id": file_id, "export": "download", "confirm": token}
                        response = session.get(
                            "https://drive.google.com/uc", params=params, timeout=30
                        )

                # Check if content looks like an image
                content_type = response.headers.get("Content-Type", "")
                content_length = len(response.content)

                if (
                    "image" in content_type or content_length > 1000
                ) and response.status_code == 200:
                    # Ensure directory exists
                    os.makedirs(
                        os.path.dirname(save_filename)
                        if os.path.dirname(save_filename)
                        else ".",
                        exist_ok=True,
                    )

                    # Save the image
                    with open(save_filename, "wb") as f:
                        f.write(response.content)

                    # Verify the image can be opened
                    try:
                        with Image.open(save_filename) as img:
                            img.verify()  # Verify it's a valid image
                        logger.info(
                            f"Successfully downloaded image from: {download_url}"
                        )
                        return save_filename
                    except Exception as e:
                        logger.warning(
                            f"Downloaded file is not a valid image from {download_url}: {e}"
                        )
                        continue

            except Exception as e:
                logger.warning(f"Failed to download from {download_url}: {e}")
                continue

        logger.error(f"All download methods failed for file ID: {file_id}")
        return None

    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        return None


class EnhancedSinglePageMatchesPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=False)  # Disable auto page break for single page
        self.left_column_width = 120  # Width for text content
        self.right_column_x = 140  # X position for photo
        self.photo_width = 60  # Increased photo width
        self.photo_height = 100  # Significantly increased photo height
        self.current_y_pos = 45  # Track vertical position (moved down for header space)

        # Enhanced designer color scheme
        self.primary_color = (0, 51, 102)  # Dark blue
        self.accent_color = (220, 50, 50)  # Red
        self.gold_color = (184, 134, 11)  # Golden
        self.border_color = (100, 100, 100)  # Gray
        self.text_color = (0, 0, 0)  # Black
        self.light_blue = (173, 216, 235)  # Light blue
        self.cream_color = (255, 253, 240)  # Cream

    def add_corner_flourish(self, x, y, size, position):
        """Add decorative flourish elements at corners"""
        try:
            self.set_draw_color(200, 180, 140)
            self.set_line_width(0.5)

            flourish_size = min(size * 0.2, 2.0)

            if position == "top-left":
                self.line(x - flourish_size, y, x + flourish_size, y - flourish_size)
                self.line(x, y - flourish_size, x + flourish_size, y + flourish_size)
            elif position == "top-right":
                self.line(x - flourish_size, y - flourish_size, x + flourish_size, y)
                self.line(x - flourish_size, y + flourish_size, x, y - flourish_size)
            elif position == "bottom-left":
                self.line(x - flourish_size, y, x + flourish_size, y + flourish_size)
                self.line(x, y + flourish_size, x + flourish_size, y - flourish_size)
            elif position == "bottom-right":
                self.line(x - flourish_size, y + flourish_size, x + flourish_size, y)
                self.line(x - flourish_size, y - flourish_size, x, y + flourish_size)

            self.set_fill_color(200, 180, 140)
            if hasattr(self, "circle"):
                self.circle(x, y, 0.3, "F")
            else:
                self.rect(x - 0.3, y - 0.3, 0.6, 0.6, "F")

        except Exception as e:
            print(f"Warning: Could not add corner flourish: {e}")

    # ... rest of your existing methods ...

    def add_decorative_border(self):
        """Add comprehensive attractive decorative border"""
        # Multiple layer border design
        self.add_outer_frame()
        self.add_ornate_border_pattern()
        self.add_corner_medallions()
        # self.add_side_flourishes()
        # self.add_inner_accent_border()

    def add_outer_frame(self):
        """Add the main outer frame with gradient effect"""
        # Outer thick border
        self.set_draw_color(*self.primary_color)
        self.set_line_width(3)
        self.rect(3, 3, self.w - 6, self.h - 6)

        # Secondary border with golden color
        self.set_draw_color(*self.gold_color)
        self.set_line_width(2)
        self.rect(6, 6, self.w - 12, self.h - 12)

        # Inner fine border
        self.set_draw_color(*self.primary_color)
        self.set_line_width(0.8)
        self.rect(9, 9, self.w - 18, self.h - 18)

    def add_ornate_border_pattern(self):
        """Add uniform ornate patterns on all borders"""
        self.set_draw_color(*self.gold_color)
        self.set_line_width(0.6)

        # All borders use the same diamond and scroll pattern
        self.add_uniform_border_pattern()

    def add_uniform_border_pattern(self):
        """Add the same decorative pattern to all four borders"""
        pattern_spacing = 15

        # Top border pattern
        y_pos = 7.5
        start_x = 25
        for x in range(int(start_x), int(self.w - 25), pattern_spacing):
            self.draw_diamond(x, y_pos, 3)
            if x + pattern_spacing < self.w - 25:
                self.draw_connecting_scroll(
                    x + 3, y_pos, x + pattern_spacing - 3, y_pos
                )

        # Bottom border pattern (same as top)
        y_pos = self.h - 7.5
        for x in range(int(start_x), int(self.w - 25), pattern_spacing):
            self.draw_diamond(x, y_pos, 3)
            if x + pattern_spacing < self.w - 25:
                self.draw_connecting_scroll(
                    x + 3, y_pos, x + pattern_spacing - 3, y_pos
                )

        # Left border pattern (rotated version of top pattern)
        x_pos = 7.5
        start_y = 25
        for y in range(int(start_y), int(self.h - 25), pattern_spacing):
            self.draw_diamond(x_pos, y, 3)
            if y + pattern_spacing < self.h - 25:
                self.draw_connecting_scroll_vertical(
                    x_pos, y + 3, x_pos, y + pattern_spacing - 3
                )

        # Right border pattern (same as left)
        x_pos = self.w - 7.5
        for y in range(int(start_y), int(self.h - 25), pattern_spacing):
            self.draw_diamond(x_pos, y, 3)
            if y + pattern_spacing < self.h - 25:
                self.draw_connecting_scroll_vertical(
                    x_pos, y + 3, x_pos, y + pattern_spacing - 3
                )

    def add_corner_medallions(self):
        """Add elaborate corner medallions"""
        self.set_draw_color(*self.primary_color)
        self.set_line_width(0.6)
        diamond_size = 2

        # TOP-LEFT diamond
        cx, cy = 15, 15
        self.line(cx, cy - diamond_size, cx + diamond_size, cy)  # Top to right
        self.line(cx + diamond_size, cy, cx, cy + diamond_size)  # Right to bottom
        self.line(cx, cy + diamond_size, cx - diamond_size, cy)  # Bottom to left
        self.line(cx - diamond_size, cy, cx, cy - diamond_size)  # Left to top

        # TOP-RIGHT diamond
        cx, cy = self.w - 15, 15
        self.line(cx, cy - diamond_size, cx + diamond_size, cy)
        self.line(cx + diamond_size, cy, cx, cy + diamond_size)
        self.line(cx, cy + diamond_size, cx - diamond_size, cy)
        self.line(cx - diamond_size, cy, cx, cy - diamond_size)

        # BOTTOM-LEFT diamond
        cx, cy = 15, self.h - 15
        self.line(cx, cy - diamond_size, cx + diamond_size, cy)
        self.line(cx + diamond_size, cy, cx, cy + diamond_size)
        self.line(cx, cy + diamond_size, cx - diamond_size, cy)
        self.line(cx - diamond_size, cy, cx, cy - diamond_size)

        # BOTTOM-RIGHT diamond
        cx, cy = self.w - 15, self.h - 15
        self.line(cx, cy - diamond_size, cx + diamond_size, cy)
        self.line(cx + diamond_size, cy, cx, cy + diamond_size)
        self.line(cx, cy + diamond_size, cx - diamond_size, cy)
        self.line(cx - diamond_size, cy, cx, cy - diamond_size)

        # medallion_size = 12
        # offset = 12

        # Top-left medallion
        # self.draw_corner_medallion(offset, offset, medallion_size, "top-left")

        # Top-right medallion
        # self.draw_corner_medallion(self.w - offset, offset, medallion_size, "top-right")

        # Bottom-left medallion
        # self.draw_corner_medallion(
        # offset, self.h - offset, medallion_size, "bottom-left"
        # )

        # Bottom-right medallion
        # self.draw_corner_medallion(
        # self.w - offset, self.h - offset, medallion_size, "bottom-right"
        # )

    def add_side_flourishes(self):
        """Add uniform decorative flourishes on all sides"""
        # All sides use the same flourish design
        flourish_size = 8

        # Center flourish on left side
        self.draw_uniform_flourish(15, self.h / 2, flourish_size)

        # Center flourish on right side
        self.draw_uniform_flourish(self.w - 15, self.h / 2, flourish_size)

        # Top center flourish
        self.draw_uniform_flourish(self.w / 2, 15, flourish_size)

        # Bottom center flourish
        self.draw_uniform_flourish(self.w / 2, self.h - 15, flourish_size)

    def draw_uniform_flourish(self, x, y, size):
        """Draw the same flourish design for all sides"""
        self.set_draw_color(*self.accent_color)
        self.set_line_width(0.8)

        # Central motif - circle with radiating elements
        self.circle(x, y, size / 4, style="D")

        # Radiating decorative lines in 4 directions
        import math

        for angle in [0, 90, 180, 270]:  # Cardinal directions
            rad = math.radians(angle)
            x1 = x + (size / 4) * math.cos(rad)
            y1 = y + (size / 4) * math.sin(rad)
            x2 = x + (size / 2) * math.cos(rad)
            y2 = y + (size / 2) * math.sin(rad)
            self.line(x1, y1, x2, y2)

            # Small decorative element at the end
            self.circle(x2, y2, size / 8, style="D")

    def add_inner_accent_border(self):
        """Add inner decorative accent border"""
        self.set_draw_color(*self.accent_color)
        self.set_line_width(0.5)
        self.set_dash(2, 2)  # Dotted pattern
        self.rect(12, 12, self.w - 24, self.h - 24)
        self.set_dash()  # Reset to solid

    def draw_diamond(self, x, y, size):
        """Draw a diamond shape"""
        self.line(x, y - size, x + size, y)
        self.line(x + size, y, x, y + size)
        self.line(x, y + size, x - size, y)
        self.line(x - size, y, x, y - size)

    def draw_connecting_scroll(self, x1, y, x2, Y):
        """Draw connecting scroll between elements"""
        import math

        mid_x = (x1 + x2) / 2

        # Create a wavy line
        segments = 8
        for i in range(segments):
            t = i / segments
            x = x1 + t * (x2 - x1)
            wave_y = y + 1.5 * math.sin(t * math.pi * 2)

            if i == 0:
                start_x, start_y = x, wave_y
            else:
                self.line(start_x, start_y, x, wave_y)
                start_x, start_y = x, wave_y

    def draw_connecting_scroll_vertical(self, x, y1, X, y2):
        """Draw vertical connecting scroll between elements"""
        import math

        mid_y = (y1 + y2) / 2

        # Create a wavy vertical line
        segments = 8
        for i in range(segments):
            t = i / segments
            y = y1 + t * (y2 - y1)
            wave_x = x + 1.5 * math.sin(t * math.pi * 2)

            if i == 0:
                start_x, start_y = wave_x, y
            else:
                self.line(start_x, start_y, wave_x, y)
                start_x, start_y = wave_x, y

    def draw_small_flourish(self, x, y, size, angle):
        """Draw small decorative flourish at given angle"""
        import math

        rad = math.radians(angle + 90)  # Perpendicular to the line

        # Small decorative cross
        x1 = x + size * math.cos(rad)
        y1 = y + size * math.sin(rad)
        x2 = x - size * math.cos(rad)
        y2 = y - size * math.sin(rad)

        self.line(x1, y1, x2, y2)

    # Remove unused methods that are no longer needed
    # (Keeping only the essential utility methods)

    def draw_corner_medallion(self, x, y, size, position):
        """Draw elaborate corner medallions"""
        self.set_draw_color(*self.gold_color)
        self.set_line_width(1.0)

        # Main medallion circle
        self.circle(x, y, size / 2, style="D")

        # Inner decorative circle
        self.set_line_width(0.6)
        self.circle(x, y, size / 4, style="D")

        # Radiating decorative elements based on corner position
        import math

        if position == "top-left":
            angles = [225, 270, 315]  # Bottom-right quadrant
        elif position == "top-right":
            angles = [135, 180, 225]  # Bottom-left quadrant
        elif position == "bottom-left":
            angles = [315, 0, 45]  # Top-right quadrant
        else:  # bottom-right
            angles = [45, 90, 135]  # Top-left quadrant

        # Draw radiating decorative lines
        for angle in angles:
            rad = math.radians(angle)
            x1 = x + (size / 2) * math.cos(rad)
            y1 = y + (size / 2) * math.sin(rad)
            x2 = x + (size * 0.8) * math.cos(rad)
            y2 = y + (size * 0.8) * math.sin(rad)
            self.line(x1, y1, x2, y2)

        # Add corner-specific decorative flourishes
        self.add_corner_flourish(x, y, size, position)

    # Keep only essential utility methods
    def arc(self, x, y, r, start_angle, end_angle):
        """Simple arc drawing method"""
        import math

        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)

        segments = 10
        angle_step = (end_rad - start_rad) / segments

        for i in range(segments):
            angle1 = start_rad + i * angle_step
            angle2 = start_rad + (i + 1) * angle_step

            x1 = x + r * math.cos(angle1)
            y1 = y + r * math.sin(angle1)
            x2 = x + r * math.cos(angle2)
            y2 = y + r * math.sin(angle2)

            self.line(x1, y1, x2, y2)

    def circle(self, x, y, r, style="D"):
        """Draw a circle"""
        import math

        segments = 16
        angle_step = 2 * math.pi / segments

        for i in range(segments):
            angle1 = i * angle_step
            angle2 = (i + 1) * angle_step

            x1 = x + r * math.cos(angle1)
            y1 = y + r * math.sin(angle1)
            x2 = x + r * math.cos(angle2)
            y2 = y + r * math.sin(angle2)

            self.line(x1, y1, x2, y2)

    def curve(self, x1, y1, x2, y2, x3, y3, x4, y4):
        """Draw a bezier curve using line segments"""
        segments = 10
        for i in range(segments + 1):
            t = i / segments
            x = (
                (1 - t) ** 3 * x1
                + 3 * (1 - t) ** 2 * t * x2
                + 3 * (1 - t) * t**2 * x3
                + t**3 * x4
            )
            y = (
                (1 - t) ** 3 * y1
                + 3 * (1 - t) ** 2 * t * y2
                + 3 * (1 - t) * t**2 * y3
                + t**3 * y4
            )

            if i == 0:
                start_x, start_y = x, y
            else:
                self.line(start_x, start_y, x, y)
                start_x, start_y = x, y

    def set_dash(self, dash_length=0, space_length=0):
        """Set dash pattern for lines"""
        if dash_length > 0 and space_length >= 0:
            dash_string = "[{0} {1}] 0 d".format(
                dash_length * self.k, space_length * self.k
            )
        else:
            dash_string = "[] 0 d"
        self._out(dash_string)

    def header(self):
        # Add the enhanced decorative border
        self.add_decorative_border()

        # Add Ganesh image at the top center
        image_path = "logo.png"
        image_width_mm = 16.0  # Increased size for the logo in mm
        page_width = self.w  # Get page width
        image_x = (page_width - image_width_mm) / 2
        image_y = 15  # Position from the top

        try:
            if os.path.exists(image_path):
                # Calculate image height to position the title correctly
                img = Image.open(image_path)
                aspect_ratio = img.height / img.width
                image_height_mm = image_width_mm * aspect_ratio
                
                self.image(image_path, x=image_x, y=image_y, w=image_width_mm, h=image_height_mm) # Explicitly set height as well
                
                # Adjust y position for the title based on image height + spacing
                title_y = image_y + image_height_mm + 3 # Maintain padding after image
            else:
                logger.warning(f"Ganesh image not found at {image_path}. Skipping image.")
                title_y = 20 # Fallback if image not found
        except Exception as e:
            logger.error(f"Error adding Ganesh image to PDF: {e}")
            title_y = 20 # Fallback on error

        # Main title with enhanced styling
        self.set_font("Arial", "B", 18)
        self.set_text_color(*self.primary_color)
        self.set_y(title_y) # Use calculated or fallback y position
        self.cell(0, 10, "Sapta.ai Digital Persona", ln=True, align="C")

        # Subtitle with accent color
        # self.set_font("Arial", "B", 16)
        # self.set_text_color(*self.accent_color)
        # self.set_y(self.get_y() + 1) # Removed to eliminate extra space
        # self.ln(3)  # Removed to eliminate extra space

    def footer(self):
        # Enhanced footer with decorative elements
        self.set_y(-20)

        # Footer text
        self.set_font("Arial", "I", 9)
        self.set_text_color(*self.border_color)
        self.cell(
            0,
            10,
            f"Page {self.page_no()} - Generated by Matrimonial Service",
            0,
            0,
            "C",
        )


def add_enhanced_photo_to_pdf(pdf, user_row, email_col):
    """Add user photo to the right side of the PDF with enhanced styling"""
    photo_col = [
        col
        for col in user_row.keys()
        if "photo" in col.lower() and "upload" in col.lower()
    ]
    if not photo_col:
        photo_col = [col for col in user_row.keys() if "photo" in col.lower()]
    
    if not photo_col:
        logger.warning("No photo column found in form data")
        return False
    
    photo_col = photo_col[0]
    photo_link = user_row.get(photo_col, "")

    if (
        not isinstance(photo_link, str)
        or not photo_link.strip()
        or "http" not in photo_link.lower()
    ):
        logger.warning(
            f"No valid photo link found for {user_row.get('Full Name', 'Unknown user')}"
        )
        return False
    
    # Create safe filename
    email = user_row.get(email_col, "unknown")
    safe_name = re.sub(r"[^\w\-_]", "_", email)
    photo_path = f"temp_{safe_name}_photo.jpg"

    # Try to download the image
    img_path = download_drive_image(photo_link, save_filename=photo_path)

    if not img_path or not os.path.exists(img_path):
        logger.warning(
            f"Failed to download image for {user_row.get('Full Name', 'Unknown user')}"
        )
        return False

    # Add image to PDF with enhanced styling
    try:
        with Image.open(img_path) as img:
            # Get image dimensions for proper scaling
            img_width, img_height = img.size
            aspect_ratio = img_width / img_height
            
            # Enhanced photo dimensions (increased height)
            max_photo_width = 70
            max_photo_height = 100  # Increased height

            if aspect_ratio > 1:  # Landscape orientation
                photo_width = max_photo_width
                photo_height = max_photo_width / aspect_ratio
            else:  # Portrait orientation
                photo_height = max_photo_height
                photo_width = max_photo_height * aspect_ratio
            
            # Ensure minimum dimensions
            if photo_width < 40:  # Increased minimum width
                photo_width = 40
                photo_height = 40 / aspect_ratio
            if photo_height < 50:  # Increased minimum height
                photo_height = 50
                photo_width = 50 * aspect_ratio

            # Position photo in top-right corner with proper margins
            photo_x = pdf.w - photo_width - 15  # 15mm from right edge
            photo_y = 57  # Increased vertical space from BIODATA text (was 55)

            # Add decorative border around photo
            border_margin = 2
            pdf.set_draw_color(*pdf.primary_color)
            pdf.set_line_width(1)
            pdf.rect(
                photo_x - border_margin,
                photo_y - border_margin,
                photo_width + 2 * border_margin,
                photo_height + 2 * border_margin,
            )
            
            # Add photo
            pdf.image(
                img_path,
                x=photo_x,
                y=photo_y,
                w=photo_width,
                h=photo_height,
            )
            logger.info("Enhanced photo added to PDF successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error adding enhanced image to PDF: {e}")
        return False
    finally:
        # Clean up the temp file
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception as e:
                logger.error(f"Error removing temp image: {e}")

    return False

def add_enhanced_section(pdf, title, y_pos):
    """Add an enhanced section header with decorative elements"""
    pdf.set_y(y_pos)

    # Decorative line before section
    pdf.set_draw_color(*pdf.accent_color)
    pdf.set_line_width(1)
    pdf.set_dash(2, 1)
    pdf.line(10, y_pos + 1, 15, y_pos + 1)
    pdf.line(10, y_pos + 5, 15, y_pos + 5)
    pdf.set_dash()
    
    # Section title
    pdf.set_text_color(*pdf.primary_color)
    pdf.set_x(18)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 6, title, ln=True)
    
    # Decorative underline
    title_width = pdf.get_string_width(title)
    pdf.set_draw_color(*pdf.accent_color)
    pdf.set_line_width(0.3)
    pdf.set_dash(1, 1)
    pdf.line(18, y_pos + 7, 18 + title_width, y_pos + 7)
    pdf.set_dash()
    return y_pos + 10


def add_enhanced_field(pdf, label, value, y_pos, label_width=35):
    """Add a field with enhanced styling"""
    if (
        pd.notna(value)
        and str(value).strip()
        and str(value).strip().lower() not in ["no", "n/a", "none", ""]
    ):
        pdf.set_y(y_pos)

        # Label with enhanced styling
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(*pdf.primary_color)
        pdf.set_x(20)
        pdf.cell(label_width, 5, f"{label}:", border=0)

        # Value with regular styling
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(*pdf.text_color)

        value_str = str(value)
        available_width = pdf.left_column_width - label_width - 25

        # Calculate max characters based on font and available width
        char_width = pdf.get_string_width("A")
        max_chars = int(available_width / char_width) - 5

        if len(value_str) > max_chars:
            value_str = value_str[: max_chars - 3] + "..."

        pdf.set_x(20 + label_width)
        pdf.cell(available_width, 5, value_str, border=0)

        return y_pos + 6
    return y_pos


def add_family_information_enhanced(pdf, matched_user, current_y):
    """Add family information with enhanced styling"""
    family_fields = [col for col in matched_user.keys() if "Family Information" in col]

    if not family_fields:
        return current_y

    # Check if we have space for family section
    if current_y > 240:
        return current_y

    current_y = add_enhanced_section(pdf, "Family Information", current_y)

    # Organize family fields by category
    family_categories = {
        "Parents": ["father", "mother", "parent"],
        "Siblings": ["brother", "sister", "sibling"],
        "Other": [],
    }

    # Categorize fields
    categorized_fields = {cat: [] for cat in family_categories.keys()}

    for field in family_fields:
        field_lower = field.lower()
        categorized = False

        for category, keywords in family_categories.items():
            if any(keyword in field_lower for keyword in keywords):
                categorized_fields[category].append(field)
                categorized = True
                break

        if not categorized:
            categorized_fields["Other"].append(field)

    # Add family information by category
    fields_added = 0
    max_family_fields = 12  # Adjusted for enhanced layout

    for category, fields in categorized_fields.items():
        if fields_added >= max_family_fields or current_y > 250:
            break

        category_has_content = False

        for field in fields:
            if fields_added >= max_family_fields or current_y > 250:
                break

            value = matched_user.get(field, "")
            if (
                pd.notna(value)
                and str(value).strip()
                and str(value).strip().lower() not in ["no", "n/a", "none", ""]
            ):
                # Extract label from field name
                label = extract_family_field_label(field)
                if label:
                    if not category_has_content and len(fields) > 1:
                        # Add mini category header
                        pdf.set_y(current_y)
                        pdf.set_x(20)
                        pdf.set_font("Arial", "I", 9)
                        pdf.set_text_color(*pdf.border_color)
                        pdf.cell(0, 4, f"{category}:", border=0)
                        current_y += 4
                        category_has_content = True

                    current_y = add_enhanced_field(pdf, label, value, current_y, 30)
                    fields_added += 1

    # Add spacing after family section
    if fields_added > 0:
        current_y += 3

    return current_y


def extract_family_field_label(field_name):
    """Extract a clean label from family field name"""
    # Remove "Family Information [" and "]" parts
    match = re.search(r"\[(.*?)\]", field_name)
    if match:
        label = match.group(1)
        # Clean up common patterns
        label = re.sub(r"^\d+\.?\s*", "", label)  # Remove leading numbers
        label = re.sub(r"\s*\(.*?\)", "", label)  # Remove parenthetical info
        label = label.strip()

        # Truncate if too long
        if len(label) > 20:
            label = label[:17] + "..."

        return label

    return None


def add_compact_section(pdf, title, y_pos):
    """Add a compact section title with proper spacing"""
    pdf.set_y(y_pos)
    pdf.set_x(15)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, title, border=0)  # Title height
    return y_pos + 8  # Increased spacing after section title from 4 to 8


def add_compact_field(pdf, label, value, y_pos, label_width=50):  # Changed default label_width to 50
    """Add a field with label and value in a compact format."""
    if not value:
        return y_pos
    
    # Handle "same" values by looking up the actual value
    value_str = str(value).strip().lower()
    if value_str.startswith("same"):
        # Try to find the actual value in the data
        actual_value = None
        if "build" in value_str:
            actual_value = "Average"  # Default to Average if not specified
        elif "mother tongue" in value_str:
            actual_value = "Gujarati"  # Default to Gujarati if not specified
        elif "religion" in value_str:
            actual_value = "Hindu"  # Default to Hindu if not specified
        elif "caste" in value_str:
            actual_value = "General"  # Default to General if not specified
        elif "education" in value_str:
            actual_value = "Graduate"  # Default to Graduate if not specified
        elif "occupation" in value_str:
            actual_value = "Private Job"  # Default to Private Job if not specified
        elif "income" in value_str:
            actual_value = "5-10 Lakhs"  # Default to 5-10 Lakhs if not specified
        elif "city" in value_str and "caste" not in value_str:  # Only match city if it's not caste
            # Don't use hardcoded default - use the original value or try to extract from context
            # If it's "same as city", we should use the original value or leave it as is
            actual_value = None  # Don't override with hardcoded value
        elif "state" in value_str:
            actual_value = "Gujarat"  # Default to Gujarat instead of Maharashtra
        elif "country" in value_str:
            actual_value = "India"  # Default to India if not specified
        
        if actual_value:
            value = actual_value
    
    # Set font for label
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(64, 64, 64)  # Dark gray for label
    
    # Special handling for Caste/Community/Tribe field
    if label == "Caste / Community / Tribe" or label == "Caste / Community":
        # Draw label
        pdf.set_xy(15, y_pos)
        pdf.cell(label_width, 5, label, 0, 0, 'L')  # Removed colon
        
        # Draw value with proper wrapping
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(0, 0, 0)  # Black for value
        
        # Calculate available width for value
        available_width = 190 - (15 + label_width + 5)
        
        # Split value into words and create wrapped lines
        words = str(value).split()
        current_line = []
        current_width = 0
        lines = []
        
        for word in words:
            word_width = pdf.get_string_width(word + " ")
            if current_width + word_width <= available_width:
                current_line.append(word)
                current_width += word_width
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_width = word_width
        
        if current_line:
            lines.append(" ".join(current_line))
        
        # Draw each line with consistent spacing
        current_y = y_pos
        for i, line in enumerate(lines):
            if i > 0:  # Move to next line for wrapped text
                current_y += 5
                # Align wrapped text with the first line
                pdf.set_xy(15 + label_width + 5, current_y)
            else:
                # First line aligned with label
                pdf.set_xy(15 + label_width + 5, current_y)
            pdf.cell(available_width, 5, line, 0, 0, 'L')
        
        return current_y + 5  # Return new y position with proper spacing
    
    # For all other fields
    pdf.set_xy(15, y_pos)
    pdf.cell(label_width, 5, label, 0, 0, 'L')  # Removed colon
    
    # Set font for value
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)  # Black for value
    
    # Draw value with consistent spacing
    pdf.set_xy(15 + label_width + 5, y_pos)
    pdf.cell(190 - (15 + label_width + 5), 5, str(value), 0, 0, 'L')
    
    return y_pos + 5  # Return new y position


def add_corner_flourish(self, x, y, size, position):
    """
    Add decorative flourish elements at corners
    """
    try:
        # Save current drawing state
        self.set_draw_color(200, 180, 140)  # Gold color
        self.set_line_width(0.5)

        # Calculate flourish dimensions based on size
        flourish_size = size * 0.3

        # Draw different flourish patterns based on position
        if position == "top-left":
            # Draw curved flourish for top-left corner
            self._draw_curved_flourish(x, y, flourish_size, "top-left")
        elif position == "top-right":
            # Draw curved flourish for top-right corner
            self._draw_curved_flourish(x, y, flourish_size, "top-right")
        elif position == "bottom-left":
            # Draw curved flourish for bottom-left corner
            self._draw_curved_flourish(x, y, flourish_size, "bottom-left")
        elif position == "bottom-right":
            # Draw curved flourish for bottom-right corner
            self._draw_curved_flourish(x, y, flourish_size, "bottom-right")

    except Exception as e:
        # Log error but don't break PDF generation
        print(f"Warning: Could not add corner flourish at {position}: {e}")


def _draw_curved_flourish(self, x, y, size, position):
    """
    Helper method to draw curved flourish elements
    """
    try:
        # Simple curved line implementation
        offset = size * 0.2

        if position == "top-left":
            # Draw small decorative curves
            self.line(x - offset, y, x + offset, y - offset)
            self.line(x, y - offset, x + offset, y + offset)

        elif position == "top-right":
            self.line(x - offset, y - offset, x + offset, y)
            self.line(x - offset, y + offset, x, y - offset)

        elif position == "bottom-left":
            self.line(x - offset, y, x + offset, y + offset)
            self.line(x, y + offset, x + offset, y - offset)

        elif position == "bottom-right":
            self.line(x - offset, y + offset, x + offset, y)
            self.line(x - offset, y - offset, x, y + offset)

        # Add small decorative dots
        self.set_fill_color(200, 180, 140)
        dot_size = 0.5
        self.circle(x, y, dot_size, "F")

    except Exception as e:
        print(f"Warning: Could not draw curved flourish: {e}")


# Alternative simpler implementation if the above is too complex:
def add_corner_flourish_simple(self, x, y, size, position):
    """
    Simple corner flourish - just adds a small decorative element
    """
    try:
        # Set decorative color
        self.set_fill_color(200, 180, 140)  # Gold
        self.set_draw_color(200, 180, 140)

        # Draw a small decorative circle or rectangle
        flourish_size = min(size * 0.1, 2)  # Limit size to prevent issues

        # Simple circle flourish
        self.circle(x, y, flourish_size, "F")

    except Exception as e:
        print(f"Warning: Could not add simple flourish: {e}")


# Quick fix - if you want to temporarily disable flourishes:
def add_corner_flourish_disabled(self, x, y, size, position):
    """
    Disabled flourish method - does nothing to prevent errors
    """
    pass  # Do nothing - this prevents the AttributeError


# RECOMMENDED IMPLEMENTATION FOR YOUR CLASS:


def add_corner_flourish(self, x, y, size, position):
    """
    Add decorative corner flourish elements
    """
    try:
        # Save current state
        current_draw_color = getattr(self, "_draw_color", (0, 0, 0))
        current_line_width = getattr(self, "_line_width", 0.2)

        # Set flourish styling
        self.set_draw_color(180, 150, 100)  # Elegant bronze color
        self.set_line_width(0.3)

        # Calculate flourish dimensions
        base_size = min(size * 0.25, 3)  # Reasonable size limit

        # Position-specific flourish patterns
        if position == "top-left":
            self._draw_corner_pattern(x, y, base_size, -1, -1)
        elif position == "top-right":
            self._draw_corner_pattern(x, y, base_size, 1, -1)
        elif position == "bottom-left":
            self._draw_corner_pattern(x, y, base_size, -1, 1)
        elif position == "bottom-right":
            self._draw_corner_pattern(x, y, base_size, 1, 1)

        # Restore previous state
        if hasattr(self, "set_draw_color"):
            self.set_draw_color(*current_draw_color)
        if hasattr(self, "set_line_width"):
            self.set_line_width(current_line_width)

    except Exception as e:
        # Fail gracefully - log but continue
        import logging

        logging.warning(f"Could not add corner flourish at {position}: {e}")


def _draw_corner_pattern(self, x, y, size, x_dir, y_dir):
    """
    Draw a simple corner pattern
    """
    try:
        # Simple L-shaped flourish
        line_length = size * 0.8

        # Horizontal line
        self.line(x, y, x + (line_length * x_dir), y)

        # Vertical line
        self.line(x, y, x, y + (line_length * y_dir))

        # Small decorative elements
        dot_offset = size * 0.3
        if hasattr(self, "circle"):
            self.set_fill_color(180, 150, 100)
            self.circle(x + (dot_offset * x_dir), y + (dot_offset * y_dir), 0.3, "F")

    except Exception as e:
        pass  # Fail silently for decorative elements


def create_single_page_match_pdf(
    matched_user,
    match_percentage,
    new_user_name,
    email_col,
    profile_number,
):
    """Create an enhanced single-page PDF with designer elements"""
    try:
        pdf = EnhancedSinglePageMatchesPDF()
        pdf.add_page()

        # Add vertical space after BIODATA
        current_y = 50  # Start below enhanced header
        current_y += 3  # Reduced extra vertical space after BIODATA from 8 to 3

        # Add photo to the right side with enhanced styling
        photo_added = add_enhanced_photo_to_pdf(pdf, matched_user, email_col)

        if photo_added:
            pdf.left_column_width = 110  # Adjust for larger photo
        else:
            pdf.left_column_width = 140

        # First Page Sections
        # Personal Details Section
        current_y = add_compact_section(pdf, "Personal Details", current_y)

        personal_fields = [
            ("Name", "Full Name"),
            ("Birth Date", "Birth Date"),
            ("Birth Time", "Birth Time"),
            ("Birth Place", "Birth Place"),
            ("Height", "Height"),
            ("Weight", "Weight"),
            ("Religion", "Religion"),
            ("Caste / Community", "Caste / Community / Tribe"),
            ("Mother Tongue", "Mother Tongue"),
            ("Nationality", "Nationality"),
        ]

        for display_name, field_name in personal_fields:
            matching_field = next(
                (
                    col
                    for col in matched_user.keys()
                    if field_name.lower() in col.lower()
                ),
                None,
            )
            if matching_field:
                current_y = add_compact_field(
                    pdf,
                    display_name,
                    matched_user.get(matching_field, "N/A"),
                    current_y,
                )

        # Professional Details Section
        current_y += 5
        current_y = add_compact_section(pdf, "Professional Details", current_y)

        career_fields = [
            ("Education", "Education"),
            ("Qualification", "Qualification"),
            ("Occupation", "Occupation"),
        ]

        for display_name, field_name in career_fields:
            matching_field = next(
                (
                    col
                    for col in matched_user.keys()
                    if field_name.lower() in col.lower()
                ),
                None,
            )
            if matching_field:
                current_y = add_compact_field(
                    pdf,
                    display_name,
                    matched_user.get(matching_field, "N/A"),
                    current_y,
                )

        # Family Information Section
        family_fields = [
            col for col in matched_user.keys() if "Family Information" in col
        ]
        if family_fields:
            current_y += 5
            current_y = add_compact_section(pdf, "Family Info", current_y)
            current_y += 3

            family_count = 0
            for field in family_fields:
                if family_count >= 20 or current_y > 245:
                    break
                value = matched_user.get(field, "")
                if pd.notna(value) and str(value).strip().lower() not in [
                    "",
                    "no",
                    "n/a",
                ]:
                    match = re.search(r"\[(.*?)\]", field)
                    if match:
                        label = match.group(1)[:35]
                        pdf.set_y(current_y)
                        pdf.set_x(15)
                        pdf.set_font("Arial", "B", 10)
                        pdf.set_text_color(50, 50, 50)
                        pdf.cell(50, 4, f"{label}", border=0)
                        pdf.set_x(70)
                        pdf.set_font("Arial", "", 10)
                        pdf.set_text_color(0, 0, 0)
                        value_text = str(value)
                        if len(value_text) > 40:
                            value_text = value_text[:37] + "..."
                        pdf.cell(pdf.left_column_width - 70, 4, value_text, border=0)
                        current_y += 5
                        family_count += 1

        # Hobbies Section
        hobbies_col = next(
            (
                col
                for col in matched_user.keys()
                if "favorite" in col.lower() or "hobby" in col.lower()
            ),
            None,
        )

        if hobbies_col:
            current_y += 5
            current_y = add_compact_section(pdf, "Hobbies & Interests", current_y)
            current_y += 3

            hobbies = matched_user.get(hobbies_col, "")
            if pd.notna(hobbies) and str(hobbies).strip():
                pdf.set_y(current_y)
                pdf.set_x(15)
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(0)
                hobbies_text = str(hobbies)
                if len(hobbies_text) > 120:
                    hobbies_text = hobbies_text[:117] + "..."
                pdf.cell(pdf.left_column_width - 15, 4, hobbies_text, border=0)

        # Second Page Sections
        pdf.add_page()
        current_y = 50
        current_y += 8  # Add the same spacing as first page after BIODATA

        # Requirements & Preferences Section
        preference_fields = [col for col in matched_user.keys() if "Requirements & Preferences" in col]
        if preference_fields:
            current_y = add_compact_section(pdf, "Requirements & Preferences", current_y)
            current_y += 3

            # Prepare Requirement and Preferences lists
            requirements = []
            preferences = {}  # Changed to dict to maintain order
            for field in preference_fields:
                value = matched_user.get(field, "")
                # Only include if value is not empty, not 'no', not 'n/a', not 'no other preferences'
                if pd.notna(value) and str(value).strip().lower() not in ["", "no", "n/a", "no other preferences"]:
                    match = re.search(r"\[(.*?)\]", field)
                    if match:
                        label = match.group(1)[:35]
                        # Remove "Prefer" from the beginning of the label if it exists
                        label = re.sub(r'^Prefer\s+', '', label, flags=re.IGNORECASE)
                        requirements.append(label)
                        # Clean up the preference value
                        pref_value = str(value).strip()
                        # Remove "Prefer" from the beginning of the value if it exists
                        pref_value = re.sub(r'^Prefer\s+', '', pref_value, flags=re.IGNORECASE)
                        # Only add if not already in preferences (maintains order of first occurrence)
                        if pref_value not in preferences:
                            preferences[pref_value] = None

            # Display as two subfields
            if requirements:
                pdf.set_y(current_y)
                pdf.set_x(15)
                pdf.set_font("Arial", "B", 10)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 5, "Requirement:", ln=1, border=0)  # ln=1 moves to next line
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(0, 0, 0)
                req_text = ", ".join(requirements)
                pdf.set_x(20)
                # Add right padding by reducing the width of the multi_cell so text doesn't touch the right edge
                right_padding = 15  # in mm, adjust as needed
                cell_width = pdf.w - 20 - right_padding
                pdf.multi_cell(cell_width, 5, req_text, border=0)
                current_y = pdf.get_y() + 2

            if preferences:
                pdf.set_y(current_y)
                pdf.set_x(15)
                pdf.set_font("Arial", "B", 10)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 5, "Preferences:", ln=1, border=0)  # ln=1 moves to next line
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(0, 0, 0)
                pref_text = ", ".join(preferences.keys())  # Use keys() to get values in original order
                pdf.set_x(20)
                # Add right padding by reducing the width of the multi_cell so text doesn't touch the right edge
                right_padding = 15  # in mm, adjust as needed
                cell_width = pdf.w - 20 - right_padding
                pdf.multi_cell(cell_width, 5, pref_text, border=0)
                current_y = pdf.get_y() + 2

        # Location Section
        current_y += 5
        current_y = add_compact_section(pdf, "Location", current_y)

        # Get the city value directly from the City column - improved search
        city_col = None
        # First try exact match for "City"
        if "City" in matched_user.keys():
            city_col = "City"
        # Then try case-insensitive search with stripped spaces (but avoid preference fields)
        elif any(col.strip().lower() == "city" and "preference" not in col.lower() for col in matched_user.keys()):
            city_col = next(col for col in matched_user.keys() if col.strip().lower() == "city" and "preference" not in col.lower())
        # Finally try partial match (but avoid preference fields)
        elif any("city" in col.lower() and "preference" not in col.lower() and "metro" not in col.lower() for col in matched_user.keys()):
            city_col = next(col for col in matched_user.keys() if "city" in col.lower() and "preference" not in col.lower() and "metro" not in col.lower())
        
        if city_col:
            city_value = matched_user.get(city_col, "")
            logger.info(f"DEBUG: Raw city value from column '{city_col}': '{city_value}'")
            if pd.notna(city_value) and str(city_value).strip():
                # Clean up the city value
                city_value = str(city_value).strip()
                logger.info(f"DEBUG: After strip city value: '{city_value}'")
                # Remove any prefixes like "City:" or "Prefer"
                city_value = re.sub(r'^(City:|Prefer)\s*', '', city_value, flags=re.IGNORECASE)
                logger.info(f"DEBUG: After regex cleanup city value: '{city_value}'")
                # Don't truncate city names - use the full cleaned value
                if city_value:
                    current_y = add_compact_field(pdf, "City", city_value, current_y)
                    logger.info(f"DEBUG: Added city field to PDF: '{city_value}'")
        else:
            logger.warning(f"DEBUG: No city column found in data. Available columns: {list(matched_user.keys())}")

        # Handle other location fields
        location_fields = [("State", "State"), ("Country", "Country")]
        for display_name, field_name in location_fields:
            matching_field = next(
                (
                    col
                    for col in matched_user.keys()
                    if field_name.lower() in col.lower()
                ),
                None,
            )
            if matching_field:
                value = matched_user.get(matching_field, "N/A")
                if pd.notna(value) and str(value).strip():
                    value = str(value).strip()
                    current_y = add_compact_field(
                        pdf,
                        display_name,
                        value,
                        current_y,
                    )

        # Contact Information (Email only)
        current_y += 10
        current_y = add_compact_section(pdf, "Contact Info", current_y)
        pdf.set_y(current_y)
        pdf.set_x(15)
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(30, 4, "Email", border=0)
        pdf.set_x(50)
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(0, 0, 0)
        email_value = matched_user.get(email_col, "N/A")
        pdf.cell(pdf.left_column_width - 50, 4, email_value, border=0)

        # Save the PDF
        matched_user_name = matched_user.get("Full Name", "Unknown").replace(" ", "_")
        output_filename = f"Profile_{profile_number}_{matched_user_name}_match.pdf"
        pdf.output(output_filename)
        logger.info(f"Single-page PDF created: {output_filename}")
        return output_filename

    except Exception as e:
        logger.error(f"Single-page PDF creation failed: {e}", exc_info=True)
        return None


def create_individual_match_pdfs(
    matched_users,
    match_percentages,
    new_user_name,
    email_col,
):
    """Create individual single-page PDFs for each matched user (up to 5)"""
    pdf_files = []

    if matched_users is None or len(matched_users) == 0:
        logger.warning("No matched users to create PDFs for")
        return pdf_files

    # Create individual PDFs for each match (up to 5)
    for i, (idx, user) in enumerate(matched_users.iterrows()):
        if i >= 5:  # Limit to 5 profiles
            break

        profile_number = i + 1
        match_percent = match_percentages[i]

        pdf_filename = create_single_page_match_pdf(
            user, match_percent, new_user_name, email_col, profile_number
        )

        if pdf_filename:
            pdf_files.append(pdf_filename)
            logger.info(f"Created single-page PDF {profile_number}: {pdf_filename}")
        else:
            logger.error(f"Failed to create PDF for profile {profile_number}")

    return pdf_files


# Function to send email with multiple PDF attachments
def send_email_with_multiple_pdfs(to_email, message, pdf_files, user_name=None, whatsapp_number=None, email_address=None, birth_date=None, location=None):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        error_msg = "Email credentials not set in environment variables."
        logger.error(error_msg)
        raise EnvironmentError(error_msg)

    # Validate the email
    if not re.match(r"[^@]+@[^@]+\.[^@]+", to_email):
        logger.error(f"Invalid email address: {to_email}")
        return False

    # Check if PDF files exist
    valid_pdf_files = []
    for pdf_path in pdf_files:
        if os.path.exists(pdf_path):
            valid_pdf_files.append(pdf_path)
        else:
            logger.warning(f"PDF file not found: {pdf_path}")

    if not valid_pdf_files:
        logger.error("No valid PDF files found to attach")
        return False

    msg = EmailMessage()
    msg["Subject"] = "Your Top 5 Match Profiles"
    msg["From"] = sender_email
    msg["To"] = to_email
    msg.set_content(message)

    # Attach all PDF files
    for i, pdf_path in enumerate(valid_pdf_files, 1):
        try:
            with open(pdf_path, "rb") as f:
                file_data = f.read()
                filename = f"Profile_{i}_Match.pdf"
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="pdf",
                    filename=filename,
                )
            logger.info(f"Attached PDF: {pdf_path} as {filename}")
        except Exception as e:
            logger.error(f"Failed to attach PDF {pdf_path}: {e}")
            continue

    # Find the last response PDF to upload to Drive
    last_response_pdf = None
    top_match_pdfs = []
    
    for pdf_path in valid_pdf_files:
        if "Last_Response_Profile.pdf" in pdf_path:
            last_response_pdf = pdf_path
        elif "Profile_" in pdf_path and "_match.pdf" in pdf_path:
            top_match_pdfs.append(pdf_path)
    
    # Sort top match PDFs by their number (Profile_1, Profile_2, etc.)
    top_match_pdfs.sort(key=lambda x: int(x.split('Profile_')[1].split('_')[0]) if 'Profile_' in x else 999)
    
    # Upload last response PDF to Drive and get URL
    pdf_url = None
    if last_response_pdf and user_name:
        pdf_url = upload_pdf_to_drive_and_get_url(last_response_pdf, user_name)
        if pdf_url:
            logger.info(f"Successfully uploaded last response PDF to Drive: {pdf_url}")
        else:
            logger.warning("Failed to upload last response PDF to Drive")

    # Upload top 5 match PDFs to Drive and get URLs
    top_match_urls = []
    if top_match_pdfs and user_name:
        top_match_urls = upload_multiple_pdfs_to_drive_and_get_urls(top_match_pdfs, user_name)
        if top_match_urls:
            logger.info(f"Successfully uploaded {len([url for url in top_match_urls if url])} top match PDFs to Drive")
        else:
            logger.warning("Failed to upload top match PDFs to Drive")

    # Extract compatibility text from email message
    email_text = extract_compatibility_text_from_email(message)
    if email_text:
        logger.info(f"Successfully extracted compatibility text from email message")
    else:
        logger.warning("No compatibility text found in email message")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            logger.info(f"Email with {len(valid_pdf_files)} PDFs sent to {to_email}")
            
            # Write name, WhatsApp number, email, birth date, location, PDF URL, top match URLs, and email text to target sheet if user_name is provided
            if user_name:
                write_name_to_target_sheet(user_name, whatsapp_number, email_address, birth_date, location, pdf_url, top_match_urls, email_text)
            
            return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def cleanup_pdf_files(pdf_files):
    """Clean up temporary PDF files after sending email"""
    for pdf_file in pdf_files:
        try:
            if os.path.exists(pdf_file):
                os.remove(pdf_file)
                logger.info(f"Cleaned up PDF file: {pdf_file}")
        except Exception as e:
            logger.error(f"Failed to remove PDF file {pdf_file}: {e}")


def send_admin_notification(
    user, matches_sent=True, match_lines="No matches", pdf_count=0, pdf_files=None
):
    admin_email = os.getenv("ADMIN_EMAIL")
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    if not admin_email or not sender_email or not sender_password:
        logger.warning("Admin notification skipped: missing email credentials")
        return False

    if pdf_files is None:
        pdf_files = []

    # Try to get user details
    name = (
        user.get("Full Name", "N/A")
        if isinstance(user, dict) or hasattr(user, "get")
        else "N/A"
    )

    # Find email column
    email_value = "N/A"
    if isinstance(user, dict) or hasattr(user, "get"):
        possible_email_keys = [k for k in user.keys() if "email" in k.lower()]
        if possible_email_keys:
            email_value = user.get(possible_email_keys[0], "N/A")

    # Find gender
    gender_value = "N/A"
    if isinstance(user, dict) or hasattr(user, "get"):
        possible_gender_keys = [k for k in user.keys() if "gender" in k.lower()]
        if possible_gender_keys:
            gender_value = user.get(possible_gender_keys[0], "N/A")

    # Check if PDF files exist
    valid_pdf_files = []
    for pdf_path in pdf_files:
        if os.path.exists(pdf_path):
            valid_pdf_files.append(pdf_path)
        else:
            logger.warning(f"PDF file not found: {pdf_path}")

    if not valid_pdf_files:
        logger.error("No valid PDF files found to attach")
        return False

    subject = (
        f"Admin Copy - Match Email for {name}" if matches_sent else "Match Email Failed"
    )
    body = f"""
[ADMIN COPY] This is a copy of the email sent to the user.

User Details:
Name: {name}
Email: {email_value}
Gender: {gender_value}
PDFs Generated: {pdf_count}
Status: {"Successfully sent" if matches_sent else "Failed to send"}

Top matches:
{match_lines}

---
Original email content sent to user is attached below along with match PDFs.
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = admin_email
    msg.set_content(body)

    # Attach all PDF files
    for i, pdf_path in enumerate(valid_pdf_files, 1):
        try:
            with open(pdf_path, "rb") as f:
                file_data = f.read()
                filename = f"Profile_{i}_Match.pdf"
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="pdf",
                    filename=filename,
                )
            logger.info(f"Attached PDF: {pdf_path} as {filename}")
        except Exception as e:
            logger.error(f"Failed to attach PDF {pdf_path}: {e}")
            continue

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            logger.info(f"Admin notified at {admin_email}")
            return True
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
        return False


def send_admin_copy_of_user_email(user_name, user_email, email_message, pdf_files):
    """Send admin a copy of the exact same email that was sent to the user"""
    from datetime import datetime

    admin_email = os.getenv("ADMIN_EMAIL")
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    if not admin_email or not sender_email or not sender_password:
        logger.warning("Admin email copy skipped: missing email credentials")
        return False

    if pdf_files is None:
        pdf_files = []

    # Check if PDF files exist
    valid_pdf_files = []
    for pdf_path in pdf_files:
        if os.path.exists(pdf_path):
            valid_pdf_files.append(pdf_path)
        else:
            logger.warning(f"PDF file not found: {pdf_path}")

    # Create admin email with same content as user email
    subject = f"[ADMIN COPY] Matrimonial Matches for {user_name}"

    # Add admin header to the original message
    admin_body = f"""[ADMIN NOTIFICATION]
This is a copy of the email sent to: {user_name} ({user_email})
Sent on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

===============================================
ORIGINAL EMAIL CONTENT BELOW:
===============================================

{email_message}

===============================================
END OF ORIGINAL EMAIL CONTENT
===============================================
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = admin_email
    msg.set_content(admin_body)

    # Attach all PDF files (same as sent to user)
    for i, pdf_path in enumerate(valid_pdf_files, 1):
        try:
            with open(pdf_path, "rb") as f:
                file_data = f.read()
                filename = f"Profile_{i}_Match.pdf"
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="pdf",
                    filename=filename,
                )
            logger.info(f"Attached PDF to admin email: {pdf_path} as {filename}")
        except Exception as e:
            logger.error(f"Failed to attach PDF to admin email {pdf_path}: {e}")
            continue

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            logger.info(f"Admin copy sent to {admin_email} for user {user_name}")
            return True
    except Exception as e:
        logger.error(f"Failed to send admin copy: {e}")
        return False


def create_email_message(new_user_name, top_matches):
    """Create email message with detailed match breakdowns"""
    # Ensure the user's name is in title case
    name_title_case = str(new_user_name).title() if new_user_name else "User"
    message = f"Dear {name_title_case},\n\n"
    message += "Welcome to Sapta.ai Based on your Sapta.ai Digital Persona here are your top 5 matches with compatability and scores\n\n"
    
    if isinstance(top_matches, pd.DataFrame):
        for i, (_, row) in enumerate(top_matches.iterrows(), 1):
            match_name = row.get('Full Name', 'Unknown')
            # Get category scores from columns
            ppf_score = row.get('PPF %', 0)
            fav_likes_score = row.get('FavLikes %', 0)
            others_score = row.get('Others %', 0)
            
            # Calculate total compatibility as average of three categories
            total_score = (ppf_score + fav_likes_score + others_score) / 3
            
            message += f"{i}. {match_name} - {total_score:.1f}% overall compatibility\n"
            message += f"  Breakdown:\n"
            message += f"    - Personal, Professional & Family: {ppf_score:.1f}%\n"
            message += f"    - Favorites, Likes & Hobbies: {fav_likes_score:.1f}%\n"
            message += f"    - Other Requirement and Preferences: {others_score:.1f}%\n\n"
    else:
        for i, match_data in enumerate(top_matches, 1):
            match = match_data[0] if isinstance(match_data, tuple) else match_data
            details = match_data[1] if isinstance(match_data, tuple) else {}
            match_name = match.get('Full Name', 'Unknown')
            category_scores = details.get('category_scores', {})
            ppf_score = category_scores.get('personal_professional_family', {}).get('score', 0)
            fav_likes_score = category_scores.get('favorites_likes_hobbies', {}).get('score', 0)
            others_score = category_scores.get('others', {}).get('score', 0)
            
            # Calculate total compatibility as average of three categories
            total_score = (ppf_score + fav_likes_score + others_score) / 3
            
            message += f"{i}. {match_name} - {total_score:.1f}% overall compatibility\n"
            message += f"  Breakdown:\n"
            message += f"    - Personal, Professional & Family: {ppf_score:.1f}%\n"
            message += f"    - Favorites, Likes & Hobbies: {fav_likes_score:.1f}%\n"
            message += f"    - Other Requirement and Preferences: {others_score:.1f}%\n\n"
    
    message += "Best regards,\nYour Matrimonial Matching Team"
    return message


def log_match_results(new_user_name, new_user_email, top_matches):
    """Log the matching results for record keeping"""
    logger.info(f"=== MATCH RESULTS FOR {new_user_name} ({new_user_email}) ===")
    logger.info(f"Total matches found: {len(top_matches)}")

    for i, (_, match) in enumerate(top_matches.iterrows(), 1):
        name = match.get("Name", "Unknown")
        email = match.get("Email", "Unknown")
        match_percent = match.get("Match %", 0)
        logger.info(f"Match {i}: {name} ({email}) - {match_percent:.1f}% overall compatibility")

    logger.info("=" * 50)


def handle_errors_gracefully(func):
    """Decorator to handle errors gracefully"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            return None

    return wrapper


@handle_errors_gracefully
def process_new_matrimonial_registration():
    """
    Main function to process a new matrimonial registration
    This function orchestrates the entire matching and notification process
    """
    try:
        # Step 1: Fetch data from Google Sheets
        logger.info("Starting matrimonial matching process...")
        df = fetch_data_from_google_sheets()

        if df is None or df.empty:
            logger.error("No data retrieved from Google Sheets")
            return False

        logger.info(f"Retrieved {len(df)} records from Google Sheets")
        logger.info(f"Columns in dataset: {df.columns.tolist()}")

        # Step 2: Process the data and find matches
        logger.info("Processing matrimonial data...")
        result = process_matrimonial_data(df)

        if not result or len(result) < 6:
            logger.error("Failed to process matrimonial data or insufficient results")
            return False

        (
            new_user,
            new_user_name,
            new_user_email,
            new_user_whatsapp,
            new_user_birth_date,
            new_user_location,
            top_matches_df,
            top_percentages,
            top_matches_df
        ) = result

        logger.info(f"Found matches for user: {new_user_name} ({new_user_email})")
        logger.info(f"Number of matches found: {len(top_matches_df)}")

        if top_matches_df is None or len(top_matches_df) == 0:
            logger.warning(f"No matches found for {new_user_name}")
            return True

        # Step 3: Log the match results
        log_match_results(new_user_name, new_user_email, top_matches_df)

        # Step 4: Find email column
        possible_email_cols = [col for col in df.columns if "email" in col.lower()]
        email_col = possible_email_cols[0] if possible_email_cols else "Email"
        logger.info(f"Using email column: {email_col}")

        # Step 5: Create last response PDF first
        logger.info("Creating last response PDF...")
        last_response_pdf = create_last_response_pdf(new_user, email_col)
        if not last_response_pdf:
            logger.error("Failed to create last response PDF")
            return False
        logger.info("Successfully created last response PDF")

        # Step 6: Create individual PDFs for each match
        logger.info("Creating individual PDF profiles...")
        pdf_files = create_individual_match_pdfs(
            top_matches_df, top_percentages, new_user_name, email_col
        )

        if not pdf_files:
            logger.error("Failed to create any PDF files")
            return False

        # Add last response PDF to the list of files to send
        pdf_files.append(last_response_pdf)
        logger.info(f"Successfully created {len(pdf_files)} PDF files (including last response)")

        # Step 7: Create personalized email message
        logger.info("Creating email message...")
        email_message = create_email_message(new_user_name, top_matches_df)
        logger.info("Email message created successfully")

        # Step 8: Send email with PDF attachments to user
        logger.info(f"Sending email to {new_user_email}...")
        email_sent = send_email_with_multiple_pdfs(
            new_user_email, email_message, pdf_files, new_user_name, new_user_whatsapp, new_user_email, new_user_birth_date, new_user_location
        )

        if email_sent:
            logger.info(
                f"Successfully sent email with {len(pdf_files)} PDF attachments to {new_user_email}"
            )

            # Step 9: Send copy to admin
            logger.info("Sending copy of user email to admin...")
            admin_copy_sent = send_admin_copy_of_user_email(
                new_user_name, new_user_email, email_message, pdf_files
            )

            if admin_copy_sent:
                logger.info("Successfully sent admin copy of user email")
            else:
                logger.warning(
                    "Failed to send admin copy, but user email was successful"
                )

            # Step 10: Send last response and matches to admin
            if pdf_files:
                admin_notification_sent = send_admin_last_response_and_matches(
                    new_user,
                    new_user_name,
                    new_user_email,
                    pdf_files
                )
                
                if admin_notification_sent:
                    logger.info("Successfully sent last response and matches to admin")
                else:
                    logger.warning("Failed to send last response and matches to admin")

        else:
            logger.error(f"Failed to send email to {new_user_email}")

        # Step 11: Clean up temporary files
        logger.info("Cleaning up temporary PDF files...")
        cleanup_pdf_files(pdf_files)

        return email_sent

    except Exception as e:
        logger.error(
            f"Critical error in matrimonial processing: {str(e)}", exc_info=True
        )
        return False


def process_specific_user_by_email(user_email):
    """
    Process matching for a specific user by their email address
    Useful for re-processing or testing specific cases
    """
    try:
        logger.info(f"Processing specific user: {user_email}")

        # Fetch data from Google Sheets
        df = fetch_data_from_google_sheets()

        if df is None or df.empty:
            logger.error("No data retrieved from Google Sheets")
            return False

        # Find email column
        possible_email_cols = [col for col in df.columns if "email" in col.lower()]
        if not possible_email_cols:
            logger.error("No email column found")
            return False

        email_col = possible_email_cols[0]

        # Filter for specific user
        user_mask = df[email_col].str.strip().str.lower() == user_email.strip().lower()
        if not user_mask.any():
            logger.error(f"User with email {user_email} not found in the data")
            return False

        # Move the specific user to the end (simulate new registration)
        user_row = df[user_mask].copy()
        other_rows = df[~user_mask].copy()
        df_reordered = pd.concat([other_rows, user_row], ignore_index=True)

        # Process the reordered data
        result = process_matrimonial_data(df_reordered)

        if not result or len(result) < 6:
            logger.error("Failed to process matrimonial data")
            return False

        (
            new_user,
            new_user_name,
            new_user_email,
            new_user_whatsapp,
            new_user_birth_date,
            new_user_location,
            top_matches_df,
            top_percentages,
            top_matches_df
        ) = result

        if top_matches_df is None or len(top_matches_df) == 0:
            logger.warning(f"No matches found for {new_user_name}")
            return True

        # Continue with PDF creation and email sending
        log_match_results(new_user_name, new_user_email, top_matches_df)

        # Create PDFs and send emails
        pdf_files = create_individual_match_pdfs(
            top_matches_df, top_percentages, new_user_name, email_col
        )

        if not pdf_files:
            logger.error("Failed to create any PDF files")
            return False

        # Create and send email
        email_message = create_email_message(new_user_name, top_matches_df)
        email_sent = send_email_with_multiple_pdfs(
            new_user_email, email_message, pdf_files, new_user_name, new_user_whatsapp, new_user_email, new_user_birth_date, new_user_location, new_user
        )

        if email_sent:
            # Send admin copy
            admin_copy_sent = send_admin_copy_of_user_email(
                new_user_name, new_user_email, email_message, pdf_files
            )

            # Send last response and matches to admin
            admin_notification_sent = send_admin_last_response_and_matches(
                new_user,
                new_user_name,
                new_user_email,
                pdf_files
            )

            # Clean up
            cleanup_pdf_files(pdf_files)
            return email_sent

    except Exception as e:
        logger.error(f"Error processing specific user: {str(e)}", exc_info=True)
        return False

def upload_pdf_to_drive_and_get_url(pdf_filename, user_name):
    """Upload PDF to Google Drive and return a shareable URL"""
    try:
        if not os.path.exists(pdf_filename):
            logger.error(f"PDF file not found: {pdf_filename}")
            return None
            
        logger.info(f"Uploading PDF '{pdf_filename}' to Google Drive for user '{user_name}'")
        
        # Check if service account file exists
        if not os.path.exists(DRIVE_SERVICE_ACCOUNT_FILE):
            logger.error(f"Drive service account file not found: {DRIVE_SERVICE_ACCOUNT_FILE}")
            return None
        
        # Create credentials for Google Drive
        credentials = service_account.Credentials.from_service_account_file(
            DRIVE_SERVICE_ACCOUNT_FILE, scopes=DRIVE_SCOPES
        )
        
        # Build Drive service
        drive_service = build("drive", "v3", credentials=credentials)
        
        # Create file metadata
        file_metadata = {
            'name': f"{user_name}_Last_Response_Profile.pdf",
            'parents': []  # Will upload to root folder
        }
        
        # Upload the file using MediaIoBaseUpload
        with open(pdf_filename, 'rb') as file:
            file_content = file.read()
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype='application/pdf',
                resumable=True
            )
            
            media = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
        
        file_id = media.get('id')
        logger.info(f"PDF uploaded to Drive with ID: {file_id}")
        
        # Make the file publicly accessible (anyone with the link can view)
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'},
            fields='id'
        ).execute()
        
        # Get the shareable URL
        shareable_url = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        
        logger.info(f"Created shareable URL for PDF: {shareable_url}")
        return shareable_url
        
    except Exception as e:
        logger.error(f"Error uploading PDF to Drive: {str(e)}", exc_info=True)
        return None

def upload_multiple_pdfs_to_drive_and_get_urls(pdf_files, user_name):
    """Upload multiple PDFs to Google Drive and return their shareable URLs"""
    try:
        if not pdf_files:
            logger.warning("No PDF files provided for upload")
            return []
            
        logger.info(f"Uploading {len(pdf_files)} PDFs to Google Drive for user '{user_name}'")
        
        # Check if service account file exists
        if not os.path.exists(DRIVE_SERVICE_ACCOUNT_FILE):
            logger.error(f"Drive service account file not found: {DRIVE_SERVICE_ACCOUNT_FILE}")
            return []
        
        # Create credentials for Google Drive
        credentials = service_account.Credentials.from_service_account_file(
            DRIVE_SERVICE_ACCOUNT_FILE, scopes=DRIVE_SCOPES
        )
        
        # Build Drive service
        drive_service = build("drive", "v3", credentials=credentials)
        
        urls = []
        
        for i, pdf_filename in enumerate(pdf_files, 1):
            try:
                if not os.path.exists(pdf_filename):
                    logger.warning(f"PDF file not found: {pdf_filename}")
                    urls.append("")
                    continue
                
                # Create file metadata
                file_metadata = {
                    'name': f"{user_name}_Match_{i}.pdf",
                    'parents': []  # Will upload to root folder
                }
                
                # Upload the file using MediaIoBaseUpload
                with open(pdf_filename, 'rb') as file:
                    file_content = file.read()
                    media = MediaIoBaseUpload(
                        io.BytesIO(file_content),
                        mimetype='application/pdf',
                        resumable=True
                    )
                    
                    media = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                
                file_id = media.get('id')
                logger.info(f"PDF {i} uploaded to Drive with ID: {file_id}")
                
                # Make the file publicly accessible (anyone with the link can view)
                drive_service.permissions().create(
                    fileId=file_id,
                    body={'type': 'anyone', 'role': 'reader'},
                    fields='id'
                ).execute()
                
                # Get the shareable URL
                shareable_url = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
                urls.append(shareable_url)
                logger.info(f"Created shareable URL for PDF {i}: {shareable_url}")
                
            except Exception as e:
                logger.error(f"Error uploading PDF {i} ({pdf_filename}) to Drive: {str(e)}")
                urls.append("")
        
        logger.info(f"Successfully uploaded {len([url for url in urls if url])} out of {len(pdf_files)} PDFs to Drive")
        return urls
        
    except Exception as e:
        logger.error(f"Error in upload_multiple_pdfs_to_drive_and_get_urls: {str(e)}", exc_info=True)
        return []

if __name__ == "__main__":
    try:
        logger.info("Starting matrimonial matching process...")
        
        # Test Google Sheets connection
        df = fetch_data_from_google_sheets()
        if df is None:
            logger.error("Failed to fetch data from Google Sheets. Please check your credentials and connection.")
            exit(1)
            
        logger.info(f"Retrieved {len(df)} records from Google Sheets")
        logger.info(f"Columns in dataset: {list(df.columns)}")
        
        # Test target sheet functionality
        logger.info("Testing target sheet functionality...")
        
        # Test the connection only (no test row insertion)
        connection_test = test_target_sheet_connection()
        if connection_test:
            logger.info("Target sheet connection test successful")
        else:
            logger.warning("Target sheet connection test failed, but continuing with main process")
        
        # Process new registrations
        process_new_matrimonial_registration()
        
        logger.info("Matrimonial matching process completed successfully.")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        print(f"An error occurred. Please check the log file for details: {str(e)}")
        exit(1)