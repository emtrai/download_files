#!/usr/bin/env python3

# Copyright [2024] Ngo Huy Anh
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Download multiple files
# Author: Anh, Ngo - ngohuyanh@gmail.com
#


from urllib.request import urlopen
from shutil import copyfileobj
import shutil
import os
import sys
import logging
import html
from urllib.parse import unquote
import urllib
import ssl
import threading
from tqdm import tqdm
import multiprocessing
from socket import timeout
from urllib.error import HTTPError, URLError
import socket

logger = logging.getLogger(__name__)

CUR_DIR = os.getcwd()
DEFAULT_OUT_DIR=os.path.join(CUR_DIR, ".download")


COMMENT_CHAR="#"

LOG_FNAME=".download.log"

URL_SPLIT=","
    
LIST_URLS = []
NEXT_URL_IDX = 0
TOTAL_URLS = 0
TOTAL_DOWNLOADED =0
NUMBER_CORES = multiprocessing.cpu_count()
DEFAULT_JOBS = NUMBER_CORES/2 if NUMBER_CORES > 1 else 1

LOG_FILE=None
DEFAULT_TIMEOUT = (2*60) # 60s

ERR_NONE = 0 
ERR_EXISTED = 1
ERR_CONNECT_ERR = 2
ERR_NOT_FOUND = 3

ERR_TO_MSG = {
    ERR_NONE: "OK",
    ERR_EXISTED: "Existed",
    ERR_CONNECT_ERR: "Connection err",
    ERR_NOT_FOUND: "Not found",
}

DEFAULT_RETRY = 3
class UrlItem(object):
    _url = None
    _fname = None
    
    def __init__(self, url, fname = None):
        self._url = url.strip()
        if len(self._url) == 0:
            raise Exception("Empty url")
        if fname is not None:
            self._fname = fname.strip()
        else:
            parts = self._url.split("/")
            # get filename from url
            for part in reversed(parts):
                part = part.strip()
                if len(part) > 0:
                    part = normalize_fname(part)
                    self._fname = part
                    break
  
    @property
    def url(self):
        return self._url
    
    @property
    def fname(self):
        return self._fname
    
    def __str__(self):
        return "%s --> %s" % (self.url, self.fname)

class DownloadProgressBar():
    _bar = None
    _running = False
    _title = None
    _line_offset = 0
    
    def __init__(self, line_offset = 0):
        self._line_offset = line_offset
        self._bar = tqdm()
        
    def set_title(self, title):
        self._title = title

    def start(self, max_value):
        maxval=max_value
        if maxval < 0:
            maxval=-1
        self._running = True
        if self._bar is not None:
            self._bar.reset(max_value)
            self._bar.clear()
            self._bar.set_description(self._title)
        
    def update(self, value):
        if self._bar is not None and self._running:
            self._bar.update(value)
            
    def end(self):
        self._running = False
        if self._bar is not None:
            self._bar.reset()
            self._bar.clear()

    def __call__(self, num_block, block_size, total_size):
        if (total_size != 0):
            if (not self._running):
                self.start(total_size)

            downloaded = num_block * block_size
            if downloaded < total_size:
                self.update(block_size)
            else:
                self.end()

class AppConfig:
    outdir = None
    skip_dup = False
    timeout = 0
    retry_cnt = DEFAULT_RETRY

def err_msg(err):
    errmsg = "Unknown"
    if err in ERR_TO_MSG:
        errmsg = ERR_TO_MSG[err]
    return errmsg

def append_log(log_msg):
    global LOG_FILE
    if log_msg is not None and len(log_msg) > 0:
        with open(LOG_FILE, 'a') as log:
            log.write("%s\n" % log_msg)
        log.close()


def normalize_fname(fname):
    fname = html.unescape(fname)
    fname = unquote(fname)
    return fname

