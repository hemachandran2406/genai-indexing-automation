import os
import json
import time
import concurrent.futures
import argparse
from typing import List, Dict
import google.generativeai as genai
from dotenv import load_dotenv
from system_instructions import *
import logging
import psycopg2

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Model configuration from indexing.py
generation_config = {
    "temperature": 0.5,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
    system_instruction=instructions
)

def process_single_document(file_path: str) -> Dict:
    """Process a single document using the existing indexing.py logic"""
    try:
        # Upload file to Gemini
        uploaded_file = genai.upload_file(file_path, mime_type="application/pdf")
        logger.info(f"Uploaded {file_path} as {uploaded_file.uri}")

        # Wait for file processing
        while True:
            file_status = genai.get_file(uploaded_file.name)
            if file_status.state.name == "ACTIVE":
                break
            if file_status.state.name != "PROCESSING":
                raise Exception(f"File processing failed for {file_path}")
            time.sleep(5)

        # Create chat session and process
        chat_session = model.start_chat(history=[{
            "role": "user",
            "parts": [uploaded_file, "Read the system instructions and extract the key fields and return in JSON. Do not make up any information. Do not generate any other text or explanation. "]
        }])

        response = chat_session.send_message("INSERT_INPUT_HERE")
        
        try:
            # Parse the response as JSON
            parsed_result = json.loads(response.text)
        except json.JSONDecodeError:
            # If JSON parsing fails, return raw content
            parsed_result = {"raw_response": response.text}
        
        return {
            "file_path": file_path,
            "status": "success",
            "response": parsed_result,
            "error": None
        }

    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}")
        return {
            "file_path": file_path,
            "status": "error",
            "response": None,
            "error": str(e)
        }

# def insert_invoice_data(data: Dict) -> Dict:
#     """Insert processed invoice data into PostgreSQL database"""
#     try:
#         # Connect to database
#         connection = psycopg2.connect(
#             user=os.getenv("SUPABASE_DB_USER"),
#             password=os.getenv("SUPABASE_DB_PASSWORD"),
#             host=os.getenv("SUPABASE_DB_HOST"),
#             port=os.getenv("SUPABASE_DB_PORT"),
#             dbname=os.getenv("SUPABASE_DB_NAME")
#         )
#         cursor = connection.cursor()

#         # Prepare SQL query
#         query = """
#             INSERT INTO invoice (
#                 exporter, invoice_number, date_of_invoice, 
#                 for_account_and_risk_of, notify, port_of_loading, 
#                 final_destination, vessel_name, voyage_number, 
#                 sailing_date, marks_and_numbers, description_of_goods, 
#                 quantity, net_weight, gross_weight, measurement
#             ) VALUES (
#                 %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
#             )
#         """
        
#         # Prepare values - now all numeric fields are treated as text
#         values = (
#             data.get("Exporter", "-"),
#             data.get("Invoice Number", "-"),
#             data.get("Date of Invoice", None),
#             data.get("For account and risk of", "-"),
#             data.get("Notify", "-"),
#             data.get("Port of Loading", "-"),
#             data.get("Final Destination", "-"),
#             data.get("Vessel Name", "-"),
#             data.get("Voyage Number", "-"),
#             data.get("Sailing Date", None),
#             data.get("Marks and Numbers", "-"),
#             data.get("Description of Goods", "-"),
#             str(data.get("Quantity", "-")),
#             str(data.get("Net Weight", "-")),
#             str(data.get("Gross Weight", "-")),
#             str(data.get("Measurement", "-"))
#         )

#         # Execute and commit
#         cursor.execute(query, values)
#         connection.commit()
        
#         return {"status": "success", "error": None}
        
#     except Exception as e:
#         logger.error(f"Database insertion error: {str(e)}")
#         return {"status": "error", "error": str(e)}
#     finally:
#         if connection:
#             cursor.close()
#             connection.close()

def batch_process(root_folder: str) -> Dict:
    """Process all PDFs in directory tree using parallel processing"""
    results = {}
    
    # Collect all PDF files
    pdf_files = []
    for root, _, files in os.walk(root_folder):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")

    # Process files in parallel with limited workers
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # First process documents
        future_to_file = {
            executor.submit(process_single_document, fp): fp
            for fp in pdf_files
        }
        
        for future in concurrent.futures.as_completed(future_to_file):
            file_path = future_to_file[future]
            result = future.result()
            results[file_path] = result
            
            # If processing was successful, insert into database
            # if result['status'] == 'success' and result['response']:
            #     executor.submit(insert_invoice_data, result['response'])

    # Save results
    output_file = f"batch_index_results_{int(time.time())}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "processed_files": results
        }, f, indent=2)

    logger.info(f"Saved results to {output_file}")
    return results

def main():
    parser = argparse.ArgumentParser(description="Parallel Document Indexer using Gemini API")
    parser.add_argument("root_folder", help="Root directory containing PDF documents")
    # parser.add_argument("--workers", type=int,
    #                    help="Maximum parallel workers (default: 5)")
    args = parser.parse_args()
    
    if not os.path.isdir(args.root_folder):
        logger.error(f"Invalid directory: {args.root_folder}")
        return

    results = batch_process(args.root_folder)
    
    # Print summary
    success = sum(1 for r in results.values() if r['status'] == 'success')
    errors = len(results) - success
    print(f"\nIndexing Complete:")
    print(f"Total PDFs: {len(results)}")
    print(f"Successful: {success}")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    main() 