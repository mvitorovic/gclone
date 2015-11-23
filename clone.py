#!/usr/bin/python


configDir = "/home/miha/.config/gclone"
rclone = "/usr/sbin/rclone"
remoteName = "remote"
localDir = "/home/miha/Google Drive"

import sys
import os
from process import check_output

def init():
    if not os.path.exists(configDir):
        os.makedirs(configDir)

def clone():
    print "clone"

def printHelp():
    print sys.argv[0] + " has two commands:"
    print "    init     to initialize the application"
    print "    clone    to synchronize with Google drive"
    print

def read_remote():
    remoteRaw = check_output([rclone, "lsl", remoteName + ":/"])


if len(sys.argv) < 2:
    printHelp()
    sys.exit()

if sys.argv[1] == "init":
    init()
elif sys.argv[1] == "clone":
    clone()
else:
    printHelp()
