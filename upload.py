import os
import sys
import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode, UploadSessionCursor, CommitInfo

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.theme import Theme

# Set up custom colors for the Rich console
custom_theme = Theme({
    "info": "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red"
})
console = Console(theme=custom_theme)

# Chunk size for large file uploads (4MB)
CHUNK_SIZE = 4 * 1024 * 1024

def authenticate() -> dropbox.Dropbox:
    """Authenticates with Dropbox using an access token."""
    token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    
    if not token:
        console.print("[warning]DROPBOX_ACCESS_TOKEN environment variable not found.[/warning]")
        token = Prompt.ask("Please enter your Dropbox Access Token", password=True)
    
    dbx = dropbox.Dropbox(token)
    
    try:
        # Test the connection by fetching the current account
        account = dbx.users_get_current_account()
        console.print(f"[success]Successfully connected as {account.name.display_name}[/success]")
        return dbx
    except AuthError as e:
        console.print("[error]Authentication failed. Please check your access token.[/error]")
        sys.exit(1)

def get_file_paths() -> tuple[str, str]:
    """Interactively prompts the user for local and remote file paths."""
    local_path = Prompt.ask("\nEnter the [cyan]local path[/cyan] of the file to upload")
    
    # Validate local path
    local_path = os.path.expanduser(local_path)
    if not os.path.isfile(local_path):
        console.print(f"[error]File not found: {local_path}[/error]")
        sys.exit(1)
        
    filename = os.path.basename(local_path)
    
    remote_dir = Prompt.ask(
        "Enter the [cyan]remote Dropbox directory[/cyan] (leave empty for main/root)", 
        default="/"
    )
    
    # Format the remote destination path
    remote_dir = remote_dir.strip()
    if remote_dir in ["", "/"]:
        dest_path = f"/{filename}"
    else:
        # Ensure it starts with / and doesn't end with /
        if not remote_dir.startswith("/"):
            remote_dir = "/" + remote_dir
        dest_path = f"{remote_dir.rstrip('/')}/{filename}"
        
    return local_path, dest_path

def upload_file(dbx: dropbox.Dropbox, local_path: str, dest_path: str):
    """Uploads the file, using chunked upload for progress tracking and large files."""
    file_size = os.path.getsize(local_path)
    
    try:
        with open(local_path, "rb") as f:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                
                task = progress.add_task(f"[info]Uploading {os.path.basename(local_path)}...", total=file_size)
                
                # If file is smaller than our chunk size, upload it in one go
                if file_size <= CHUNK_SIZE:
                    dbx.files_upload(f.read(), dest_path, mode=WriteMode.overwrite)
                    progress.update(task, advance=file_size)
                else:
                    # For larger files, use the upload session API to upload in chunks
                    upload_session_start_result = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                    progress.update(task, advance=CHUNK_SIZE)
                    
                    cursor = UploadSessionCursor(
                        session_id=upload_session_start_result.session_id, 
                        offset=f.tell()
                    )
                    commit = CommitInfo(path=dest_path, mode=WriteMode.overwrite)

                    while f.tell() < file_size:
                        if (file_size - f.tell()) <= CHUNK_SIZE:
                            # Final chunk
                            dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                            progress.update(task, advance=(file_size - cursor.offset))
                        else:
                            # Intermediate chunks
                            dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                            cursor.offset = f.tell()
                            progress.update(task, advance=CHUNK_SIZE)

        console.print(f"\n[success]✨ File successfully uploaded to Dropbox at:[/success] [cyan]{dest_path}[/cyan]")
        
    except ApiError as err:
        console.print(f"\n[error]Dropbox API Error:[/error] {err}")
    except Exception as err:
        console.print(f"\n[error]An unexpected error occurred:[/error] {err}")

def main():
    console.print(Panel.fit(
        "[bold cyan]Dropbox Interactive Uploader[/bold cyan]\n"
        "Securely upload files from your local machine to Dropbox.",
        border_style="cyan"
    ))
    
    dbx = authenticate()
    
    while True:
        local_path, dest_path = get_file_paths()
        
        # Confirmation step
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  • [cyan]Local file:[/cyan] {local_path} ({os.path.getsize(local_path) / (1024*1024):.2f} MB)")
        console.print(f"  • [cyan]Destination:[/cyan] {dest_path}")
        
        if Confirm.ask("\nProceed with upload?", default=True):
            upload_file(dbx, local_path, dest_path)
        else:
            console.print("[warning]Upload cancelled.[/warning]")
            
        if not Confirm.ask("\nWould you like to upload another file?", default=False):
            console.print("[info]Goodbye![/info]")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user.[/warning]")
        sys.exit(0)