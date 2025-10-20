import os
import re
import tempfile
import requests
from loguru import logger
from typing import Tuple, Optional

# --- Constants ---
GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://localhost:3000")

OFFICE_EXTENSIONS = {
    ".123", ".602", ".abw", ".bib", ".bmp", ".cdr", ".cgm", ".cmx", ".csv", ".cwk", ".dbf", ".dif", 
    ".doc", ".docm", ".docx", ".dot", ".dotm", ".dotx", ".dxf", ".emf", ".eps", ".epub", ".fodg", 
    ".fodp", ".fods", ".fodt", ".fopd", ".gif", ".htm", ".html", ".hwp", ".jpeg", ".jpg", ".key", 
    ".ltx", ".lwp", ".mcw", ".met", ".mml", ".mw", ".numbers", ".odd", ".odg", ".odm", ".odp", 
    ".ods", ".odt", ".otg", ".oth", ".otp", ".ots", ".ott", ".pages", ".pbm", ".pcd", ".pct", 
    ".pcx", ".pdb", ".pgm", ".png", ".pot", ".potm", ".potx", ".ppm", ".pps", ".ppt", ".pptm", 
    ".pptx", ".psd", ".psw", ".pub", ".pwp", ".pxl", ".ras", ".rtf", ".sda", ".sdc", ".sdd", 
    ".sdp", ".sdw", ".sgl", ".slk", ".smf", ".stc", ".std", ".sti", ".stw", ".svg", ".svm", 
    ".swf", ".sxc", ".sxd", ".sxg", ".sxi", ".sxm", ".sxw", ".tga", ".tif", ".tiff", ".txt", 
    ".uof", ".uop", ".uos", ".uot", ".vdx", ".vor", ".vsd", ".vsdm", ".vsdx", ".wb2", ".wk1", 
    ".wks", ".wmf", ".wpd", ".wpg", ".wps", ".xbm", ".xhtml", ".xls", ".xlsb", ".xlsm", ".xlsx", 
    ".xlt", ".xltm", ".xltx", ".xlw", ".xml", ".xpm", ".zabw"
}
# --- End Constants ---

