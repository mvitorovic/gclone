#!/usr/bin/python

import sys, os, re, json, hashlib

from subprocess import check_output
from subprocess import CalledProcessError
from datetime import datetime
from time import ctime

import argparse
from argparse import RawTextHelpFormatter

##################################################
#
# Configuration variables
#
##################################################

configDir = os.environ['HOME'] + "/.config/gclone"
remoteDataFileName = configDir + "/remote-data"
localDataFileName = configDir + "/local-data"
rclone = "/usr/sbin/rclone"
remoteName = "remote"
localDir = os.environ['HOME'] + "/GDrive"
verbose = False
debug = False
useMd5 = True
fastRemote = False
dryRun = False
ADD = "add"
DEL = "remove"
MOD = "modify"

stdErrLogFile = open(configDir + "/error.log", 'w')

##################################################
#
# Configuration variables - End
#
##################################################

##################################################
#
# Main commands
#
##################################################

def init():
    print "Initializing..."
    if not os.path.exists(configDir):
        os.makedirs(configDir)

    # Local files
    localData = readLocalTree()

    # put into the file
    localDataFile = open(localDataFileName, 'w')
    json.dump(localData, localDataFile, default=dateTimeSerializer)
    localDataFile.close()

    # Remote files
    dirs = {}
    verbosePrint("Fetching remote folders data...")
    readRemoteTree("/", dirs)
    verbosePrint("Done.\n")
    readRemoteFiles(dirs)
    debugPrint("Final remote data structure:\n" + str(dirs) + "\n")

    # put into the file
    remoteDataFile = open(remoteDataFileName, 'w')
    json.dump(dirs, remoteDataFile, default=dateTimeSerializer)
    remoteDataFile.close()

def clone():
    verbosePrint("Reading state data...")
    with open(remoteDataFileName) as dataFile:
        oldRemoteData = json.load(dataFile, object_pairs_hook=dateTimeDeserailizer)

    with open(localDataFileName) as dataFile:
        oldLocalData = json.load(dataFile, object_pairs_hook=dateTimeDeserailizer)

    #read new remote files
    dirs = {}
    verbosePrint("Fetching remote folders data...")
    readRemoteTree("/", dirs, fastRemoteHandling=fastRemote)
    verbosePrint("Done.\n")
    newRemoteData = readRemoteFiles(dirs, fastRemoteHandling=fastRemote)

    #read new local files
    newLocalData = readLocalTree()

    verbosePrint("Calculating action lists...")
    incoming = compareStates(oldRemoteData, newRemoteData)
    outgoing = compareStates(oldLocalData, newLocalData)

    printActionList("INCOMING", incoming)
    print
    printActionList("OUTGOING", outgoing)
    print

def config():
    print "Configuration directory: " + configDir
    print "Remote state file name:  " + remoteDataFileName
    print "Local state file name:   " + localDataFileName
    print "Path to rclone:          " + rclone
    print "The name of the remote:  " + remoteName
    print "Local directory:         " + localDir

##################################################
#
# Building remote file information
#
##################################################

def readRemoteTree(dirName, dirs, fastRemoteHandling=False):
    """Gather data on all remote dirs"""

    if fastRemoteHandling:
        return dirs

    remoteDirs = check_output([rclone, "lsd", remoteName + ":" + dirName], stderr=stdErrLogFile)
    for line in remoteDirs.splitlines():
        dirRaw = re.split(r"\s*", line, maxsplit=5)
        newDirName = dirName + "/" + dirRaw[5]
        if dirName == "/":
            newDirName = dirName + dirRaw[5]
        dirData = {
            'size': 0L, 
            'date': datetime.strptime(dirRaw[2] + " " + dirRaw[3], "%Y-%m-%d %H:%M:%S"), 
            'name': newDirName,
            'md5': "0",
            'type': "dir"
        }
        debugPrint(str(dirData))
        dirs[newDirName] = dirData
        readRemoteTree(newDirName, dirs, fastRemoteHandling)
    return dirs

def readRemoteFiles(dirs, fastRemoteHandling=False):
    verbosePrint("Fetching remote files...")
    md5sums = {}
    if useMd5:
        remoteMd5Files = check_output([rclone, "md5sum", remoteName + ":/"], stderr=stdErrLogFile)
        for line in remoteMd5Files.splitlines():
            fileLine = re.split(r"\s*", line, maxsplit=1)
            md5sums[fileLine[1]] = fileLine[0]
        debugPrint("Remote file md5 checsums:\n" + str(md5sums) + "\n")

    debugPrint("Remote files data:")
    remoteFiles = check_output([rclone, "lsl", remoteName + ":/"], stderr=stdErrLogFile)
    for line in remoteFiles.splitlines():
        fileLine = re.split(r"\s*", line, maxsplit=4)
        fileData = {
            'size': long(fileLine[1]),
            'date': datetime.strptime(fileLine[2] + " " + fileLine[3][0:15], "%Y-%m-%d %H:%M:%S.%f"), 
            'name': fileLine[4],
            'md5': md5sums[fileLine[4]] if useMd5 else "0",
            'type': "file"
        }
        debugPrint(str(fileData))
        dirs[fileLine[4]] = fileData
        if fastRemoteHandling:
            deduceDirName(dirs, fileLine[4])
    del md5sums
    verbosePrint("Done.\n")
    return dirs

