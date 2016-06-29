#!python

import sys, os
import getopt
import ConfigParser
import numpy as np
import math
from pprint import pprint
from svgProcessor import *

def formatVal(val, f="%0.2f"):
    return (f % (val))
def cmp_start_node(path1, path2):
    x1, y1 = path1.xy
    x2, y2 = path2.xy
    return x1[0] < x2[0]
def genGCode(path, zDraw, zMove, xOffset, yOffset, zOffset, drawSpeed, moveSpeed, zMoveSpeed):
    code = []
    #code += 'G1 Z'+formatVal(zMove + zOffset)+';\n'
    code += '\n;****************************************************************\n'
    code += 'G1 X'+formatVal(path[0][0]+xOffset)+' Y'+formatVal(path[0][1]+yOffset)+' F'+formatVal(moveSpeed)+';\n'
    code += 'G1 Z'+formatVal(zDraw + zOffset)+' F'+formatVal(zMoveSpeed)+';\nG1 F' + formatVal(drawSpeed) + ';\n'
    for p in path[1:]:
        code += 'G1 X'+formatVal(p[0]+xOffset)+' Y'+formatVal(p[1]+yOffset)+';\n'
    code += 'G1 Z'+formatVal(zMove + zOffset)+';\n'
    return code
def printProgress (iteration, total, prefix = '', suffix = '', decimals = 2, barLength = 100):
    filledLength    = int(round(barLength * iteration / float(total)))
    percents        = round(100.00 * (iteration / float(total)), decimals)
    bar             = '#' * filledLength + '-' * (barLength - filledLength)
    sys.stdout.write('%s [%s] %s%s %s\r' % (prefix, bar, percents, '%', suffix)),
    sys.stdout.flush()
    if iteration == total:
        print("\n")


