#!/usr/bin/python
__author__="Claudia Chu"
__date__ ="2/18/19"


from os.path import abspath, join, isfile
from Bio import SeqIO
import subprocess
import time
from shutil import copyfile
import datetime
from sys import argv, stderr, exit

#========================
# Defaults
def_query    = "nifH"
def_tag      = "GENE"
def_start    = "2012"
def_end      = "2019"
def_datetype = "PDAT"
def_elements = "Id Caption TaxId Slen CreateDate Organism Title"
def_sorttype = ["nifH", "genome"]

def_blastnOutfmt = '6 qseqid sseqid pident length qlen mismatch gapopen qstart qend sstart send evalue bitscore sstrand qcovhsp'
def_dbfiles = ["nhr", "nsd", "nin", "nsi", "nsq"]
def_evalue = 0.001

# #========================
# Allowed sets
DATETYPES = set(["PDAT"])
stages = set(['esearch', 'fasta', 'set_db', 'blastn', 'filter_best_alignments', 'trim_seq', 'cluster'])
MAX_REUQUESTS = 3 # for entrex direct


#========================
def wait(subprocess):
    while subprocess.poll() == None:
        time.sleep(2)

#========================
def createShFile(cmdList, basePath, prefix, stage):

    shFileName = "%s/%s_%s.sh" % (basePath, prefix, stage)

    with open(shFileName, "w") as fh:

        now = datetime.datetime.now()
        fh.write("#!/bin/bash\n")
        fh.write("# %s\n" % str(now))
        fh.write("\n")
        for cmd in cmdList:
            fh.write(cmd + "\n")
            # fh.write("echo " + cmd + "\n")
        #####
    #####

    time.sleep(2)

    return shFileName

#========================
def esearchCmds(configDict, year, outputFile):

    esearch  = """esearch -db nucleotide -query \"%s\""""    % (configDict["QUERY"])
    efilter  = """efilter -mindate %s -maxdate %s -datetype %s""" % (year, year, configDict["DATETYPE"])
    efetch_1 = """efetch -format docsum"""
    xtract   = """xtract -pattern DocumentSummary -element %s"""  % (def_elements)
    edirectCmd = """%s | %s | %s | %s > %s\n""" % (esearch, efilter, efetch_1, xtract, outputFile)

    return edirectCmd

#========================
def fastaCmds(esearchFile, grepFilter, basePath, fastaFileName):

    cat = "cat %s" % (esearchFile)
    acc = """awk 'BEGIN { ORS="," }; { print $2 }'"""


    fastaCmd = """%s | grep '%s' | %s | python3 %s/nifHupdate_Lib/nifHupdate_fasta.py > %s\n""" % (cat, grepFilter, acc, basePath, fastaFileName)

    return fastaCmd

def fasta(esearchFile, sortterm, outputFasta):
    fastaFileHandle = open(outputFasta, "w")

    requestCont = 0
    for line in open(esearchFile.strip(), "r"):
        if (sortterm in line):
            tmpName = "tmp.%s" % outputFasta
            tmpFileHandle = open(tmpName, "w")
            recId, acc, taxId, slen, date, organism, title = line.strip().split("\t")
            fastaCmd = """efetch -db nuccore -id %s -format gene_fasta""" % (acc)

            n = subprocess.Popen(fastaCmd, shell=True, stdin = subprocess.PIPE, stdout = tmpFileHandle)
            wait(n)
            n.kill()

            requestCont += 1 # increment count

            if (requestCont == MAX_REUQUESTS ):
                time.sleep(1)
                requestCont = 0
            #####

            i = 1
            for record in SeqIO.parse(tmpName, "fasta"):
                if (sortterm in record.description):
                    record.description = "[Acc: %s] [Ver: %d] [Date: %s] [Organism: %s] [Title: %s] [TaxID: %s]" % (record.id, i, date, organism, title, taxId)
                    record.id = acc
                    SeqIO.write(record, fastaFileHandle, "fasta")
                    i += 1
            #####
        #####
    #####

#========================
def blastnCmds(dbName, fastaFile, blastOutputFile, fmtString = def_blastnOutfmt):


    blastCmd = """blastn -query %s -db %s -outfmt '%s' -evalue %s -out %s\n""" % (fastaFile, dbName, def_blastnOutfmt, def_evalue, blastOutputFile)
    return blastCmd

#========================
def bestAlignment(blastnFile, fh):
    seqAlignDict = {}
    for line in open(blastnFile, "r"):
        alignmentData = line.split()
        fastaLabel = alignmentData[0]
        pident     = alignmentData[2]
        qcovhsp    = alignmentData[14]

        try:
            # compare previous qcovhsp, and change if better score
            if (seqAlignDict[fastaLabel][14] < qcovhsp):
                seqAlignDict[fastaLabel] = alignmentData
                # pass in everything about the alignment
            elif (seqAlignDict[fastaLabel][14] == qcovhsp):
                if (seqAlignDict[fastaLabel][2] < pident):
                    seqAlignDict[fastaLabel] = alignmentData
        except:
            seqAlignDict[fastaLabel] = alignmentData
        #####
    #####

    # Book keeping
    for label in seqAlignDict:
        fh.write("\t".join(seqAlignDict[label]) + "\n")


#========================
def verifyDb(dbLabel):
    checkFiles = [int(isfile("%s.%s" % (dbLabel, fileType))) for fileType in def_dbfiles]
    #check if all the database files exist
    if (sum(checkFiles) != len(def_dbfiles)):
        return False
    else:
        return True

