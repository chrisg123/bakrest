# BakRest

**BakRest** is a tool designed to simplify the process of restoring SQL Server
`.bak` files to a remote SQL Server instance. It bridges the gap between the
client's environment and a SQL Server running in a containerized or remote
environment by leveraging a REST API for file uploads.

**Note**: This tool was created as an aid for development purposes. It is not
intended as a production-grade solution for database restoration.


## Key Features

- **File Upload**: Upload large `.bak` files to a remote server using an
  HTTP-based API.
- **Database Restore**: Restore the uploaded `.bak` file to a SQL Server
  instance, with support for logical file remapping and progress monitoring.
- **Progress Tracking**: Provides progress updates for both file uploads and
  database restoration.

## How It Works

1. **File Upload**:
   - The `.bak` file is uploaded to the remote server using a REST API.
   - Progress of the upload is monitored and displayed.

2. **Database Restoration**:
   - The uploaded `.bak` file is restored to the SQL Server.
   - Logical file names in the `.bak` are remapped to fit the remote environment.
   - Progress of the restoration is queried using SQL Server's system views.


## Usage

See:
```bash
bakrest --help
```

## REST API Assumptions

This project does not include the implementation of the REST API running on the
remote server. Instead, it expects the API to behave in a specific way, as
defined by the interactions in `FileUploader.py` and `DatabaseRestorer.py`.

## Licence

**BakRest** is released under the MIT License. See the [LICENSE](LICENSE) file for
more details.
