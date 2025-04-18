import streamlit as st
import os
import time
from llm_batch_indexer import batch_process, process_single_document, logger

# Add the logo at the top left corner
def add_logo():
    """Display the company logo in the top left corner."""
    logo_path = "logo4.png"  # Path to the logo file
    st.markdown(
        f"""
        <div style="display: flex; align-items: left; justify-content: flex-start;">
            <img src="data:image/png;base64,{get_base64_image(logo_path)}" alt="Company Logo" style="height: 50px;">

        </div>
        """,
        unsafe_allow_html=True
    )

def get_base64_image(image_path):
    """Convert an image to a base64 string."""
    import base64
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def display_file_list(root_folder):
    """Display the list of PDF files with icons in Streamlit"""
    pdf_files = []
    
    # Collect all PDF files
    for root, _, files in os.walk(root_folder):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    if pdf_files:
        st.subheader(f"📄 Found {len(pdf_files)} PDF files:")
        for file_path in pdf_files:
            st.markdown(f"📑 **{os.path.basename(file_path)}**")
        st.markdown("---")
    else:
        st.warning("⚠️ No PDF files found in the specified directory")
    
    return pdf_files


def show_processing_animation_single(file_path, result):
    """Show processing animation for a single file"""
    with st.status("🔍 Agent is analyzing the document...", expanded=True) as status:
        st.write(f"🔍 Processing {os.path.basename(file_path)}...")
        time.sleep(1)  # Simulate processing time
        
        if result['status'] == 'success':
            status.update(label="✅ Processing complete!", state="complete")
        else:
            status.update(label="❌ Processing failed!", state="error")


def show_processing_animation_batch(root_folder, results):
    """Show processing animation with real-time updates for batch processing"""
    total_files = len(results)
    processed_files = 0
    
    with st.status("🔍 Agent is analyzing the documents...", expanded=True) as status:
        # Loading documents phase
        st.write("📂 Loading documents...")
        time.sleep(0.5)  # Simulate document loading
        
        # Processing phase
        for file_path, result in results.items():
            processed_files += 1
            st.write(f"🔍 Processing {os.path.basename(file_path)} ({processed_files}/{total_files})...")
            
            # Simulate actual processing time
            if result['status'] == 'success':
                time.sleep(1)  # Simulate extraction time
            else:
                time.sleep(0.5)  # Simulate error handling time
            
        status.update(label="✅ Processing complete!", state="complete")


def display_results(results):
    """Display processing results in Streamlit"""
    # Display detailed view directly
    st.subheader("📋 Extracted Data")
    for file_path, result in results.items():
        with st.expander(f"📄 {os.path.basename(file_path)}", expanded=True):
            if result['status'] == 'success':
                st.success("✅ Processing successful")
                
                # Convert JSON to table
                if isinstance(result['response'], dict):
                    detail_table = []
                    for key, value in result['response'].items():
                        detail_table.append({
                            "Field": key,
                            "Value": str(value) if value is not None else "N/A"
                        })
                    
                    st.dataframe(
                        detail_table,
                        column_config={
                            "Field": "Field Name",
                            "Value": "Extracted Value"
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.warning("⚠️ Response is not in JSON format")
                    st.json(result['response'])
            else:
                st.error(f"❌ Error: {result['error']}")


def main():
    st.set_page_config(page_title="Document Processor", page_icon="📄", layout="wide")
    
    # Add the logo at the top
    add_logo()
    
    st.title("📄 Document Processing Agent")
    st.markdown("Choose an option to process PDF files with our AI agent")
    
    # Add radio buttons for selecting the processing mode
    processing_mode = st.radio(
        "Select processing mode:",
        options=["Batch Process Folder", "Process Single PDF"]
    )
    
    if processing_mode == "Batch Process Folder":
        # Batch processing mode
        root_folder = st.text_input("📂 Enter root folder path:", placeholder="e.g., /path/to/documents")
        
        if root_folder and os.path.isdir(root_folder):
            # Display file list
            pdf_files = display_file_list(root_folder)
            
            # Only show batch process button if PDF files are found
            if pdf_files:
                if st.button("🚀 Start Batch Processing", type="primary"):
                    with st.spinner("Initializing batch processing..."):
                        try:
                            # Process once and store results
                            results = batch_process(root_folder)
                            show_processing_animation_batch(root_folder, results)
                            display_results(results)
                        except Exception as e:
                            logger.error(f"Batch processing failed: {str(e)}")
                            st.error(f"❌ Batch processing failed: {str(e)}")
        elif root_folder:
            st.error("❌ Invalid directory path")
    
    elif processing_mode == "Process Single PDF":
        # Single file processing mode
        uploaded_file = st.file_uploader("📂 Upload a PDF file", type="pdf")
        
        if uploaded_file:
            file_path = os.path.join(os.getcwd(), uploaded_file.name)
            
            # Save the uploaded file temporarily
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            if st.button("🚀 Start Processing Single File", type="primary"):
                with st.spinner("Initializing single file processing..."):
                    try:
                        # Process the single file
                        result = process_single_document(file_path)
                        show_processing_animation_single(file_path, result)
                        display_results({file_path: result})
                    except Exception as e:
                        logger.error(f"Single file processing failed: {str(e)}")
                        st.error(f"❌ Single file processing failed: {str(e)}")


if __name__ == "__main__":
    main()