#========================
def mapBlast(blastnFofn):
    blastnMap = {}
    for blastnFile in open(blastnFofn, "r"):
        for line in open(blastnFile):
            alignmentData = line.split(None)
            qseqid, sseqid, pident, length, qlen, mismatch, gapopen, qstart, qend, sstart, send, evalue, bitscore, sstrand, qcovhsp = line.strip().split(None)
            blastItems[qseqid] = BlastAlignment(qseqid, sseqid, pident, length, qlen, mismatch, gapopen, qstart, qend, sstart, send, evalue, bitscore, sstrand, qcovhsp)
        #####
    #####
    return blastnMap

#========================
def mapEsearch(esearchFofn):
    esearchMap = {}

    for fileName in open(esearchFofn, "r"):
        for record in open(fileName.strip(), "r"):
            xtractData = line.split("\t")
            recordAccession = xtractData[1]
            description = xtractData[3]

            if recordAccession not in esearchMap:
                esearchMap[recordAccession] = description
            #####
        #####
    #####
    return esearchMap

#========================
def throwError(errorMessage):
    stderr.write("\n-----------------\n")
    stderr.write("Time: %s\n" % datetime.datetime.now())
    stderr.write("%s\n" % errorMessage)
    stderr.write("Halting execution\n")
    stderr.write("-----------------\n")
    assert False


#========================
def parseConfig(configFile, basePath):

    if ( not isfile(configFile)):
        throwError("parse_config did not find config file %s" % ( configFile ) )

    configDict = {}
    for line in open(configFile, "r"):
        key, val = line.strip().split(None, 1)
        configDict[key] = val


    # check config errors and put in defaults


    # -----------------------------
    # Test prefix
    try:
        prefix = configDict["PREFIX"]
    except:
        throwError("No PREFIX provided in the configuration file %s" % configFile.split("/")[-1])
    # -----------------------------
    # Test QUERY
    try:
        queries = configDict["QUERY"]
    except KeyError:
        throwError("No QUERY provided in the configuration file %s" % configFile.split("/")[-1])
    except:
        throwError("Improper formatting of query terms in the configuration file %s. \
            Please delimit with semicolons ';'", configFile.split("/")[-1])
    # -----------------------------
    # Test DATERANGE, START, END, and DATETYPE
    try:
        useDateRange = configDict["DATERANGE"]
        if (useDateRange.lower() == 'true'):
            try:
                start = configDict["START"]
                end   = configDict["END"]
                if (parseDate(start) > parseDate(end)):
                    throwError("Invalid START and END date in Config File %s. \
                        Check that start date is before end date." % configFile.split("/")[-1])
            except KeyError:
                throwError("Unable to query in date range without specified start and end time. Please provide START and END tags (MM/DD/YYY, MM/YYYY, or YYYY) in the configuration file %s" % configFile.split("/")[-1])
            #####

            try:
                datetype = configDict["DATETYPE"]
            except KeyError:
                throwError("Unable to query data in date range without specified datetype. Options are %s" % ",".join(DATETYPES))
            #####

            # Everything there
            configDict["DATERANGE"] = True
        else:
            throwError("%s is not a valid value. Only valid value for DATERANGE is 'true'. Otherwise, do not include the DATERANGE tag.", useDateRange)
        #####
    except KeyError:
        # check if other tags were used
        try:
            start = configDict["START"]
            throwError("Provided START tag, but DATERANGE is not specified in configFile %s" % configFile.split("/")[-1])
        except:
            pass
        #####

        try:
            end   = configDict["END"]
            throwError("Provided END tag, but DATERANGE is not specified in configFile %s" % configFile.split("/")[-1])
        except:
            pass
        #####

        try:
            datetype = configDict["DATETYPE"]
            throwError("Provided DATETYPE tag, but DATERANGE is not specified in configFile %s" % configFile.split("/")[-1])
        except:
            pass
        #####

        # Default to not use date range
        configDict["DATERANGE"] = False
    # -----------------------------
    try:
        dbFile = "%s/%s" % (basePath, configDict["DBFILE"])
        if (not isfile(dbFile)):
            throwError("Could not find database fasta file %s" % dbFile)
    except KeyError:
        throwError("No database fasta file provided in configuration file %s" % configFile.split("/")[-1])
    # -----------------------------
    try:
        x = configDict["SORTTERMS"]
        configDict["SORTTERMS"] = x.split(None) # store the space delmited sort terms into a list
    except:
        # place default
        configDict["SORTTERMS"] = def_sorttype
    #####
    return configDict


#========================
def launch(shFileName):
    n = subprocess.Popen(["bash", shFileName])
    wait(n) # wait for the shfile to finish running before proceeding
    n.poll()

#========================
def parseDate(date):
    nums = date.split('/')

    if len(nums) == 3:
        # MM/DD/YYYY
        year = int(nums[2])
    elif len(nums) == 2:
        year = int(nums[1])
    else:
        year = int(nums[0])
    #####

    return year


# TESTING
#========================
def testPrintFile(fileName):
    print("\n======== %s =========" % fileName)
    for line in open(fileName, "r"):
        print(line.strip())
    ######
    print("\n======== %s =========" % fileName)
    assert False

#========================
def test(*statements):
    print("\n==========TESTING===========")
    for statement in statements:
        print(statement)
    #####
    print("============================")
    assert False