def _convert_url_to_pdf(url_string: str, output_pdf_path: str, timeout: int = None) -> bool:
    """Uses Gotenberg to convert a URL to PDF."""
    endpoint = f"{GOTENBERG_URL}/forms/chromium/convert/url"
    logger.info(f"Converting URL to PDF: {url_string} -> {output_pdf_path}")
    try:
        response = requests.post(endpoint, data={"url": url_string}, stream=True)
        response.raise_for_status()
        with open(output_pdf_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Successfully converted URL to PDF: {output_pdf_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Gotenberg URL conversion failed for {url_string}. Error: {e}")
        return False

def _convert_office_to_pdf(office_file_path: str, output_pdf_path: str, timeout: int = None) -> bool:
    """Uses Gotenberg to convert an Office document to PDF."""
    endpoint = f"{GOTENBERG_URL}/forms/libreoffice/convert"
    logger.info(f"Converting Office document to PDF: {office_file_path} -> {output_pdf_path}")
    if not os.path.exists(office_file_path):
        logger.error(f"Office file not found: {office_file_path}")
        return False
    try:
        with open(office_file_path, 'rb') as f:
            files = {"files": (os.path.basename(office_file_path), f)}
            response = requests.post(endpoint, files=files, stream=True)
            response.raise_for_status()
        with open(output_pdf_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Successfully converted Office document to PDF: {output_pdf_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Gotenberg Office document conversion failed for {office_file_path}. Error: {e}")
        return False
    except FileNotFoundError: # Should be caught by os.path.exists, but as a safeguard
        logger.error(f"Office file not found (during open): {office_file_path}")
        return False

def _generate_safe_temp_filename(original_input: str, base_temp_dir: str, prefix: str = "conv", suffix: str = ".pdf") -> str:
    """Generates a safe temporary filename within base_temp_dir based on the original input."""
    base_name = os.path.basename(original_input)
    if original_input.startswith("http"): # For URLs
        # Try to get a meaningful name from URL path, remove query params
        name_part = base_name.split('?')[0]
        # Limit length and sanitize
        safe_base = re.sub(r'[^a-zA-Z0-9_.-]', '_', name_part)[:50]
        if not safe_base or safe_base.endswith(('.htm', '.html', '.php', '.asp', '.aspx', '')) : # if empty or common web ext
             safe_base = "webpage" # default if name is too generic or just an extension
        
    else: # For local files
        name_part = os.path.splitext(base_name)[0]
        safe_base = re.sub(r'[^a-zA-Z0-9_.-]', '_', name_part)[:50]

    return os.path.join(base_temp_dir, f"{prefix}_{safe_base}{suffix}")


def ensure_pdf(file_input: str, job_temp_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Ensures the input is a PDF file. If it's a URL or Office document,
    it attempts to convert it to PDF using Gotenberg.

    Args:
        file_input: Path to a local file or a URL.
        job_temp_dir: The dedicated temporary directory for this job's files.

    Returns:
        A tuple: (path_to_pdf_for_processing, path_of_temp_pdf_to_delete_later).
        Returns (None, None) if processing/conversion fails.
    """
    logger.info(f"Ensuring PDF for input: {file_input}")
    
    file_ext = os.path.splitext(file_input)[1].lower()

    if file_input.startswith("http://") or file_input.startswith("https://"):
        logger.info(f"Input is a URL: {file_input}")
        temp_pdf_path = _generate_safe_temp_filename(file_input, job_temp_dir, prefix="url")
        if _convert_url_to_pdf(file_input, temp_pdf_path):
            return temp_pdf_path, temp_pdf_path # Process this temp PDF, and delete it later
        else:
            logger.error(f"Failed to convert URL to PDF: {file_input}")
            return None, None
            
    elif file_ext in OFFICE_EXTENSIONS:
        logger.info(f"Input is an Office/document file: {file_input} (ext: {file_ext})")
        if not os.path.exists(file_input):
            logger.error(f"Source Office/document file not found: {file_input}")
            return None, None
        temp_pdf_path = _generate_safe_temp_filename(file_input, job_temp_dir, prefix="office")
        if _convert_office_to_pdf(file_input, temp_pdf_path):
            return temp_pdf_path, temp_pdf_path # Process this temp PDF, and delete it later
        else:
            logger.error(f"Failed to convert Office/document to PDF: {file_input}")
            return None, None
            
    elif file_ext == ".pdf":
        logger.info(f"Input is already a PDF file: {file_input}")
        if not os.path.exists(file_input):
            logger.error(f"Source PDF file not found: {file_input}")
            return None, None
        return file_input, None # Process this PDF, no temp file to delete for this step
        
    else:
        logger.warning(f"Unsupported file type or scheme for input: {file_input} (ext: {file_ext})")
        return None, None

# Example Usage (can be removed or kept for direct testing of this module)
if __name__ == '__main__':
    logger.add(lambda _: print(_.getMessage())) # Simple logger for testing

    # Create a dummy temp dir for testing
    test_job_temp_dir = tempfile.mkdtemp(prefix="converter_test_")
    logger.info(f"Test temporary directory: {test_job_temp_dir}")

    # Test URL
    # Replace with a live URL for actual testing, e.g., "https://www.google.com"
    # For CI/offline tests, this will likely fail unless Gotenberg is mocked or a local static page is used.
    # test_url = "https://www.orimi.com/pdf-test.pdf" # A direct PDF link
    test_url = "https://www.example.com"
    pdf_path, temp_to_delete = ensure_pdf(test_url, test_job_temp_dir)
    if pdf_path:
        logger.info(f"URL test successful. PDF at: {pdf_path}, To delete: {temp_to_delete}")
        # if temp_to_delete and os.path.exists(temp_to_delete): os.remove(temp_to_delete) # Clean up
    else:
        logger.error("URL test failed.")

    # Test Office (dummy file - will fail conversion unless a real .docx is present and Gotenberg running)
    # Create a dummy docx for testing structure
    dummy_docx_path = os.path.join(test_job_temp_dir, "test.docx")
    try:
        with open(dummy_docx_path, "w") as f_dummy:
            f_dummy.write("This is a test docx.")
        logger.info(f"Created dummy file: {dummy_docx_path}")
        pdf_path_office, temp_to_delete_office = ensure_pdf(dummy_docx_path, test_job_temp_dir)
        if pdf_path_office:
            logger.info(f"Office test successful (simulated). PDF at: {pdf_path_office}, To delete: {temp_to_delete_office}")
            # if temp_to_delete_office and os.path.exists(temp_to_delete_office): os.remove(temp_to_delete_office)
        else:
            logger.error("Office test failed (simulated - Gotenberg communication might fail).")
    except Exception as e_main_test:
        logger.error(f"Error in __main__ test block: {e_main_test}")
    finally:
        # Clean up the main test temporary directory
        import shutil
        if os.path.exists(test_job_temp_dir):
            # shutil.rmtree(test_job_temp_dir)
            # logger.info(f"Cleaned up test temporary directory: {test_job_temp_dir}")
            logger.info(f"Test temporary directory {test_job_temp_dir} and its contents are left for inspection.")
            pass 