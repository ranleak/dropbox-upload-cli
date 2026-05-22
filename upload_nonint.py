import os
import sys
import argparse
import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode, UploadSessionCursor, CommitInfo

# Chunk size for large file uploads (4MB)
CHUNK_SIZE = 4 * 1024 * 1024

def authenticate() -> dropbox.Dropbox:
    """Authenticates with Dropbox using the environment variable."""
    token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    
    if not token:
        print("Error: DROPBOX_ACCESS_TOKEN environment variable not found.")
        sys.exit(1)
    
    dbx = dropbox.Dropbox(token)
    
    try:
        # Test the connection by fetching the current account
        account = dbx.users_get_current_account()
        print(f"Successfully connected as {account.name.display_name}")
        return dbx
    except AuthError:
        print("Error: Authentication failed. Please check your access token.")
        sys.exit(1)

def format_destination_path(local_path: str, remote_dir: str) -> str:
    """Formats the remote destination path correctly."""
    filename = os.path.basename(local_path)
    remote_dir = remote_dir.strip()
    
    if remote_dir in ["", "/"]:
        return f"/{filename}"
    else:
        # Ensure it starts with / and doesn't end with /
        if not remote_dir.startswith("/"):
            remote_dir = "/" + remote_dir
        return f"{remote_dir.rstrip('/')}/{filename}"

def upload_file(dbx: dropbox.Dropbox, local_path: str, dest_path: str):
    """Uploads the file, using chunked upload for large files."""
    file_size = os.path.getsize(local_path)
    print(f"Uploading {os.path.basename(local_path)} ({file_size / (1024*1024):.2f} MB)...")
    
    try:
        with open(local_path, "rb") as f:
            # If file is smaller than our chunk size, upload it in one go
            if file_size <= CHUNK_SIZE:
                dbx.files_upload(f.read(), dest_path, mode=WriteMode.overwrite)
            else:
                # For larger files, use the upload session API to upload in chunks
                upload_session_start_result = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                
                cursor = UploadSessionCursor(
                    session_id=upload_session_start_result.session_id, 
                    offset=f.tell()
                )
                commit = CommitInfo(path=dest_path, mode=WriteMode.overwrite)

                while f.tell() < file_size:
                    if (file_size - f.tell()) <= CHUNK_SIZE:
                        # Final chunk
                        dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                    else:
                        # Intermediate chunks
                        dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                        cursor.offset = f.tell()

        print(f"Success: File successfully uploaded to Dropbox at {dest_path}")
        
    except ApiError as err:
        print(f"Dropbox API Error: {err}")
        sys.exit(1)
    except Exception as err:
        print(f"An unexpected error occurred: {err}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Securely upload files from your local machine to Dropbox.")
    parser.add_argument("local_path", help="The local path of the file to upload")
    parser.add_argument("-d", "--dest", default="/", help="The remote Dropbox directory (defaults to root '/')")
    
    args = parser.parse_args()
    
    # Validate local path
    local_path = os.path.expanduser(args.local_path)
    if not os.path.isfile(local_path):
        print(f"Error: File not found: {local_path}")
        sys.exit(1)
        
    dest_path = format_destination_path(local_path, args.dest)
    
    # Authenticate and execute upload
    dbx = authenticate()
    upload_file(dbx, local_path, dest_path)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)