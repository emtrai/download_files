#!/usr/bin/python3

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

from urllib.request import urlopen
from shutil import copyfileobj
import shutil
import os
import sys
import logging
import html
from urllib.parse import unquote

logger = logging.getLogger(__name__)

CUR_DIR = os.getcwd()
DEFAULT_OUT_DIR=os.path.join(CUR_DIR, ".download")

COMMENT_CHAR="#"



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
        

def normalize_fname(fname):
    # fname.replace("%20", "_")
    fname = html.unescape(fname)
    fname = unquote(fname)
    return fname

def download_file(url, fpath):
    logger.info("Download file from %s" % (url))
    logger.info("Store to %s" % (fpath))
    with urlopen(url) as istream:
        with open(fpath, 'wb') as ofile:
            copyfileobj(istream, ofile)


def parse_one_url(url):
    url_item = UrlItem(url)
    logger.debug("parsed url '%s'" % str(url_item))
    return url_item

def parse_urls(urls):
    logger.debug("Get list of URL from '%s'" % urls)
    # TODO: parse list of URL from commandline, i.e pslit by comma, or anything else
    url = parse_one_url(urls)
    return [url]


def get_urls_from_file(fpath):
    urls = []
    logger.debug("Get list of URL from file '%s'" % fpath)
    lines = None
    with open(fpath, 'r') as file:
        lines = file.readlines()
    for line in lines:
        line = line.strip()
        if len(line) > 0 and not line.startswith(COMMENT_CHAR):
            urls.append(parse_one_url(line))
    return urls

def main(args):
    logger.info("Output dir '%s'" % args.outdir)
    if not os.path.exists(args.outdir):
        logger.info("Create output dir '%s'" % args.outdir)
        os.makedirs(args.outdir)
    
    list_urls = []
    if args.url is not None and len(args.url) > 0:
        urls = parse_urls(args.url)
        if (urls is not None and len(urls) > 0):
            list_urls += urls
    
    if args.fileurl is not None and len(args.fileurl) > 0:
        if os.path.exists(args.fileurl):
            urls = get_urls_from_file(args.fileurl)
            if (urls is not None and len(urls) > 0):
                list_urls += urls
        else:
            raise Exception("File '%s' does not exist" % args.fileurl)
    
    logger.debug("List of url: \n" + "\n".join(str(url) for url in list_urls))
    
    skip_url=[]
    
    for url in list_urls:
        logger.info("\nDOWNLOAD FILE from '%s' ......." % url.url)
        fpath = None
        fname = url.fname
        for i in range(100):
            fpath = os.path.join(args.outdir, fname)
            if (not os.path.exists(fpath)):
                break
            else:
                parts = os.path.splitext(fpath)
                fname = "%s(%d)%s" % (parts[0], i, parts[1])
        if (fpath is not None):
            download_file(url.url, fpath)
        else:
            logger.error("FAILED to download from '%s'. Not found and suitable file to download" % url.url)
            skip_url.append(url)
    if len(skip_url) > 0:
        logger.info("\nSKIP TO DOWNLOAD FROM FOLLOWING URLS:\n")
        for url in skip_url:
            logger.info(str(url))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
                    prog='Download file',
                    description='Download multiple files',
                    epilog='Copyright @ 2024 Ngo Huy Anh')
    parser.add_argument('--fileurl', action='store',
                        help='File contains list of url to be download')
    parser.add_argument('--outdir', action='store',
                        default=DEFAULT_OUT_DIR,
                        help='Output directory')
    
    parser.add_argument('--url', action='store',
                        help='URl to download file')

    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG)  
    main(args)