def get_non_exist_fpath(outdir, fname, skip_dup):
    fpath = None
    fpath_tmp = None
    suffix = None
    global ERR_NONE
    global ERR_EXISTED
    ret = ERR_NONE
    for i in range(100):
        path = os.path.join(outdir, fname)
        # Try to find suitable file name, if it exists, add "(number)"
        if (os.path.exists(path)):
            if (skip_dup):
                ret = ERR_EXISTED
                fpath = None
                break
            else:
                parts = os.path.splitext(path)
                fname_no_ex = parts[0]
                if suffix is not None and parts[0].endswith(suffix):
                    fname_no_ex = fname_no_ex[:len(fname_no_ex) - len(suffix)]
                suffix = "(%s)" % i
                fname = "%s%s%s" % (fname_no_ex, suffix, parts[1])
        else:
            fpath = path
            fpath_tmp = path = os.path.join(outdir, ".%s" % fname)
            break
    return fpath,fpath_tmp,ret

def download_file(title, url, fpath, bar, app_cfg):
    '''
    Download file
    '''
    global ERR_NONE
    global ERR_EXISTED
    global ERR_NOT_FOUND
    ret = ERR_NONE
    # TODO: Download multi parts of file
    for retry in range(app_cfg.retry_cnt):
        try:
            bar.set_title(title)
            socket.setdefaulttimeout(app_cfg.timeout)
            urllib.request.urlretrieve(url, fpath, bar)
            ret = ERR_NONE
            break
        except Exception as e:
            bar.end()
            logger.error(("Exception when download file from url '%s', tried %d/%d\n" % (url, retry, app_cfg.retry_cnt)) + str(e))
            if (os.path.exists(fpath)):
                os.remove(fpath)
            ret = ERR_CONNECT_ERR
    if (ret == ERR_NONE) and not os.path.exists(fpath):
        ret = ERR_NOT_FOUND
    return ret
        

def download_thread(thread_id, lock, app_cfg, bar):
    '''
    Download thread
    
    @param lock: synchornize lock
    @param app_cfg: App configuration
    @param bar: Progress bar
    '''
    global NEXT_URL_IDX
    global LIST_URLS
    global TOTAL_URLS
    global TOTAL_DOWNLOADED
    global ERR_NONE

    while True:
        url_item = None
        
        # get next index of URL to download
        lock.acquire() 
        if (NEXT_URL_IDX < len(LIST_URLS)):
            url_item = LIST_URLS[NEXT_URL_IDX]
            NEXT_URL_IDX += 1
        lock.release() 
        
        if (url_item is None):
            break
        
        
        fpath, tmp_fpath, err = get_non_exist_fpath(app_cfg.outdir, url_item.fname, app_cfg.skip_dup)
        log_msg = None
        
        # download file
        if (fpath is not None and err == ERR_NONE):
            file_name = os.path.basename(fpath)
            err = download_file("[%d] %s" % (thread_id, file_name), url_item.url, tmp_fpath, bar, app_cfg)
            lock.acquire()
            TOTAL_DOWNLOADED += 1
            if (err == ERR_NONE):
                log_msg = "[%d] Done : %s" % (TOTAL_DOWNLOADED, str(url_item))
            else:
                log_msg = "[%d] Error : %s : %s" % (TOTAL_DOWNLOADED, err_msg(err), str(url_item))
            lock.release()
            if (err == ERR_NONE):
                os.rename(tmp_fpath, fpath)
            else:
                if (os.path.exists(tmp_fpath)):
                    os.remove(tmp_fpath)
        else:
            # logger.error("FAILED to get file path for URL '%s', file name '%s'" % (url_item.url, url_item.fname))
            lock.acquire()
            TOTAL_DOWNLOADED += 1 
            log_msg = "[%d] Error : %s : %s" % (TOTAL_DOWNLOADED, err_msg(err), str(url_item))
            lock.release()

        append_log(log_msg)

    logger.debug("Stop thread %d" % thread_id)

def parse_one_url(url):
    '''
    Convert url to UrlItem for downloading
    '''
    url_item = UrlItem(url)
    logger.debug("parsed url '%s'" % str(url_item))
    return url_item


def get_urls_from_file(fpath):
    '''
    Get List of URLs from file
    
    @return list of UrlItem object
    '''
    urls = []
    logger.debug("Get list of URL from file '%s'" % fpath)
    lines = None
    if fpath is None or len(fpath) == 0 or not os.path.exists(fpath):
        logger.error("Invalid file")
        return urls
    
    with open(fpath, 'r') as file:
        lines = file.readlines()
    for line in lines:
        line = line.strip()
        if len(line) > 0 and not line.startswith(COMMENT_CHAR):
            urls.append(parse_one_url(line))
    return urls

