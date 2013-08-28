#!/usr/local/bin/python
# Author: Siva Kumar
# 

"""
    This program creates a "p4 diff" output which can be used in conjunction 
    with CodeStriker p4 diff has the problem of not being able to 
    "diff" NEW (added) files
    This wrapper script uses unified diff to overcome this issue
"""

import sys
import subprocess


P4DEFAULT_OPT = "-du"

USAGE_MSG = """
    Usage: %s [-h|--help] [p4 diff opts] [files]
    This script is used to create a "p4 diff" output which includes newly added
    but not yet committed files

    "p4 diff" doesn't handle newly added files, so this script uses unified diff for new files

    The default behavior is to generate a diff for all files opened, but a user can 
    specify files explicitly or use "..." to indicate files in the current directory (and below)

    The difference output goes to stdout.

Options:

    -h|--help      : displays the help message

    [p4 diff opts] : such as -du, etc. See 'p4 help diff' for further details
                     The default option used for "p4 diff" is %s, but a user can override this with 
    cmd-line options

    [files]        : one or more files explicitly named. In absence of files, all opened files are used to
                     generate the diff output. "..." has the special meaning of "current directory"

""" % (sys.argv[0], P4DEFAULT_OPT)


def main():
    """
    Function generates the p4 diff and unified diff for the files
    """

    myfiles = ""
    myopts = None

    # let's see what cmd-line args are passed. A leading "-" is treated as an 
    # option to 'p4 diff'unless it's "-h" or "--help"

    for arg in sys.argv[1:]:
        if arg == "-h" or arg == "--help":
            print USAGE_MSG
            sys.exit(0)
        elif arg.startswith('-'):
            myopts += arg + " "
        else:
            myfiles += arg + " "

    if not myopts:
        myopts = P4DEFAULT_OPT

    output = ""

    pipe = subprocess.Popen("p4 where", stdout=subprocess.PIPE, shell=True)
    (output, err) = pipe.communicate()
    if err or output == "":
        print "Error: %s, maybe not in p4 workspace?" % (err, )
        sys.exit(1)

    # The output looks like this:
    # //depot/icm/proj/Appia/rev1.0/dev/newArchitecture/...  \
    # //skumar+Appia+rev1.0+3/newArchitecture/... \
    # /u/skumar/wa/HHead/newArchitecture/...
    vals = str(output).split(' ')

    p4depot = vals[0]
    myhome = vals[2]
    # get rid of trailing "..."
    p4depot = p4depot[0:p4depot.rindex("...")]
    myhome = myhome[0:myhome.rindex("...")]

    pipe = subprocess.Popen("p4 opened " + myfiles, 
                         stdout=subprocess.PIPE, shell=True)

    (output, err) = pipe.communicate()

    existingfiles = []
    newfiles = []
    lines = str(output).split('\n')
    # The output looks like this for each "p4 opened" file
    # //depot/<SNIP>ev/newArchitecture/firmware/include/dbgMsgs.h#3 - \
    #                                                 edit default changes
    for line in lines:
        if line.find("edit default change") != -1:
            myf = line.split(" ")[0]
            myf = myf[0:myf.rindex('#')]
            myf = myf.replace(p4depot, myhome, 1)
            existingfiles.append(myf)
        elif line.find("add default change") != -1:
            myf = line.split(" ")[0]
            myf = myf[0:myf.rindex('#')]
            # a tuple of "depot" file and actual file
            newfiles.append((myf, myf.replace(p4depot, myhome, 1)))

    # Now write to stdout the p4 differences for existing (modified) files
    modfiles = " ".join(existingfiles)
    pipe = subprocess.Popen("p4 diff " + myopts + " " + modfiles,
                         stdout=subprocess.PIPE, shell=True)
    (output, err) = pipe.communicate()

    newoutput = output
    for nfiles in newfiles:
        newoutput += "==== %s#0 - %s ====\n" % (nfiles[0], nfiles[1])
        pipe = subprocess.Popen("diff -u  /dev/null %s" % (nfiles[1]),
                             stdout=subprocess.PIPE, shell=True)
        (output, err) = pipe.communicate()

        # get rid of 1st two lines of diff output:
        # olines = output.split('\n')[2:]
        newoutput += output

    # for some reason, the last newline needs to be deleted ...
    # XXX: TODO try to figure out why
    newoutput = str(newoutput).rstrip('\n')
    print newoutput

# Main code

if __name__ == '__main__' :
    main()
