#!/usr/bin/python

import sys
import os
from subprocess import check_output
import re
from datetime import datetime
import json
import argparse

configDir = os.environ['HOME'] + "/.config/gclone"
rclone = "/usr/sbin/rclone"
remoteName = "remote"
localDir = "/home/miha/Google Drive"
verbose = True
debug = False
useMd5 = True
stdErrLogFile = open(configDir + "/error.log", 'w')

def init():
    print "Initializing..."
    if not os.path.exists(configDir):
        os.makedirs(configDir)
    dirs = {}
    if (verbose):
        print "Fetching remote folders data..."
    readRemoteTree("/", dirs)
    if (verbose):
        print "Done."
        print
    readRemoteFiles(dirs)
    if (verbose and debug):
        print "Final remote data structure:"
        print dirs
        print
    # put into the file
    #remoteFile = open(configDir + "/remote-data", 'w')
    #remoteFile.write(dirs)
    #json.dump(dirs, remoteFile)
    #remoteFile.close()

def clone():
    print "clone"

def readRemoteTree(dir, dirs):
    remoteDirs = check_output([rclone, "lsd", remoteName + ":" + dir], stderr=stdErrLogFile)
    for line in remoteDirs.splitlines():
        dirRaw = re.split(r"\s*", line, maxsplit=5)
        newDirName = dir + "/" + dirRaw[5]
        if (dir == "/"):
            newDirName = dir + dirRaw[5]
        dirData = {
            'size': 0, 
            'date': datetime.strptime(dirRaw[2] + " " + dirRaw[3], "%Y-%m-%d %H:%M:%S"), 
            'name': newDirName,
            'md5': "0",
            'type': "dir"
        }
        if (verbose and debug):
            print dirData
        dirs[newDirName] = dirData
        readRemoteTree(newDirName, dirs)
    return dirs

def readRemoteFiles(dirs):
    if (verbose):
        print "Fetching remote files..."
    md5sums = {}
    if (useMd5):
        remoteMd5Files = check_output([rclone, "md5sum", remoteName + ":/"], stderr=stdErrLogFile)
        for line in remoteMd5Files.splitlines():
            fileLine = re.split(r"\s*", line, maxsplit=1)
            md5sums[fileLine[1]] = fileLine[0]
        if (verbose and debug):
            print "Remote file md5 checsums:"
            print md5sums
            print

    if (verbose and debug):
        print "Remote files data:"
    remoteFiles = check_output([rclone, "lsl", remoteName + ":/"], stderr=stdErrLogFile)
    for line in remoteFiles.splitlines():
        fileLine = re.split(r"\s*", line, maxsplit=4)
        fileData = {
            'size': int(fileLine[1]),
            'date': datetime.strptime(fileLine[2] + " " + fileLine[3][0:15], "%Y-%m-%d %H:%M:%S.%f"), 
            'name': fileLine[4],
            'md5': md5sums[fileLine[4]] if useMd5 else "0",
            'type': "file"
        }
        if (verbose and debug):
            print fileData
        dirs[fileLine[4]] = fileData
    del md5sums
    if (verbose):
        print "Done."
        print
    return


# main program

argParser = argparse.ArgumentParser(description="Utility to clone Google drive using rclone.")
argParser.add_argument("init", help="Initialize the application. Create state description files.", nargs='?')
argParser.add_argument("clone", help="Synchronize with Google drive.", nargs='?')
argParser.add_argument("-v", "--verbose", help="Print progress.", default=False, action="store_true")
argParser.add_argument("-d", "--debug", help="Print debugging information.", default=False, action="store_true")
argParser.add_argument("--md5", help="Use MD5 checksums when synchronizing.", default=False, action="store_true")

args = argParser.parse_args()
verbose = args.verbose
debug = args.debug
useMd5 = args.md5

if args.init:
    init()
elif args.clone:
    clone()
else:
    argParser.print_help()

stdErrLogFile.close()
