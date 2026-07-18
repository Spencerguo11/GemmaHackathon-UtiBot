"""Safe ZIP file extraction."""
import zipfile
from pathlib import Path
from typing import List, Tuple
import tempfile
import shutil


class ZIPExtractionError(Exception):
    """Raised when ZIP extraction fails."""
    pass


def validate_zip_file(
    zip_path: Path,
    max_files: int = 75,
    max_uncompressed_mb: int = 100,
) -> Tuple[bool, List[str], List[str]]:
    """
    Validate ZIP file safely.
    
    Args:
        zip_path: Path to ZIP file
        max_files: Maximum number of files allowed
        max_uncompressed_mb: Maximum uncompressed size in MB
    
    Returns:
        Tuple of (is_valid, pdf_files, errors)
    """
    errors = []
    pdf_files = []
    
    # Check if file exists
    if not zip_path.exists():
        errors.append(f"ZIP file not found: {zip_path}")
        return False, [], errors
    
    # Check if it's a valid ZIP
    if not zipfile.is_zipfile(zip_path):
        errors.append(f"File is not a valid ZIP archive")
        return False, [], errors
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for path traversal attacks
            for member in zf.namelist():
                # Reject absolute paths
                if member.startswith("/"):
                    errors.append(f"Rejected absolute path: {member}")
                    continue
                
                # Reject parent directory references
                if ".." in member:
                    errors.append(f"Rejected path traversal attempt: {member}")
                    continue
                
                # Only accept PDF files
                if not member.lower().endswith(".pdf"):
                    continue
                
                pdf_files.append(member)
            
            # Check file count
            if len(pdf_files) > max_files:
                errors.append(f"Too many files: {len(pdf_files)} > {max_files}")
                return False, [], errors
            
            # Check uncompressed size
            total_size = sum(zf.getinfo(name).file_size for name in pdf_files)
            total_size_mb = total_size / (1024 * 1024)
            if total_size_mb > max_uncompressed_mb:
                errors.append(f"Uncompressed size too large: {total_size_mb:.1f} MB > {max_uncompressed_mb} MB")
                return False, [], errors
    
    except zipfile.BadZipFile as e:
        errors.append(f"Corrupt ZIP file: {e}")
        return False, [], errors
    except Exception as e:
        errors.append(f"Error reading ZIP: {e}")
        return False, [], errors
    
    if not pdf_files:
        errors.append("No PDF files found in archive")
        return False, [], errors
    
    return True, pdf_files, errors


def extract_pdfs_from_zip(
    zip_path: Path,
    output_dir: Path,
    max_files: int = 75,
    max_uncompressed_mb: int = 100,
) -> Tuple[List[Path], List[str]]:
    """
    Safely extract PDF files from ZIP.
    
    Args:
        zip_path: Path to ZIP file
        output_dir: Directory to extract to
        max_files: Maximum number of files
        max_uncompressed_mb: Maximum uncompressed size
    
    Returns:
        Tuple of (extracted_paths, errors)
    """
    is_valid, pdf_files, errors = validate_zip_file(zip_path, max_files, max_uncompressed_mb)
    
    if not is_valid:
        return [], errors
    
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_paths = []
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for pdf_file in pdf_files:
                # Extract to temp first to ensure safety
                extracted_path = output_dir / Path(pdf_file).name
                
                # Read from ZIP and write to disk
                with zf.open(pdf_file) as source:
                    with open(extracted_path, 'wb') as target:
                        target.write(source.read())
                
                extracted_paths.append(extracted_path)
    
    except Exception as e:
        errors.append(f"Error extracting files: {e}")
        # Cleanup on failure
        for path in extracted_paths:
            if path.exists():
                path.unlink()
        return [], errors
    
    return extracted_paths, []
