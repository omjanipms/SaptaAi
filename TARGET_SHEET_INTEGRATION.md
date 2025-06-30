# Target Google Sheet Integration

## Overview
This document describes the integration of a target Google Sheet to track users who have received email notifications from the matrimonial matching system.

## Changes Made

### 1. New Constants Added
Added constants for the target Google Sheet in `app.py`:

```python
# Target Google Sheet constants for tracking sent emails
TARGET_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TARGET_SERVICE_ACCOUNT_FILE = "service_account_target.json"
TARGET_SPREADSHEET_ID = "16UglHoVyKT97BFCkbXZSAiPcoKGjRLdjhQCb3X6jg8w"
TARGET_RANGE_NAME = "Sheet1!A:M"  # Updated to include column M for email text: Sr no, name, whatsappnumber, email, birth date, location, pdf_url, top1_url, top2_url, top3_url, top4_url, top5_url, email_text

# Google Drive constants for PDF upload
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_SERVICE_ACCOUNT_FILE = "service_account_target.json"  # Using same service account for Drive
```

### 2. New Functions Added

#### `test_target_sheet_connection()`
- Tests the connection to the target Google Sheet
- Verifies the service account credentials
- Checks if the sheet is accessible and readable
- Logs the sheet structure (number of rows, headers)

#### `upload_pdf_to_drive_and_get_url(pdf_filename, user_name)`
- Uploads the last response PDF to Google Drive
- Creates a shareable URL for the PDF
- Makes the file publicly accessible (anyone with the link can view)
- Returns the shareable URL for the target sheet

#### `upload_multiple_pdfs_to_drive_and_get_urls(pdf_files, user_name)`
- Uploads multiple PDFs (top 5 match PDFs) to Google Drive
- Creates shareable URLs for each PDF
- Makes all files publicly accessible (anyone with the link can view)
- Returns a list of shareable URLs for the target sheet
- Handles errors gracefully for individual PDF uploads

#### `extract_compatibility_text_from_email(email_message)`
- Extracts the compatibility calculation portion from the email message
- Uses regex patterns to identify numbered matches with compatibility percentages
- Returns only the compatibility breakdown section
- Handles fallback patterns if the main pattern doesn't match
- Logs extraction success/failure for debugging

#### `write_name_to_target_sheet(user_name, whatsapp_number=None, email_address=None, birth_date=None, location=None, pdf_url=None, top_match_urls=None, email_text=None)`
- Writes the user name, WhatsApp number, email, birth date, location, PDF URL, top 5 match PDF URLs, and email text to the target Google Sheet
- Automatically calculates and increments the Sr No
- Adds the name in column B (name column)
- Adds the WhatsApp number in column C (WhatsApp number column)
- Adds the email address in column D (email column)
- Adds the birth date in column E (birth date column)
- Adds the location in column F (location column) as comma-separated values
- Adds the PDF URL in column G (PDF URL column)
- Adds the top 1 match PDF URL in column H (top1_url column)
- Adds the top 2 match PDF URL in column I (top2_url column)
- Adds the top 3 match PDF URL in column J (top3_url column)
- Adds the top 4 match PDF URL in column K (top4_url column)
- Adds the top 5 match PDF URL in column L (top5_url column)
- Adds the email text in column M (email_text column)
- Includes comprehensive error handling and validation

### 3. Modified Functions

#### `process_matrimonial_data(df)`
- Now extracts WhatsApp number, birth date, and location from source sheet
- Returns WhatsApp number, birth date, and location along with other user data
- Automatically detects WhatsApp number, birth date, and location columns using pattern matching
- Combines City, State, and Country into a comma-separated location string

#### `send_email_with_multiple_pdfs()`
- Added PDF URL functionality for both last response and top 5 match PDFs
- Added email text extraction functionality
- Automatically uploads the last response PDF to Google Drive
- Automatically uploads the top 5 match PDFs to Google Drive
- Creates shareable URLs for all PDFs
- Extracts compatibility text from the email message
- Calls `write_name_to_target_sheet()` with name, WhatsApp number, email, birth date, location, PDF URL, top match URLs, and email text when email is sent successfully
- Maintains backward compatibility with existing code

### 4. Updated Function Calls
All calls to `send_email_with_multiple_pdfs()` have been updated to include `user_name`, `whatsapp_number`, `email_address`, `birth_date`, and `location` parameters:
- `process_new_matrimonial_registration()`
- `process_specific_user_by_email()`

## Target Sheet Structure
The target Google Sheet should have the following structure:
- **Column A**: Sr No (auto-incremented)
- **Column B**: Name (from source sheet)
- **Column C**: WhatsApp Number (from source sheet)
- **Column D**: Email Address (from source sheet)
- **Column E**: Birth Date (from source sheet)
- **Column F**: Location (from source sheet) - comma-separated format
- **Column G**: PDF URL (from Google Drive) - shareable link to the last response PDF
- **Column H**: Top 1 Match PDF URL (from Google Drive) - shareable link to the first match PDF
- **Column I**: Top 2 Match PDF URL (from Google Drive) - shareable link to the second match PDF
- **Column J**: Top 3 Match PDF URL (from Google Drive) - shareable link to the third match PDF
- **Column K**: Top 4 Match PDF URL (from Google Drive) - shareable link to the fourth match PDF
- **Column L**: Top 5 Match PDF URL (from Google Drive) - shareable link to the fifth match PDF
- **Column M**: Email Text (from email message) - compatibility calculation portion