def main(argv):
    zDraw = -0.1
    zMove = 1.0
    xOffset = 0.0
    yOffset = 0.0
    zOffset = 1.0
    zApproach = 10
    zRetreat = 10
    userScale = 1.0
    feed = 500
    moveFeed = 1000
    zMoveFeed = 120
    penRadius = 0.15
    minPenRadius = 0.1
    includeBorder = False
    numRepeatFirst = 3
    makeSetupFile = False
    insideFirst = False
    #Possible 1, 2, 3
    jointStyle = 1
    maxInfilIterations = 50
    mirrored = False
    mergeTracks = False

    defs = {
    'userScale':            str(userScale),
    'penRadius':            str(penRadius),
    'jointStyle':           str(jointStyle),
    'maxInfilIterations':   str(maxInfilIterations),
    'zDraw':                str(zDraw),
    'zMove':                str(zMove),
    'xOffset':              str(xOffset),
    'yOffset':              str(yOffset),
    'zOffset':              str(zOffset),
    'zApproach':            str(zApproach),
    'zRetreat':             str(zRetreat),
    'feed':                 str(feed),
    'moveFeed':             str(moveFeed),
    'zMoveFeed':            str(zMoveFeed),
    'minPenRadius':         str(minPenRadius),
    'includeBorder':        str(includeBorder),
    'numRepeatFirst':       str(numRepeatFirst),
    'makeSetupFile':        str(makeSetupFile),
    'insideFirst':          str(insideFirst),
    'mirrored':             str(mirrored),
    'mergeTracks':          str(mergeTracks)
    }

    conf = ConfigParser.SafeConfigParser(defs)
    conf.read(os.path.dirname(os.path.realpath(__file__))+'/config')
    userScale = conf.getfloat('default', 'userScale')
    penRadius = conf.getfloat('default', 'penRadius')
    jointStyle = conf.getint('default', 'jointStyle')
    maxInfilIterations = conf.getint('default', 'maxInfilIterations')
    zDraw = conf.getfloat('default', 'zDraw')
    zMove = conf.getfloat('default', 'zMove')
    xOffset = conf.getfloat('default', 'xOffset')
    yOffset = conf.getfloat('default', 'yOffset')
    zOffset = conf.getfloat('default', 'zOffset')
    zApproach = conf.getfloat('default', 'zApproach')
    zRetreat = conf.getfloat('default', 'zRetreat')
    feed = conf.getfloat('default', 'feed')
    moveFeed = conf.getfloat('default', 'moveFeed')
    zMoveFeed = conf.getfloat('default', 'zMoveFeed')
    minPenRadius = conf.getfloat('default', 'minPenRadius')
    includeBorder = conf.getboolean('default', 'includeBorder')
    numRepeatFirst = conf.getint('default', 'numRepeatFirst')
    makeSetupFile = conf.getboolean('default', 'makeSetupFile')
    insideFirst = conf.getboolean('default', 'insideFirst')
    mirrored = conf.getboolean('default', 'mirrored')
    mergeTracks = conf.getboolean('default', 'mergeTracks')


    helpString = 'svg2penGcode.py [options] <inputfile[s]>'
    try:
        opts, args = getopt.getopt(argv,"hp:d:m:x:y:z:s:f:b",["help",
            "pen-radius=", "min-pen-radius=", "draw=", "move=",
            "x-offset=", "y-offset=", "z-offset=", "scale=", "mirrored", "merge-tracks",
            "feed=", "feed-move=",
            "border", "repeat=", "inside-first",
            "join-style=", "max-iterations=",
            "setup"])
    except getopt.GetoptError:
        print helpString
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print helpString
            sys.exit(0)
        elif opt in ("-p", "--pen-radius"):
            penRadius = float(arg)
        elif opt in ("--min-pen-radius"):
            minPenRadius = float(arg)
        elif opt in ("-d", "--draw"):
            zDraw = float(arg)
        elif opt in ("-m", "--move"):
            zMove = float(arg)
        elif opt in ("-x", "--x-offset"):
            xOffset = float(arg)
        elif opt in ("-y", "--y-offset"):
            yOffset = float(arg)
        elif opt in ("-z", "--z-offset"):
            zOffset = float(arg)
        elif opt in ("-s", "--scale"):
            userScale = float(arg)
        elif opt in ("-f", "--feed"):
            feed = float(arg)
        elif opt in ("--feed-move"):
            feedMove = float(arg)
        elif opt in ("-b", "--border"):
            includeBorder = True
        elif opt in ("--repeat"):
            numRepeatFirst = int(arg)
        elif opt in ("--inside-first"):
            insideFirst = True
        elif opt in ("--join-style"):
            jointStyle = int(arg)
        elif opt in ("--max-iterations"):
            maxInfilIterations = int(arg)
        elif opt in ("--setup"):
            makeSetupFile = True
        elif opt in ("--mirrored"):
            mirrored = True
        elif opt in ("--merge-tracks"):
            mergeTracks = True
        else:
            raise RuntimeError("Unknown option:" + opt)
    
    fileName = args[0]
    parcer = SVGProcessor()
    parcer.parce(fileName, penRadius)
    parcer.process(mirrored, mergeTracks)
    code = []
    code.append('G21;\nG90;\nG28 X0 Y0;\nG28 Z0;\n')
    code.append('G1 Z' + formatVal(zMove + zOffset + zApproach) + ';\n')
    count = 0
    allPaths = parcer.penPaths()
    for penPath in allPaths:
        printProgress(count, len(allPaths), prefix='Generating')
        code += genGCode(penPath, zDraw, zMove, xOffset, yOffset, zOffset, feed, moveFeed, zMoveFeed)
        count += 1
    code.append('G1 Z' + formatVal(zMove + zOffset + zRetreat) + ';\n')
    code.append('G28 X0;\n')
    code.append('M84;\n;')
    f = open(fileName+'.gcode', 'w')
    f.writelines(code)
    f.close()
    printProgress(1, 1, prefix='Generating', suffix='Done')
    width, height = parcer.PCBSize()
    print 'PCB size ', formatVal(width, f="%0.f"), formatVal(height, f="%0.f")

    if makeSetupFile:
        #Gen setup code for pointing to corners
        targets = {'LB':[xOffset, yOffset], 'LT':[xOffset, yOffset+(height)], 'RT':[xOffset+(width), yOffset+(height)], 'RB':[xOffset+(width), yOffset]}
        for k in targets:
            code = []
            code.append('G21;\nG90;\nG28 X0 Y0;\nG28 Z0;\n')
            code.append('G1 Z' + formatVal(zMove + zOffset + zApproach) + ';\n')
            code.append('G1 X'+formatVal(targets[k][0])+' Y'+formatVal(targets[k][1])+' F'+formatVal(moveFeed)+';\n')
            code.append('G1 Z' + formatVal(zOffset) + ';\n')
            code.append('M84;\n;')
            f = open(fileName+'.setup'+k+'.gcode', 'w')
            f.writelines(code)
            f.close()
        #Gen code for mark corners
        stroke = 2.0;
        cornerNodes = []
        cornerNodes.append([])
        cornerNodes[-1].append([[0.0, 0.0 + stroke], [0.0, 0.0], [0.0 + stroke, 0.0]])
        cornerNodes.append([])
        cornerNodes[-1].append([[(width) - stroke, 0.0], [(width), 0.0], [(width), 0.0 + stroke]])
        cornerNodes.append([])
        cornerNodes[-1].append([[(width), (height) - stroke], [(width), (height)], [(width) - stroke, (height)]])
        cornerNodes.append([])
        cornerNodes[-1].append([[0.0 + stroke, (height)], [0.0, (height)], [0.0, (height) - stroke]])
        code = []
        code.append('G21;\nG90;\nG28 X0 Y0;\nG28 Z0;\n')
        code.append('G1 Z' + formatVal(zMove + zOffset + zApproach) + ';\n')
        for nodesGroup in cornerNodes:
            maxIter = 1
            for nodes in nodesGroup:
                code += genGCode(nodes, zDraw, zMove, xOffset, yOffset, zOffset, feed, moveFeed, zMoveFeed)
        code.append('G1 Z' + formatVal(zMove + zOffset + zRetreat) + ';\n')
        code.append('G28 X0;\n')
        code.append('M84;\n;')
        f = open(fileName+'.corners.gcode', 'w')
        f.writelines(code)
        f.close()


if __name__ == "__main__":
    main(sys.argv[1:])

