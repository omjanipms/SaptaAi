/**
 * Google Apps Script for Matrimonial Form Webhook
 * This script should be attached to your Google Form to send webhook notifications
 * when the form is submitted.
 */

// Configuration - Update these values
const WEBHOOK_URL = 'http://localhost:5000/webhook'; // Replace with your webhook server URL
const WEBHOOK_SECRET = '-O_h5p9grG2WaoK9Xrt9sNNPr98v6szGDyIEHBH30Is'; // Replace with your webhook secret

/**
 * Trigger function that runs when the form is submitted
 */
function onFormSubmit(e) {
  try {
    // Get form response data
    const formResponse = e.response;
    const itemResponses = formResponse.getItemResponses();
    const timestamp = formResponse.getTimestamp();
    const responseId = formResponse.getId();
    
    // Get form information
    const form = e.source;
    const formId = form.getId();
    const formTitle = form.getTitle();
    
    // Create webhook payload
    const webhookData = {
      formId: formId,
      formTitle: formTitle,
      responseId: responseId,
      createTime: timestamp.toISOString(),
      submissionData: {
        timestamp: timestamp.toISOString(),
        responseId: responseId
      }
    };
    
    // Add form responses to the payload
    const responses = {};
    itemResponses.forEach(function(itemResponse) {
      const question = itemResponse.getItem().getTitle();
      const answer = itemResponse.getResponse();
      responses[question] = answer;
    });
    webhookData.submissionData.responses = responses;
    
    // Send webhook notification
    const success = sendWebhookNotification(webhookData);
    
    if (success) {
      console.log('Webhook notification sent successfully');
      // Optionally log to a spreadsheet for debugging
      logWebhookSuccess(formId, responseId, timestamp);
    } else {
      console.error('Failed to send webhook notification');
      logWebhookError(formId, responseId, timestamp, 'Failed to send webhook');
    }
    
  } catch (error) {
    console.error('Error in onFormSubmit:', error);
    logWebhookError(e.source.getId(), e.response.getId(), e.response.getTimestamp(), error.toString());
  }
}

/**
 * Send webhook notification to the server
 */
function sendWebhookNotification(data) {
  try {
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${WEBHOOK_SECRET}`
      },
      payload: JSON.stringify(data),
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(WEBHOOK_URL, options);
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    
    console.log(`Webhook response: ${responseCode} - ${responseText}`);
    
    // Consider success if we get a 2xx response
    return responseCode >= 200 && responseCode < 300;
    
  } catch (error) {
    console.error('Error sending webhook notification:', error);
    return false;
  }
}

/**
 * Log successful webhook notifications to a spreadsheet
 */
function logWebhookSuccess(formId, responseId, timestamp) {
  try {
    // You can create a separate spreadsheet for logging if needed
    const logSheetId = 'YOUR_LOG_SPREADSHEET_ID'; // Optional: Replace with your log spreadsheet ID
    if (logSheetId && logSheetId !== 'YOUR_LOG_SPREADSHEET_ID') {
      const logSheet = SpreadsheetApp.openById(logSheetId).getActiveSheet();
      logSheet.appendRow([
        timestamp,
        formId,
        responseId,
        'SUCCESS',
        'Webhook sent successfully'
      ]);
    }
  } catch (error) {
    console.error('Error logging webhook success:', error);
  }
}

/**
 * Log webhook errors to a spreadsheet
 */
function logWebhookError(formId, responseId, timestamp, errorMessage) {
  try {
    // You can create a separate spreadsheet for logging if needed
    const logSheetId = 'YOUR_LOG_SPREADSHEET_ID'; // Optional: Replace with your log spreadsheet ID
    if (logSheetId && logSheetId !== 'YOUR_LOG_SPREADSHEET_ID') {
      const logSheet = SpreadsheetApp.openById(logSheetId).getActiveSheet();
      logSheet.appendRow([
        timestamp,
        formId,
        responseId,
        'ERROR',
        errorMessage
      ]);
    }
  } catch (error) {
    console.error('Error logging webhook error:', error);
  }
}

/**
 * Test function to manually trigger webhook (for testing purposes)
 */
function testWebhook() {
  const testData = {
    formId: '1Hn25v05F0NfyRRv2aCQt236qktrd6rdZJctldHnONUc',
    formTitle: 'Matrimonial Registration Form',
    responseId: 'test-response-id-' + new Date().getTime(),
    createTime: new Date().toISOString(),
    submissionData: {
      timestamp: new Date().toISOString(),
      responseId: 'test-response-id-' + new Date().getTime(),
      responses: {
        'Email': 'test@example.com',
        'Full Name': 'Test User',
        'Gender': 'Male'
      }
    }
  };
  
  const success = sendWebhookNotification(testData);
  console.log('Test webhook result:', success);
}

/**
 * Setup function to create form trigger
 * Run this once to set up the form submission trigger
 */
function setupFormTrigger() {
  try {
    // Get the form
    const form = FormApp.openById('1Hn25v05F0NfyRRv2aCQt236qktrd6rdZJctldHnONUc');
    
    // Delete existing triggers
    const triggers = ScriptApp.getProjectTriggers();
    triggers.forEach(function(trigger) {
      if (trigger.getHandlerFunction() === 'onFormSubmit') {
        ScriptApp.deleteTrigger(trigger);
      }
    });
    
    // Create new trigger
    ScriptApp.newTrigger('onFormSubmit')
      .forForm(form)
      .onFormSubmit()
      .create();
    
    console.log('Form trigger set up successfully');
    
  } catch (error) {
    console.error('Error setting up form trigger:', error);
  }
}

/**
 * Function to check webhook server status
 */
function checkWebhookServerStatus() {
  try {
    const statusUrl = WEBHOOK_URL.replace('/webhook', '/health');
    const response = UrlFetchApp.fetch(statusUrl, {
      method: 'GET',
      muteHttpExceptions: true
    });
    
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    
    console.log(`Server status: ${responseCode} - ${responseText}`);
    return responseCode === 200;
    
  } catch (error) {
    console.error('Error checking webhook server status:', error);
    return false;
  }
} 