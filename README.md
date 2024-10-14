Download multiple files

This small tool, a python code, can be used to download multiple files.

List of urls to download can be specified in a file, each line of file is URL to download a file, i.e.
```
https://github.com/verigak/progress/blob/master/test_progress.py
```


> **_NOTE:_**  For Chrome user, use [Link Grabber extension](https://chromewebstore.google.com/detail/link-grabber/caodelkhipncidmoebgbbeemedohcdma) to get multiple download links of a webpage

# REQUIREMENT

python3 with following package installed
- tqdm

# USAGE

```
usage: Download file [-h] [--fileurl FILEURL] [--outdir OUTDIR] [--url URL]
                     [-j JOB] [--untrusted] [--skipdup] [--timeout TIMEOUT]
                     [--retry RETRY]

Download multiple files in seperated threads/tasks

optional arguments:
  -h, --help         show this help message and exit
  --fileurl FILEURL  File contains list of url to be download
  --outdir OUTDIR    Output directory, default
                     '/Users/worker/work/github/download_files/.download'
  --url URL          URl to download file, multiple URLs can be separated by
                     ','
  -j JOB, --job JOB  The number of jobs/threads to download. Default is a haft
                     of CPU cores, i.e. 2
  --untrusted        By-pass untrusted URL (skip SSL failure)
  --skipdup          Skip duplicate file or not
  --timeout TIMEOUT  Timeout connection in second, default 120
  --retry RETRY      Retry count, default 2

Copyright @ 2024 Ngo Huy Anh
```

# EXAMPLE

Download URLs from argument

```
./download_file.py --untrusted --url https://raw.githubusercontent.com/emtrai/download_files/refs/heads/main/README.md,https://raw.githubusercontent.com/emtrai/download_files/refs/heads/main/download_file.py
```

Download URLs from file
```
./download_file.py --fileurl list_url --untrusted -j 10
```

# TODO

- Download file in multi parts
- Parse webpage to get download links and download
- Download over proxy
- Re-direct download link


# COPYRIGHT

Copyright (C) 2024, Ngo Huy Anh

# LICENSE 

Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

# CONTACT

Ngo Huy Anh, ngohuyanh@gmail.com, emtrai@gmail.com
