#!/usr/bin/env python

"""
    This program creates a "p4 diff" output which can be used in conjunction
    with CodeStriker p4 diff has the problem of not being able to
    "diff" NEW (added) files
    This wrapper script uses unified diff to overcome this issue
"""

import sys
import os
import subprocess
import re


P4DEFAULT_OPT = "-du"

ISWINDOWS = True

REV_NUM = ""

USAGE_MSG = """
    Usage: {0} [-h|--help] [-c|--changelist <changelist-number>] [p4 diff opts] [files]
    This script is used to create a "p4 diff" output which includes newly added
    (but not yet committed) files and deleted files


    The default behavior is to generate a diff for all files opened, but a user can
    specify files explicitly or use "..." to indicate files in the current
    directory (and below)

    The difference output goes to stdout.

Options:

    -h|--help      : displays the help message

    -c|--changelist <changelist-number> : does a p4 diff between the current
                     version and the file at changelist-number
                     Essentially, this does a "p4 diff file@chaneglist"
                     NOTE: For this to work properly, you'll have to "p4 edit" the
                     files that you're interested in for the patch file

    [p4 diff opts] : such as -du, etc. See 'p4 help diff' for further details
                     The default option used for "p4 diff" is {1}, but a user can
                     override this with cmd-line options

    [files]        : one or more files explicitly named. In absence of files, all opened
                     files are used to generate the diff output.

                     "..." has the special meaning of "current directory"


    Typical Uses Cases:
    1.
        cd <your-workspace>
        {0} > p4diffs-all-files

      In this case, ALL files that have been modified and ADDED are included in the
      "diff output"

    2.
        cd <your-workspace/some-directory>
        {0} ... > p4diffs-files-in-this-directory-and-below
      In this case, ALL files that have been modified and ADDED in *the current directory and below*
      (the '...') are included in the "diff output"

    3.
        cd <your-workspace/some-directory>
        {0} -c 12345 ... > p4diffs-files-in-this-directory-and-below-with-changelist-12345

      In this case, the files are compared against a specific changelist (in this case, 12345)

    4.
        cd <your-workspace>
        {0} foo1.c dir2/foo2.py ../dir3/foo3.h > p4diffs-specific-files

      In this case, just the explicitly listed files are included in the "diff output"

    In all four examples above, the script can handle modified, newly added, and deleted files



""".format(sys.argv[0], P4DEFAULT_OPT)

P4FILECHANGED_REGEX = re.compile(r'(.*?)#(\d+)\s*-\s*(\w+).*?\((\w+)\)')

MODIFIED_STR = """\
... depotFile %s
... clientFile %s
... rev %s
... type %s

"""


def usage(exitcode):
    """
        prints usage message and exits
    """
    print USAGE_MSG
    sys.exit(exitcode)


def getp4depotinfo():
    """
        get the p4 depot information
    """
    output = ""
    pipe = subprocess.Popen("p4 where", stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=True)
    (output, err) = pipe.communicate()
    if err or output == "":
        pipe = subprocess.Popen("p4 client -o", stdout=subprocess.PIPE,
                                shell=True)
        (output, err) = pipe.communicate()
        vals = str(output).split('\n')
        #
        # View:
        # //depot/branch/pioneer-sivak-br1/... //sb14-pioneer-sivak-br1/...
        try:
            p4depot = vals[vals.index('View:') + 1]
            p4depot = p4depot.strip()
            vals = p4depot.split()
            p4depot = None
            for myval in vals[::-1]:
                if myval.startswith('//depot'):
                    p4depot = myval
                    break

        except IndexError:
            print "Couldn't get p4depot info"
            sys.exit(1)
    else:

        # The output looks like this:
        # //depot/icm/proj/Appia/rev1.0/dev/newArchitecture/...  \
        # //skumar+Appia+rev1.0+3/newArchitecture/... \
        # /u/skumar/wa/HHead/newArchitecture/...
        vals = str(output).split()

        p4depot = None
        # for myval in vals[::-1]:
        #     if myval.startswith('//depot'):
        #         p4depot = myval
        #         break
        myindstart = output.rindex("//depot")
        if myindstart != -1:
            myindlast = output[myindstart:].find("...")
            if myindlast != -1:
                p4depot = output[myindstart:myindlast]

    return (p4depot, output)