## Source Sheet Integration
The system automatically extracts data from the source sheet:
- **Name**: `"Full Name"` column
- **WhatsApp Number**: `"WhatsApp Number ( CCxxxxxyyyyy format )"` column
- **Email**: Email column (automatically detected)
- **Birth Date**: `"Birth Date"` column (automatically detected)
- **Location**: Combines City, State, and Country columns into comma-separated format
  - **City**: `"City"` column (cleaned of prefixes like "City:", "Prefer", etc.)
  - **State**: `"State"` column
  - **Country**: `"Country"` column
- **PDF URL**: Automatically generated by uploading the last response PDF to Google Drive
- **Top Match PDF URLs**: Automatically generated by uploading the top 5 match PDFs to Google Drive
- **Email Text**: Automatically extracted from the email message compatibility section
- **Pattern Matching**: Automatically detects relevant columns
- **Fallback**: If any field is not found, the corresponding column remains empty

## Location Format
The location is formatted as: `"City, State, Country"`
- Example: `"Ahmedabad, Gujarat, India"`
- If any component is missing, it's omitted from the string
- City values are cleaned of common prefixes before being included

## PDF URL Generation
The PDF URLs are automatically generated by:

### Last Response PDF URL (Column G)
1. Identifying the last response PDF file (`Last_Response_Profile.pdf`)
2. Uploading it to Google Drive using the target service account
3. Creating a shareable URL with public read access
4. Storing the URL in column G of the target sheet

### Top 5 Match PDF URLs (Columns H-L)
1. Identifying the top 5 match PDF files (`Profile_1_match.pdf`, `Profile_2_match.pdf`, etc.)
2. Uploading each PDF to Google Drive using the target service account
3. Creating shareable URLs with public read access for each PDF
4. Storing the URLs in columns H-L of the target sheet in order
5. The URL format is: `https://drive.google.com/file/d/{file_id}/view?usp=sharing`

## Email Text Extraction
The email text (compatibility calculation portion) is automatically extracted by:

### Pattern Matching
1. Looking for numbered matches (1., 2., 3., etc.) in the email message
2. Identifying compatibility percentages and breakdown sections
3. Extracting the complete compatibility calculation portion
4. Storing the extracted text in column M of the target sheet

### Example Extracted Text
```
1. om jani - 58.1% overall compatibility
  Breakdown:
    - Personal, Professional & Family: 85.0%
    - Favorites, Likes & Hobbies: 10.0%
    - Other Requirement and Preferences: 79.2%

2. om gajjar - 52.1% overall compatibility
  Breakdown:
    - Personal, Professional & Family: 54.5%
    - Favorites, Likes & Hobbies: 36.1%
    - Other Requirement and Preferences: 65.6%
```

### Fallback Patterns
- If the main pattern doesn't match, the system tries fallback patterns
- Ensures compatibility text is extracted even if the format varies slightly
- Logs extraction success/failure for debugging purposes

## Error Handling
- If PDF upload to Drive fails, the corresponding PDF URL column remains empty
- If email text extraction fails, the email text column remains empty
- If target sheet operations fail, the main email sending process continues
- All errors are logged for debugging purposes
- The system gracefully handles missing service account files or API errors
- Individual PDF upload failures don't affect other PDF uploads

## Security Considerations
- PDFs uploaded to Drive are set to "anyone with the link can view"
- The target service account has minimal required permissions
- PDF URLs are publicly accessible but not searchable
- No sensitive data is exposed in the URLs
- Email text extraction only captures compatibility information, not personal details

## Benefits
- Complete tracking of all sent emails with user details
- Easy access to user PDFs via shareable links
- Easy access to all match PDFs via shareable links
- Automated PDF management and URL generation
- Automated email text extraction and storage
- Comprehensive audit trail for all matching activities
- No manual intervention required for PDF sharing or text extraction
- Organized storage of all PDFs with clear naming conventions
- Complete compatibility calculation history for analysis

## Notes
- All existing functionality remains unchanged
- The target sheet operations are non-blocking (failures don't stop email sending)
- The system gracefully handles missing service account files or API errors
- WhatsApp numbers, emails, birth dates, and locations are automatically extracted from the source sheet
- If any field is not available, the corresponding column remains empty
- The email address used is the same one to which the match email was sent
- Birth dates are copied exactly as they appear in the source sheet
- Location combines City, State, and Country into a single comma-separated field
- City values are automatically cleaned of common prefixes for better formatting
- PDF URLs are automatically generated and stored for easy access
- Top match PDFs are sorted by their profile number before uploading
- All PDFs are named with user name and type for easy identification
- Email text extraction uses regex patterns for reliable compatibility text identification
- The system handles variations in email message format gracefully 