def main(args):
    if args.untrusted:
        ssl._create_default_https_context = ssl._create_unverified_context

    
    global LIST_URLS
    global NEXT_URL_IDX
    global TOTAL_URLS
    global LOG_FILE
    
    
    NEXT_URL_IDX = 0
    LIST_URLS = []
    
    # get list of URL from argument
    if args.url is not None and len(args.url) > 0:
        parts = args.url.split(URL_SPLIT)
        for part in parts:
            part = part.strip()
            if len(part) == 0:
                continue
            url = parse_one_url(part)
            if url is not None:
                LIST_URLS.append(url)
    
    # get list of URL from file
    if args.fileurl is not None and len(args.fileurl) > 0:
        if os.path.exists(args.fileurl):
            urls = get_urls_from_file(args.fileurl)
            if (urls is not None and len(urls) > 0):
                LIST_URLS += urls
        else:
            raise Exception("File '%s' does not exist" % args.fileurl)
    
    outdir = args.outdir
    if (outdir is None):
        outdir = DEFAULT_OUT_DIR
        if args.fileurl is not None:
            fname = os.path.basename(args.fileurl)
            outdir = os.path.join(outdir, fname)

    if not os.path.exists(outdir):
        logger.info("Create output dir '%s'" % outdir)
        os.makedirs(outdir)
      

    logger.info("Output dir '%s'" % outdir)
    LOG_FILE=os.path.join(outdir, LOG_FNAME)
    logger.debug("List of url: \n" + "\n".join(str(url) for url in LIST_URLS))
    
    TOTAL_URLS = len(LIST_URLS)
    
    # init log
    with open(LOG_FILE, 'w') as log:
        log.write("Total URLs: %d\n" % TOTAL_URLS)
    
    num_jobs = int(args.job)
    if (num_jobs > TOTAL_URLS):
        num_jobs = TOTAL_URLS
    
    lock = threading.Lock()
    run_threads = []

    logger.info("Create %d job(s) to download" % num_jobs)
    
    app_cfg = AppConfig()
    app_cfg.outdir = outdir
    app_cfg.skip_dup = args.skipdup
    app_cfg.timeout = args.timeout
    app_cfg.retry_cnt = args.retry
    if (app_cfg.retry_cnt <= 0):
        app_cfg.retry_cnt = 1

    # Create thread to download
    for job in range(num_jobs):
        run_thread = threading.Thread(target=download_thread, args=(job, lock, app_cfg, DownloadProgressBar(job))) 
        run_threads.append(run_thread)
        run_thread.start()
    
    # wait for threads complete
    for t in run_threads:
        t.join()

    print("\nALL DONE\n")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
                    prog='Download file',
                    description='Download multiple files in seperated threads/tasks',
                    epilog='Copyright @ 2024 Ngo Huy Anh')
    
    parser.add_argument('--fileurl', action='store',
                        help='File contains list of url to be download')
    
    parser.add_argument('--outdir', action='store',
                        help="Output directory, default '%s'" % DEFAULT_OUT_DIR)
    
    parser.add_argument('--url', action='store',
                        help="URl to download file, multiple URLs can be separated by '%s'" % URL_SPLIT)
    
    parser.add_argument('-j', '--job', action='store', type=int, default=DEFAULT_JOBS,
                        help="The number of jobs/threads to download. Default is a haft of CPU cores, i.e. %d" % DEFAULT_JOBS)
    
    parser.add_argument('--untrusted', action='store_true', default=False,
                        help='By-pass untrusted URL (skip SSL failure)')
    
    parser.add_argument('--skipdup', action='store_true', default=False,
                        help='Skip duplicate file or not')
    
    parser.add_argument('--timeout', action='store', type=int, default=DEFAULT_TIMEOUT,
                        help="Timeout connection in second, default %d" % DEFAULT_TIMEOUT)
    
    
    parser.add_argument('--retry', action='store', type=int, default=DEFAULT_RETRY,
                        help="Retry count, default %d" % DEFAULT_RETRY)

    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)  
    main(args)