def getp4info():
    """ get p4 info details """

    # sanity check, make sure that we're logged in ...
    tpipe = subprocess.Popen(['p4', 'where'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    (toutput, terr) = tpipe.communicate()
    if terr or toutput == "":
        print "Error, maybe not in workspace or not 'p4 logged in'?\n"
        print "Error message: %s\n" % (terr, )
        sys.exit(1)

    pipe = subprocess.Popen("p4 info", stdout=subprocess.PIPE, shell=True)
    (output, err) = pipe.communicate()
    if err or output == "":
        print "Error: %s, maybe not in p4 workspace?" % (err, )
        sys.exit(1)
    vals = str(output).split('\n')
    myclroot = None
    mycwd = None
    for myval in vals:
        if myval.startswith("Client root:"):
            myclroot = myval[len("Client root:"):].strip()
        elif myval.startswith("Current directory:"):
            mycwd = myval[len("Current directory:"):].strip()
        if myclroot and mycwd:
            break

    if not myclroot or not mycwd:
        print "Error: Unable to parse the output of 'p4 info':\n%s\n" % (
            output, )
        sys.exit(1)

    return (mycwd, myclroot)


def get_modified(myopts, mfile, efile, rev, fltype):
    """ get details of modified files """

    mycmd = "p4 diff " + myopts + " " + "\"" + efile + "\"" + REV_NUM
    pipe = subprocess.Popen(mycmd,
                            stdout=subprocess.PIPE, shell=True)

    (output, _) = pipe.communicate()
    newoutput = MODIFIED_STR % (mfile, efile, rev, fltype)
    lines = output.splitlines()
    newoutput += '\n'.join(lines[2:]) + '\n'

    return newoutput


def get_add(dfile, afile, rev):
    """ get details of added files """

    fdin = open(afile)
    lines = fdin.read().replace('\xc2\x85', '\n').splitlines()
    fdin.close()

    output = '\n' + '--- /dev/null\n' + \
             '+++ ' + dfile + '\t(revision ' + rev + ')\n' + \
             '@@ -0,0 +1,' + str(len(lines)) + ' @@\n'
    output += '+' + '\n+'.join(lines) + '\n'
    return output


def get_deleted(dfile, rev):

    """ get details of deleted files """

    pipe = subprocess.Popen("p4 print -q " + "\"" + dfile + "\"" +
                            '#' + rev, stdout=subprocess.PIPE,
                            shell=True)

    (output, _) = pipe.communicate()
    lines = output.splitlines()

    newoutput = '\n' + '--- ' + dfile + '\t(revision ' + rev + ')\n' + \
             '+++ /dev/null\n' + \
             '@@ -1,' + str(len(lines)) + ' +0,0 @@\n'

    newoutput += '-' + '\n-'.join(lines) + '\n'
    return newoutput


def get_changed_files(p4depot, myclroot, filelist):
    """ get changed, new and deleted p4 files """

    # p4depot = p4depot[0:p4depot.rindex("...")]

    if len(filelist) == 0:
        pipe = subprocess.Popen("p4 opened",
                                stdout=subprocess.PIPE, shell=True)
    else:
        pipe = subprocess.Popen("p4 opened " + filelist,
                                stdout=subprocess.PIPE, shell=True)

    (output, _) = pipe.communicate()

    existingfiles = []
    newfiles = []
    deletedfiles = []
    # lines = str(output).split('\n')

    # The output looks like this for each "p4 opened" file
    # //depot/<SNIP>ev/newArchitecture/firmware/include/dbgMsgs.h#3 - \
    #                                                 edit change
    for line in str(output).split('\n'):
        match = P4FILECHANGED_REGEX.search(line)
        if match:
            myf = match.group(1)
            revision = match.group(2)
            changetype = match.group(3)
            filetype = match.group(4)

            if ISWINDOWS:
                myf = myclroot + myf[2:].replace('/', '\\')
            else:
                # myf = myf.replace(p4depot, myclroot, 1)
                myf = myclroot + myf[2:]
            if changetype == 'edit':
                existingfiles.append((match.group(1), myf, revision, filetype))
            elif changetype == 'add':
                newfiles.append((match.group(1), myf, revision))
            elif changetype == 'delete':
                deletedfiles.append((match.group(1), myf, revision))

    return (existingfiles, newfiles, deletedfiles)


def get_p4files(p4depot, myfiles, realcwd, myclroot):

    """ get details of p4 opened  files """

    fullfiles = []
    for myfile in myfiles:
        # check to make sure that the file is NOT full-qualified already
        # if myfile.startswith("." + os.path.sep):
        #    fullfiles.append(realcwd + os.path.sep + myfile[2:])
        # if myfile.startswith(".." + os.path.sep):
        #    fullfiles.append(myfile)
        # elif not myfile.startswith(os.path.sep):
        #    fullfiles.append(realcwd + os.path.sep + myfile)
        # else:
        #    fullfiles.append(myfile)
        fullfiles.append("\"" + myfile + "\"")

    filelist = " ".join(fullfiles)

    (existingfiles, newfiles, deletedfiles) = get_changed_files(
        p4depot, myclroot, filelist)

    return(existingfiles, newfiles, deletedfiles)


def get_args():
    """
       get the options and args
       optparse and argparse are not used since they get confused
       with options meant for the diff command ...
    """

    global REV_NUM
    myfiles = []
    myopts = ""

    # let's see what cmd-line args are passed. A leading "-" is treated as an
    # option to 'p4 diff' unless it's "-h", "--help", "-c", or "--changelist"

    skiparg = False

    allargs = sys.argv[1:]
    for (myindex, arg) in enumerate(allargs):
        if skiparg:
            skiparg = False
            continue
        if arg in ["-h", "--help"]:
            usage(0)
        elif arg in ["-c", "--changelist"]:
            try:
                REV_NUM = "@" + allargs[myindex + 1]
            except IndexError:
                print "changelist number required option"
                usage(1)
            try:
                _ = int(allargs[myindex + 1])
            except ValueError:
                print "{} not a valid changelist number".format(
                    allargs[myindex + 1])
                usage(1)

            skiparg = True
        elif arg.startswith('-'):
            myopts += arg + " "
        else:
            myfiles.append(arg)

    return (myopts, myfiles)


def main():
    """
    Function generates the p4 diff and unified diff for the files
    """

    global ISWINDOWS
    if sys.platform.startswith('win'):
        ISWINDOWS = True
    else:
        ISWINDOWS = False

    (myopts, myfiles) = get_args()

    if myopts == "":
        myopts = P4DEFAULT_OPT

    (mycwd, myclroot) = getp4info()

    # Client root: /fs/home/sivak/links/sb14-ws/pioneer-sivak-br1
    # Current directory:
    #  /<...>/root/sb14/sivak/pioneer-sivak-br1/src/osd

    bname = os.path.basename(myclroot)
    dname = os.path.dirname(myclroot)

    mylist = mycwd.split(os.path.sep)
    if ISWINDOWS:
        mynl = mycwd.rindex(bname)
        realcwd = dname + os.path.sep + mycwd[mycwd.rindex(bname):]
    else:
        mynl = mylist[mylist.index(bname):]
        realcwd = dname + os.path.sep + os.path.sep.join(mynl)

    myclroot += os.path.sep
    mycwd += os.path.sep

    (p4depot, output) = getp4depotinfo()

    if not p4depot:
        print "Error in reading p4 depot info: %s couldn't be parsed\n" % (
            output,)
        sys.exit(1)

    (existingfiles, newfiles, deletedfiles) = get_p4files(
        p4depot, myfiles, realcwd, myclroot)

    if (len(existingfiles) == 0 and
            len(newfiles) == 0 and
            len(deletedfiles) == 0):
        print "Nothing modified, added, nor deleted\n"
        sys.exit(0)

    newoutput = ""

    for (depotfile, efile, revision, fltype) in existingfiles:
        output = get_modified(myopts, depotfile, efile, revision, fltype)
        newoutput += output

    for (dfile, nfile, revision) in newfiles:
        output = get_add(dfile, nfile, revision)
        newoutput += output

    for (dfile, nfile, revision) in deletedfiles:
        output = get_deleted(dfile, revision)
        newoutput += output

    # for some reason, the last newline needs to be deleted ...
    newoutput = str(newoutput).rstrip('\n')
    print newoutput

# Main code

if __name__ == '__main__':
    main()