def deduceDirName(dirs, fileName):
    """Adds the file's parent dirs as an entry"""

    try:
        lastDel = fileName.rindex("/")
        dirName = "/" + fileName[:lastDel]
        dirData = {
            'size': 0L, 
            'date': datetime.now(), 
            'name': dirName,
            'md5': "0",
            'type': "dir"
            }
        dirs[dirName] = dirData
        debugPrint(str(dirData))
        deduceDirName(dirs, fileName[:lastDel])
    except ValueError:
        pass # files in root dir are not preceeded by a '/'

    return dirs

##################################################
#
# Building local file information
#
##################################################

def readLocalTree():
    """Read data on all local dirs."""

    localData = {}
    verbosePrint("Inspecting local files and folders.")
    for root, dirs, files in os.walk(localDir):
        relativeDir = root[len(localDir):]
        fileBase = ""
        if len(relativeDir) > 0:
            localData[relativeDir] = localDirData(root, relativeDir)
            fileBase = relativeDir[1:] + "/"
        for fileName in files:
            localData[fileBase + fileName] = localFileData(root + "/" + fileName, fileBase + fileName)
    debugPrint("Local file and folder data:\n" + str(localData))
    return localData

def localDirData(dirName, relativeDir):
    dirInfo = os.lstat(dirName)
    dirData = {
        'size': 0,
        'date': datetime.fromtimestamp(dirInfo.st_mtime).replace(microsecond=0),
        'name': relativeDir,
        'md5': "0",
        'type': "dir"
    }
    return dirData

def localFileData(fileName, relativeFileName, calcMd5=True):
    fileInfo = os.lstat(fileName)
    fileData = {
        'size': fileInfo.st_size,
        'date': datetime.fromtimestamp(fileInfo.st_mtime),
        'name': relativeFileName,
        'md5': md5(fileName) if calcMd5 else "0",
        'type': "file"
    }
    return fileData

##################################################
#
# Helper functions
#
##################################################

def md5(fname):
    hash = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(102400), b""):
            hash.update(chunk)
    return hash.hexdigest()

def verbosePrint(str):
    if verbose:
        print str

def debugPrint(str):
    if verbose and debug:
        print str

##################################################
#
# Datetime serializer/deserializer
#
##################################################

def dateTimeSerializer(obj):
    """JSON serializer for datetime objects"""

    if isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

def dateTimeDeserailizer(pairs):
    """JSON deserializer for dateime objects"""
    d = {}
    for k, v in pairs:
        if isinstance(v, basestring):
            for dateFormat in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    d[k] = datetime.strptime(v, dateFormat)
                    break
                except ValueError:
                    d[k] = v
        else:
            d[k] = v
    return d

##################################################
#
# Calculation sync actions
#
##################################################

def compareStates(oldState, newState):
    actionList = []
    oldStateCopy = dict(oldState)
    newStateCopy = dict(newState)
    # find incoming add or modify changes
    for k, v in newState.iteritems():
        key = k.decode('utf-8')
        try:
            oldVal = oldState[key]
            if not isStateEqual(oldVal, v):
                action = {}
                action['object'] = v
                action['actionType'] = MOD
                actionList.append(action)
            del oldStateCopy[key]
            del newStateCopy[k]
        except KeyError:
            # newState contains file that is not present in old state -> ADD
            action = {}
            action['object'] = v
            action['actionType'] = ADD
            actionList.append(action)
            del newStateCopy[k]
    # whaetever is left in oldState is deleted in newState
    for k, v in oldStateCopy.iteritems():
        action = {}
        action['object'] = v
        action['actionType'] = DEL
        actionList.append(action)

    return actionList

def isStateEqual(oldState, newState):
    if oldState['type'] != newState['type']:
        raise Exception("Type of entry changed: [old]:" + oldState['type'] + " [new]:" + newState['type'], 
            oldState['name'])
    if oldState['type'] == "dir":
        return True
    if oldState['size'] != newState['size']:
        return False
    if oldState['date'] != newState['date']:
        return False
    if useMd5:
        if oldState['md5'] != "0" and newState['md5'] != "0" and oldState['md5'] != newState['md5']:
            return False
    return True

def printActionList(name, list):
    print "Action list " + name + ":"
    for action in list:
        print action['actionType'].ljust(10) + ":: " + str(action['object'])

def remoteDirExists(dirName):
    try:
        remoteOutput = check_output([rclone, "lsd", remoteName + ":" + dirName], stderr=stdErrLogFile)
    except CalledProcessError as e:
        return False
    return True

##################################################
#
# main program
#
##################################################

argParser = argparse.ArgumentParser(description="Utility to clone Google drive using rclone.", 
    formatter_class=RawTextHelpFormatter)
argParser.add_argument("cmd", choices=["init", "clone", "config"], help=
"""init   - Initialize the application and create state
         description files.
clone  - Synchronize with Google drive.
config - Print the program configuration.""")
argParser.add_argument("-v", "--verbose", help="Print progress.", default=False, action="store_true")
argParser.add_argument("-d", "--debug", help="Print debugging information.", default=False, action="store_true")
argParser.add_argument("--no-md5", help="Don't use MD5 checksums when synchronizing.", default=True, 
    action="store_false", dest="md5")
argParser.add_argument("--fast-remote", help="Deduce dir names from remote file listing.", default=False, 
    action="store_true", dest="fastRemote")
argParser.add_argument("--dry-run", help="Only print the resulting actions, do not execute them.", default=False, 
    action="store_true", dest="dryRun")

args = argParser.parse_args()
verbose = args.verbose
debug = args.debug
useMd5 = args.md5
fastRemote = args.fastRemote
dryRun = args.dryRun

if args.cmd == "init":
    init()
elif args.cmd == "clone":
    clone()
elif args.cmd == "config":
    config()
else:
    argParser.print_help()

stdErrLogFile.close()
