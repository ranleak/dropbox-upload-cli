# Dropbox Upload CLI
An easy to use automated Dropbox CLI for uploading files.

## Important Notice!
This repo is going to be seperated into two, isolated Python libraries instead of just the scripts. They will be called ```dbupload-cli``` and ```dbupload-cli-nonint``` accordingly. I'll link them here before I archive this repository.

Use ```upload.py``` for the interactive. It will automatically guide you through the upload process, more like using an app.
Use ```upload_nonint.py``` for the non-interactive. You can use it like shown below:
```
# Basic upload command
python upload.py /path/to/local/file.txt

# Specific destination directory
python upload.py /path/to/local/file.txt -d /Documents/Backups
```

Enjoy!
