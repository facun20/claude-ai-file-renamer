import os
import argparse
import datetime
import time
import renamer_lib as lib

def get_directory_summaries(directory_path):
    """Get summaries of all files in a directory."""
    summaries = []
    
    # Supported file extensions
    supported_extensions = [
        '.docx', '.doc',                     # Word documents
        '.xlsx', '.xls', '.csv',             # Excel/CSV files
        '.pdf',                              # PDF files
        '.jpg', '.jpeg', '.png', '.gif'      # Image files
    ]
    
    # Get a list of all files in the directory (no subdirectories)
    all_files = []
    for item in os.listdir(directory_path):
        file_path = os.path.join(directory_path, item)
        if os.path.isfile(file_path):
            all_files.append((file_path, item))
    
    print(f"Total files found in directory: {len(all_files)}")
    
    # Files to skip
    skip_files = ['claude_renamer.py', 'claude_renamer_gui.py', '.env', 'renamer_lib.py']
    
    # Process each file
    for file_path, relative_path in all_files:
        # Get file extension
        _, extension = os.path.splitext(file_path)
        extension = extension.lower()
        
        # Skip files that don't match our supported extensions
        if extension not in supported_extensions:
            print(f"Skipping unsupported file type: {relative_path}")
            continue
            
        # Skip certain files
        if relative_path in skip_files or relative_path.startswith('.'):
            print(f"Skipping file: {relative_path}")
            continue
            
        print(f"Processing file: {relative_path}")
        
        # Get basic file info
        try:
            file_size = os.path.getsize(file_path)
            file_mtime = os.path.getmtime(file_path)
            # Use library function to get content
            file_content = lib.get_file_content(file_path)
            
            summaries.append({
                "path": relative_path,
                "src_path": relative_path,
                "filename": os.path.basename(file_path),
                "extension": extension,
                "size": file_size,
                "modified": datetime.datetime.fromtimestamp(file_mtime).isoformat(),
                "content": file_content[:4000] if isinstance(file_content, str) else "",
            })
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    return summaries

def create_file_tree(summaries, api_key):
    """Process each file with Claude and get back organized structure."""
    # If no files, return empty list
    if not summaries:
        print("No files to organize.")
        return []

    # Use Claude to generate naming suggestions
    files = []
    
    # Process each file
    for i, file_info in enumerate(summaries):
        print(f"Analyzing file {i+1}/{len(summaries)}: {file_info['filename']}")
        
        try:
            # Use library function to generate naming suggestion
            suggestion = lib.create_claude_naming_suggestion(file_info, api_key)
            
            # Check if this name would cause a collision and add a unique identifier if needed
            file_dir = os.path.dirname(os.path.join(os.getcwd(), file_info["src_path"]))
            
            # Don't check uniqueness against itself if the name hasn't changed (though unlikely with this convention)
            # But here we are generating a *new* name.

            # Use library helper for unique filename
            # Note: The suggestion["new_name"] is just the filename.
            unique_name = lib.get_unique_filename(file_dir, suggestion["new_name"])
            
            if unique_name != suggestion["new_name"]:
                suggestion["new_name"] = unique_name
                suggestion["reason"] += f" (Unique identifier added to prevent naming collision)"
            
            files.append(suggestion)
            
            # Rate limit to avoid hitting API limits
            if i < len(summaries) - 1:
                time.sleep(0.5)  # 0.5 second delay between requests
                
        except Exception as e:
            print(f"Error processing {file_info['filename']}: {str(e)}")
            # Fall back to smart naming
            files.append(lib.smart_fallback_naming(file_info))
    
    return files

def rename_files(src_dir, files, auto_yes=False):
    """Rename files in place following the naming convention."""
    print("\nProposed file renaming:")
    print("======================")
    
    for file in files:
        src_path = os.path.join(src_dir, file["src_path"])
        dir_name = os.path.dirname(src_path)
        new_path = os.path.join(dir_name, file["new_name"])
        
        print(f"\nFrom: {os.path.basename(src_path)}")
        print(f"To:   {file['new_name']}")
        if "reason" in file:
            print(f"Reason: {file['reason']}")
    
    if not auto_yes:
        proceed = input("\nProceed with renaming these files? (y/n): ").lower().strip()
        if proceed != 'y':
            print("Operation cancelled.")
            return
    
    # Rename files in place
    success_count = 0
    error_count = 0
    
    for file in files:
        src_path = os.path.join(src_dir, file["src_path"])
        dir_name = os.path.dirname(src_path)
        new_path = os.path.join(dir_name, file["new_name"])
        
        try:
            os.rename(src_path, new_path)
            print(f"Renamed: {os.path.basename(src_path)} -> {file['new_name']}")
            success_count += 1
        except Exception as e:
            print(f"Error renaming {src_path}: {str(e)}")
            error_count += 1
    
    print(f"\nRenamed {success_count} files successfully. {error_count} files failed.")

def main():
    parser = argparse.ArgumentParser(description="Claude-Powered File Renamer - Rename files using standardized naming conventions")
    parser.add_argument("directory", help="Directory containing files to rename")
    parser.add_argument("--auto-yes", action="store_true", help="Automatically proceed without confirmation")
    parser.add_argument("--api-key", help="Claude API key (required)")
    args = parser.parse_args()
    
    # Get API key from args or environment
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: Claude API key not provided. Use --api-key or set the ANTHROPIC_API_KEY environment variable.")
        return
    
    print(f"Analyzing files in: {args.directory}")
    
    # Get file summaries
    summaries = get_directory_summaries(args.directory)
    print(f"Found {len(summaries)} files to process")
    
    if not summaries:
        print("No files found to rename. Try adding some files to the directory.")
        return
    
    # Get renaming suggestions
    files = create_file_tree(summaries, api_key)
    
    if not files:
        print("Error: Could not get file renaming suggestions.")
        return
    
    # Rename files in place
    rename_files(args.directory, files, args.auto_yes)

if __name__ == "__main__":
    main()
